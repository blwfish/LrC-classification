#!/usr/bin/env python3
"""
Racing Photography Metadata Extraction Tool

Automatically extracts metadata from racing photography using local vision models
and writes keywords to XMP sidecars for Lightroom searchability.
"""

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
        'input_path',
        type=Path,
        help='Directory containing images to process, or single image file'
    )

    parser.add_argument(
        '--profile',
        choices=['racing-porsche', 'racing-general', 'college-sports'],
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
        help='Override default model (e.g., llava:7b, llava:13b, llava:34b)'
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
        'make': None,
        'model': None,
        'color': None,
        'class': None,
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
                # Return early with no car data
                return metadata

            metadata['car_detected'] = True
            metadata['make'] = data.get('make')
            metadata['model'] = data.get('model')
            metadata['color'] = data.get('color')
            metadata['class'] = data.get('class')

            # Handle numbers - with hallucination detection
            nums = data.get('numbers', data.get('number', []))
            if isinstance(nums, (str, int)):
                nums = [nums]
            nums = [str(n) for n in nums if n]

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

    # Primary numbers (confident)
    for num in metadata.get('numbers', []):
        keywords.append(f"Num:{num}")

    # Fuzzy numbers (uncertain, only if flag enabled)
    if fuzzy_numbers:
        for num in metadata.get('fuzzy_numbers', []):
            if num not in metadata.get('numbers', []):
                keywords.append(f"Num:{num}?")

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

        # Only generate keywords if a car was detected
        if not metadata.get('car_detected', True):
            result['keywords'] = []
            result['success'] = True
            return result

        keywords = metadata_to_keywords(metadata, fuzzy_numbers=fuzzy_numbers)
        result['keywords'] = keywords

        if not dry_run and keywords:
            # Determine where to write (XMP sidecar for RAW, embed for JPG)
            target_path = get_target_path(image_path, output_dir)

            # Write keywords (exiftool handles merging)
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

    for i, image_path in enumerate(images, 1):
        logger.info(f"[{i}/{len(images)}] Processing {image_path.name}...")

        result = process_single_image(
            image_path=image_path,
            inference=inference,
            profile=args.profile,
            fuzzy_numbers=args.fuzzy_numbers,
            output_dir=args.output_dir,
            dry_run=args.dry_run
        )

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

    # Save detailed results
    if args.log_file:
        results_path = args.log_file.with_suffix('.results.json')
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Detailed results saved to: {results_path}")


if __name__ == '__main__':
    main()
