--[[
    Racing Tagger - Tag Folder

    Runs the tagger on the folder(s) containing selected photos.
    More efficient than processing individual files when tagging
    many images in the same directory.
]]

local LrDialogs = import 'LrDialogs'
local LrTasks = import 'LrTasks'

local TaggerCore = require 'TaggerCore'

LrTasks.startAsyncTask(function()
    local folders = TaggerCore.getSelectedPhotoFolders()

    if #folders == 0 then
        LrDialogs.message('Racing Tagger', 'No photos selected.', 'info')
        return
    end

    -- Warn if multiple folders
    if #folders > 1 then
        local result = LrDialogs.confirm(
            'Tag Multiple Folders?',
            string.format(
                'Selected photos are in %d different folders.\n\n' ..
                'All images in these folders will be processed.\n\n' ..
                'Continue?',
                #folders
            ),
            'Tag All Folders',
            'Cancel'
        )
        if result == 'cancel' then
            return
        end
    end

    TaggerCore.runOnFolders(folders, false, true)  -- resume=true for folder processing
    TaggerCore.showStartedMessage(#folders, 'folder(s)', false)
end)
