"""
Progress tracker for resumable image processing.

Tracks which images have been processed to enable:
- Resuming interrupted runs
- Avoiding re-processing
- Reporting on progress
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import hashlib

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Track processing progress for resumable batch jobs.

    Stores progress in a JSON file alongside the images being processed.
    Uses file paths and modification times to detect changes.
    """

    def __init__(self, progress_file: Path):
        """
        Initialize tracker with path to progress file.

        Args:
            progress_file: Path to JSON file for storing progress
        """
        self.progress_file = Path(progress_file)
        self.data = self._load()

    def _load(self) -> dict:
        """Load progress data from file."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded progress: {len(data.get('processed', {}))} images")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load progress file: {e}")

        return {
            'version': 1,
            'created': datetime.now().isoformat(),
            'processed': {},
            'failed': {},
            'stats': {
                'total_processed': 0,
                'total_failed': 0,
                'total_time': 0,
            }
        }

    def _save(self):
        """Save progress data to file."""
        try:
            self.data['updated'] = datetime.now().isoformat()
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.progress_file, 'w') as f:
                json.dump(self.data, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Failed to save progress: {e}")

    def _get_file_key(self, image_path: Path) -> str:
        """
        Get a unique key for an image file.

        Uses the filename (not full path) to allow moving directories.
        """
        return image_path.name

    def _get_file_signature(self, image_path: Path) -> str:
        """
        Get a signature for detecting file changes.

        Uses size and mtime rather than content hash for speed.
        """
        try:
            stat = image_path.stat()
            return f"{stat.st_size}:{stat.st_mtime}"
        except OSError:
            return ""

    def is_processed(self, image_path: Path, check_signature: bool = True) -> bool:
        """
        Check if an image has been processed.

        Args:
            image_path: Path to check
            check_signature: If True, also verify file hasn't changed

        Returns:
            True if already processed (and unchanged if check_signature)
        """
        key = self._get_file_key(image_path)
        entry = self.data['processed'].get(key)

        if not entry:
            return False

        if check_signature:
            current_sig = self._get_file_signature(image_path)
            if entry.get('signature') != current_sig:
                logger.debug(f"File changed since processing: {key}")
                return False

        return True

    def mark_processed(
        self,
        image_path: Path,
        keywords: list[str],
        inference_time: float = 0,
        metadata: dict = None
    ):
        """
        Mark an image as successfully processed.

        Args:
            image_path: Path to the processed image
            keywords: Keywords that were extracted
            inference_time: Time taken for inference
            metadata: Optional additional metadata to store
        """
        key = self._get_file_key(image_path)
        self.data['processed'][key] = {
            'path': str(image_path),
            'signature': self._get_file_signature(image_path),
            'processed_at': datetime.now().isoformat(),
            'keywords': keywords,
            'inference_time': inference_time,
            'metadata': metadata or {},
        }

        # Update stats
        self.data['stats']['total_processed'] += 1
        self.data['stats']['total_time'] += inference_time

        # Remove from failed if it was there
        if key in self.data['failed']:
            del self.data['failed'][key]
            self.data['stats']['total_failed'] -= 1

        self._save()

    def mark_failed(self, image_path: Path, error: str):
        """
        Mark an image as failed processing.

        Args:
            image_path: Path to the failed image
            error: Error message/description
        """
        key = self._get_file_key(image_path)
        self.data['failed'][key] = {
            'path': str(image_path),
            'failed_at': datetime.now().isoformat(),
            'error': error,
            'attempts': self.data['failed'].get(key, {}).get('attempts', 0) + 1,
        }
        self.data['stats']['total_failed'] += 1
        self._save()

    def get_failed(self) -> list[dict]:
        """Get list of failed images."""
        return list(self.data['failed'].values())

    def reset(self):
        """Reset all progress tracking."""
        self.data = {
            'version': 1,
            'created': datetime.now().isoformat(),
            'processed': {},
            'failed': {},
            'stats': {
                'total_processed': 0,
                'total_failed': 0,
                'total_time': 0,
            }
        }
        self._save()
        logger.info("Progress tracking reset")

    def get_stats(self) -> dict:
        """Get processing statistics."""
        stats = self.data['stats'].copy()
        stats['processed_count'] = len(self.data['processed'])
        stats['failed_count'] = len(self.data['failed'])

        if stats['total_processed'] > 0:
            stats['avg_time'] = stats['total_time'] / stats['total_processed']
        else:
            stats['avg_time'] = 0

        return stats

    def get_processed_keywords(self) -> dict[str, list[str]]:
        """
        Get all extracted keywords grouped by image.

        Returns:
            Dict mapping image names to their keywords
        """
        return {
            key: entry['keywords']
            for key, entry in self.data['processed'].items()
        }

    def generate_report(self) -> str:
        """Generate a human-readable progress report."""
        stats = self.get_stats()

        lines = [
            "=" * 50,
            "Processing Progress Report",
            "=" * 50,
            f"Processed: {stats['processed_count']} images",
            f"Failed: {stats['failed_count']} images",
            f"Total time: {stats['total_time']:.1f} seconds",
            f"Average time per image: {stats['avg_time']:.1f} seconds",
        ]

        if self.data['failed']:
            lines.append("\nFailed images:")
            for key, entry in self.data['failed'].items():
                lines.append(f"  - {key}: {entry['error']}")

        return '\n'.join(lines)


class BatchProgress:
    """
    Track progress within a single batch run.

    Provides real-time progress updates without persisting to disk.
    """

    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.start_time = datetime.now()
        self.times = []

    def update(self, success: bool, inference_time: float = 0):
        """Update progress after processing an image."""
        if success:
            self.completed += 1
        else:
            self.failed += 1
        self.times.append(inference_time)

    @property
    def remaining(self) -> int:
        return self.total - self.completed - self.failed

    @property
    def elapsed(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def avg_time(self) -> float:
        return sum(self.times) / len(self.times) if self.times else 0

    @property
    def eta_seconds(self) -> float:
        if not self.times:
            return 0
        return self.remaining * self.avg_time

    def format_eta(self) -> str:
        """Format ETA as human-readable string."""
        seconds = self.eta_seconds
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.0f}m"
        else:
            hours = seconds / 3600
            mins = (seconds % 3600) / 60
            return f"{hours:.0f}h {mins:.0f}m"

    def progress_line(self) -> str:
        """Generate a single-line progress update."""
        pct = (self.completed + self.failed) / self.total * 100 if self.total else 0
        return (
            f"[{self.completed + self.failed}/{self.total}] "
            f"{pct:.1f}% complete | "
            f"{self.avg_time:.1f}s/img | "
            f"ETA: {self.format_eta()}"
        )
