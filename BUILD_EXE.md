# Building Windows Executable

## Option 1: Batch Files (Recommended for most users)

Three batch files are provided for easy drag-and-drop operation:

1. **`cleanup_keywords_dryrun.bat`** - Preview changes without modifying files
2. **`cleanup_keywords_run.bat`** - Clean up keywords (asks for confirmation)
3. **`cleanup_keywords_single_file.bat`** - Test on a single file

### Usage:
- **Drag and drop** a folder or file onto the `.bat` file
- Or double-click and it will prompt you for the path
- Or run from command line: `cleanup_keywords_dryrun.bat "C:\path\to\images"`

### Requirements:
- Python 3.10+ installed
- exiftool installed

---

## Option 2: Windows Executable (.exe)

For distribution to users without Python installed, you can build a standalone .exe:

### Install PyInstaller:
```bash
pip install pyinstaller
```

### Build the executable:
```bash
# Simple one-file executable
pyinstaller --onefile --name cleanup_keywords cleanup_old_keywords.py

# Or with more options:
pyinstaller --onefile ^
    --name cleanup_keywords ^
    --console ^
    --add-data "xmp_writer.py;." ^
    cleanup_old_keywords.py
```

### Output:
- Executable will be in `dist/cleanup_keywords.exe`
- Size: ~10-15 MB (includes Python runtime)

### Usage of .exe:
```cmd
# Dry run
cleanup_keywords.exe "C:\path\to\images" --dry-run

# Real run
cleanup_keywords.exe "C:\path\to\images"

# Drag and drop also works if you create a wrapper .bat:
@echo off
cleanup_keywords.exe "%~1" --dry-run --verbose
pause
```

### Important Notes:
- **exiftool must still be installed** - The .exe doesn't bundle exiftool
- Users need exiftool in PATH or in `C:\WINDOWS\exiftool.EXE`
- The .exe is portable and doesn't require Python installation
- Antivirus software may flag PyInstaller .exe files - this is a false positive

---

## Option 3: Full Installer with exiftool

For the ultimate user-friendly experience, you could create an installer that bundles both the cleanup tool AND exiftool:

### Using Inno Setup (free):
1. Download Inno Setup: https://jrsoftware.org/isinfo.php
2. Create an installer script that:
   - Installs the .exe
   - Installs exiftool to a known location
   - Creates desktop shortcuts
   - Adds Start menu entries

This is overkill for a one-time cleanup utility, but available if needed.

---

## Recommended Approach

For most users: **Use the batch files** - they're simple, transparent, and easy to modify if needed.

For distribution to non-technical users: **Build the .exe** and provide simple instructions for installing exiftool.
