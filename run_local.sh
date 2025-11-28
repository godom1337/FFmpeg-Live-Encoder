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

# Check if FFmpeg is installed locally
echo -e "${BLUE}Checking local FFmpeg installation...${NC}"
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}Error: FFmpeg not found in PATH${NC}"
    echo "Please install FFmpeg with AVFoundation support:"
    echo "  brew install ffmpeg"
    exit 1
fi

# Show FFmpeg version
echo -e "${GREEN}Found FFmpeg:${NC}"
ffmpeg -version | head -3
echo ""

# Check for AVFoundation support
if ffmpeg -version 2>&1 | grep -q "enable-avfoundation"; then
    echo -e "${GREEN}✓ AVFoundation support detected${NC}"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${YELLOW}⚠ AVFoundation support not explicitly shown (may still work)${NC}"
fi
echo ""

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

# Check if Python 3.9+ is available
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
    exit 1
fi

echo -e "${GREEN}Found Python: $PYTHON_CMD${NC}"
$PYTHON_CMD --version
echo ""

# Check if Node.js is installed
echo -e "${BLUE}Checking Node.js installation...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js not found${NC}"
    echo "Please install Node.js from https://nodejs.org/"
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
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install backend dependencies${NC}"
    exit 1
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

# Detect server IP address for VITE_API_URL
SERVER_IP=$(hostname -I | awk '{print $1}')
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="localhost"
fi

# Allow override via environment variable
API_URL="${VITE_API_URL:-http://${SERVER_IP}:8000/api/v1}"

echo -e "${BLUE}Using API URL:${NC} $API_URL"

# Set environment variable for Vite build
export VITE_API_URL="$API_URL"

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

