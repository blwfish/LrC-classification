# Racing Tagger - Session Checkpoint

**Date:** 2024-12-18

## Current Status

**Production Ready** - Successfully tested on 7,509 images with 99.97% success rate.

## Recent Changes (2024-12-18)

### 1. Improved False Positive Detection
- **Issue:** Paddock scenes with tiny/partial cars were getting hallucinated tags (e.g., pit crew photo with car sliver at edge → "Porsche 911 #202")
- **Fix:** Updated prompts to require car to be PRIMARY SUBJECT of image
- **Result:** Returns `car_detected: false` for:
  - Partial cars at frame edges
  - Cars <20% of frame
  - Paddock/pit scenes where people are main subject
- **Files:** `prompts.py`

### 2. Lightroom Classic Plugin
- **New:** Cross-platform plugin (macOS + Windows)
- **Location:** `RacingTagger.lrplugin/`
- **Menu:** Library → Plug-in Extras → Racing Tagger
  - Tag Selected Photos
  - Tag Selected Photos (Dry Run)
  - Tag Folder(s)
  - Tag Folder(s) (Dry Run)
- Runs tagger in background, returns to LrC immediately
- After completion: Metadata → Read Metadata from Files

## Previous Session (2024-12-15)

- Full test on 7,509 images: 99.97% success rate
- Added no-car detection for non-car images
- Fixed badge number false positives (911, GT3, etc.)
- Benchmarked at ~6 seconds/image on M4 Max

## Repository

- **Gitea:** http://localhost:3000/blw/LrC-classification
- **GitHub:** https://github.com/blwfish/LrC-classification

## Architecture

```
racing-tagger/
├── racing_tagger.py        # Main CLI tool
├── llama_inference.py      # Ollama vision model integration
├── xmp_writer.py           # XMP sidecar writing via exiftool
├── prompts.py              # Vision prompts by profile
├── progress_tracker.py     # Resume capability
├── setup.sh                # Installation script (macOS/Linux)
├── RacingTagger.lrplugin/  # Lightroom Classic plugin
│   ├── Info.lua            # Plugin manifest
│   ├── Config.lua          # Cross-platform paths/commands
│   ├── TaggerCore.lua      # Shared functionality
│   ├── TagPhotos.lua       # Tag selected photos
│   ├── TagPhotosDryRun.lua
│   ├── TagFolder.lua       # Tag entire folder(s)
│   └── TagFolderDryRun.lua
├── README.md
├── CHECKPOINT.md           # This file
└── WINDOWS_SETUP.md        # Windows installation guide
```

## Requirements

### All Platforms
- Python 3.10+
- Ollama with `qwen2.5vl:7b` model
- exiftool (for XMP writing)

### macOS
- Apple Silicon recommended (Metal acceleration)
- `brew install ollama exiftool`
- Plugin: `~/Library/Application Support/Adobe/Lightroom/Modules/`

### Windows 11
- NVIDIA GPU recommended (CUDA acceleration)
- Python in PATH
- Ollama from https://ollama.ai
- exiftool from https://exiftool.org (add to PATH)
- Plugin: `%APPDATA%\Adobe\Lightroom\Modules\`

## Quick Commands

```bash
# Test single image
python3 racing_tagger.py /path/to/image.NEF --dry-run --verbose

# Process directory
python3 racing_tagger.py /path/to/images --verbose

# Resume interrupted run
python3 racing_tagger.py /path/to/images --resume --verbose

# Use larger model (slower, not necessarily better)
python3 racing_tagger.py /path/to/image.NEF --model qwen2.5vl:72b --dry-run --verbose
```

## Performance (M4 Max)

| Metric | Value |
|--------|-------|
| Model | qwen2.5vl:7b (6GB) |
| Speed | ~5-6 sec/image |
| GPU | ~85% Metal |
| Memory | ~8GB during inference |

## Known Limitations

- Fisheye/heavily distorted shots can confuse number detection
- Multi-car pileup shots may miss some numbers
- Very dark/backlit images have lower accuracy
- First image after cold start takes ~6s extra (model loading)
