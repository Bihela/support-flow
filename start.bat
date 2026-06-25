@echo off
setlocal
cd /d "%~dp0"

if not exist venv (
    echo [SupportHub] Creating python virtual environment...
    python -m venv venv
)

echo [SupportHub] Activating virtual environment...
call venv\Scripts\activate

echo [SupportHub] Upgrading pip and installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [SupportHub] Initializing database (app/database.py)...
python -m app.database

echo [SupportHub] Starting FastAPI server on http://localhost:8000
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
