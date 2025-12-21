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

### Hardware

**macOS (recommended):**
- Apple Silicon (M1/M2/M3/M4) for Metal acceleration
- 16GB+ RAM recommended

**Windows 11:**
- NVIDIA GPU with 8GB+ VRAM for CUDA acceleration
- Or CPU-only (slower, ~30-60 sec/image)
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
                       Options: racing-porsche, racing-general, college-sports

--fuzzy-numbers        Attempt to detect duct-tape number variants

--output-dir DIR       Write XMP files to different directory

--resume               Continue from last run, skipping processed images

--reset                Clear progress and start fresh

--dry-run              Show what would happen without writing files

--verbose, -v          Enable detailed output

--max-images N         Limit processing to N images (for testing)

--model MODEL          Override vision model (e.g., llava:13b)

--log-file FILE        Write logs to file
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
```

## Keyword Format

Keywords use a prefix format for clear categorization:

```
Make:Porsche
Model:CaymanGT4
Color:Blue
Class:SPB
Num:73
Num:173?     (uncertain, with fuzzy-numbers flag)
```

### Searching in Lightroom

After importing XMP sidecars, search in Lightroom using:
- `Make:Porsche` - All Porsches
- `Num:73` - Car number 73
- `Class:SPB` - SPB class cars
- `Color:Blue` - Blue cars

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

**Windows (Ryzen 9 5950X + RTX 3060, CUDA acceleration):**

| Model | Size | Speed | Recommendation |
|-------|------|-------|----------------|
| qwen2.5vl:7b | 6GB | ~25s/img | Good for batch processing overnight |

**Note:** First image after model load incurs a cold-start penalty (~6s for 7b, ~17s for 32b, ~50s for 72b). Subsequent images benefit from model caching via `keep_alive: 30m`.

### Estimated Processing Times

**M4 Max (qwen2.5vl:7b, cached):**

| Dataset Size | Time |
|--------------|------|
| 100 images | ~9 min |
| 1,000 images | ~1.5 hours |
| 10,000 images | ~15 hours |

**Windows/CUDA (qwen2.5vl:7b, Ryzen 9 5950X + RTX 3060):**

| Dataset Size | Time |
|--------------|------|
| 100 images | ~42 min |
| 1,000 images | ~7 hours |
| 10,000 images | ~70 hours (~3 days) |

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

## Development

### Project Structure

```
racing-tagger/
├── racing_tagger.py        # Main CLI tool
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
