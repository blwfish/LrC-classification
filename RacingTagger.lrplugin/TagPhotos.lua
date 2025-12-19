--[[
    Racing Tagger - Tag Selected Photos

    Runs the racing tagger on selected photos in background,
    writing keywords to XMP sidecars for RAW files.
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

    if #paths == 1 then
        TaggerCore.runOnPath(paths[1], false, false)
    else
        TaggerCore.runOnMultipleFiles(paths, false)
    end

    TaggerCore.showStartedMessage(#paths, 'photo(s)', false)
end)
