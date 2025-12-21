"""
Keyword Writer for Lightroom

Uses exiftool to write hierarchical keywords to:
- XMP sidecar files (for RAW files like NEF, CR2, ARW)
- Directly into image files (for JPG, TIFF, PNG)

Writes keywords using pipe-separated hierarchical paths (e.g., AI Keywords|Make|Porsche)
that Lightroom displays as expandable tree structures in the Keyword List panel.

Exiftool handles all the XMP format complexity and ensures
compatibility with Lightroom's expected metadata structure.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Check if exiftool is available
# First try to find it in PATH, then try Windows default location
EXIFTOOL_PATH = shutil.which('exiftool')
if not EXIFTOOL_PATH:
    # Try Windows default installation location
    windows_exiftool = 'C:\\Windows\\exiftool\\exiftool.exe'
    if Path(windows_exiftool).exists():
        EXIFTOOL_PATH = windows_exiftool

# File extensions that require XMP sidecars (can't embed metadata)
RAW_EXTENSIONS = {'.nef', '.cr2', '.cr3', '.arw', '.raf', '.orf', '.rw2', '.dng', '.raw'}

# File extensions that support embedded metadata
EMBEDDABLE_EXTENSIONS = {'.jpg', '.jpeg', '.tif', '.tiff', '.png'}

def check_exiftool() -> bool:
    """Check if exiftool is available."""
    return EXIFTOOL_PATH is not None


def is_raw_file(path: Path) -> bool:
    """Check if a file is a RAW format that requires XMP sidecars."""
    return path.suffix.lower() in RAW_EXTENSIONS


def is_embeddable(path: Path) -> bool:
    """Check if a file supports embedded metadata."""
    return path.suffix.lower() in EMBEDDABLE_EXTENSIONS


def get_target_path(image_path: Path, output_dir: Optional[Path] = None) -> Path:
    """
    Determine where to write metadata.

    For RAW files: returns XMP sidecar path
    For JPG/TIFF: returns the image path itself (embed)
    """
    if is_raw_file(image_path):
        # Write to XMP sidecar
        if output_dir:
            return output_dir / f"{image_path.stem}.xmp"
        else:
            return image_path.with_suffix('.xmp')
    else:
        # Embed in image
        return image_path


def build_hierarchical_keywords(keywords: list[str]) -> str:
    """
    Build hierarchical keyword paths for Lightroom's HierarchicalSubject field.

    Converts flat keywords like ["Make:Porsche", "Model:Cayman", "Color:Black"]
    into comma-separated pipe-delimited paths that Lightroom displays as expandable trees.

    IMPORTANT: Include ALL levels of the hierarchy (root, parent, and leaf nodes)
    so Lightroom recognizes the parent-child relationships.

    Format: AI Keywords, AI Keywords|Make, AI Keywords|Make|Porsche, AI Keywords|Color, AI Keywords|Color|Black

    Args:
        keywords: List of keywords in "Category:Value" format

    Returns:
        Comma-separated all-levels hierarchical paths for HierarchicalSubject field
    """
    hierarchical_paths = set()

    # Always include the root level
    hierarchical_paths.add('AI Keywords')

    # For each keyword, add all levels of the hierarchy
    for keyword in keywords:
        if ':' not in keyword:
            continue

        category, value = keyword.split(':', 1)

        # Add parent level (category)
        hierarchical_paths.add(f'AI Keywords|{category}')

        # Add leaf level (complete path)
        hierarchical_paths.add(f'AI Keywords|{category}|{value}')

    # Return as comma-separated string, sorted for consistency
    return ', '.join(sorted(hierarchical_paths))


def read_existing_keywords(file_path: Path) -> list[str]:
    """
    Read existing keywords from a file using exiftool.

    Args:
        file_path: Path to image or XMP file

    Returns:
        List of existing keywords, empty list if file doesn't exist or has none
    """
    if not file_path.exists():
        return []

    if not EXIFTOOL_PATH:
        logger.warning("exiftool not found, cannot read keywords")
        return []

    try:
        result = subprocess.run(
            [EXIFTOOL_PATH, '-Subject', '-s', '-s', '-s', str(file_path)],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            # Keywords are comma-separated
            keywords = [kw.strip() for kw in result.stdout.strip().split(',')]
            return [kw for kw in keywords if kw]  # Filter empty strings

        return []

    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout reading keywords from {file_path}")
        return []
    except Exception as e:
        logger.warning(f"Error reading keywords from {file_path}: {e}")
        return []


def write_xmp_keywords(
    target_path: Path,
    keywords: list[str],
    source_image: Optional[Path] = None,
    merge: bool = True
) -> bool:
    """
    Write keywords using exiftool in hierarchical format for Lightroom.

    Writes to both:
    - Subject field (flat): Make:Porsche, Model:911, Color:Blue
    - HierarchicalSubject field (hierarchical): AI Keywords|Make|Porsche, AI Keywords|Model|911, AI Keywords|Color|Blue

    Lightroom displays the HierarchicalSubject as an expandable tree:
        ▼ AI Keywords
          ▼ Make
            Porsche
          ▼ Model
            911
          ▼ Color
            Blue

    For RAW files, target_path should be the XMP sidecar.
    For JPG/TIFF, target_path is the image itself.

    Args:
        target_path: Path to write keywords to (XMP sidecar or image file)
        keywords: List of keywords to write (format: "Category:Value")
        source_image: Original image (used to create XMP sidecar if needed)
        merge: If True, add to existing keywords; if False, replace

    Returns:
        True if successful, False otherwise
    """
    if not EXIFTOOL_PATH:
        logger.error("exiftool not found, cannot write keywords")
        return False

    if not keywords:
        logger.debug("No keywords to write")
        return True

    try:
        # Build hierarchical keyword paths for Lightroom
        hierarchical_keywords = build_hierarchical_keywords(keywords)

        if not hierarchical_keywords:
            logger.debug("No valid keywords to write")
            return True

        # Build exiftool command
        cmd = [EXIFTOOL_PATH, '-overwrite_original']

        # If writing to XMP sidecar that doesn't exist, create from source image
        if target_path.suffix.lower() == '.xmp' and not target_path.exists():
            if source_image and source_image.exists():
                # Create XMP sidecar from source image metadata
                create_cmd = [EXIFTOOL_PATH, '-o', str(target_path), str(source_image)]
                subprocess.run(create_cmd, capture_output=True, timeout=30)

        # Write hierarchical keywords using pipe-separated paths
        # Lightroom reads Subject field and displays pipe-separated paths as expandable trees
        if merge:
            # Add hierarchical paths to both Subject and HierarchicalSubject
            # Subject field: use pipe-separated paths that Lightroom can parse as hierarchy
            for path in hierarchical_keywords.split(', '):
                cmd.append(f'-Subject+={path}')
            # HierarchicalSubject field: for compatibility with other apps
            for path in hierarchical_keywords.split(', '):
                cmd.append(f'-XMP-lr:HierarchicalSubject+={path}')
        else:
            # Replace all keywords with hierarchical structure
            # Clear old Subject keywords first
            cmd.append('-Subject=')
            # Write new hierarchical keywords to Subject with pipe separators
            for path in hierarchical_keywords.split(', '):
                cmd.append(f'-Subject+={path}')
            # Also write to HierarchicalSubject for compatibility
            for path in hierarchical_keywords.split(', '):
                cmd.append(f'-XMP-lr:HierarchicalSubject+={path}')

        cmd.append(str(target_path))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            logger.debug(f"Wrote keywords (flat and hierarchical) to {target_path}")
            return True
        else:
            logger.error(f"exiftool error: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout writing keywords to {target_path}")
        return False
    except Exception as e:
        logger.error(f"Failed to write keywords to {target_path}: {e}")
        return False


def validate_keyword_format(keyword: str) -> bool:
    """
    Validate that a keyword follows our prefix format.

    Expected formats:
    - Make:Porsche
    - Model:CaymanGT4
    - Color:Blue
    - Class:SPB
    - Num:73
    - Num:173?  (uncertain)
    """
    valid_prefixes = ['Make:', 'Model:', 'Color:', 'Class:', 'Num:']
    return any(keyword.startswith(prefix) for prefix in valid_prefixes)


def keywords_to_dict(keywords: list[str]) -> dict:
    """
    Convert keyword list to structured dictionary.

    Useful for analysis and reporting.
    """
    result = {
        'make': [],
        'model': [],
        'color': [],
        'class': [],
        'num': [],
        'num_uncertain': [],
        'other': [],
    }

    for kw in keywords:
        if kw.startswith('Make:'):
            result['make'].append(kw[5:])
        elif kw.startswith('Model:'):
            result['model'].append(kw[6:])
        elif kw.startswith('Color:'):
            result['color'].append(kw[6:])
        elif kw.startswith('Class:'):
            result['class'].append(kw[6:])
        elif kw.startswith('Num:'):
            num = kw[4:]
            if num.endswith('?'):
                result['num_uncertain'].append(num[:-1])
            else:
                result['num'].append(num)
        else:
            result['other'].append(kw)

    return result


# Self-test
if __name__ == '__main__':
    print(f"exiftool available: {check_exiftool()}")
    print(f"exiftool path: {EXIFTOOL_PATH}")

    if check_exiftool():
        print("\nTesting with a sample file...")
        # Would need a real image file to test properly
        print("Run with an actual image to test keyword writing")
    else:
        print("\nWARNING: exiftool not found. Install with:")
        print("  macOS: brew install exiftool")
        print("  Linux: apt install libimage-exiftool-perl")
