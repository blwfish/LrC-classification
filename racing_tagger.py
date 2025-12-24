#!/usr/bin/env python3
"""
Racing Photography Metadata Extraction Tool

Automatically extracts metadata from racing photography using local vision models
and writes keywords to XMP sidecars for Lightroom searchability.
"""

__version__ = '1.2.0'

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from llama_inference import LlamaVisionInference
from xmp_writer import write_xmp_keywords, read_existing_keywords, get_target_path, check_exiftool
from prompts import get_prompt
from progress_tracker import ProgressTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Extract metadata from racing photography using local vision AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/images
  %(prog)s /path/to/images --fuzzy-numbers --profile racing-porsche
  %(prog)s /path/to/images --dry-run --verbose
  %(prog)s /path/to/images --resume  # Continue from last run
        """
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    parser.add_argument(
        'input_path',
        type=Path,
        help='Directory containing images to process, or single image file'
    )

    parser.add_argument(
        '--profile',
        choices=[
            'racing-porsche',
            'racing-general',
            'racing-nascar',
            'racing-imsa',
            'racing-world-challenge',
            'racing-indycar',
            'college-sports'
        ],
        default='racing-porsche',
        help='Processing profile (default: racing-porsche)'
    )

    parser.add_argument(
        '--fuzzy-numbers',
        action='store_true',
        help='Attempt to detect duct-tape number variants (marks uncertain with ?)'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Directory for XMP sidecars (default: same as input images)'
    )

    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last run, skipping already-processed images'
    )

    parser.add_argument(
        '--reset',
        action='store_true',
        help='Clear progress tracking and start fresh'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without writing XMP files'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=1,
        help='Number of images to process in parallel (default: 1)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Override default model (e.g., qwen2.5vl:7b, qwen2.5vl:72b)'
    )

    parser.add_argument(
        '--warm-up',
        action='store_true',
        help='Pre-load model into GPU memory before processing (faster first image)'
    )

    parser.add_argument(
        '--server-url',
        type=str,
        default='http://localhost:11434',
        help='Ollama server URL (default: http://localhost:11434)'
    )

    parser.add_argument(
        '--max-images',
        type=int,
        default=None,
        help='Maximum number of images to process (for testing)'
    )

    parser.add_argument(
        '--log-file',
        type=Path,
        default=None,
        help='Write logs to file in addition to console'
    )

    # Sequence detection options
    parser.add_argument(
        '--detect-sequences',
        action='store_true',
        help='Enable sequence detection and sharpness scoring'
    )

    parser.add_argument(
        '--sequence-threshold',
        type=float,
        default=0.5,
        help='Max seconds between frames in a sequence (default: 0.5)'
    )

    parser.add_argument(
        '--sequence-dry-run',
        action='store_true',
        help='Preview sequence detection without writing XMP'
    )

    parser.add_argument(
        '--skip-sequence-sharpness',
        action='store_true',
        help='Skip sharpness scoring (only detect sequences by timestamp)'
    )

    return parser.parse_args()


def setup_logging(verbose: bool, log_file: Path = None):
    """Configure logging based on verbosity and optional file output."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True
    )


def find_images(input_path: Path, recursive: bool = True) -> list[Path]:
    """Find all supported image files in the input path.

    Args:
        input_path: Directory or file to search
        recursive: If True, search subdirectories recursively
    """
    supported_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.nef', '.cr2', '.arw', '.dng', '.raf', '.orf', '.rw2'}

    # Directories to skip (Lightroom data folders)
    skip_patterns = {'.lrdata', 'Previews.lrdata', 'Helper.lrdata'}

    if input_path.is_file():
        if input_path.suffix.lower() in supported_extensions:
            return [input_path]
        else:
            logger.warning(f"Unsupported file type: {input_path}")
            return []

    images = []
    glob_pattern = '**/*' if recursive else '*'

    for ext in supported_extensions:
        for img in input_path.glob(f'{glob_pattern}{ext}'):
            # Skip Lightroom cache/preview folders
            if not any(skip in str(img) for skip in skip_patterns):
                images.append(img)
        for img in input_path.glob(f'{glob_pattern}{ext.upper()}'):
            if not any(skip in str(img) for skip in skip_patterns):
                images.append(img)

    # Sort by full path for consistent ordering across directories
    return sorted(set(images), key=lambda p: str(p))


def fix_json_numbers(json_str: str) -> tuple[str, bool]:
    """Fix common JSON issues from model output, especially leading zeros in numbers.

    Models often output numbers like [06] or [007] which are invalid JSON.
    This converts them to strings like ["06"] or ["007"].

    Returns:
        Tuple of (fixed_json_str, was_modified)
    """
    import re
    was_modified = False

    # Fix leading zeros in arrays: [06] -> ["06"], [007, 123] -> ["007", "123"]
    # Match numbers in arrays that have leading zeros
    def fix_array_numbers(match):
        nonlocal was_modified
        content = match.group(1)
        # Split by comma, fix each number
        parts = []
        for part in content.split(','):
            part = part.strip()
            if part and re.match(r'^0\d+$', part):
                # Leading zero - quote it
                was_modified = True
                parts.append(f'"{part}"')
            elif part and re.match(r'^\d+$', part):
                # Regular number - also quote for consistency
                parts.append(f'"{part}"')
            else:
                parts.append(part)
        return '[' + ', '.join(parts) + ']'

    # Match array contents after "numbers": or similar
    fixed_str = re.sub(r'\[(\s*\d+(?:\s*,\s*\d+)*\s*)\]', fix_array_numbers, json_str)
    return fixed_str, was_modified


def fix_truncated_json(json_str: str) -> str:
    """Attempt to fix truncated JSON from model output.

    Models sometimes get cut off mid-response, leaving incomplete JSON.
    This tries to salvage what we can by closing open brackets/braces.
    """
    import re

    # If JSON looks complete, return as-is
    if json_str.rstrip().endswith('}'):
        return json_str

    # For arrays with quoted strings, find the last complete element
    # Look for patterns like: "value", "value", "value"... and truncate at last complete one
    # This handles cases like: ["911", "911", "911", "9  (incomplete)

    # Find the last complete quoted string followed by comma or nothing
    # Pattern: find position of last complete "xxx", or "xxx"]
    last_complete = -1
    in_string = False
    i = 0
    while i < len(json_str):
        c = json_str[i]
        if c == '"' and (i == 0 or json_str[i-1] != '\\'):
            in_string = not in_string
            if not in_string:
                # End of string - this is a complete element
                # Check if followed by comma, bracket, or brace
                rest = json_str[i+1:].lstrip()
                if rest and rest[0] in ',]}':
                    last_complete = i + 1
        i += 1

    # If we found a last complete string and it's not at the very end, truncate there
    # (truncate if we'd remove at least 2 chars - handles trailing incomplete elements)
    if last_complete > 0 and last_complete < len(json_str) - 1:
        json_str = json_str[:last_complete]
        # Clean up trailing comma if needed
        json_str = json_str.rstrip().rstrip(',')

    # Also handle lines that look like hallucinated content
    lines = json_str.split('\n')
    fixed_lines = []

    for line in lines:
        # Skip lines that look like truncated array content (long lines of just numbers/commas)
        if re.match(r'^\s*[\d\s,\[\]"]+$', line) and len(line) > 100:
            # This is likely a hallucinated array line, truncate
            logger.debug("Truncating hallucinated array content")
            break
        fixed_lines.append(line)

    result = '\n'.join(fixed_lines)

    # Count unclosed brackets
    open_brackets = result.count('[') - result.count(']')
    open_braces = result.count('{') - result.count('}')

    # Close them
    result = result.rstrip().rstrip(',')
    result += ']' * max(0, open_brackets)
    result += '}' * max(0, open_braces)

    return result


def parse_model_response(response: str) -> dict:
    """Parse the model's response into structured metadata."""
    metadata = {
        'car_detected': True,  # Assume true for backwards compatibility
        'people_detected': False,  # Whether people are visible in the image
        'make': None,
        'model': None,
        'color': None,
        'class': None,
        'subcategory': None,  # NASCAR subcategory (Cup, LateModel, etc.)
        'engine': None,       # IndyCar engine manufacturer (Chevrolet, Honda)
        'numbers': [],
        'fuzzy_numbers': [],
        'raw_response': response
    }

    # Try to parse JSON response first
    try:
        # Look for JSON block in response
        if '{' in response:
            start = response.find('{')
            # Try to find closing brace, but handle truncated responses
            end = response.rfind('}')
            if end > start:
                json_str = response[start:end + 1]
            else:
                # No closing brace - try to fix truncated JSON
                json_str = response[start:]
                json_str = fix_truncated_json(json_str)
                logger.debug("Attempted to fix truncated JSON response")

            # Fix common JSON issues from model output
            json_str, json_was_fixed = fix_json_numbers(json_str)
            if json_was_fixed:
                logger.debug(f"Fixed JSON leading zeros in model response")
            data = json.loads(json_str)

            # Check if car was detected
            car_detected = data.get('car_detected', True)
            if car_detected is False or str(car_detected).lower() == 'false':
                metadata['car_detected'] = False
                # Still check for people even if no car detected
                people_detected = data.get('people_detected', False)
                if people_detected is True or str(people_detected).lower() == 'true':
                    metadata['people_detected'] = True
                # Return early with no car data but possible people
                return metadata

            metadata['car_detected'] = True
            metadata['make'] = data.get('make')
            metadata['model'] = data.get('model')

            # Handle color - may be a list from model output
            color = data.get('color')
            if isinstance(color, list):
                # Join multiple colors with " and "
                color = ' and '.join(str(c) for c in color if c)
            metadata['color'] = color

            metadata['class'] = data.get('class')
            metadata['subcategory'] = data.get('subcategory')  # NASCAR
            metadata['engine'] = data.get('engine')            # IndyCar

            # Check if people are present
            people_detected = data.get('people_detected', False)
            if people_detected is True or str(people_detected).lower() == 'true':
                metadata['people_detected'] = True

            # Handle numbers - with hallucination detection
            nums = data.get('numbers', data.get('number', []))
            if isinstance(nums, (str, int)):
                nums = [nums]
            # Filter to only numeric values (avoid color names ending up in numbers)
            nums = [str(n) for n in nums if n and str(n).isdigit()]

            # Detect hallucination: too many numbers or excessive repetition
            if len(nums) > 10:
                logger.warning(f"Detected likely hallucination: {len(nums)} numbers, truncating to unique values")
                # Keep only unique numbers, max 5
                seen = set()
                unique_nums = []
                for n in nums:
                    if n not in seen and len(unique_nums) < 5:
                        seen.add(n)
                        unique_nums.append(n)
                nums = unique_nums

            metadata['numbers'] = nums

            # Handle fuzzy numbers
            fuzzy = data.get('fuzzy_numbers', data.get('possible_numbers', []))
            if isinstance(fuzzy, (str, int)):
                fuzzy = [fuzzy]
            metadata['fuzzy_numbers'] = [str(n) for n in fuzzy if n]

            return metadata
    except json.JSONDecodeError:
        pass

    # Fallback: parse text response
    lines = response.lower().split('\n')
    for line in lines:
        line = line.strip()
        if 'make:' in line or 'manufacturer:' in line:
            metadata['make'] = line.split(':', 1)[1].strip().title()
        elif 'model:' in line:
            metadata['model'] = line.split(':', 1)[1].strip()
        elif 'color:' in line or 'colour:' in line:
            metadata['color'] = line.split(':', 1)[1].strip().title()
        elif 'class:' in line:
            metadata['class'] = line.split(':', 1)[1].strip().upper()
        elif 'number:' in line or 'num:' in line:
            num_part = line.split(':', 1)[1].strip()
            # Extract numbers, handling comma-separated lists
            for num in num_part.replace(',', ' ').split():
                if num.isdigit():
                    metadata['numbers'].append(num)

    return metadata


def metadata_to_keywords(metadata: dict, fuzzy_numbers: bool = False) -> list[str]:
    """Convert parsed metadata to Lightroom keyword format."""
    keywords = []

    if metadata.get('make'):
        keywords.append(f"Make:{metadata['make']}")

    if metadata.get('model'):
        # Normalize model name (remove spaces, common variations)
        model = metadata['model'].replace(' ', '').replace('-', '')
        keywords.append(f"Model:{model}")

    if metadata.get('color'):
        keywords.append(f"Color:{metadata['color']}")

    if metadata.get('class'):
        keywords.append(f"Class:{metadata['class']}")

    # NASCAR subcategory (Cup, Truck, LateModel, Modified, Sportsman)
    if metadata.get('subcategory'):
        keywords.append(f"Subcategory:{metadata['subcategory']}")

    # IndyCar engine manufacturer (Chevrolet, Honda)
    if metadata.get('engine'):
        keywords.append(f"Engine:{metadata['engine']}")

    # Primary numbers (confident)
    for num in metadata.get('numbers', []):
        keywords.append(f"Num:{num}")

    # Fuzzy numbers (uncertain, only if flag enabled)
    if fuzzy_numbers:
        for num in metadata.get('fuzzy_numbers', []):
            if num not in metadata.get('numbers', []):
                keywords.append(f"Num:{num}?")

    # People detection (adds "People:People" when people are visible)
    # This will create the hierarchy: AI Keywords | People | People
    if metadata.get('people_detected'):
        keywords.append("People:People")

    return keywords


def process_single_image(
    image_path: Path,
    inference: LlamaVisionInference,
    profile: str,
    fuzzy_numbers: bool,
    output_dir: Path,
    dry_run: bool
) -> dict:
    """Process a single image and return results."""
    result = {
        'image': str(image_path),
        'success': False,
        'keywords': [],
        'error': None,
        'inference_time': 0
    }

    try:
        # Get the appropriate prompt
        prompt = get_prompt(profile, fuzzy_numbers=fuzzy_numbers)

        # Run inference
        start_time = datetime.now()
        response = inference.analyze_image(image_path, prompt)
        result['inference_time'] = (datetime.now() - start_time).total_seconds()

        # Parse response
        metadata = parse_model_response(response)
        result['metadata'] = metadata
        result['car_detected'] = metadata.get('car_detected', True)

        # Generate keywords if either a car was detected OR people were detected
        car_detected = metadata.get('car_detected', True)
        people_detected = metadata.get('people_detected', False)

        if not car_detected and not people_detected:
            # No car and no people - tag as "No Subject" (two-level hierarchy only)
            keywords = ['NoSubject']
            result['keywords'] = keywords
        else:
            keywords = metadata_to_keywords(metadata, fuzzy_numbers=fuzzy_numbers)
            result['keywords'] = keywords

        if not dry_run:
            # Determine where to write (XMP sidecar for RAW, embed for JPG)
            target_path = get_target_path(image_path, output_dir)

            # Always write at least a marker keyword to indicate processing completed
            if not keywords:
                keywords = ['Classified']

            # Write keywords (exiftool handles merging)
            write_xmp_keywords(target_path, keywords, source_image=image_path, merge=True)
            result['target_path'] = str(target_path)

        result['success'] = True

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error processing {image_path.name}: {e}")

    return result


def process_with_encoded_image(
    image_path: Path,
    image_data: str,
    inference: LlamaVisionInference,
    profile: str,
    fuzzy_numbers: bool,
    output_dir: Path,
    dry_run: bool
) -> dict:
    """Process a single image with pre-encoded data (for pipelining)."""
    result = {
        'image': str(image_path),
        'success': False,
        'keywords': [],
        'error': None,
        'inference_time': 0
    }

    try:
        prompt = get_prompt(profile, fuzzy_numbers=fuzzy_numbers)

        # Run inference with pre-encoded image
        start_time = datetime.now()
        response = inference.analyze_encoded_image(image_data, prompt)
        result['inference_time'] = (datetime.now() - start_time).total_seconds()

        # Parse response
        metadata = parse_model_response(response)
        result['metadata'] = metadata
        result['car_detected'] = metadata.get('car_detected', True)

        # Generate keywords if either a car was detected OR people were detected
        car_detected = metadata.get('car_detected', True)
        people_detected = metadata.get('people_detected', False)

        if not car_detected and not people_detected:
            # No car and no people - tag as "No Subject" (two-level hierarchy only)
            keywords = ['NoSubject']
            result['keywords'] = keywords
        else:
            keywords = metadata_to_keywords(metadata, fuzzy_numbers=fuzzy_numbers)
            result['keywords'] = keywords

        if not dry_run:
            target_path = get_target_path(image_path, output_dir)

            # Always write at least a marker keyword to indicate processing completed
            if not keywords:
                keywords = ['Classified']

            write_xmp_keywords(target_path, keywords, source_image=image_path, merge=True)
            result['target_path'] = str(target_path)

        result['success'] = True

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error processing {image_path.name}: {e}")

    return result


def main():
    args = parse_args()
    setup_logging(args.verbose, args.log_file)

    # Validate input path
    if not args.input_path.exists():
        logger.error(f"Input path does not exist: {args.input_path}")
        sys.exit(1)

    # Find images
    images = find_images(args.input_path)
    if not images:
        logger.error(f"No supported images found in {args.input_path}")
        sys.exit(1)

    logger.info(f"Found {len(images)} images to process")

    # Sequence detection (runs on all images, before resume filtering)
    if args.detect_sequences:
        from sequence_stacking import (
            SequenceDetector, SharpnessScorer,
            print_sequence_preview, write_sequence_metadata
        )

        logger.info(f"Detecting sequences (threshold: {args.sequence_threshold}s)...")
        detector = SequenceDetector()
        sequences = detector.detect_sequences(images, args.sequence_threshold)

        if sequences:
            # Score sharpness unless skipped
            if not args.skip_sequence_sharpness:
                logger.info("Scoring sharpness for sequence frames...")
                scorer = SharpnessScorer()
                for i, seq in enumerate(sequences, 1):
                    logger.info(f"  Scoring sequence {i}/{len(sequences)}: {seq.sequence_id}")
                    scorer.score_sequence(seq)

            # Dry run: preview and exit
            if args.sequence_dry_run:
                print_sequence_preview(sequences)
                sys.exit(0)

            # Write sequence metadata
            if not args.dry_run:
                logger.info("Writing sequence keywords...")
                for seq in sequences:
                    write_sequence_metadata(seq, output_dir=args.output_dir, dry_run=False)
                logger.info(f"Sequence metadata written for {len(sequences)} sequences")
            else:
                logger.info(f"[DRY RUN] Would write sequence metadata for {len(sequences)} sequences")
        else:
            if args.sequence_dry_run:
                print("No sequences detected.")
                sys.exit(0)

    # Setup progress tracker
    tracker_path = args.input_path if args.input_path.is_dir() else args.input_path.parent
    tracker = ProgressTracker(tracker_path / '.racing_tagger_progress.json')

    if args.reset:
        tracker.reset()
        logger.info("Progress tracking reset")

    # Filter already-processed images if resuming
    if args.resume:
        original_count = len(images)
        images = [img for img in images if not tracker.is_processed(img)]
        skipped = original_count - len(images)
        if skipped > 0:
            logger.info(f"Resuming: skipping {skipped} already-processed images")

    if not images:
        logger.info("All images already processed. Use --reset to start fresh.")
        sys.exit(0)

    # Apply max-images limit
    if args.max_images:
        images = images[:args.max_images]
        logger.info(f"Limited to {len(images)} images (--max-images)")

    # Setup output directory
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize inference engine
    logger.info("Initializing vision model...")
    try:
        inference = LlamaVisionInference(
            server_url=args.server_url,
            model=args.model
        )

        # Verify connection
        if not inference.check_connection():
            logger.error("Cannot connect to Ollama server. Is it running?")
            logger.error(f"Expected at: {args.server_url}")
            logger.error("Start with: ollama serve")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Failed to initialize inference engine: {e}")
        sys.exit(1)

    # Optional warm-up: pre-load model into GPU memory
    if args.warm_up:
        inference.warm_up()

    # Process images
    results = []
    processed = 0
    failed = 0
    no_car_count = 0

    logger.info(f"Processing {len(images)} images with profile '{args.profile}'...")
    if args.fuzzy_numbers:
        logger.info("Fuzzy number detection enabled")
    if args.dry_run:
        logger.info("DRY RUN - no XMP files will be written")

    # Pipelined processing: encode next image while running inference on current
    # This overlaps the ~0.3-0.5s encoding time with the ~5s inference time
    from concurrent.futures import ThreadPoolExecutor

    def encode_image_task(img_path):
        """Background task to encode an image."""
        try:
            return inference.encode_image(img_path)
        except Exception as e:
            logger.debug(f"Failed to pre-encode {img_path.name}: {e}")
            return None

    # Pre-encode the first image
    next_encoded = None
    if images:
        logger.debug(f"Pre-encoding first image: {images[0].name}")
        next_encoded = encode_image_task(images[0])

    with ThreadPoolExecutor(max_workers=1) as executor:
        for i, image_path in enumerate(images, 1):
            logger.info(f"[{i}/{len(images)}] Processing {image_path.name}...")

            # Get pre-encoded data for current image
            current_encoded = next_encoded

            # Start encoding next image in background (if there is one)
            next_future = None
            if i < len(images):
                next_future = executor.submit(encode_image_task, images[i])

            # Process current image
            if current_encoded:
                result = process_with_encoded_image(
                    image_path=image_path,
                    image_data=current_encoded,
                    inference=inference,
                    profile=args.profile,
                    fuzzy_numbers=args.fuzzy_numbers,
                    output_dir=args.output_dir,
                    dry_run=args.dry_run
                )
            else:
                # Fallback if pre-encoding failed
                result = process_single_image(
                    image_path=image_path,
                    inference=inference,
                    profile=args.profile,
                    fuzzy_numbers=args.fuzzy_numbers,
                    output_dir=args.output_dir,
                    dry_run=args.dry_run
                )

            # Get pre-encoded data for next iteration
            if next_future:
                next_encoded = next_future.result()
            else:
                next_encoded = None

            results.append(result)

            if result['success']:
                processed += 1
                tracker.mark_processed(image_path, result['keywords'])
                if not result.get('car_detected', True):
                    kw_str = '(no car detected)'
                    no_car_count += 1
                elif result['keywords']:
                    kw_str = ', '.join(result['keywords'])
                else:
                    kw_str = '(no keywords)'
                logger.info(f"  -> {kw_str} ({result['inference_time']:.1f}s)")
            else:
                failed += 1
                logger.warning(f"  -> FAILED: {result['error']}")

    # Summary
    logger.info("-" * 50)
    summary_parts = [f"{processed} successful", f"{failed} failed"]
    if no_car_count > 0:
        summary_parts.append(f"{no_car_count} no car detected")
    logger.info(f"Processing complete: {', '.join(summary_parts)}")

    if args.dry_run:
        logger.info("DRY RUN complete - no files were modified")

    # Write completion file for Lightroom plugin
    try:
        # Determine completion file path - ALWAYS use temp directory to match Config.lua
        # Config.lua looks for it at: LrPathUtils.child(tempDir, 'racing_tagger_output.complete')
        import tempfile
        completion_file = Path(tempfile.gettempdir()) / 'racing_tagger_output.complete'

        # Get cumulative stats from tracker (persistent across invocations)
        cumulative_total_time = 0
        if tracker and hasattr(tracker, 'get_stats'):
            stats = tracker.get_stats()
            cumulative_total_time = stats.get('total_time', 0)

        # Read sequence number and accumulate stats from existing file (for batch processing)
        sequence = 0
        previous_total_images = 0
        previous_successful = 0
        previous_failed = 0
        previous_no_car = 0

        if completion_file.exists():
            try:
                with open(completion_file, 'r') as f:
                    existing = json.load(f)
                    sequence = existing.get('sequence', 0) + 1
                    # Extract previous accumulated stats (but NOT total_time - tracker has that)
                    if 'stats' in existing:
                        previous_total_images = existing['stats'].get('total_images', 0)
                        previous_successful = existing['stats'].get('successful', 0)
                        previous_failed = existing['stats'].get('failed', 0)
                        previous_no_car = existing['stats'].get('no_car', 0)
            except:
                sequence = 1
        else:
            sequence = 1

        # Accumulate stats across all invocations in the batch
        accumulated_total_images = previous_total_images + (len(images) if images else 0)
        accumulated_successful = previous_successful + processed
        accumulated_failed = previous_failed + failed
        accumulated_no_car = previous_no_car + no_car_count
        # Use tracker's cumulative total_time directly (don't double-count)
        accumulated_total_time = cumulative_total_time

        # Calculate cumulative average time per image
        if accumulated_successful > 0:
            accumulated_avg_time = accumulated_total_time / accumulated_successful
        else:
            accumulated_avg_time = 0

        completion_data = {
            'completed': True,
            'sequence': sequence,  # Increments each time a file finishes (batch processing)
            'timestamp': datetime.now().isoformat(),
            'stats': {
                'total_images': accumulated_total_images,
                'successful': accumulated_successful,
                'failed': accumulated_failed,
                'no_car': accumulated_no_car,
                'avg_time_per_image': accumulated_avg_time,
                'total_time': accumulated_total_time
            },
            'dry_run': args.dry_run
        }

        with open(completion_file, 'w') as f:
            json.dump(completion_data, f, indent=2)
        logger.debug(f"Wrote completion file: {completion_file}")
    except Exception as e:
        logger.warning(f"Failed to write completion file: {e}")

    # Save detailed results
    if args.log_file:
        results_path = args.log_file.with_suffix('.results.json')
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Detailed results saved to: {results_path}")


if __name__ == '__main__':
    main()
