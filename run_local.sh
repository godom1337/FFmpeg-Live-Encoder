#!/bin/bash
# Local development script - runs backend and frontend locally (not in Docker)
# This uses your local FFmpeg installation with AVFoundation support for device input

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FFmpeg Live Encoder - Local Development${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS_TYPE="macos"
        echo -e "${BLUE}Detected OS:${NC} macOS"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS_TYPE="linux"
        echo -e "${BLUE}Detected OS:${NC} Linux"
    else
        OS_TYPE="unknown"
        echo -e "${YELLOW}Detected OS:${NC} Unknown ($OSTYPE)"
    fi
    echo ""
}

# Check and install dependencies for Linux
install_linux_deps() {
    echo -e "${YELLOW}Checking Linux dependencies...${NC}"

    # Use system python3
    PYTHON_CMD=python3

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: Python 3 not found${NC}"
        echo "Please install Python 3:"
        echo "  sudo apt install python3 python3-pip python3-venv"
        exit 1
    fi

    echo -e "${GREEN}Using Python: $PYTHON_CMD${NC}"
    $PYTHON_CMD --version

    # Get Python version for package names
    PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

    MISSING_DEPS=()

    if ! command -v ffmpeg &> /dev/null; then
        MISSING_DEPS+=("ffmpeg")
    fi

    if ! command -v node &> /dev/null; then
        MISSING_DEPS+=("nodejs")
    fi

    if ! command -v npm &> /dev/null; then
        MISSING_DEPS+=("npm")
    fi

    # Check for build-essential (needed for compiling some packages)
    if ! command -v gcc &> /dev/null || ! command -v make &> /dev/null; then
        MISSING_DEPS+=("build-essential")
    fi

    # Python packages - try version-specific first, fallback to generic
    if ! $PYTHON_CMD -m venv --help &> /dev/null 2>&1; then
        # Try version-specific package first
        if apt-cache show "python${PY_VERSION}-venv" &> /dev/null; then
            MISSING_DEPS+=("python${PY_VERSION}-venv")
        else
            MISSING_DEPS+=("python3-venv")
        fi
    fi

    # Check for python-dev
    if [ ! -f "/usr/include/python${PY_VERSION}/Python.h" ] 2>/dev/null; then
        if apt-cache show "python${PY_VERSION}-dev" &> /dev/null; then
            MISSING_DEPS+=("python${PY_VERSION}-dev")
        else
            MISSING_DEPS+=("python3-dev")
        fi
    fi

    # Check for pip
    if ! $PYTHON_CMD -m pip --version &> /dev/null 2>&1; then
        MISSING_DEPS+=("python3-pip")
    fi

    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo -e "${YELLOW}Installing missing dependencies: ${MISSING_DEPS[*]}${NC}"
        sudo apt update
        sudo apt install -y "${MISSING_DEPS[@]}"
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install dependencies${NC}"
            exit 1
        fi
        echo -e "${GREEN}✓ Dependencies installed${NC}"
    else
        echo -e "${GREEN}✓ All dependencies already installed${NC}"
    fi
    echo ""
}

# Show instructions for macOS dependencies
check_macos_deps() {
    echo -e "${BLUE}Checking macOS dependencies...${NC}"

    MISSING_DEPS=()
    BREW_INSTALL_CMDS=()

    if ! command -v ffmpeg &> /dev/null; then
        MISSING_DEPS+=("FFmpeg")
        BREW_INSTALL_CMDS+=("brew install ffmpeg")
    fi

    if ! command -v python3 &> /dev/null; then
        MISSING_DEPS+=("Python 3")
        BREW_INSTALL_CMDS+=("brew install python")
    fi

    if ! command -v node &> /dev/null; then
        MISSING_DEPS+=("Node.js")
        BREW_INSTALL_CMDS+=("brew install node")
    fi

    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo -e "${RED}Error: Missing dependencies: ${MISSING_DEPS[*]}${NC}"
        echo ""
        echo -e "${YELLOW}Please install the missing dependencies using Homebrew:${NC}"
        echo ""
        for cmd in "${BREW_INSTALL_CMDS[@]}"; do
            echo "  $cmd"
        done
        echo ""
        echo -e "${YELLOW}If you don't have Homebrew installed, visit: https://brew.sh${NC}"
        exit 1
    fi

    # Use system python3
    PYTHON_CMD=python3

    echo -e "${GREEN}Using Python: $PYTHON_CMD${NC}"
    $PYTHON_CMD --version
    echo -e "${GREEN}✓ All dependencies found${NC}"
    echo ""
}

# Detect OS first
detect_os

# Handle dependencies based on OS
if [ "$OS_TYPE" == "linux" ]; then
    install_linux_deps
    # PYTHON_CMD is set by install_linux_deps
elif [ "$OS_TYPE" == "macos" ]; then
    check_macos_deps
fi

# Check if FFmpeg is installed locally
echo -e "${BLUE}Checking local FFmpeg installation...${NC}"
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}Error: FFmpeg not found in PATH${NC}"
    if [ "$OS_TYPE" == "macos" ]; then
        echo "Please install FFmpeg:"
        echo "  brew install ffmpeg"
    else
        echo "Please install FFmpeg:"
        echo "  sudo apt install ffmpeg"
    fi
    exit 1
fi

# Show FFmpeg version
echo -e "${GREEN}Found FFmpeg:${NC}"
ffmpeg -version | head -3
echo ""

# Check for AVFoundation support (macOS only)
if [ "$OS_TYPE" == "macos" ]; then
    if ffmpeg -version 2>&1 | grep -q "enable-avfoundation"; then
        echo -e "${GREEN}✓ AVFoundation support detected${NC}"
    else
        echo -e "${YELLOW}⚠ AVFoundation support not explicitly shown (may still work)${NC}"
    fi
    echo ""
fi

# Check for V4L2 support (Linux only)
if [ "$OS_TYPE" == "linux" ]; then
    if ffmpeg -version 2>&1 | grep -q "enable-libv4l2"; then
        echo -e "${GREEN}✓ V4L2 (Video4Linux2) support detected${NC}"
    else
        echo -e "${YELLOW}⚠ V4L2 support not explicitly shown (may still work for device input)${NC}"
    fi
    echo ""
fi

# Check if backend directory exists
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}Error: Backend directory not found at $BACKEND_DIR${NC}"
    exit 1
fi

# Check if frontend directory exists
if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}Error: Frontend directory not found at $FRONTEND_DIR${NC}"
    exit 1
fi

# Check if Python 3.9+ is available (skip if already set by Linux deps)
if [ -z "$PYTHON_CMD" ]; then
    echo -e "${BLUE}Checking Python installation...${NC}"
    if command -v python3.12 &> /dev/null; then
        PYTHON_CMD=python3.12
    elif command -v python3.11 &> /dev/null; then
        PYTHON_CMD=python3.11
    elif command -v python3.10 &> /dev/null; then
        PYTHON_CMD=python3.10
    elif command -v python3.9 &> /dev/null; then
        PYTHON_CMD=python3.9
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
    else
        echo -e "${RED}Error: Python 3.9+ not found${NC}"
        if [ "$OS_TYPE" == "macos" ]; then
            echo "Please install Python:"
            echo "  brew install python"
        else
            echo "Please install Python:"
            echo "  sudo apt install python3 python3-pip python3-venv"
        fi
        exit 1
    fi
fi

echo -e "${GREEN}Found Python: $PYTHON_CMD${NC}"
$PYTHON_CMD --version
echo ""

# Check if Node.js is installed
echo -e "${BLUE}Checking Node.js installation...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js not found${NC}"
    if [ "$OS_TYPE" == "macos" ]; then
        echo "Please install Node.js:"
        echo "  brew install node"
    else
        echo "Please install Node.js:"
        echo "  sudo apt install nodejs npm"
    fi
    exit 1
fi

echo -e "${GREEN}Found Node.js:${NC}"
node --version
npm --version
echo ""

# Setup backend virtual environment if it doesn't exist
if [ ! -d "$BACKEND_DIR/venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    cd "$BACKEND_DIR"
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create virtual environment${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Virtual environment created${NC}"
    echo ""
fi

# Install backend dependencies
echo -e "${YELLOW}Installing backend dependencies...${NC}"
cd "$BACKEND_DIR"
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1

# Core dependencies (required)
echo -e "${BLUE}Installing core packages...${NC}"
pip install \
    fastapi==0.115.0 \
    uvicorn==0.30.6 \
    pydantic==2.9.0 \
    python-multipart==0.0.9 \
    aiosqlite==0.20.0 \
    httpx==0.27.0 \
    python-dotenv==1.0.1 \
    psutil==6.1.0 \
    websockets==12.0

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install core dependencies${NC}"
    exit 1
fi

# Performance packages (optional - uvicorn works without them)
echo -e "${BLUE}Installing performance packages (optional)...${NC}"
pip install uvloop==0.20.0 httptools==0.6.1 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠ uvloop/httptools not installed (Python 3.13 compatibility)${NC}"
    echo -e "${YELLOW}  Uvicorn will use asyncio fallback - still works fine${NC}"
fi

echo -e "${GREEN}✓ Backend dependencies installed${NC}"
echo ""

# Install frontend dependencies
echo -e "${YELLOW}Installing frontend dependencies...${NC}"
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    npm install
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install frontend dependencies${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
echo ""

# Build frontend
echo -e "${YELLOW}Building frontend...${NC}"
npm run build
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to build frontend${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Frontend built${NC}"
echo ""

# Create necessary directories
echo -e "${YELLOW}Creating output directories...${NC}"
mkdir -p "$PROJECT_ROOT/input"
mkdir -p "$PROJECT_ROOT/output/hls"
mkdir -p "$PROJECT_ROOT/output/files"
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Set output directory for local development
export OUTPUT_BASE_DIR="$PROJECT_ROOT/output"
echo -e "${BLUE}Output directory:${NC} $OUTPUT_BASE_DIR"
echo ""

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
cd "$BACKEND_DIR"
source venv/bin/activate
$PYTHON_CMD scripts/init_db.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database initialized${NC}"
else
    echo -e "${RED}Failed to initialize database${NC}"
    exit 1
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Starting Services${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Backend:${NC}  http://localhost:8000"
echo -e "${BLUE}API Docs:${NC} http://localhost:8000/docs"
echo -e "${BLUE}Frontend:${NC} http://localhost:8000"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping services...${NC}"
    kill $BACKEND_PID 2>/dev/null
    wait $BACKEND_PID 2>/dev/null
    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend in background
cd "$BACKEND_DIR/src"
source "$BACKEND_DIR/venv/bin/activate"
echo -e "${BLUE}[BACKEND]${NC} Starting backend server..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Failed to start backend${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Backend running (PID: $BACKEND_PID)${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Visit: ${BLUE}http://localhost:8000${NC}"
echo ""
echo -e "${YELLOW}Logs will appear below. Press Ctrl+C to stop.${NC}"
echo ""

# Wait for backend process (this keeps the script running)
wait $BACKEND_PID
