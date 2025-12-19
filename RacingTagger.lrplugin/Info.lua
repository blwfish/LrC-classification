return {
    LrSdkVersion = 10.0,
    LrSdkMinimumVersion = 6.0,
    LrToolkitIdentifier = 'com.blw.racingtagger',
    LrPluginName = 'Racing Tagger',
    LrPluginInfoUrl = 'https://github.com/blwfish/LrC-classification',

    LrLibraryMenuItems = {
        {
            title = 'Tag Selected Photos',
            file = 'TagPhotos.lua',
        },
        {
            title = 'Tag Selected Photos (Dry Run)',
            file = 'TagPhotosDryRun.lua',
        },
        {
            title = 'Tag Folder(s)',
            file = 'TagFolder.lua',
        },
        {
            title = 'Tag Folder(s) (Dry Run)',
            file = 'TagFolderDryRun.lua',
        },
    },

    LrExportMenuItems = {
        {
            title = 'Tag Selected Photos',
            file = 'TagPhotos.lua',
        },
        {
            title = 'Tag Folder(s)',
            file = 'TagFolder.lua',
        },
    },

    VERSION = { major=1, minor=1, revision=0, build=1 },
}
