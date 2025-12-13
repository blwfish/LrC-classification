"""
Vision inference wrapper for local LLM backends.

Supports:
- Ollama (recommended, uses llama.cpp internally)
- Direct llama.cpp server (advanced)

The default backend is Ollama, which provides the easiest setup experience
and handles model management automatically.
"""

import base64
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# Detect available image conversion tools
MAGICK_PATH = shutil.which('magick') or shutil.which('convert')  # ImageMagick 7 or 6
SIPS_PATH = shutil.which('sips')  # macOS built-in


class LlamaVisionInference:
    """
    Vision inference using Ollama or llama.cpp server.

    Ollama is the recommended backend as it:
    - Handles model downloading/management
    - Provides consistent API across platforms
    - Uses llama.cpp internally for Metal/CUDA acceleration
    """

    # Default vision models in order of preference
    # Qwen2.5-VL recommended for best OCR/number detection accuracy
    DEFAULT_MODELS = [
        'qwen2.5vl:7b',  # Best accuracy for text/number OCR
        'minicpm-v',     # Good alternative, fast
        'llava:7b',      # Fallback - has hallucination issues with numbers
        'llava:13b',     # Fallback
        'llava',         # Latest default
    ]

    def __init__(
        self,
        server_url: str = 'http://localhost:11434',
        model: Optional[str] = None,
        timeout: int = 300  # 5 minutes for slow inference
    ):
        self.server_url = server_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self._available_model = None

    def check_connection(self) -> bool:
        """Check if the Ollama server is running and accessible."""
        try:
            req = urllib.request.Request(f"{self.server_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception as e:
            logger.debug(f"Connection check failed: {e}")
            return False

    def get_available_model(self) -> Optional[str]:
        """Find an available vision model on the server."""
        if self._available_model:
            return self._available_model

        # If user specified a model, use that
        if self.model:
            self._available_model = self.model
            return self.model

        try:
            req = urllib.request.Request(f"{self.server_url}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read())
                available = {m['name'] for m in data.get('models', [])}

                # Check for vision models
                for model in self.DEFAULT_MODELS:
                    if model in available:
                        self._available_model = model
                        logger.info(f"Using vision model: {model}")
                        return model

                    # Also check without tag
                    base_model = model.split(':')[0]
                    matching = [m for m in available if m.startswith(base_model)]
                    if matching:
                        self._available_model = matching[0]
                        logger.info(f"Using vision model: {matching[0]}")
                        return matching[0]

                logger.warning(f"No vision model found. Available: {available}")
                return None

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return None

    def ensure_model_available(self) -> bool:
        """Ensure a vision model is available, pulling if necessary."""
        model = self.get_available_model()
        if model:
            return True

        # Try to pull the default model
        model_to_pull = self.model or self.DEFAULT_MODELS[0]
        logger.info(f"Vision model not found. Pulling {model_to_pull}...")

        try:
            data = json.dumps({'name': model_to_pull}).encode('utf-8')
            req = urllib.request.Request(
                f"{self.server_url}/api/pull",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=3600) as response:  # 1 hour timeout for download
                # Stream the response to show progress
                for line in response:
                    try:
                        status = json.loads(line)
                        if 'status' in status:
                            logger.info(f"  {status['status']}")
                    except json.JSONDecodeError:
                        pass

            self._available_model = model_to_pull
            return True

        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False

    # RAW file extensions that have embedded preview JPGs
    RAW_EXTENSIONS = {'.nef', '.cr2', '.cr3', '.arw', '.raf', '.orf', '.rw2', '.dng', '.raw'}

    # Extensions that need conversion/resize (not already small JPEGs)
    NEEDS_PROCESSING = {'.tif', '.tiff', '.psd', '.png', '.bmp'}

    # Target size for normalized images (longest edge)
    # 2500px provides good detail for text/number recognition while keeping file size reasonable
    NORMALIZE_SIZE = 2500

    # Track temp files for cleanup
    _temp_files: list[Path] = []

    def _encode_image(self, image_path: Path) -> str:
        """
        Encode image to base64 for API request.

        Normalizes all input to a consistent format:
        - RAW files: extract embedded preview JPEG
        - Large TIF/PSD/PNG: resize to NORMALIZE_SIZE and convert to JPEG
        - Small JPEGs: use as-is
        """
        suffix = image_path.suffix.lower()

        # For RAW files, extract the embedded preview JPG
        if suffix in self.RAW_EXTENSIONS:
            preview_data = self._extract_raw_preview(image_path)
            if preview_data:
                return base64.b64encode(preview_data).decode('utf-8')
            logger.warning(f"Could not extract preview from {image_path.name}, will try conversion")

        # For TIF/PSD/PNG or failed RAW extraction, normalize via conversion
        if suffix in self.NEEDS_PROCESSING or suffix in self.RAW_EXTENSIONS:
            normalized_data = self._normalize_image(image_path)
            if normalized_data:
                return base64.b64encode(normalized_data).decode('utf-8')
            logger.warning(f"Could not normalize {image_path.name}, using original")

        # For JPEGs or fallback, check size and possibly resize
        # If file is large (>2MB), try to resize it
        file_size = image_path.stat().st_size
        if file_size > 2 * 1024 * 1024:  # 2MB threshold
            normalized_data = self._normalize_image(image_path)
            if normalized_data:
                return base64.b64encode(normalized_data).decode('utf-8')

        # Use original file
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _extract_raw_preview(self, image_path: Path) -> Optional[bytes]:
        """
        Extract and normalize embedded preview from RAW file.

        Strategy: Extract the highest quality embedded JPEG and resize to
        NORMALIZE_SIZE for consistent input to the vision model.

        Priority order:
        1. JpgFromRaw (full res) -> resize to NORMALIZE_SIZE (best quality)
        2. OtherImage (~1620px) -> use as-is or upscale slightly
        3. PreviewImage (~640px) -> last resort, low quality

        Uses ImageMagick pipe for efficient extract+resize in one pass.
        """
        # Try JpgFromRaw first with resize (best quality source)
        if MAGICK_PATH:
            try:
                # Pipe: exiftool extracts -> ImageMagick resizes
                fd, temp_path = tempfile.mkstemp(suffix='.jpg')
                os.close(fd)

                # Extract full-res JPEG and resize in one pipeline
                extract = subprocess.Popen(
                    ['exiftool', '-JpgFromRaw', '-b', str(image_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                resize = subprocess.run(
                    [MAGICK_PATH, '-', '-resize', f'{self.NORMALIZE_SIZE}x{self.NORMALIZE_SIZE}',
                     '-quality', '85', temp_path],
                    stdin=extract.stdout,
                    capture_output=True,
                    timeout=30
                )
                extract.wait()

                if resize.returncode == 0 and os.path.exists(temp_path):
                    with open(temp_path, 'rb') as f:
                        data = f.read()
                    os.unlink(temp_path)
                    if len(data) > 10000:
                        logger.debug(f"Extracted and resized JpgFromRaw to {len(data)} bytes from {image_path.name}")
                        return data

                if os.path.exists(temp_path):
                    os.unlink(temp_path)

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout extracting JpgFromRaw from {image_path.name}")
            except Exception as e:
                logger.debug(f"JpgFromRaw extraction failed for {image_path.name}: {e}")

        # Fall back to OtherImage or PreviewImage (no resize needed for OtherImage)
        for tag in ['-OtherImage', '-PreviewImage']:
            try:
                result = subprocess.run(
                    ['exiftool', tag, '-b', str(image_path)],
                    capture_output=True,
                    timeout=30
                )
                if result.returncode == 0 and result.stdout and len(result.stdout) > 10000:
                    logger.debug(f"Extracted {len(result.stdout)} byte preview ({tag}) from {image_path.name}")
                    return result.stdout
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout extracting {tag} from {image_path.name}")
            except FileNotFoundError:
                logger.warning("exiftool not found, cannot extract RAW preview")
                return None
            except Exception as e:
                logger.warning(f"Failed to extract {tag} from {image_path.name}: {e}")

        return None

    def _normalize_image(self, image_path: Path) -> Optional[bytes]:
        """
        Normalize image to a consistent size and format for the vision model.

        Resizes to NORMALIZE_SIZE (longest edge) and converts to JPEG.
        Uses ImageMagick if available, falls back to sips on macOS.
        """
        # Try ImageMagick first (cross-platform)
        if MAGICK_PATH:
            return self._normalize_with_imagemagick(image_path)

        # Fall back to sips on macOS
        if SIPS_PATH:
            return self._normalize_with_sips(image_path)

        logger.debug("No image conversion tool available (install ImageMagick)")
        return None

    def _normalize_with_imagemagick(self, image_path: Path) -> Optional[bytes]:
        """Resize and convert image using ImageMagick."""
        try:
            # Create temp file for output
            fd, temp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(fd)

            # ImageMagick command: resize to fit within NxN, convert to JPEG
            result = subprocess.run(
                [MAGICK_PATH, str(image_path),
                 '-resize', f'{self.NORMALIZE_SIZE}x{self.NORMALIZE_SIZE}>',
                 '-quality', '85',
                 temp_path],
                capture_output=True,
                timeout=60
            )

            if result.returncode == 0 and os.path.exists(temp_path):
                with open(temp_path, 'rb') as f:
                    data = f.read()
                os.unlink(temp_path)
                logger.debug(f"Normalized {image_path.name} to {len(data)} bytes via ImageMagick")
                return data

            # Cleanup on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout normalizing {image_path.name} with ImageMagick")
        except Exception as e:
            logger.warning(f"Failed to normalize {image_path.name} with ImageMagick: {e}")
        return None

    def _normalize_with_sips(self, image_path: Path) -> Optional[bytes]:
        """Resize and convert image using macOS sips."""
        try:
            # Create temp file for output
            fd, temp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(fd)

            # sips command: resample to max dimension, output as JPEG
            # sips works in-place, so we copy first then modify
            subprocess.run(
                ['cp', str(image_path), temp_path],
                capture_output=True,
                timeout=30
            )

            result = subprocess.run(
                [SIPS_PATH, '-Z', str(self.NORMALIZE_SIZE),
                 '-s', 'format', 'jpeg',
                 '-s', 'formatOptions', '85',
                 temp_path,
                 '--out', temp_path],
                capture_output=True,
                timeout=60
            )

            if result.returncode == 0 and os.path.exists(temp_path):
                with open(temp_path, 'rb') as f:
                    data = f.read()
                os.unlink(temp_path)
                logger.debug(f"Normalized {image_path.name} to {len(data)} bytes via sips")
                return data

            # Cleanup on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout normalizing {image_path.name} with sips")
        except Exception as e:
            logger.warning(f"Failed to normalize {image_path.name} with sips: {e}")
        return None

    def analyze_image(self, image_path: Path, prompt: str) -> str:
        """
        Analyze an image using the vision model.

        Args:
            image_path: Path to the image file
            prompt: The analysis prompt

        Returns:
            The model's text response
        """
        model = self.get_available_model()
        if not model:
            if not self.ensure_model_available():
                raise RuntimeError("No vision model available")
            model = self.get_available_model()

        # Encode and normalize the image
        image_data = self._encode_image(image_path)

        # Build request
        payload = {
            'model': model,
            'prompt': prompt,
            'images': [image_data],
            'stream': False,
            'options': {
                'temperature': 0.1,  # Low temperature for consistent outputs
                'num_predict': 500,  # Limit response length
            }
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{self.server_url}/api/generate",
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read())
                return result.get('response', '')

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='ignore')
            logger.error(f"HTTP error {e.code}: {error_body}")
            raise RuntimeError(f"Inference failed: HTTP {e.code}")

        except urllib.error.URLError as e:
            raise RuntimeError(f"Connection failed: {e.reason}")

    def analyze_batch(self, images: list[Path], prompt: str) -> list[str]:
        """
        Analyze multiple images with the same prompt.

        Note: Currently processes sequentially. Ollama doesn't support
        true batch inference, but this provides a consistent interface
        for future optimization.
        """
        results = []
        for image_path in images:
            try:
                result = self.analyze_image(image_path, prompt)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze {image_path}: {e}")
                results.append('')
        return results


class LlamaCppServerInference:
    """
    Alternative inference using direct llama.cpp server.

    This is for advanced users who want more control over the inference
    parameters or are running a custom llama.cpp setup.

    Requires: llama-server running with a multimodal model
    """

    def __init__(
        self,
        server_url: str = 'http://localhost:8080',
        timeout: int = 300
    ):
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout

    def check_connection(self) -> bool:
        """Check if llama.cpp server is running."""
        try:
            req = urllib.request.Request(f"{self.server_url}/health")
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    def analyze_image(self, image_path: Path, prompt: str) -> str:
        """Analyze image using llama.cpp server's /completion endpoint."""
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        payload = {
            'prompt': f"[img-1]\n{prompt}",
            'image_data': [{'data': image_data, 'id': 1}],
            'temperature': 0.1,
            'n_predict': 500,
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{self.server_url}/completion",
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            result = json.loads(response.read())
            return result.get('content', '')


def check_ollama_installed() -> bool:
    """Check if Ollama is installed on the system."""
    try:
        result = subprocess.run(
            ['ollama', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_llamacpp_installed() -> bool:
    """Check if llama.cpp is installed on the system."""
    try:
        result = subprocess.run(
            ['llama-server', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
