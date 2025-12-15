# Racing Tagger - Session Checkpoint

**Date:** 2024-12-15

## Current Status

**Completed:** Full test on dev-export4 (7,509 images)
- **Success rate:** 99.97% (7,507 successful, 2 failed due to HTTP 500)
- **Average time:** ~6 seconds/image on M4 Max with Metal
- **Total runtime:** ~12 hours

## Recent Fixes (2024-12-15)

### 1. No-Car Detection
- **Issue:** Non-car images (people, landscapes, pit scenes) were getting false positive car tags
- **Fix:** Updated prompts to explicitly detect when no car is present
- **Result:** Model now returns `car_detected: false` for non-car images
- **Files:** `prompts.py`, `racing_tagger.py`

### 2. Badge Number False Positives
- **Issue:** Model was detecting "911" from model badges instead of actual racing numbers
- **Fix:** Added explicit instructions to distinguish racing numbers from badge numbers
- **Result:** Model now ignores "911", "718", "GT3", "GT4", "992" badges
- **Files:** `prompts.py`

### 3. README Updates
- Updated recommended model to qwen2.5vl:7b
- Added actual benchmark results from 7,509 image test
- Updated processing speed estimates

## Performance Observed

- **Hardware:** M4 Max with Metal GPU acceleration
- **Model:** qwen2.5vl:7b via Ollama (qwen2.5vl:72b also available)
- **Speed:** ~5-7 seconds per image (avg ~6s)
- **GPU Usage:** ~85%
- **Memory:** ~6GB for 7b model (of 128GB system)
- **System Impact:** Essentially transparent - barely noticeable in foreground use

## Test Dataset

- **Location:** `/Volumes/Additional Files/development/dev-export4`
- **Images:** 7,509 total
- **Types:** NEF, TIF, DNG (RAW + edited variants)
- **Content:** Mixed racing photos - multiple events, cameras, includes some non-car images

## Repository

- **Gitea:** http://localhost:3000/blw/LrC-classification
- **GitHub:** https://github.com/blwfish/LrC-classification

## Files Modified This Session

1. `racing_tagger.py` - Added no-car detection, improved logging
2. `prompts.py` - Added car_detected field, badge number exclusion
3. `README.md` - Updated benchmarks and model recommendations

## Known Edge Cases

- **Fisheye/multi-car shots:** Challenging for 7b model due to distortion
  - Example: `_BLW2844-2.NEF` (checkered flag from flag stand)
  - May improve with 72b model (now downloaded, untested)

## Available Models

```bash
ollama list | grep qwen
# qwen2.5vl:72b  48 GB
# qwen2.5vl:7b   6.0 GB
```

## Quick Commands

```bash
# Test on single image
python3 racing_tagger.py /path/to/image.NEF --dry-run --verbose

# Test with 72b model
python3 racing_tagger.py /path/to/image.NEF --model qwen2.5vl:72b --dry-run --verbose

# Process directory
python3 racing_tagger.py /path/to/images --verbose --log-file run.log

# Resume interrupted run
python3 racing_tagger.py /path/to/images --resume --verbose
```
