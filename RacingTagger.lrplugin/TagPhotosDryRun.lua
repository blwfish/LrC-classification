--[[
    Racing Tagger - Tag Selected Photos (Dry Run)

    Same as TagPhotos but with --dry-run flag to preview without writing.
]]

local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'

local TaggerCore = require 'TaggerCore'

LrTasks.startAsyncTask(function()
    local paths = TaggerCore.getSelectedPhotoPaths()

    if #paths == 0 then
        LrDialogs.message('Racing Tagger', 'No photos selected.', 'info')
        return
    end

    local success
    if #paths == 1 then
        success = TaggerCore.runOnPath(paths[1], true, false)  -- dryRun=true
    else
        success = TaggerCore.runOnMultipleFiles(paths, true)
    end

    if success then
        TaggerCore.showStartedMessage(#paths, 'photo(s)', true)
        TaggerCore.monitorCompletion(#paths, 'photo(s)', true)
    end
end)
