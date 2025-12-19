# Racing Tagger - Windows 11 Setup Guide

This guide will help you get the Racing Tagger running on Windows 11 with Lightroom Classic.

## Prerequisites

You'll need:
- Windows 11
- NVIDIA GPU (recommended for CUDA acceleration, but CPU works too)
- Lightroom Classic
- ~10GB free disk space (for model + tools)

## Step 1: Install Python

1. Download Python 3.12 from https://www.python.org/downloads/
2. **Important:** Check "Add Python to PATH" during installation
3. Verify installation:
   ```cmd
   python --version
   ```
   Should show `Python 3.12.x`

## Step 2: Install Ollama

1. Download from https://ollama.ai/download/windows
2. Run the installer
3. Ollama will start automatically and run in the system tray
4. Open Command Prompt and pull the vision model:
   ```cmd
   ollama pull qwen2.5vl:7b
   ```
   This downloads ~6GB - takes a few minutes depending on connection.

5. Verify it's working:
   ```cmd
   ollama list
   ```
   Should show `qwen2.5vl:7b`

## Step 3: Install exiftool

1. Download from https://exiftool.org/ (Windows Executable)
2. Extract `exiftool(-k).exe`
3. Rename it to `exiftool.exe`
4. Move to a folder in your PATH, e.g., `C:\Windows\` or create `C:\Tools\` and add to PATH
5. Verify:
   ```cmd
   exiftool -ver
   ```
   Should show version number like `12.xx`

## Step 4: Clone the Repository

```cmd
cd %USERPROFILE%\Documents
git clone https://github.com/blwfish/LrC-classification.git
cd LrC-classification
```

Or download ZIP from GitHub and extract.

## Step 5: Test the Tagger

```cmd
cd %USERPROFILE%\Documents\LrC-classification

# Test on a single image (dry run - no files modified)
python racing_tagger.py "C:\path\to\your\image.NEF" --dry-run --verbose
```

You should see output like:
```
Processing image.NEF...
  -> Make:Porsche, Model:911GT3, Color:White, Num:247 (5.2s)
```

## Step 6: Install Lightroom Plugin

1. Copy the plugin folder:
   ```cmd
   xcopy /E /I RacingTagger.lrplugin "%APPDATA%\Adobe\Lightroom\Modules\RacingTagger.lrplugin"
   ```

2. Restart Lightroom Classic

3. Go to **File → Plug-in Manager** and verify "Racing Tagger" shows as "Installed and running"

## Step 7: Using the Plugin

1. In Lightroom, select photos you want to tag
2. Go to **Library → Plug-in Extras → Racing Tagger**
3. Choose:
   - **Tag Selected Photos** - process individual images
   - **Tag Folder(s)** - process entire folder (more efficient for many images)
   - **Dry Run** variants to preview without writing

4. The tagger runs in background. Check progress:
   ```cmd
   type %TEMP%\racing_tagger_output.log
   ```

5. When complete, select the photos in Lightroom and use:
   **Metadata → Read Metadata from Files**

## Troubleshooting

### "python is not recognized"
- Python wasn't added to PATH during install
- Reinstall Python and check "Add Python to PATH"
- Or manually add `C:\Users\YourName\AppData\Local\Programs\Python\Python312\` to PATH

### "ollama is not recognized"
- Ollama may not be running
- Check system tray for Ollama icon
- Try restarting Ollama from Start menu

### "exiftool is not recognized"
- exiftool.exe isn't in PATH
- Move it to `C:\Windows\` or add its folder to PATH

### Plugin shows "may not work"
- Click "Reload Plug-in" in Plugin Manager
- Check the error message in Plugin Manager details

### Slow performance
- Make sure Ollama is using GPU:
  ```cmd
  ollama ps
  ```
  Should show the model loaded
- First image is always slower (model loading)
- Subsequent images should be 3-8 seconds each with GPU

## Performance Expectations

| Hardware | Speed |
|----------|-------|
| NVIDIA RTX 3080+ | ~3-5 sec/image |
| NVIDIA RTX 2070 | ~5-8 sec/image |
| CPU only | ~30-60 sec/image |

## Quick Reference

```cmd
# Process a folder
python racing_tagger.py "D:\Photos\RaceEvent" --verbose

# Resume interrupted run
python racing_tagger.py "D:\Photos\RaceEvent" --resume --verbose

# Check Ollama status
ollama ps
ollama list
```

## Getting Help

- Check `CHECKPOINT.md` for current project status
- GitHub Issues: https://github.com/blwfish/LrC-classification/issues
- Use Claude Code to help debug any issues!
