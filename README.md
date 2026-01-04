# Racing Photography Metadata Extraction Tool

Automatically extract metadata from racing photography using local vision AI and write keywords to Lightroom-compatible XMP sidecars.

## Features

- **Local inference** - No cloud API, your images stay on your machine
- **Porsche/PCA optimized** - Specialized prompts for Porsche Club of America racing
- **Lightroom Classic plugin** - Tag photos directly from within Lightroom
- **Lightroom integration** - Writes standard XMP keywords that Lightroom imports automatically
- **Cross-platform** - Works on macOS and Windows 11
- **Resumable** - Track progress and resume interrupted runs
- **Hardware accelerated** - Uses Metal (Mac) or CUDA (NVIDIA) when available

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai) for local vision model inference
- Vision model: `qwen2.5vl:7b` (recommended)
- [exiftool](https://exiftool.org) for writing XMP metadata
- [ImageMagick](https://imagemagick.org) for image resizing (recommended, improves stability and speed)

### Hardware

**macOS (recommended):**
- Apple Silicon (M1/M2/M3/M4) for Metal acceleration
- 16GB+ RAM recommended

**Windows 11:**
- NVIDIA GPU with 8GB+ VRAM for CUDA acceleration (16GB+ recommended)
- ImageMagick 7.x (install with "Add to PATH" option) - **Required for optimal performance**
- Modern CPUs (Ryzen 9 or Intel i9) recommended
- 32GB+ RAM recommended (128GB ideal for large batches)
- See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for detailed installation guide

## Installation

1. Clone or download this repository

2. Install Ollama:
   - Mac: `brew install ollama` or download from https://ollama.ai
   - Linux: `curl -fsSL https://ollama.ai/install.sh | sh`
   - Windows: Download from https://ollama.ai

3. Run the setup script:
   ```bash
   ./setup.sh
   ```

4. Or manually pull a vision model:
   ```bash
   ollama pull qwen2.5vl:7b
   ```

## Usage

### Lightroom Classic Plugin (Recommended)

The easiest way to use Racing Tagger is via the Lightroom Classic plugin:

1. **Install the plugin:**
   - macOS: Copy or symlink `RacingTagger.lrplugin` to `~/Library/Application Support/Adobe/Lightroom/Modules/`
   - Windows: Copy `RacingTagger.lrplugin` to `%APPDATA%\Adobe\Lightroom\Modules\`

2. **Restart Lightroom Classic**

3. **Select photos** in Library module

4. **Run the tagger:** Library → Plug-in Extras → Racing Tagger
   - **Tag Selected Photos** - Process individual selected images
   - **Tag Folder(s)** - Process entire folder(s) containing selected images
   - **Dry Run** variants - Preview what would be detected without writing files

5. **Import keywords:** After processing completes, select the photos and use Metadata → Read Metadata from Files

The tagger runs in background so you can continue working in Lightroom. Check progress in the log file:
- macOS: `/tmp/racing_tagger_output.log`
- Windows: `%TEMP%\racing_tagger_output.log`

### Command Line

```bash
# Process a directory of images
python3 racing_tagger.py /path/to/images

# Process a single image
python3 racing_tagger.py /path/to/image.jpg
```

### Options

```
--profile PROFILE      Processing profile (default: racing-porsche)
                       Options: racing-porsche, racing-general, racing-nascar,
                                racing-imsa, racing-world-challenge, racing-indycar,
                                college-sports

--fuzzy-numbers        Attempt to detect duct-tape number variants

--output-dir DIR       Write XMP files to different directory

--resume               Continue from last run, skipping processed images

--reset                Clear progress and start fresh

--dry-run              Show what would happen without writing files

--verbose, -v          Enable detailed output

--max-images N         Limit processing to N images (for testing)

--model MODEL          Override vision model (e.g., llava:13b)

--log-file FILE        Write logs to file

# Sequence Detection Options
--detect-sequences     Enable sequence detection and sharpness scoring
--sequence-threshold N Max seconds between frames in sequence (default: 0.5)
--sequence-dry-run     Preview sequences without writing XMP
--skip-sequence-sharpness  Skip sharpness scoring (group only)
```

### Examples

```bash
# Test on a few images first
python3 racing_tagger.py /path/to/images --max-images 5 --verbose

# Dry run to see what would be extracted
python3 racing_tagger.py /path/to/images --dry-run

# Process with fuzzy number detection
python3 racing_tagger.py /path/to/images --fuzzy-numbers

# Resume an interrupted run
python3 racing_tagger.py /path/to/images --resume

# Use an alternate model
python3 racing_tagger.py /path/to/images --model llava:7b

# Detect sequences and mark best (sharpest) frames
python3 racing_tagger.py /path/to/images --detect-sequences

# Preview sequence detection without writing
python3 racing_tagger.py /path/to/images --detect-sequences --sequence-dry-run

# Adjust sequence threshold for faster burst rates
python3 racing_tagger.py /path/to/images --detect-sequences --sequence-threshold 0.3
```

## Keyword Format

Keywords use a prefix format for clear categorization:

```
Make:Porsche
Model:CaymanGT4
Color:Blue
Class:SPB
Num:73
Num:173?       (uncertain, with fuzzy-numbers flag)
Sequence:Best  (best/sharpest frame in a sequence)
Sequence:SEQ_2024-12-22_14-35-26  (sequence membership)
Classified     (marker indicating image was processed but no metadata detected)
```

**Note:** The `Classified` keyword is automatically added when an image is processed but no racing metadata is detected. This helps distinguish between "not yet processed" and "processed with no detections".

### Hierarchical Keyword Display

Keywords are written as hierarchical paths, so they display as expandable trees in Lightroom's Keyword List:

```
▼ AI Keywords
  ▼ Class
    SPB
    SPA
  ▼ Color
    Black
    Blue
    Red
  ▼ Make
    Porsche
  ▼ Model
    718Cayman
    911GT3
    911GT3Cup
  ▼ Num
    73
    92
```

This structure makes it easy to browse and filter keywords visually in Lightroom.

## Sequence Detection

Racing photographers often shoot pan sequences at 6-15 fps. The sequence detection feature automatically groups consecutive frames and identifies the sharpest image in each sequence using Laplacian variance analysis.

### How It Works

1. **Timestamp Analysis**: Reads `DateTimeOriginal` and `SubSecTimeOriginal` from EXIF
2. **Grouping**: Groups consecutive images where the time gap is within threshold (default: 0.5s)
3. **Sharpness Scoring**: Calculates Laplacian variance for each frame (higher = sharper)
4. **Marking**: Writes `Sequence:Best` keyword to the sharpest frame in each sequence

### Lightroom Workflow

After processing with `--detect-sequences`:

1. Import images to Lightroom Classic
2. Use **Photo > Stacking > Auto-Stack by Capture Time** (set same threshold, e.g., 0.5s)
3. Lightroom creates stacks automatically based on timestamps
4. Filter by `Sequence:Best` to see only the top picks from each sequence

### Requirements

Sequence detection requires `opencv-python`:
```bash
pip install opencv-python
```

### Performance

- Timestamp reading: ~1-2 seconds for 1000 images (batch exiftool)
- Sharpness scoring: ~5-8ms per image on M1 Max
- 3000 images: ~25-40 minutes total for sharpness analysis

### Searching in Lightroom

After importing XMP sidecars, search in Lightroom using:
- `Make:Porsche` - All Porsches
- `Num:73` - Car number 73
- `Class:SPB` - SPB class cars
- `Color:Blue` - Blue cars
- Or browse the hierarchical tree in the Keyword List panel

## Keyword Cleanup Utility

If you previously ran Racing Tagger with the old flat keyword format (e.g., `Make:Porsche`, `Model:911GT3Cup`) and have since migrated to the hierarchical keyword structure (e.g., `AI Keywords|Make|Porsche`), you can use the cleanup utility to remove old flat keywords while preserving the new hierarchical keywords and any manual keywords.

### Usage

```bash
# Dry run to preview what would be removed
python3 cleanup_old_keywords.py /path/to/images --dry-run

# Clean up a specific directory
python3 cleanup_old_keywords.py /path/to/images

# Clean up a single file
python3 cleanup_old_keywords.py /path/to/image.xmp

# Verbose output showing preserved keywords
python3 cleanup_old_keywords.py /path/to/images --verbose
```

### What Gets Removed

The cleanup tool removes **only** old flat auto-generated keywords:
- `Make:Porsche`, `Model:911GT3Cup`, `Color:Blue`, `Color:Black`
- `Num:73`, `Class:SPB`, `Engine:Flat6`
- `Error:*`, `Sequence:*`, `People:*`, `Subcategory:*`
- `Classified`, `NoSubject`

### What Gets Preserved

The cleanup tool **preserves**:
- **New hierarchical keywords**: `AI Keywords|Make|Porsche`, `AI Keywords|Model|911GT3`, etc.
- **Manual keywords**: Track names, customer info, event names, etc.

### Logging

Each run creates a timestamped log file (e.g., `cleanup_keywords_20260103_191652.log`) with detailed information about which keywords were removed from each file.

### Safety

- Always use `--dry-run` first to preview changes
- The tool reads from both `Subject` and `HierarchicalSubject` XMP fields
- Keywords are removed from both fields to ensure complete cleanup
- No backups are created (exiftool's `-overwrite_original` flag is used)

## How It Works

1. **Image Analysis**: Each image is sent to a local vision model (qwen2.5vl recommended)
2. **Metadata Extraction**: The model identifies car make, model, color, class, and numbers
3. **XMP Writing**: Extracted metadata is written to XMP sidecar files
4. **Lightroom Import**: Lightroom reads the XMP sidecars and adds keywords to images

## Processing Speed

### Model Comparison

**M4 Max (128GB RAM, Metal acceleration):**

| Model | Size | Speed (cached) | Memory | Recommendation |
|-------|------|----------------|--------|----------------|
| qwen2.5vl:7b | 6GB | ~5.5s/img | ~8GB | **Best choice** - fast, accurate, low memory |
| qwen2.5vl:32b | 21GB | ~15.5s/img | ~24GB | No quality improvement over 7b |
| qwen2.5vl:72b | 48GB | ~31s/img | ~51GB | Slower, different but not better results |

**Windows (Ryzen 9 9950X + RTX 5070 Ti, CUDA acceleration):**

| Model | Size | Speed | Recommendation |
|-------|------|-------|----------------|
| qwen2.5vl:7b | 6GB | ~11.5s/img | **Best choice** - batch processing average with ImageMagick |
| qwen2.5vl:7b | 6GB | ~25s+/img | Without ImageMagick (full-res images, not recommended) |

**Note:** RTX 5070 Ti has 16GB VRAM, allowing headroom for larger models if desired. Older hardware (RTX 3060/3070) will be slower but still functional.

**Note:** First image after model load incurs a cold-start penalty (~6s for 7b, ~17s for 32b, ~50s for 72b). Subsequent images benefit from model caching via `keep_alive: 30m`.

### Estimated Processing Times

**M4 Max (qwen2.5vl:7b, cached):**

| Dataset Size | Time |
|--------------|------|
| 100 images | ~9 min |
| 1,000 images | ~1.5 hours |
| 10,000 images | ~15 hours |

**Windows/CUDA (qwen2.5vl:7b, Ryzen 9 9950X + RTX 5070 Ti with ImageMagick):**

| Dataset Size | Time |
|--------------|------|
| 100 images | ~19 min |
| 500 images | ~1.6 hours |
| 1,000 images | ~3.2 hours |
| 5,000 images | ~16 hours |
| 10,000 images | ~32 hours |

Based on real-world batch processing average of 11.5s/image (includes model load, I/O, and XMP writing).

Run in background with `--resume` for interruption tolerance.

## Troubleshooting

### "Cannot connect to Ollama server"

Make sure Ollama is running:
```bash
ollama serve
```

### "No vision model found"

Pull a vision model:
```bash
ollama pull qwen2.5vl:7b
```

### Slow inference

- Use qwen2.5vl:7b (fastest tested model with good accuracy)
- Ensure hardware acceleration is working (Metal on Mac, CUDA on NVIDIA)
- Check `ollama ps` to see if model is loaded

### Keywords not appearing in Lightroom

1. Make sure XMP files are in the same directory as images
2. In Lightroom, select images and choose Metadata > Read Metadata from Files
3. Or enable "Automatically read changes from XMP" in preferences

### GGML assertion failures (Windows)

If you see `GGML_ASSERT` errors, install ImageMagick to enable image resizing:
1. Download from https://imagemagick.org/script/download.php#windows
2. Install with "Add application directory to system PATH" checked
3. Restart Lightroom

The script automatically detects ImageMagick in `C:\Program Files\ImageMagick*` even if not in PATH.

### Plugin runs but nothing happens (Windows)

1. **Check for hung Python processes:** Open Task Manager and look for old `python.exe` processes. Kill any that have been running for hours.
2. **Delete stale progress files:** Delete `.racing_tagger_progress.json` files in image folders to allow reprocessing.
3. **Restart Lightroom:** The plugin caches Lua code, so restart Lightroom after any plugin updates.

### Lightroom plugin not finding Python script

The plugin looks for Python scripts in the same folder as the `.lrplugin` folder. If you installed the plugin to `%APPDATA%\Adobe\Lightroom\Modules\`, copy all `.py` files there too.

## Development

### Project Structure

```
racing-tagger/
├── racing_tagger.py        # Main CLI tool
├── cleanup_old_keywords.py # Keyword cleanup utility
├── llama_inference.py      # Ollama/llama.cpp integration
├── xmp_writer.py           # XMP sidecar writing (via exiftool)
├── prompts.py              # Vision prompts by profile
├── progress_tracker.py     # Resume capability
├── setup.sh                # Installation script (macOS/Linux)
├── RacingTagger.lrplugin/  # Lightroom Classic plugin
│   ├── Info.lua            # Plugin manifest
│   ├── Config.lua          # Cross-platform configuration
│   ├── TaggerCore.lua      # Shared functionality
│   ├── TagPhotos.lua       # Tag selected photos
│   ├── TagPhotosDryRun.lua
│   ├── TagFolder.lua       # Tag folder(s)
│   └── TagFolderDryRun.lua
├── README.md               # This file
├── WINDOWS_SETUP.md        # Windows installation guide
└── CHECKPOINT.md           # Development status
```

### Adding New Profiles

Edit `prompts.py` to add new prompt profiles for different racing series or sports.

### Testing

```bash
# Test XMP writing
python3 xmp_writer.py

# Test on sample images
python3 racing_tagger.py /path/to/samples --max-images 5 --verbose --dry-run
```

## License

MIT
