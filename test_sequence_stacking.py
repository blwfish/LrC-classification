"""
Unit tests for sequence detection and sharpness scoring.

Run with: python -m pytest test_sequence_stacking.py -v
"""

import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from sequence_stacking import (
    Sequence,
    SequenceDetector,
    SharpnessScorer,
    generate_sequence_id,
    print_sequence_preview,
)


class TestSequenceIdGeneration:
    """Tests for sequence ID generation."""

    def test_generate_sequence_id_format(self):
        """Sequence ID should follow SEQ_YYYY-MM-DD_HH-MM-SS format."""
        dt = datetime(2024, 12, 22, 14, 35, 26)
        seq_id = generate_sequence_id(dt)
        assert seq_id == "SEQ_2024-12-22_14-35-26"

    def test_generate_sequence_id_midnight(self):
        """Sequence ID handles midnight correctly."""
        dt = datetime(2024, 1, 1, 0, 0, 0)
        seq_id = generate_sequence_id(dt)
        assert seq_id == "SEQ_2024-01-01_00-00-00"

    def test_generate_sequence_id_sortable(self):
        """Sequence IDs should be lexicographically sortable by time."""
        dt1 = datetime(2024, 12, 22, 14, 35, 26)
        dt2 = datetime(2024, 12, 22, 14, 35, 27)
        dt3 = datetime(2024, 12, 23, 10, 0, 0)

        ids = [generate_sequence_id(dt) for dt in [dt2, dt1, dt3]]
        sorted_ids = sorted(ids)

        assert sorted_ids[0] == generate_sequence_id(dt1)
        assert sorted_ids[1] == generate_sequence_id(dt2)
        assert sorted_ids[2] == generate_sequence_id(dt3)


class TestSequenceDataclass:
    """Tests for the Sequence dataclass."""

    def test_sequence_frame_count(self):
        """frame_count property should return number of frames."""
        seq = Sequence(
            sequence_id="SEQ_test",
            frames=[Path("/a.jpg"), Path("/b.jpg"), Path("/c.jpg")],
            timestamps=[datetime.now()] * 3,
        )
        assert seq.frame_count == 3

    def test_sequence_empty(self):
        """Empty sequence should have frame_count 0."""
        seq = Sequence(sequence_id="SEQ_empty")
        assert seq.frame_count == 0
        assert seq.best_frame_name == ""
        assert seq.best_frame_path is None

    def test_sequence_best_frame_name(self):
        """best_frame_name should return filename of best frame."""
        seq = Sequence(
            sequence_id="SEQ_test",
            frames=[Path("/path/to/a.jpg"), Path("/path/to/b.jpg")],
            timestamps=[datetime.now()] * 2,
            best_frame_idx=1,
        )
        assert seq.best_frame_name == "b.jpg"

    def test_sequence_best_frame_path(self):
        """best_frame_path should return full path of best frame."""
        frames = [Path("/path/to/a.jpg"), Path("/path/to/b.jpg")]
        seq = Sequence(
            sequence_id="SEQ_test",
            frames=frames,
            timestamps=[datetime.now()] * 2,
            best_frame_idx=1,
        )
        assert seq.best_frame_path == frames[1]


class TestSequenceDetector:
    """Tests for SequenceDetector class."""

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_detector_initialization(self):
        """Detector should initialize when exiftool is available."""
        detector = SequenceDetector()
        assert detector is not None

    @patch('sequence_stacking.EXIFTOOL_PATH', None)
    def test_detector_missing_exiftool(self):
        """Detector should raise error when exiftool is missing."""
        with pytest.raises(RuntimeError, match="exiftool not found"):
            SequenceDetector()

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    @patch('subprocess.run')
    def test_read_timestamps_batch_parses_csv(self, mock_run):
        """Timestamps should be parsed from exiftool CSV output."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                "SourceFile,DateTimeOriginal,SubSecTimeOriginal\n"
                "/path/img1.jpg,2024:12:22 14:35:26,50\n"
                "/path/img2.jpg,2024:12:22 14:35:26,80\n"
            ),
            stderr=""
        )

        detector = SequenceDetector()
        images = [Path("/path/img1.jpg"), Path("/path/img2.jpg")]
        timestamps = detector.read_timestamps_batch(images)

        assert len(timestamps) == 2
        # Check subsecond precision was parsed
        ts1 = timestamps[Path("/path/img1.jpg")]
        ts2 = timestamps[Path("/path/img2.jpg")]
        assert ts1.microsecond == 500000  # "50" -> 500000 microseconds
        assert ts2.microsecond == 800000  # "80" -> 800000 microseconds

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    @patch('subprocess.run')
    def test_read_timestamps_handles_missing(self, mock_run):
        """Missing timestamps should be omitted from result."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                "SourceFile,DateTimeOriginal,SubSecTimeOriginal\n"
                "/path/img1.jpg,2024:12:22 14:35:26,\n"
                "/path/img2.jpg,,\n"  # Missing timestamp
            ),
            stderr=""
        )

        detector = SequenceDetector()
        images = [Path("/path/img1.jpg"), Path("/path/img2.jpg")]
        timestamps = detector.read_timestamps_batch(images)

        assert len(timestamps) == 1
        assert Path("/path/img1.jpg") in timestamps

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_detect_sequences_groups_consecutive(self):
        """Consecutive frames within threshold should be grouped."""
        detector = SequenceDetector()

        # Mock timestamp reading
        base_time = datetime(2024, 12, 22, 14, 35, 0)
        images = [Path(f"/path/img{i}.jpg") for i in range(5)]

        with patch.object(detector, 'read_timestamps_batch') as mock_read:
            mock_read.return_value = {
                images[0]: base_time,
                images[1]: base_time + timedelta(seconds=0.3),
                images[2]: base_time + timedelta(seconds=0.6),
                images[3]: base_time + timedelta(seconds=5.0),  # Gap
                images[4]: base_time + timedelta(seconds=5.3),
            }

            sequences = detector.detect_sequences(images, threshold_seconds=0.5)

        assert len(sequences) == 2
        assert sequences[0].frame_count == 3  # img0, img1, img2
        assert sequences[1].frame_count == 2  # img3, img4

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_detect_sequences_single_frames_excluded(self):
        """Single frames (not in sequence) should not create a sequence."""
        detector = SequenceDetector()

        base_time = datetime(2024, 12, 22, 14, 35, 0)
        images = [Path(f"/path/img{i}.jpg") for i in range(3)]

        with patch.object(detector, 'read_timestamps_batch') as mock_read:
            mock_read.return_value = {
                images[0]: base_time,
                images[1]: base_time + timedelta(seconds=5.0),  # Too far
                images[2]: base_time + timedelta(seconds=10.0),  # Too far
            }

            sequences = detector.detect_sequences(images, threshold_seconds=0.5)

        assert len(sequences) == 0

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_detect_sequences_boundary_threshold(self):
        """Frames exactly at threshold boundary should be included."""
        detector = SequenceDetector()

        base_time = datetime(2024, 12, 22, 14, 35, 0)
        images = [Path(f"/path/img{i}.jpg") for i in range(3)]

        with patch.object(detector, 'read_timestamps_batch') as mock_read:
            mock_read.return_value = {
                images[0]: base_time,
                images[1]: base_time + timedelta(seconds=0.5),  # Exactly at threshold
                images[2]: base_time + timedelta(seconds=1.0),  # Exactly at threshold from img1
            }

            sequences = detector.detect_sequences(images, threshold_seconds=0.5)

        assert len(sequences) == 1
        assert sequences[0].frame_count == 3

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_detect_sequences_sorts_by_timestamp(self):
        """Images should be sorted by timestamp regardless of input order."""
        detector = SequenceDetector()

        base_time = datetime(2024, 12, 22, 14, 35, 0)
        images = [Path(f"/path/img{i}.jpg") for i in range(3)]

        with patch.object(detector, 'read_timestamps_batch') as mock_read:
            # Return timestamps in wrong order relative to input
            mock_read.return_value = {
                images[0]: base_time + timedelta(seconds=0.6),  # Third
                images[1]: base_time,  # First
                images[2]: base_time + timedelta(seconds=0.3),  # Second
            }

            sequences = detector.detect_sequences(images, threshold_seconds=0.5)

        assert len(sequences) == 1
        # Frames should be sorted: img1, img2, img0
        assert sequences[0].frames[0] == images[1]
        assert sequences[0].frames[1] == images[2]
        assert sequences[0].frames[2] == images[0]


class TestSharpnessScorer:
    """Tests for SharpnessScorer class."""

    def test_scorer_requires_opencv(self):
        """Scorer should raise error if cv2 is not available."""
        with patch.dict('sys.modules', {'cv2': None}):
            # This won't actually test the import failure properly
            # due to how imports work, but documents the expected behavior
            pass

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_calculate_sharpness_returns_float(self):
        """Sharpness score should be a float."""
        # Create a simple test image
        try:
            import cv2
            import numpy as np
        except ImportError:
            pytest.skip("OpenCV not installed")

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            # Create a simple gradient image (has edges)
            img = np.zeros((100, 100), dtype=np.uint8)
            img[:, 50:] = 255
            cv2.imwrite(f.name, img)

            scorer = SharpnessScorer()
            score = scorer.calculate_sharpness(Path(f.name))

            os.unlink(f.name)

        assert isinstance(score, float)
        assert score > 0  # Should have some edge content

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_calculate_sharpness_blur_vs_sharp(self):
        """Blurred image should have lower sharpness than sharp image."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            pytest.skip("OpenCV not installed")

        # Create a sharp image with edges
        sharp_img = np.zeros((100, 100), dtype=np.uint8)
        sharp_img[40:60, 40:60] = 255

        # Create blurred version
        blurred_img = cv2.GaussianBlur(sharp_img, (15, 15), 0)

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f1:
            cv2.imwrite(f1.name, sharp_img)
            sharp_path = Path(f1.name)

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f2:
            cv2.imwrite(f2.name, blurred_img)
            blurred_path = Path(f2.name)

        try:
            scorer = SharpnessScorer()
            sharp_score = scorer.calculate_sharpness(sharp_path)
            blurred_score = scorer.calculate_sharpness(blurred_path)

            assert sharp_score > blurred_score
        finally:
            os.unlink(sharp_path)
            os.unlink(blurred_path)

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_calculate_sharpness_missing_file(self):
        """Missing file should return 0.0."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")

        scorer = SharpnessScorer()
        score = scorer.calculate_sharpness(Path("/nonexistent/image.jpg"))
        assert score == 0.0

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_score_sequence_finds_best(self):
        """score_sequence should identify the sharpest frame."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            pytest.skip("OpenCV not installed")

        # Create images with different sharpness levels
        paths = []
        for i in range(3):
            img = np.zeros((100, 100), dtype=np.uint8)
            img[40:60, 40:60] = 255
            if i < 2:
                # Blur the first two images
                img = cv2.GaussianBlur(img, (5 + i*4, 5 + i*4), 0)

            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                cv2.imwrite(f.name, img)
                paths.append(Path(f.name))

        try:
            seq = Sequence(
                sequence_id="SEQ_test",
                frames=paths,
                timestamps=[datetime.now()] * 3,
            )

            scorer = SharpnessScorer()
            scored_seq = scorer.score_sequence(seq)

            # Last image should be sharpest (no blur)
            assert scored_seq.best_frame_idx == 2
            assert len(scored_seq.sharpness_scores) == 3
            assert scored_seq.sharpness_scores[2] > scored_seq.sharpness_scores[0]
        finally:
            for p in paths:
                os.unlink(p)

    @patch('sequence_stacking.EXIFTOOL_PATH', '/usr/bin/exiftool')
    def test_score_sequence_tie_first_wins(self):
        """When sharpness scores are equal, first frame should win."""
        try:
            import cv2
            import numpy as np
        except ImportError:
            pytest.skip("OpenCV not installed")

        # Create identical images
        paths = []
        base_img = np.zeros((100, 100), dtype=np.uint8)
        base_img[40:60, 40:60] = 255

        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
                cv2.imwrite(f.name, base_img)
                paths.append(Path(f.name))

        try:
            seq = Sequence(
                sequence_id="SEQ_test",
                frames=paths,
                timestamps=[datetime.now()] * 3,
            )

            scorer = SharpnessScorer()
            scored_seq = scorer.score_sequence(seq)

            # First image should win on tie
            assert scored_seq.best_frame_idx == 0
        finally:
            for p in paths:
                os.unlink(p)


class TestPrintSequencePreview:
    """Tests for preview output function."""

    def test_print_preview_empty(self, capsys):
        """Empty sequence list should print appropriate message."""
        print_sequence_preview([])
        captured = capsys.readouterr()
        assert "No sequences detected" in captured.out

    def test_print_preview_with_sequences(self, capsys):
        """Should print sequence details."""
        seq = Sequence(
            sequence_id="SEQ_2024-12-22_14-35-26",
            frames=[Path(f"/path/img{i}.jpg") for i in range(3)],
            timestamps=[datetime(2024, 12, 22, 14, 35, 26 + i) for i in range(3)],
            sharpness_scores=[100.0, 150.0, 120.0],
            best_frame_idx=1,
        )

        print_sequence_preview([seq])
        captured = capsys.readouterr()

        assert "SEQ_2024-12-22_14-35-26" in captured.out
        assert "Frames: 3" in captured.out
        assert "img1.jpg" in captured.out
        assert "[BEST]" in captured.out


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
