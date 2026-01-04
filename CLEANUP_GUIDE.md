# Keyword Cleanup Utility - Quick Start Guide

This tool removes old flat keywords (e.g., `Make:Porsche`, `Model:911GT3`, `Num:73`) from your racing photos while preserving:
- ✅ New hierarchical keywords (`AI Keywords|Make|Porsche`)
- ✅ Manual keywords (track names, customer info, event names)

## Why Use This Tool?

If you previously ran Racing Tagger with the old flat keyword format and have since migrated to hierarchical keywords, you'll have duplicate keywords in your files. This tool cleans up the old ones.

## Windows Batch Files (Easiest Method)

Three batch files are provided for drag-and-drop operation:

### 1. `cleanup_keywords_dryrun.bat` - Safe Preview
**Use this first!** Shows what would be removed WITHOUT modifying files.

**How to use:**
1. Drag and drop a folder (or single file) onto the `.bat` file
2. Review the output - it shows what will be removed and what will be kept
3. Check the log file for complete details

### 2. `cleanup_keywords_run.bat` - Real Cleanup
Removes old flat keywords from your files.

**How to use:**
1. **Run dry-run first** to make sure you're comfortable with the changes
2. Drag and drop the same folder onto this `.bat` file
3. Type `yes` when prompted to confirm
4. Wait for completion (545 files takes ~7 minutes)
5. Check the log file for results

**Safety:** Asks for confirmation before making changes.

### 3. `cleanup_keywords_single_file.bat` - Test One File
Test the cleanup on a single file with automatic preview.

**How to use:**
1. Drag and drop a single image file onto this `.bat` file
2. Review the dry-run preview
3. Type `yes` if you want to clean that file

## Requirements

- **Python 3.10+** - Must be installed and in PATH
- **exiftool** - Must be installed (automatically detected in `C:\WINDOWS\exiftool.EXE` or PATH)

### Installing exiftool (if needed):
1. Download from https://exiftool.org/
2. Rename `exiftool(-k).exe` to `exiftool.exe`
3. Copy to `C:\WINDOWS\` or add to PATH

## What Gets Removed

Old flat auto-generated keywords:
- `Make:Porsche`, `Make:BMW`, etc.
- `Model:911GT3Cup`, `Model:Cayman`, etc.
- `Color:Black`, `Color:Blue`, etc.
- `Num:73`, `Num:911`, etc.
- `Class:SPB`, `Class:SPC`, etc.
- `Error:*`, `Sequence:*`, `People:*`, `Subcategory:*`, `Engine:*`
- `Classified`, `NoSubject`

## What Gets Preserved

- **Hierarchical keywords:** `AI Keywords|Make|Porsche`, `AI Keywords|Model|911GT3`, etc.
- **Manual keywords:** `Customer`, `Porsche Club of America`, `PCA Club Racing`, `Racetracks|Road America`, etc.

## Log Files

Each run creates a timestamped log file in the same directory:
- Example: `cleanup_keywords_20260103_202329.log`
- Contains detailed information about every file processed
- Shows exactly which keywords were removed from each file

## Command Line (Advanced)

If you prefer command line:

```bash
# Dry run (preview)
python cleanup_old_keywords.py "C:\path\to\images" --dry-run --verbose

# Real run
python cleanup_old_keywords.py "C:\path\to\images"

# Single file
python cleanup_old_keywords.py "C:\path\to\image.jpg" --dry-run
```

## Safety Features

- **Dry-run mode** - Preview changes before making them
- **Confirmation prompts** - Prevents accidental execution
- **Detailed logging** - Track exactly what was changed
- **Idempotent** - Safe to run multiple times (won't break already-cleaned files)
- **No backups created** - Uses exiftool's `-overwrite_original` flag (original files are modified directly)

## Troubleshooting

### "Python is not recognized"
- Python is not installed or not in PATH
- Install Python 3.10+ from https://python.org
- Make sure "Add Python to PATH" is checked during installation

### "exiftool not found"
- exiftool is not installed
- Download from https://exiftool.org
- Copy `exiftool.exe` to `C:\WINDOWS\` or add to PATH

### "No keywords to remove"
- Your files are already clean! ✅
- Or they never had the old flat keywords

### Keywords still showing in Lightroom
- In Lightroom, select the photos
- Go to **Metadata → Read Metadata from Files**
- This forces Lightroom to re-read the cleaned metadata

## Example Output

```
INFO - Found 545 files to process
INFO - ------------------------------------------------------------
INFO - [DRY RUN] 2025-09-01-PCA Rd America-00027.JPG
INFO -   Removed 4 auto-generated keywords:
INFO -     - Color:Black
INFO -     - Make:Porsche
INFO -     - Model:911GT3Cup
INFO -     - Num:37
INFO -
INFO - ------------------------------------------------------------
INFO - Processing complete:
INFO -   Files processed: 545/545
INFO -   Files modified: 498
INFO -   Total keywords removed: 2363
INFO -   Total keywords kept: 8722
INFO -   Failed: 0
```

## Questions?

See the main [README.md](README.md) for more information about the Racing Tagger project.
