#!/bin/bash
set -e

# Resolve script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo ""
echo "============================================"
echo "  SupportHub - Local Startup Script"
echo "============================================"
echo ""

# [0/4] Check Python3 is available
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 is not installed or not on PATH."
    echo "        Please install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

# [1/4] Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "[1/4] Creating python virtual environment..."
    python3 -m venv venv
else
    echo "[1/4] Virtual environment already exists, skipping creation."
fi

# [2/4] Activate and install dependencies
echo "[2/4] Activating virtual environment and installing dependencies..."
source venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install llama-cpp-python 2>/dev/null || pip install --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary llama-cpp-python

# [3/4] Initialize database
echo "[3/4] Initializing database (app/database.py)..."
python3 -m app.database

# [4/4] Launch server and open browser
echo "[4/4] Starting FastAPI server on http://localhost:8000"
echo ""
open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null &
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
