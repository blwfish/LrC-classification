# Testing Guide

## Test Dataset

Location: `/Volumes/Additional Files/samples`
- 133 JPEG images from a PCA racing event
- High resolution (5893x4542) from Nikon Z9
- Exported via Lightroom Classic

## Quick Validation

### 1. Verify Installation

```bash
cd /Volumes/Additional\ Files/development/racing-tagger
./setup.sh
```

### 2. Check Ollama Connection

```bash
# Start Ollama if not running
ollama serve &

# Verify connection
curl http://localhost:11434/api/tags
```

### 3. Verify Vision Model

```bash
# List available models
ollama list

# Pull llava if needed
ollama pull llava:7b
```

## Test Runs

### Dry Run (No Files Written)

```bash
python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --max-images 3 \
    --dry-run \
    --verbose
```

Expected output:
- Should connect to Ollama
- Process 3 images
- Display extracted keywords
- No XMP files created

### Single Image Test

```bash
python3 racing_tagger.py "/Volumes/Additional Files/samples/_BLW0278.jpg" \
    --verbose
```

Check results:
```bash
ls -la "/Volumes/Additional Files/samples/_BLW0278.xmp"
cat "/Volumes/Additional Files/samples/_BLW0278.xmp"
```

### Batch Test (10 Images)

```bash
python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --max-images 10 \
    --verbose \
    --log-file test_run.log
```

Review results:
```bash
# Check XMP files created
ls "/Volumes/Additional Files/samples"/*.xmp | wc -l

# View extracted keywords
cat test_run.log | grep "keywords"
```

### Fuzzy Numbers Test

```bash
python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --max-images 5 \
    --fuzzy-numbers \
    --verbose
```

Look for `Num:XX?` keywords indicating uncertain number variants.

### Resume Test

```bash
# Process 5 images
python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --max-images 5

# Process remaining with resume
python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --resume
```

Should skip the 5 already-processed images.

### Reset Test

```bash
# Clear progress
python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --reset \
    --max-images 3
```

Should reprocess from scratch.

## Validation Criteria

### Accuracy Metrics

For each test run, evaluate:

1. **Car Detection** - Is there a car in the image? Was it detected?
2. **Make Accuracy** - Is the make correct? (Should be Porsche for PCA)
3. **Model Accuracy** - Is the model reasonably identified?
4. **Number Detection** - Are car numbers found and correct?
5. **Color Accuracy** - Is the color reasonably described?
6. **Class Detection** - Is the PCA class identified (if visible)?

### Manual Verification

Sample verification process:
1. Open original image
2. Compare extracted keywords against visual inspection
3. Note any:
   - Missed information (visible but not extracted)
   - Incorrect information (wrong make/model/number)
   - Hallucinated information (extracted but not present)

### Expected Results

For PCA racing photos, expect:
- Make: "Porsche" for 95%+ of images
- Model: Variable accuracy, expect 60-80% correct
- Numbers: 70-90% detection rate, 80-95% accuracy when detected
- Color: 80-90% reasonable accuracy
- Class: 40-60% detection (depends on visibility in photos)

## Performance Benchmarks

### M4 Max (Brian's System)

Target benchmarks:
- llava:7b: 30-60 seconds/image
- llava:13b: 60-120 seconds/image

Measure:
```bash
time python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --max-images 10 \
    --verbose 2>&1 | tee benchmark.log
```

Calculate average:
```bash
grep "inference_time" benchmark.log
```

### GPU System (Vic's System)

Target benchmarks:
- llava:7b: 1-3 seconds/image
- llava:13b: 3-8 seconds/image

## Troubleshooting Tests

### Connection Issues

```bash
# Test Ollama API directly
curl -X POST http://localhost:11434/api/generate \
    -d '{"model": "llava:7b", "prompt": "test"}' \
    -H "Content-Type: application/json"
```

### Model Loading

```bash
# Check if model is loaded
ollama ps

# Force model load
ollama run llava:7b "hello"
```

### Memory Issues

Monitor during processing:
```bash
# Mac
watch -n 1 'memory_pressure'

# Linux
watch -n 1 'free -h'
```

### XMP Validation

Verify XMP structure:
```bash
# Check XML is valid
xmllint --noout "/Volumes/Additional Files/samples/_BLW0278.xmp"

# Check namespace
grep -E "dc:subject|rdf:Bag" "/Volumes/Additional Files/samples/_BLW0278.xmp"
```

## Full Test Suite

Run complete test suite:

```bash
#!/bin/bash
cd /Volumes/Additional\ Files/development/racing-tagger

echo "=== Racing Tagger Test Suite ==="
echo

# 1. Module tests
echo "1. Testing modules..."
python3 xmp_writer.py

# 2. Dry run
echo "2. Dry run test..."
python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --max-images 2 --dry-run

# 3. Single image
echo "3. Single image test..."
python3 racing_tagger.py "/Volumes/Additional Files/samples/_BLW0278.jpg" \
    --verbose

# 4. Verify XMP
echo "4. Verifying XMP..."
if [[ -f "/Volumes/Additional Files/samples/_BLW0278.xmp" ]]; then
    echo "✓ XMP file created"
    cat "/Volumes/Additional Files/samples/_BLW0278.xmp"
else
    echo "✗ XMP file not found"
fi

# 5. Batch test
echo "5. Batch test (5 images)..."
python3 racing_tagger.py "/Volumes/Additional Files/samples" \
    --max-images 5 --verbose

echo
echo "=== Test Suite Complete ==="
```

## Recording Results

Create a test results file:

```markdown
# Test Results - [DATE]

## Environment
- OS: macOS [version]
- Python: [version]
- Ollama: [version]
- Model: llava:7b
- Hardware: M4 Max / 128GB

## Results

### Accuracy (10 image sample)
- Car Detection: X/10
- Make Accuracy: X/10
- Model Accuracy: X/10
- Number Detection: X/10
- Color Accuracy: X/10

### Performance
- Average inference time: XX seconds
- Total time for 10 images: XX seconds

### Issues Found
1. [Description]
2. [Description]

### Recommendations
1. [Suggestion]
2. [Suggestion]
```
