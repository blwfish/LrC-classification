"""
Sequence Detection and Sharpness Scoring for Racing Photography

Detects pan shot sequences from consecutive frames based on capture timestamps,
scores each frame for sharpness using Laplacian variance, and marks the best
frame in each sequence with keywords for Lightroom filtering.
"""

import csv
import io
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Check for required tools
EXIFTOOL_PATH = shutil.which('exiftool')

# RAW file extensions (need preview extraction for sharpness scoring)
RAW_EXTENSIONS = {'.nef', '.cr2', '.cr3', '.arw', '.raf', '.orf', '.rw2', '.dng', '.raw'}


@dataclass
class Sequence:
    """Represents a sequence of consecutive frames."""
    sequence_id: str                          # e.g., "SEQ_2024-12-22_14-35-26"
    frames: List[Path] = field(default_factory=list)  # Sorted by timestamp
    timestamps: List[datetime] = field(default_factory=list)
    sharpness_scores: List[float] = field(default_factory=list)
    best_frame_idx: int = 0

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def best_frame_name(self) -> str:
        if self.frames:
            return self.frames[self.best_frame_idx].name
        return ""

    @property
    def best_frame_path(self) -> Optional[Path]:
        if self.frames:
            return self.frames[self.best_frame_idx]
        return None


def generate_sequence_id(first_frame_timestamp: datetime) -> str:
    """Generate unique, sortable sequence ID from first frame's timestamp."""
    return f"SEQ_{first_frame_timestamp.strftime('%Y-%m-%d_%H-%M-%S')}"


class SequenceDetector:
    """
    Detects sequences of consecutive frames based on capture timestamps.

    Uses exiftool to batch-read DateTimeOriginal and SubSecTimeOriginal
    from image EXIF data, then groups images where the time delta between
    consecutive frames is within the specified threshold.
    """

    def __init__(self):
        if not EXIFTOOL_PATH:
            raise RuntimeError("exiftool not found. Install with: brew install exiftool")

    def read_timestamps_batch(self, images: List[Path]) -> Dict[Path, datetime]:
        """
        Batch read capture timestamps from all images using exiftool CSV output.

        Returns dict mapping image path to datetime (with subsecond precision if available).
        Images with missing/invalid timestamps are omitted from the result.
        """
        if not images:
            return {}

        timestamps = {}

        # Use exiftool with CSV output for efficiency
        # Request DateTimeOriginal and SubSecTimeOriginal
        cmd = [
            EXIFTOOL_PATH,
            '-csv',
            '-DateTimeOriginal',
            '-SubSecTimeOriginal',
            '-d', '%Y:%m:%d %H:%M:%S',  # Date format
        ] + [str(p) for p in images]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minutes for large batches
            )

            if result.returncode != 0:
                logger.warning(f"exiftool returned non-zero: {result.stderr}")

            # Parse CSV output
            reader = csv.DictReader(io.StringIO(result.stdout))
            for row in reader:
                source_file = row.get('SourceFile', '')
                date_str = row.get('DateTimeOriginal', '')
                subsec = row.get('SubSecTimeOriginal', '')

                if not source_file or not date_str:
                    continue

                try:
                    # Parse base datetime
                    dt = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')

                    # Add subsecond precision if available
                    if subsec:
                        # SubSecTimeOriginal is typically 2-3 digits (hundredths/thousandths)
                        # Normalize to microseconds
                        subsec = subsec.strip()
                        if subsec.isdigit():
                            # Pad or truncate to 6 digits for microseconds
                            subsec_padded = subsec.ljust(6, '0')[:6]
                            dt = dt.replace(microsecond=int(subsec_padded))

                    # Match path from our input list
                    source_path = Path(source_file)
                    for img in images:
                        if img.name == source_path.name or str(img) == source_file:
                            timestamps[img] = dt
                            break

                except ValueError as e:
                    logger.debug(f"Failed to parse timestamp for {source_file}: {e}")
                    continue

        except subprocess.TimeoutExpired:
            logger.error("Timeout reading timestamps from images")
        except Exception as e:
            logger.error(f"Failed to read timestamps: {e}")

        logger.debug(f"Read timestamps for {len(timestamps)}/{len(images)} images")
        return timestamps

    def detect_sequences(
        self,
        images: List[Path],
        threshold_seconds: float = 0.5
    ) -> List[Sequence]:
        """
        Group consecutive images into sequences based on capture time.

        Args:
            images: List of image paths to analyze
            threshold_seconds: Maximum time gap between frames in a sequence

        Returns:
            List of Sequence objects (only sequences with 2+ frames)
        """
        if not images:
            return []

        # Read all timestamps
        logger.info(f"Reading timestamps from {len(images)} images...")
        timestamps = self.read_timestamps_batch(images)

        if not timestamps:
            logger.warning("No timestamps found in images")
            return []

        # Sort images by timestamp
        sorted_images = sorted(
            [(img, ts) for img, ts in timestamps.items()],
            key=lambda x: x[1]
        )

        # Group into sequences
        sequences = []
        current_group: List[Tuple[Path, datetime]] = []

        for img, ts in sorted_images:
            if not current_group:
                current_group.append((img, ts))
            else:
                # Check time delta from previous frame
                prev_ts = current_group[-1][1]
                delta = (ts - prev_ts).total_seconds()

                if delta <= threshold_seconds:
                    # Same sequence
                    current_group.append((img, ts))
                else:
                    # New sequence - save current if it has 2+ frames
                    if len(current_group) >= 2:
                        seq = self._create_sequence(current_group)
                        sequences.append(seq)
                    current_group = [(img, ts)]

        # Don't forget the last group
        if len(current_group) >= 2:
            seq = self._create_sequence(current_group)
            sequences.append(seq)

        # Log summary
        if sequences:
            total_frames = sum(s.frame_count for s in sequences)
            avg_frames = total_frames / len(sequences)
            logger.info(
                f"Detected {len(sequences)} sequences "
                f"({total_frames} frames, avg {avg_frames:.1f} frames/seq)"
            )
        else:
            logger.info("No sequences detected (no consecutive frames within threshold)")

        return sequences

    def _create_sequence(self, group: List[Tuple[Path, datetime]]) -> Sequence:
        """Create a Sequence object from a group of (path, timestamp) tuples."""
        frames = [img for img, _ in group]
        timestamps = [ts for _, ts in group]
        seq_id = generate_sequence_id(timestamps[0])

        return Sequence(
            sequence_id=seq_id,
            frames=frames,
            timestamps=timestamps,
            sharpness_scores=[],
            best_frame_idx=0
        )


class SharpnessScorer:
    """
    Calculates image sharpness using Laplacian variance.

    Higher variance = sharper image (more high-frequency edge content).
    Motion blur and out-of-focus images have lower variance.
    """

    def __init__(self):
        # Import cv2 here to make it optional until actually needed
        try:
            import cv2
            self.cv2 = cv2
        except ImportError:
            raise RuntimeError(
                "opencv-python required for sharpness scoring. "
                "Install with: pip install opencv-python"
            )

    def calculate_sharpness(self, image_path: Path) -> float:
        """
        Calculate Laplacian variance (sharpness metric) for an image.

        Higher values = sharper image.
        Returns 0.0 if image cannot be read.
        """
        try:
            # Handle RAW files by extracting preview
            if image_path.suffix.lower() in RAW_EXTENSIONS:
                img_data = self._extract_raw_preview(image_path)
                if img_data is None:
                    logger.warning(f"Could not extract preview from {image_path.name}")
                    return 0.0

                # Decode from bytes
                import numpy as np
                nparr = np.frombuffer(img_data, np.uint8)
                img = self.cv2.imdecode(nparr, self.cv2.IMREAD_GRAYSCALE)
            else:
                # Read directly for JPG/TIFF/PNG
                img = self.cv2.imread(str(image_path), self.cv2.IMREAD_GRAYSCALE)

            if img is None:
                logger.warning(f"Could not read image: {image_path.name}")
                return 0.0

            # Apply Laplacian edge detection
            laplacian = self.cv2.Laplacian(img, self.cv2.CV_64F)

            # Return variance (measure of edge sharpness)
            variance = laplacian.var()
            return float(variance)

        except Exception as e:
            logger.warning(f"Sharpness calculation failed for {image_path.name}: {e}")
            return 0.0

    def _extract_raw_preview(self, image_path: Path) -> Optional[bytes]:
        """
        Extract embedded JPEG preview from RAW file using exiftool.

        Priority: JpgFromRaw > PreviewImage
        """
        if not EXIFTOOL_PATH:
            return None

        # Try JpgFromRaw first (highest quality)
        for tag in ['-JpgFromRaw', '-PreviewImage']:
            try:
                result = subprocess.run(
                    [EXIFTOOL_PATH, tag, '-b', str(image_path)],
                    capture_output=True,
                    timeout=30
                )
                if result.returncode == 0 and result.stdout and len(result.stdout) > 10000:
                    return result.stdout
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout extracting {tag} from {image_path.name}")
            except Exception as e:
                logger.debug(f"Failed to extract {tag}: {e}")

        return None

    def score_sequence(self, sequence: Sequence) -> Sequence:
        """
        Score all frames in a sequence and identify the best (sharpest) frame.

        Updates sequence.sharpness_scores and sequence.best_frame_idx.
        In case of tie, first frame (by timestamp) wins.
        """
        scores = []

        for frame in sequence.frames:
            score = self.calculate_sharpness(frame)
            scores.append(score)
            logger.debug(f"  {frame.name}: sharpness={score:.2f}")

        sequence.sharpness_scores = scores

        # Find best frame (highest score; first-in-time wins ties)
        if scores:
            max_score = max(scores)
            sequence.best_frame_idx = scores.index(max_score)

            logger.debug(
                f"Sequence {sequence.sequence_id}: "
                f"best frame is {sequence.best_frame_name} "
                f"(score={max_score:.2f})"
            )

        return sequence


def print_sequence_preview(sequences: List[Sequence]):
    """Print a human-readable preview of detected sequences."""
    if not sequences:
        print("No sequences detected.")
        return

    total_frames = sum(s.frame_count for s in sequences)
    print(f"\n{'='*60}")
    print(f"SEQUENCE DETECTION PREVIEW")
    print(f"{'='*60}")
    print(f"Sequences found: {len(sequences)}")
    print(f"Total frames in sequences: {total_frames}")
    print(f"Average frames per sequence: {total_frames/len(sequences):.1f}")
    print(f"{'='*60}\n")

    for i, seq in enumerate(sequences, 1):
        print(f"Sequence {i}: {seq.sequence_id}")
        print(f"  Frames: {seq.frame_count}")
        print(f"  Time span: {seq.timestamps[0].strftime('%H:%M:%S')} - {seq.timestamps[-1].strftime('%H:%M:%S')}")

        if seq.sharpness_scores:
            print(f"  Best frame: {seq.best_frame_name} (sharpness: {seq.sharpness_scores[seq.best_frame_idx]:.2f})")
            print(f"  Sharpness range: {min(seq.sharpness_scores):.2f} - {max(seq.sharpness_scores):.2f}")

        # Show first few and last few frames
        if seq.frame_count <= 6:
            for j, frame in enumerate(seq.frames):
                marker = " [BEST]" if j == seq.best_frame_idx and seq.sharpness_scores else ""
                score = f" ({seq.sharpness_scores[j]:.2f})" if seq.sharpness_scores else ""
                print(f"    {frame.name}{score}{marker}")
        else:
            for j in range(3):
                marker = " [BEST]" if j == seq.best_frame_idx and seq.sharpness_scores else ""
                score = f" ({seq.sharpness_scores[j]:.2f})" if seq.sharpness_scores else ""
                print(f"    {seq.frames[j].name}{score}{marker}")
            print(f"    ... ({seq.frame_count - 6} more frames)")
            for j in range(seq.frame_count - 3, seq.frame_count):
                marker = " [BEST]" if j == seq.best_frame_idx and seq.sharpness_scores else ""
                score = f" ({seq.sharpness_scores[j]:.2f})" if seq.sharpness_scores else ""
                print(f"    {seq.frames[j].name}{score}{marker}")
        print()


def write_sequence_metadata(
    sequence: Sequence,
    output_dir: Optional[Path] = None,
    dry_run: bool = False
) -> bool:
    """
    Write sequence keywords to XMP for all frames in the sequence.

    - Best frame gets: Sequence:Best, Sequence:{sequence_id}
    - Other frames get: Sequence:{sequence_id}

    Args:
        sequence: The sequence to process
        output_dir: Optional output directory for XMP sidecars
        dry_run: If True, don't write anything

    Returns:
        True if successful
    """
    from xmp_writer import write_xmp_keywords, get_target_path

    if dry_run:
        logger.info(f"[DRY RUN] Would write sequence metadata for {sequence.sequence_id}")
        return True

    success = True
    seq_keyword = f"Sequence:{sequence.sequence_id}"

    for i, frame in enumerate(sequence.frames):
        keywords = [seq_keyword]

        if i == sequence.best_frame_idx:
            keywords.append("Sequence:Best")

        target_path = get_target_path(frame, output_dir)

        try:
            result = write_xmp_keywords(
                target_path,
                keywords,
                source_image=frame,
                merge=True
            )
            if not result:
                success = False
                logger.warning(f"Failed to write sequence keywords to {frame.name}")
        except Exception as e:
            success = False
            logger.error(f"Error writing sequence keywords to {frame.name}: {e}")

    return success


# Self-test
if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print("Usage: python sequence_stacking.py /path/to/images [threshold_seconds]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5

    # Find images
    supported = {'.jpg', '.jpeg', '.nef', '.cr2', '.arw', '.dng', '.tif', '.tiff'}
    if input_path.is_file():
        images = [input_path]
    else:
        images = sorted([
            p for p in input_path.iterdir()
            if p.suffix.lower() in supported
        ])

    print(f"Found {len(images)} images")

    # Detect sequences
    detector = SequenceDetector()
    sequences = detector.detect_sequences(images, threshold)

    # Score sharpness
    if sequences:
        print("\nScoring sharpness...")
        scorer = SharpnessScorer()
        for seq in sequences:
            scorer.score_sequence(seq)

    # Preview
    print_sequence_preview(sequences)
