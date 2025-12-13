#!/bin/bash
#
# Racing Tagger Setup Script
# Installs dependencies and downloads vision model for local inference
#

set -e

echo "========================================"
echo "Racing Tagger Setup"
echo "========================================"
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
fi

echo "Detected OS: $OS"
echo

# Check Python
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    echo "Please install Python 3.10+ and try again"
    exit 1
fi

# Check Ollama
echo
echo "Checking Ollama..."
if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>&1 || echo "unknown")
    echo -e "${GREEN}✓ Ollama found${NC}"
else
    echo -e "${YELLOW}! Ollama not found${NC}"
    echo
    echo "Ollama is required for local vision model inference."
    echo

    if [[ "$OS" == "macos" ]]; then
        echo "Install options for macOS:"
        echo "  1. Download from: https://ollama.ai/download"
        echo "  2. Or via Homebrew: brew install ollama"
    elif [[ "$OS" == "linux" ]]; then
        echo "Install for Linux:"
        echo "  curl -fsSL https://ollama.ai/install.sh | sh"
    else
        echo "Download Ollama from: https://ollama.ai/download"
    fi
    echo
    read -p "Would you like to continue without Ollama? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Ollama is running
echo
echo "Checking if Ollama server is running..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollama server is running${NC}"
    OLLAMA_RUNNING=true
else
    echo -e "${YELLOW}! Ollama server is not running${NC}"
    OLLAMA_RUNNING=false

    if command -v ollama &> /dev/null; then
        echo
        read -p "Would you like to start Ollama now? (Y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "Starting Ollama server in background..."
            ollama serve > /dev/null 2>&1 &
            sleep 3

            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Ollama server started${NC}"
                OLLAMA_RUNNING=true
            else
                echo -e "${RED}Failed to start Ollama${NC}"
            fi
        fi
    fi
fi

# Check for vision model
echo
echo "Checking for vision model..."
if [[ "$OLLAMA_RUNNING" == true ]]; then
    MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys, json; data=json.load(sys.stdin); print(' '.join(m['name'] for m in data.get('models', [])))" 2>/dev/null || echo "")

    HAS_LLAVA=false
    for model in llava llava:7b llava:13b llava:34b llava-llama3 llava:latest; do
        if [[ " $MODELS " =~ " $model " ]]; then
            echo -e "${GREEN}✓ Vision model found: $model${NC}"
            HAS_LLAVA=true
            break
        fi
    done

    if [[ "$HAS_LLAVA" == false ]]; then
        echo -e "${YELLOW}! No vision model found${NC}"
        echo
        echo "Available vision models:"
        echo "  - llava:7b   (4.7GB, fastest, good for testing)"
        echo "  - llava:13b  (8GB, better accuracy)"
        echo "  - llava:34b  (20GB, best accuracy, slower)"
        echo
        read -p "Would you like to download llava:7b now? (Y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "Downloading llava:7b (this may take a while)..."
            ollama pull llava:7b
            echo -e "${GREEN}✓ Model downloaded${NC}"
        fi
    fi
else
    echo -e "${YELLOW}! Cannot check models - Ollama not running${NC}"
fi

# Check GPU acceleration
echo
echo "Checking hardware acceleration..."
if [[ "$OS" == "macos" ]]; then
    # Check for Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        echo -e "${GREEN}✓ Apple Silicon detected - Metal acceleration available${NC}"
    else
        echo -e "${YELLOW}! Intel Mac detected - CPU inference only${NC}"
    fi
elif [[ "$OS" == "linux" ]]; then
    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
        echo -e "${GREEN}✓ NVIDIA GPU detected: $GPU_INFO${NC}"
    else
        echo -e "${YELLOW}! No NVIDIA GPU detected - CPU inference only${NC}"
    fi
fi

# Verify the tool
echo
echo "Verifying Racing Tagger installation..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/racing_tagger.py" ]]; then
    echo -e "${GREEN}✓ racing_tagger.py found${NC}"
else
    echo -e "${RED}✗ racing_tagger.py not found${NC}"
    exit 1
fi

# Test Python imports
echo "Testing Python imports..."
cd "$SCRIPT_DIR"
python3 -c "
import sys
try:
    from llama_inference import LlamaVisionInference
    from xmp_writer import write_xmp_keywords
    from prompts import get_prompt
    from progress_tracker import ProgressTracker
    print('✓ All modules imported successfully')
except ImportError as e:
    print(f'✗ Import error: {e}')
    sys.exit(1)
"

# Create convenience symlink or alias
echo
echo "Setup complete!"
echo
echo "========================================"
echo "Quick Start"
echo "========================================"
echo
echo "1. Make sure Ollama is running:"
echo "   ollama serve"
echo
echo "2. Process images:"
echo "   python3 $SCRIPT_DIR/racing_tagger.py /path/to/images"
echo
echo "3. For help:"
echo "   python3 $SCRIPT_DIR/racing_tagger.py --help"
echo
echo "Example with options:"
echo "   python3 $SCRIPT_DIR/racing_tagger.py /path/to/images --fuzzy-numbers --verbose"
echo
