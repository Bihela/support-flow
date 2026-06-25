#!/bin/bash
set -e

# Resolve script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ ! -d "venv" ]; then
    echo "[SupportHub] Creating python virtual environment..."
    python3 -m venv venv
fi

echo "[SupportHub] Activating virtual environment..."
source venv/bin/activate

echo "[SupportHub] Upgrading pip and installing requirements..."
python3 -m pip install --upgrade pip
pip install -r requirements.txt

echo "[SupportHub] Initializing database (app/database.py)..."
python3 -m app.database

echo "[SupportHub] Starting FastAPI server on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
