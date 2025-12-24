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
    -- Clean up any old completion file before starting
    Config.deleteCompletionFile()

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

    -- Clean up any old completion file before starting
    Config.deleteCompletionFile()

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
    -- Clean up any old completion file before starting
    Config.deleteCompletionFile()

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

-- Monitor for completion and show results dialog
function TaggerCore.monitorCompletion(expectedCount, itemType, dryRun)
    LrTasks.startAsyncTask(function()
        local completionFile = Config.getCompletionFile()
        local maxWaitTime = 14400  -- 4 hours max (increased from 2 for large batches)
        local pollInterval = 5     -- Check every 5 seconds (reduced from 2 to be less aggressive)
        local stabilityWaitTime = 45   -- Wait 45 seconds after sequence reaches expectedCount
                                        -- Gives time for final stats to be written and settled
        local elapsed = 0
        local lastSequence = nil
        local stableTime = 0
        local loggedProgress = false

        logger:info('Monitoring for completion... (expecting ' .. expectedCount .. ' files)')

        while elapsed < maxWaitTime do
            LrTasks.sleep(pollInterval)
            elapsed = elapsed + pollInterval

            if LrFileUtils.exists(completionFile) then
                logger:info('Completion file detected')

                -- Parse stats and watch sequence number
                -- Sequence increments each time a file finishes in batch processing
                local stats = Config.parseCompletionFile(completionFile)

                if stats and stats.sequence then
                    if stats.sequence == expectedCount then
                        -- We've reached the expected number of files - now wait for stability
                        if lastSequence == stats.sequence then
                            -- Sequence hasn't changed since last check
                            stableTime = stableTime + pollInterval
                        else
                            -- Sequence just updated to expectedCount, reset stability timer
                            stableTime = 0
                            lastSequence = stats.sequence
                            logger:info('Sequence reached expected count (' .. expectedCount .. '), starting stability timer')
                        end

                        -- Once we reach expectedCount, wait for stability period to ensure final stats are written
                        if stableTime >= stabilityWaitTime then
                            logger:info('Sequence stable at ' .. stats.sequence .. ' (expected ' .. expectedCount .. '), all processing done')
                            LrTasks.sleep(0.5)  -- Ensure file fully written

                            stats = Config.parseCompletionFile(completionFile)

                            if stats then
                                TaggerCore.showCompletionDialog(stats, itemType)
                            else
                                -- Fallback if parsing fails
                                LrDialogs.message('Racing Tagger',
                                    'Processing complete! Check log for details:\n' ..
                                    Config.getOutputLog(), 'info')
                            end

                            Config.deleteCompletionFile()
                            return
                        end
                    else
                        -- Still waiting for more files to finish
                        if not loggedProgress or (elapsed % 60 == 0) then  -- Log progress every 60 seconds
                            logger:info('Sequence at ' .. stats.sequence .. ' of ' .. expectedCount .. ', continuing to monitor')
                            loggedProgress = true
                        end
                        lastSequence = stats.sequence
                        stableTime = 0
                    end
                end
            end
        end

        -- Timeout
        logger:error('Completion monitoring timed out')
        LrDialogs.message('Racing Tagger',
            'Processing is taking longer than expected.\n\n' ..
            'Check log for status:\n' .. Config.getOutputLog(),
            'info')
    end)
end

-- Show completion dialog with results
function TaggerCore.showCompletionDialog(stats, itemType)
    local message
    local title = 'Racing Tagger Complete'

    if stats.dry_run then
        message = string.format(
            'DRY RUN completed!\n\n' ..
            'Processed: %d %s\n' ..
            'Successful: %d\n' ..
            'Failed: %d\n',
            stats.total_images, itemType,
            stats.successful, stats.failed
        )
        if stats.no_car and stats.no_car > 0 then
            message = message .. string.format('No car detected: %d\n', stats.no_car)
        end
        if stats.avg_time and stats.avg_time > 0 then
            message = message .. string.format('\nAverage time: %.1f seconds per image\n\n', stats.avg_time)
        end
        message = message .. 'No files were modified (dry run mode).'
    else
        message = string.format(
            'Processing completed!\n\n' ..
            'Processed: %d %s\n' ..
            'Successful: %d\n' ..
            'Failed: %d\n',
            stats.total_images, itemType,
            stats.successful, stats.failed
        )
        if stats.no_car and stats.no_car > 0 then
            message = message .. string.format('No car detected: %d\n', stats.no_car)
        end
        if stats.avg_time and stats.avg_time > 0 then
            message = message .. string.format('\nAverage time: %.1f seconds per image\n\n', stats.avg_time)
        end
        message = message .. 'Keywords written to XMP sidecars.\n\nSelect photos and use:\nMetadata > Read Metadata from Files'
    end

    local messageType = (stats.failed and stats.failed > 0) and 'warning' or 'info'
    LrDialogs.message(title, message, messageType)
end

return TaggerCore
