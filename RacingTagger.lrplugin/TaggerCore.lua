--[[
    Racing Tagger - Core Functions

    Shared functionality for running the tagger from Lightroom.
    Cross-platform support for macOS and Windows.
]]

local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'
local LrFileUtils = import 'LrFileUtils'
local LrPathUtils = import 'LrPathUtils'
local LrLogger = import 'LrLogger'

local Config = require 'Config'

local logger = LrLogger('RacingTagger')
logger:enable('logfile')

local TaggerCore = {}

-- Get paths of selected photos
function TaggerCore.getSelectedPhotoPaths()
    local catalog = LrApplication.activeCatalog()
    local selectedPhotos = catalog:getTargetPhotos()
    local paths = {}

    for _, photo in ipairs(selectedPhotos) do
        local path = photo:getRawMetadata('path')
        if path and LrFileUtils.exists(path) then
            table.insert(paths, path)
        end
    end

    return paths
end

-- Get unique parent folders of selected photos
function TaggerCore.getSelectedPhotoFolders()
    local paths = TaggerCore.getSelectedPhotoPaths()
    local folders = {}
    local seen = {}

    for _, path in ipairs(paths) do
        local folder = LrPathUtils.parent(path)
        if folder and not seen[folder] then
            seen[folder] = true
            table.insert(folders, folder)
        end
    end

    return folders
end

-- Run tagger on a single path (file or directory)
function TaggerCore.runOnPath(path, dryRun, resume)
    local args = Config.quotePath(path) .. ' --verbose'

    if dryRun then
        args = args .. ' --dry-run'
    end

    if resume then
        args = args .. ' --resume'
    end

    args = args .. ' --log-file ' .. Config.quotePath(Config.getLogFile())

    local cmd = Config.buildBackgroundCommand(args)
    logger:info('Running: ' .. cmd)

    return LrTasks.execute(cmd)
end

-- Run tagger on multiple files via batch script
function TaggerCore.runOnMultipleFiles(paths, dryRun)
    if #paths == 0 then
        return false
    end

    local tempDir = Config.getTempDir()
    local scriptFile = LrPathUtils.child(tempDir, 'racing_tagger_batch' .. Config.getBatchExtension())
    local lineEnd = Config.getLineEnding()

    local f = io.open(scriptFile, 'w')
    if not f then
        logger:error('Could not create batch script: ' .. scriptFile)
        return false
    end

    f:write(Config.getBatchHeader())
    f:write('echo Racing Tagger starting on ' .. #paths .. ' files...' .. lineEnd)

    local python = Config.getPythonPath()
    local script = Config.getTaggerScript()

    for _, path in ipairs(paths) do
        local args = Config.quotePath(path) .. ' --verbose'
        if dryRun then
            args = args .. ' --dry-run'
        end

        if Config.isWindows() then
            f:write(string.format('%s %s %s%s',
                Config.quotePath(python),
                Config.quotePath(script),
                args,
                lineEnd
            ))
        else
            f:write(string.format('%s %s %s%s',
                Config.quotePath(python),
                Config.quotePath(script),
                args,
                lineEnd
            ))
        end
    end

    f:write('echo Racing Tagger complete.' .. lineEnd)
    f:close()

    -- Make executable on Unix
    if not Config.isWindows() then
        LrTasks.execute('chmod +x ' .. Config.quotePath(scriptFile))
    end

    local cmd = Config.buildBatchCommand(scriptFile)
    logger:info('Running batch: ' .. cmd)

    return LrTasks.execute(cmd)
end

-- Run tagger on folder(s)
function TaggerCore.runOnFolders(folders, dryRun, resume)
    if #folders == 0 then
        return false
    end

    if #folders == 1 then
        -- Single folder - run directly
        return TaggerCore.runOnPath(folders[1], dryRun, resume)
    end

    -- Multiple folders - create batch script
    local tempDir = Config.getTempDir()
    local scriptFile = LrPathUtils.child(tempDir, 'racing_tagger_batch' .. Config.getBatchExtension())
    local lineEnd = Config.getLineEnding()

    local f = io.open(scriptFile, 'w')
    if not f then
        logger:error('Could not create batch script: ' .. scriptFile)
        return false
    end

    f:write(Config.getBatchHeader())
    f:write('echo Racing Tagger starting on ' .. #folders .. ' folders...' .. lineEnd)

    local python = Config.getPythonPath()
    local script = Config.getTaggerScript()

    for _, folder in ipairs(folders) do
        local args = Config.quotePath(folder) .. ' --verbose'
        if dryRun then
            args = args .. ' --dry-run'
        end
        if resume then
            args = args .. ' --resume'
        end
        args = args .. ' --log-file ' .. Config.quotePath(Config.getLogFile())

        f:write(string.format('%s %s %s%s',
            Config.quotePath(python),
            Config.quotePath(script),
            args,
            lineEnd
        ))
    end

    f:write('echo Racing Tagger complete.' .. lineEnd)
    f:close()

    if not Config.isWindows() then
        LrTasks.execute('chmod +x ' .. Config.quotePath(scriptFile))
    end

    local cmd = Config.buildBatchCommand(scriptFile)
    logger:info('Running batch: ' .. cmd)

    return LrTasks.execute(cmd)
end

-- Show completion message
function TaggerCore.showStartedMessage(count, itemType, dryRun)
    local outputLog = Config.getOutputLog()
    local message

    if dryRun then
        message = string.format(
            'Racing Tagger started in DRY RUN mode on %d %s.\n\n' ..
            'Check log for progress:\n%s\n\n' ..
            'No files will be modified.',
            count, itemType, outputLog
        )
    else
        message = string.format(
            'Racing Tagger started on %d %s.\n\n' ..
            'Keywords will be written to XMP sidecars.\n' ..
            'Check log for progress:\n%s\n\n' ..
            'When complete, select photos and use:\n' ..
            'Metadata > Read Metadata from Files',
            count, itemType, outputLog
        )
    end

    LrDialogs.message('Racing Tagger', message, 'info')
end

return TaggerCore
