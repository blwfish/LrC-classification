# Context for Claude - Racing Tagger Project

**For:** Vic's Claude instance helping with Windows setup/testing

## What This Project Does

Racing Tagger is a tool that automatically extracts metadata from motorsport photography using local vision AI (Ollama + qwen2.5vl). It identifies:
- Car make/model (Porsche 911, Cayman GT4, etc.)
- Racing numbers (on doors, hood, roof)
- Car color
- Racing class (if visible on windshield stickers)

It writes keywords to XMP sidecar files that Lightroom Classic can read.

## Current State

- **Production ready** - tested on 7,509 images with 99.97% success
- **Cross-platform** - works on macOS (Brian's M4 Max) and Windows 11 (Vic's system)
- **LrC Plugin** - can be invoked directly from Lightroom Classic

## Vic's Task

Help Vic get this running on his Windows 11 system with Lightroom Classic. Follow `WINDOWS_SETUP.md` for step-by-step instructions.

## Key Files

| File | Purpose |
|------|---------|
| `racing_tagger.py` | Main CLI tool |
| `WINDOWS_SETUP.md` | Windows installation guide |
| `CHECKPOINT.md` | Project status and architecture |
| `RacingTagger.lrplugin/` | Lightroom Classic plugin |
| `RacingTagger.lrplugin/Config.lua` | Cross-platform path configuration |

## Windows-Specific Notes

1. **Python path detection** in `Config.lua` checks common locations:
   - `python` / `python3` in PATH
   - `C:\Python31x\python.exe`
   - `%LOCALAPPDATA%\Programs\Python\Python31x\python.exe`

2. **Background execution** uses `start /b` instead of `nohup`

3. **Log files** go to `%TEMP%\racing_tagger_output.log`

4. **exiftool** must be in PATH - download from https://exiftool.org

## Testing Commands (Windows)

```cmd
# Verify prerequisites
python --version
ollama list
exiftool -ver

# Test single image (dry run)
python racing_tagger.py "D:\path\to\image.NEF" --dry-run --verbose

# Process a folder
python racing_tagger.py "D:\Photos\RaceEvent" --verbose --resume
```

## If Something Doesn't Work

1. **Check Ollama is running** - should be in system tray
2. **Check the log** - `type %TEMP%\racing_tagger_output.log`
3. **Test CLI first** - before using LrC plugin, verify CLI works
4. **GPU detection** - `ollama ps` should show the model loaded

## Architecture Context

```
User selects photos in LrC
    ↓
Plugin (Lua) gets file paths
    ↓
Plugin spawns: python racing_tagger.py <paths> (background)
    ↓
racing_tagger.py encodes image → sends to Ollama API
    ↓
Ollama runs qwen2.5vl:7b vision model (GPU accelerated)
    ↓
Model returns JSON with car metadata
    ↓
racing_tagger.py calls exiftool to write XMP sidecar
    ↓
User does "Read Metadata from Files" in LrC
    ↓
Keywords appear in LrC: Make:Porsche, Num:73, Color:Blue, etc.
```

## Contact

- Brian (blw) - macOS development
- GitHub: https://github.com/blwfish/LrC-classification
