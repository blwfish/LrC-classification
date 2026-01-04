# Racing Tagger - Session Checkpoint

**Date:** 2026-01-03

## Current Status

**Production Ready** - Successfully running in production with RTX 5070 Ti achieving 11.5s/image average.

## Recent Changes (2026-01-03)

### 1. Windows Stability Improvements
- **ImageMagick Detection:** Added automatic detection in `C:\Program Files\ImageMagick*` for Windows
- **Image Resizing:** Reduced NORMALIZE_SIZE from 2500px to 1500px to prevent GGML assertion failures
- **Command Execution Fix:** Fixed Lightroom plugin Windows command execution using temp batch files
- **Performance:** Improved from ~25s/image to ~11.5s/image on RTX 5070 Ti
- **Files:** `llama_inference.py`, `RacingTagger.lrplugin/Config.lua`

### 2. Error Keyword Writing
- **New Feature:** Failed images now get error keywords written to XMP
- **Error Categories:**
  - `Error:ModelCrash` - GGML assertion failures
  - `Error:InferenceFailed` - HTTP 500 errors
  - `Error:Timeout` - Request timeouts
  - `Error:ParseError` - JSON parsing failures
  - `Error:ConnectionError` - Ollama connection issues
  - `Error:Unknown` - Other errors
- **Benefit:** Easy filtering in Lightroom to identify and retry problematic images
- **Files:** `racing_tagger.py`

### 3. Keyword Cleanup Utility
- **New Tool:** `cleanup_old_keywords.py` - One-time migration utility
- **Purpose:** Remove old flat keywords (e.g., `Make:Porsche`, `Num:73`) after migrating to hierarchical structure
- **Preserves:**
  - New hierarchical keywords (`AI Keywords|Make|Porsche`)
  - Manual keywords (track names, customer info, event names)
- **Features:** Dry-run mode, timestamped logging, reads/removes from both Subject and HierarchicalSubject
- **Files:** `cleanup_old_keywords.py` (new), `README.md`, `CHANGELOG.md`

### 4. Updated Benchmarks
- **Hardware:** Ryzen 9 9950X + RTX 5070 Ti (16GB VRAM) + 128GB RAM
- **Performance:** 11.5s/image average in batch processing
- **Comparison:** Only ~2x slower than M4 Max (5.5s/image)
- **Files:** `README.md`

## Previous Session (2024-12-18)

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
├── cleanup_old_keywords.py # Keyword cleanup utility (one-time migration)
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

## Performance

### M4 Max (macOS, Metal)
| Metric | Value |
|--------|-------|
| Model | qwen2.5vl:7b (6GB) |
| Speed | ~5.5 sec/image |
| GPU | ~85% Metal |
| Memory | ~8GB during inference |

### RTX 5070 Ti (Windows, CUDA)
| Metric | Value |
|--------|-------|
| Model | qwen2.5vl:7b (6GB) |
| Speed | ~11.5 sec/image (batch average) |
| GPU | 16GB VRAM, 100% loaded |
| CPU | Ryzen 9 9950X (16-core) |
| Memory | 128GB RAM |
| ImageMagick | Required - resizes to 1500px |

## Known Limitations

- Fisheye/heavily distorted shots can confuse number detection
- Multi-car pileup shots may miss some numbers
- Very dark/backlit images have lower accuracy
- First image after cold start takes ~6s extra (model loading)
