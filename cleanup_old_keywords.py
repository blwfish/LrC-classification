#!/usr/bin/env python3
"""
Cleanup Old Flat Keywords

Removes ONLY old flat auto-generated keywords from XMP files while preserving:
- New hierarchical keywords (AI Keywords|Make|Porsche, etc.)
- Manual keywords (track names, customer info, event names, etc.)

This is a one-time utility to clean up keywords after migrating to hierarchical keyword structure.

Old flat keywords REMOVED:
- Make:Porsche, Model:911GT3Cup, Color:Blue, etc.
- Num:73, Class:SPB, etc.
- Error:*, Sequence:*, People:*, etc.
- Classified, NoSubject

Keywords PRESERVED:
- AI Keywords|Make|Porsche (new hierarchical format)
- AI Keywords|Model|911GT3 (new hierarchical format)
- Track names, customer info, event names, etc. (manual keywords)
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# Import exiftool path from xmp_writer
from xmp_writer import EXIFTOOL_PATH, check_exiftool

logger = logging.getLogger(__name__)


# Patterns for auto-generated keywords that should be removed
AUTO_GENERATED_PREFIXES = [
    'Make:',
    'Model:',
    'Color:',
    'Class:',
    'Num:',
    'Error:',
    'People:',
    'Sequence:',
    'Subcategory:',
    'Engine:',
]

AUTO_GENERATED_STANDALONE = [
    'Classified',
    'NoSubject',
]


def parse_args():
    parser = argparse.ArgumentParser(
        description='Remove old flat auto-generated keywords from images/XMP files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/images --dry-run
  %(prog)s /path/to/images --verbose
  %(prog)s /path/to/images/specific_file.xmp

This tool removes ONLY old flat keywords like:
  Make:Porsche, Model:911GT3Cup, Color:Blue, Num:73, etc.

It PRESERVES:
  - New hierarchical keywords (AI Keywords|Make|Porsche, etc.)
  - Manual keywords (track names, customer info, event names, etc.)
        """
    )

    parser.add_argument(
        'input_path',
        type=Path,
        help='Directory containing images/XMP files, or single image/XMP file'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without modifying files'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output including preserved keywords'
    )

    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        default=True,
        help='Process subdirectories recursively (default: True)'
    )

    return parser.parse_args()


def find_files(input_path: Path, recursive: bool = True) -> list[Path]:
    """Find all image and XMP files in the input path."""
    # Image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.nef', '.cr2', '.arw', '.dng', '.raf', '.orf', '.rw2'}

    # XMP files
    xmp_extensions = {'.xmp'}

    all_extensions = image_extensions | xmp_extensions

    # Directories to skip (Lightroom data folders)
    skip_patterns = {'.lrdata', 'Previews.lrdata', 'Helper.lrdata'}

    if input_path.is_file():
        if input_path.suffix.lower() in all_extensions:
            return [input_path]
        else:
            logger.warning(f"Unsupported file type: {input_path}")
            return []

    files = []
    glob_pattern = '**/*' if recursive else '*'

    for ext in all_extensions:
        for file in input_path.glob(f'{glob_pattern}{ext}'):
            # Skip Lightroom cache/preview folders
            if not any(skip in str(file) for skip in skip_patterns):
                files.append(file)
        for file in input_path.glob(f'{glob_pattern}{ext.upper()}'):
            if not any(skip in str(file) for skip in skip_patterns):
                files.append(file)

    # Sort for consistent ordering
    return sorted(set(files), key=lambda p: str(p))


def read_all_keywords(file_path: Path) -> list[str]:
    """
    Read all keywords from a file using exiftool.

    Reads from Subject, HierarchicalSubject, and IPTC:Keywords fields to get everything.
    """
    if not file_path.exists():
        return []

    if not EXIFTOOL_PATH:
        logger.error("exiftool not found")
        return []

    try:
        # Read Subject, HierarchicalSubject, and IPTC:Keywords fields
        result = subprocess.run(
            [EXIFTOOL_PATH, '-Subject', '-HierarchicalSubject', '-IPTC:Keywords', '-s', '-s', '-s', str(file_path)],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            # Parse output - each line is a keyword (or comma-separated list)
            keywords = set()
            for line in result.stdout.strip().split('\n'):
                # Handle comma-separated keywords on same line
                for kw in line.split(','):
                    kw = kw.strip()
                    if kw:
                        keywords.add(kw)
            return sorted(keywords)

        return []

    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout reading keywords from {file_path.name}")
        return []
    except Exception as e:
        logger.warning(f"Error reading keywords from {file_path.name}: {e}")
        return []


def is_auto_generated_keyword(keyword: str) -> bool:
    """Check if a keyword matches our OLD flat auto-generated patterns.

    This function identifies ONLY the old flat keywords that need to be removed.
    Hierarchical keywords (AI Keywords|...) are the NEW correct format and should be kept.
    """
    # KEEP hierarchical keywords - they are the new correct format
    if keyword.startswith('AI Keywords'):
        return False

    # REMOVE old flat keywords with prefixes
    for prefix in AUTO_GENERATED_PREFIXES:
        if keyword.startswith(prefix):
            return True

    # REMOVE old standalone keywords
    if keyword in AUTO_GENERATED_STANDALONE:
        return True

    return False


def categorize_keywords(keywords: list[str]) -> tuple[list[str], list[str]]:
    """
    Categorize keywords into auto-generated (to remove) and manual (to keep).

    Returns:
        Tuple of (keywords_to_remove, keywords_to_keep)
    """
    to_remove = []
    to_keep = []

    for kw in keywords:
        if is_auto_generated_keyword(kw):
            to_remove.append(kw)
        else:
            to_keep.append(kw)

    return to_remove, to_keep


def remove_keywords(file_path: Path, keywords_to_remove: list[str], dry_run: bool = False) -> bool:
    """
    Remove specific keywords from a file using exiftool.

    Args:
        file_path: Path to image or XMP file
        keywords_to_remove: List of keywords to remove
        dry_run: If True, don't actually modify the file

    Returns:
        True if successful (or dry run), False otherwise
    """
    if not EXIFTOOL_PATH:
        logger.error("exiftool not found")
        return False

    if not keywords_to_remove:
        logger.debug(f"No keywords to remove from {file_path.name}")
        return True

    if dry_run:
        return True

    try:
        # Build exiftool command to remove keywords
        cmd = [EXIFTOOL_PATH, '-overwrite_original']

        # Remove from Subject, HierarchicalSubject, and IPTC:Keywords fields
        for kw in keywords_to_remove:
            cmd.append(f'-Subject-={kw}')
            cmd.append(f'-HierarchicalSubject-={kw}')
            cmd.append(f'-IPTC:Keywords-={kw}')

        cmd.append(str(file_path))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            return True
        else:
            logger.error(f"exiftool error removing keywords from {file_path.name}: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout removing keywords from {file_path.name}")
        return False
    except Exception as e:
        logger.error(f"Failed to remove keywords from {file_path.name}: {e}")
        return False


def process_file(file_path: Path, dry_run: bool = False, verbose: bool = False) -> dict:
    """Process a single file and return results."""
    result = {
        'file': str(file_path),
        'success': False,
        'removed_count': 0,
        'kept_count': 0,
        'removed_keywords': [],
        'kept_keywords': [],
        'error': None
    }

    try:
        # Read existing keywords
        keywords = read_all_keywords(file_path)

        if not keywords:
            logger.debug(f"No keywords found in {file_path.name}")
            result['success'] = True
            return result

        # Categorize into auto-generated vs manual
        to_remove, to_keep = categorize_keywords(keywords)

        result['removed_keywords'] = to_remove
        result['kept_keywords'] = to_keep
        result['removed_count'] = len(to_remove)
        result['kept_count'] = len(to_keep)

        if not to_remove:
            logger.debug(f"No auto-generated keywords to remove from {file_path.name}")
            result['success'] = True
            return result

        # Remove the auto-generated keywords
        success = remove_keywords(file_path, to_remove, dry_run=dry_run)
        result['success'] = success

        return result

    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error processing {file_path.name}: {e}")
        return result


def main():
    args = parse_args()

    # Create timestamped log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = Path(f'cleanup_keywords_{timestamp}.log')

    # Set up logging to both console and file
    level = logging.DEBUG if args.verbose else logging.INFO

    # Clear any existing handlers
    logging.getLogger().handlers.clear()

    # Create formatters
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_handler.setFormatter(file_formatter)

    # Configure root logger
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().addHandler(console_handler)
    logging.getLogger().addHandler(file_handler)

    logger.info(f"Cleanup started - logging to {log_file}")
    logger.info(f"Command: {' '.join(sys.argv)}")
    logger.info("")

    # Check for exiftool
    if not check_exiftool():
        logger.error("exiftool not found. Please install it:")
        logger.error("  Windows: Download from https://exiftool.org/")
        logger.error("  macOS: brew install exiftool")
        logger.error("  Linux: apt install libimage-exiftool-perl")
        sys.exit(1)

    # Validate input path
    if not args.input_path.exists():
        logger.error(f"Input path does not exist: {args.input_path}")
        sys.exit(1)

    # Find files
    files = find_files(args.input_path, recursive=args.recursive)
    if not files:
        logger.error(f"No supported files found in {args.input_path}")
        sys.exit(1)

    logger.info(f"Found {len(files)} files to process")

    if args.dry_run:
        logger.info("DRY RUN MODE - no files will be modified")

    # Process files
    processed = 0
    modified = 0
    total_removed = 0
    total_kept = 0
    failed = 0

    logger.info("-" * 60)

    for i, file_path in enumerate(files, 1):
        result = process_file(file_path, dry_run=args.dry_run, verbose=args.verbose)

        if result['success']:
            processed += 1

            if result['removed_count'] > 0:
                modified += 1
                total_removed += result['removed_count']
                total_kept += result['kept_count']

                action = "[DRY RUN]" if args.dry_run else "[CLEANED]"
                logger.info(f"{action} {file_path.name}")
                logger.info(f"  Removed {result['removed_count']} auto-generated keywords:")
                for kw in result['removed_keywords']:
                    logger.info(f"    - {kw}")

                if args.verbose and result['kept_keywords']:
                    logger.info(f"  Kept {result['kept_count']} manual keywords:")
                    for kw in result['kept_keywords']:
                        logger.info(f"    + {kw}")

                logger.info("")
        else:
            failed += 1
            logger.error(f"[FAILED] {file_path.name}: {result.get('error', 'Unknown error')}")

    # Summary
    logger.info("-" * 60)
    logger.info(f"Processing complete:")
    logger.info(f"  Files processed: {processed}/{len(files)}")
    logger.info(f"  Files modified: {modified}")
    logger.info(f"  Total keywords removed: {total_removed}")
    logger.info(f"  Total keywords kept: {total_kept}")
    logger.info(f"  Failed: {failed}")

    if args.dry_run:
        logger.info("")
        logger.info("This was a DRY RUN - no files were modified")
        logger.info("Run without --dry-run to actually remove keywords")

    logger.info("")
    logger.info(f"Full log saved to: {log_file.absolute()}")


if __name__ == '__main__':
    main()
