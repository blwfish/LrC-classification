--[[
    Racing Tagger - Tag Folder (Dry Run)

    Same as TagFolder but with --dry-run flag to preview without writing.
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

    if #folders > 1 then
        local result = LrDialogs.confirm(
            'Preview Multiple Folders?',
            string.format(
                'Selected photos are in %d different folders.\n\n' ..
                'All images in these folders will be analyzed (dry run).\n\n' ..
                'Continue?',
                #folders
            ),
            'Preview All Folders',
            'Cancel'
        )
        if result == 'cancel' then
            return
        end
    end

    TaggerCore.runOnFolders(folders, true, true)  -- dryRun=true, resume=true
    TaggerCore.showStartedMessage(#folders, 'folder(s)', true)
end)
