--[[
    Racing Tagger - Configuration (Fixed)

    Cross-platform configuration for the Racing Tagger plugin.
    Detects OS and sets appropriate paths.
    FIXED: No os.getenv() calls - uses Lightroom APIs only
]]

local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrSystemInfo = import 'LrSystemInfo'

local Config = {}

-- Detect platform
function Config.isWindows()
    return WIN_ENV == true
end

function Config.isMac()
    return MAC_ENV == true
end

-- Get the plugin's directory (where the .lrplugin folder is)
function Config.getPluginDir()
    return _PLUGIN.path
end

-- Get the racing tagger script directory
-- The plugin is in RacingTagger.lrplugin/, script is in parent
function Config.getTaggerDir()
    local pluginPath = _PLUGIN.path
    -- Go up one level from the .lrplugin folder
    return LrPathUtils.parent(pluginPath)
end

-- Get Python executable path
function Config.getPythonPath()
    if Config.isWindows() then
        -- Common Windows Python locations
        local candidates = {
            'python',      -- If in PATH
            'python3',     -- If in PATH
            'C:\\Python312\\python.exe',
            'C:\\Python311\\python.exe',
            'C:\\Python310\\python.exe',
        }
        for _, path in ipairs(candidates) do
            -- For 'python' or 'python3', assume it works if in PATH
            if not path:find('\\') then
                return path
            end
            if LrFileUtils.exists(path) then
                return path
            end
        end
        return 'python'  -- Fallback, hope it's in PATH
    else
        -- macOS / Linux
        local candidates = {
            '/usr/bin/python3',
            '/usr/local/bin/python3',
            '/opt/homebrew/bin/python3',
        }
        for _, path in ipairs(candidates) do
            if LrFileUtils.exists(path) then
                return path
            end
        end
        return 'python3'  -- Fallback
    end
end

-- Get the racing tagger script path
function Config.getTaggerScript()
    local taggerDir = Config.getTaggerDir()
    return LrPathUtils.child(taggerDir, 'racing_tagger.py')
end

-- Get temp directory using Lightroom API (not os.getenv!)
function Config.getTempDir()
    return LrPathUtils.getStandardFilePath('temp')
end

-- Get log file path using Lightroom's temp directory
function Config.getLogFile()
    local tempDir = LrPathUtils.getStandardFilePath('temp')
    if Config.isWindows() then
        return LrPathUtils.child(tempDir, 'racing_tagger.log')
    else
        return LrPathUtils.child(tempDir, 'racing_tagger.log')
    end
end

-- Get output log path using Lightroom's temp directory
function Config.getOutputLog()
    local tempDir = LrPathUtils.getStandardFilePath('temp')
    if Config.isWindows() then
        return LrPathUtils.child(tempDir, 'racing_tagger_output.log')
    else
        return LrPathUtils.child(tempDir, 'racing_tagger_output.log')
    end
end

-- Quote a path for shell command (handles spaces and special chars)
function Config.quotePath(path)
    if Config.isWindows() then
        -- Windows: use double quotes, escape internal quotes
        return '"' .. path:gsub('"', '""') .. '"'
    else
        -- macOS/Linux: use double quotes, escape internal quotes and backslashes
        return '"' .. path:gsub('\\', '\\\\'):gsub('"', '\\"') .. '"'
    end
end

-- Build command to run tagger in background
function Config.buildBackgroundCommand(taggerArgs)
    local python = Config.getPythonPath()
    local script = Config.getTaggerScript()
    local outputLog = Config.getOutputLog()

    if Config.isWindows() then
        -- Windows: write a temp batch file to avoid quote escaping issues
        local tempDir = Config.getTempDir()
        local batchFile = LrPathUtils.child(tempDir, 'racing_tagger_single.bat')
        local f = io.open(batchFile, 'w')
        if f then
            f:write('@echo off\r\n')
            f:write(string.format('%s %s %s > %s 2>&1\r\n',
                Config.quotePath(python),
                Config.quotePath(script),
                taggerArgs,
                Config.quotePath(outputLog)
            ))
            f:close()
            return string.format('start /b cmd /c %s', Config.quotePath(batchFile))
        end
        -- Fallback if file creation fails
        return string.format('start /b %s %s %s',
            Config.quotePath(python),
            Config.quotePath(script),
            taggerArgs
        )
    else
        -- macOS/Linux: use nohup with &
        return string.format(
            'nohup %s %s %s > %s 2>&1 &',
            Config.quotePath(python),
            Config.quotePath(script),
            taggerArgs,
            outputLog
        )
    end
end

-- Build command to run a batch script in background
function Config.buildBatchCommand(scriptPath)
    local outputLog = Config.getOutputLog()

    if Config.isWindows() then
        -- Use cmd /c with the batch script, redirect output
        local innerCmd = string.format(
            '%s > %s 2>&1',
            Config.quotePath(scriptPath),
            Config.quotePath(outputLog)
        )
        return string.format('start /b cmd /c "%s"', innerCmd)
    else
        return string.format(
            'nohup bash %s > %s 2>&1 &',
            Config.quotePath(scriptPath),
            outputLog
        )
    end
end

-- Get batch script extension
function Config.getBatchExtension()
    if Config.isWindows() then
        return '.bat'
    else
        return '.sh'
    end
end

-- Write batch script header
function Config.getBatchHeader()
    if Config.isWindows() then
        return '@echo off\r\n'
    else
        return '#!/bin/bash\n'
    end
end

-- Get line ending for batch scripts
function Config.getLineEnding()
    if Config.isWindows() then
        return '\r\n'
    else
        return '\n'
    end
end

-- Get completion file path (matches Python's location in temp directory)
function Config.getCompletionFile()
    local tempDir = LrPathUtils.getStandardFilePath('temp')
    return LrPathUtils.child(tempDir, 'racing_tagger_output.complete')
end

-- Parse completion file JSON (simple pattern matching, no JSON library needed)
function Config.parseCompletionFile(filePath)
    local f = io.open(filePath, 'r')
    if not f then
        return nil
    end

    local content = f:read('*all')
    f:close()

    local stats = {}
    stats.sequence = tonumber(content:match('"sequence"%s*:%s*(%d+)')) or 0
    stats.total_images = tonumber(content:match('"total_images"%s*:%s*(%d+)')) or 0
    stats.successful = tonumber(content:match('"successful"%s*:%s*(%d+)')) or 0
    stats.failed = tonumber(content:match('"failed"%s*:%s*(%d+)')) or 0
    stats.no_car = tonumber(content:match('"no_car"%s*:%s*(%d+)')) or 0
    stats.avg_time = tonumber(content:match('"avg_time_per_image"%s*:%s*([%d%.]+)')) or 0
    stats.dry_run = content:match('"dry_run"%s*:%s*true') ~= nil

    return stats
end

-- Delete completion file
function Config.deleteCompletionFile()
    local filePath = Config.getCompletionFile()
    if LrFileUtils.exists(filePath) then
        LrFileUtils.delete(filePath)
    end
end

return Config
