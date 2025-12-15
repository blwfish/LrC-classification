# Racing Photography Metadata Extraction Tool

Automatically extract metadata from racing photography using local vision AI and write keywords to Lightroom-compatible XMP sidecars.

## Features

- **Local inference** - No cloud API, your images stay on your machine
- **Porsche/PCA optimized** - Specialized prompts for Porsche Club of America racing
- **Lightroom integration** - Writes standard XMP keywords that Lightroom imports automatically
- **Resumable** - Track progress and resume interrupted runs
- **Hardware accelerated** - Uses Metal (Mac) or CUDA (NVIDIA) when available

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai) for local vision model inference
- A vision model (qwen2.5vl:7b recommended)

### Hardware

**Mac (recommended):**
- Apple Silicon (M1/M2/M3/M4) for Metal acceleration
- 16GB+ RAM recommended

**Windows/Linux:**
- NVIDIA GPU with 8GB+ VRAM for CUDA acceleration
- Or CPU-only (slower)

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

### Basic Usage

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

Tested with qwen2.5vl:7b (recommended model):

| Hardware | Acceleration | Time/Image | Notes |
|----------|--------------|------------|-------|
| M4 Max | Metal GPU | ~6s | 85% GPU utilization, minimal system impact |
| RTX 4090 | CUDA | ~2-3s | Estimated |

**Benchmark Results (7,509 images):**
- Success rate: 99.97% (2 failures due to HTTP 500)
- Average time: ~6 seconds/image on M4 Max with Metal
- Total runtime: ~12 hours

For large back catalogs:
- 10K images @ 6s/img ≈ 17 hours (M4 Max)
- 100K images @ 6s/img ≈ 7 days (M4 Max)

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
├── racing_tagger.py      # Main CLI tool
├── llama_inference.py    # Ollama/llama.cpp integration
├── xmp_writer.py         # XMP sidecar writing
├── prompts.py            # Vision prompts by profile
├── progress_tracker.py   # Resume capability
├── setup.sh              # Installation script
└── README.md             # This file
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
