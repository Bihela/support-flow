@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo   SupportHub - Local Startup Script
echo ============================================
echo.

:: [0/4] Check Python is available
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Please install Python 3.10+ from https://www.python.org/downloads/
    echo         and make sure "Add Python to PATH" is checked during installation.
    pause
    exit /b 1
)

:: [1/4] Create virtual environment if it doesn't exist
if not exist venv (
    echo [1/4] Creating python virtual environment...
    python -m venv venv
) else (
    echo [1/4] Virtual environment already exists, skipping creation.
)

:: [2/4] Activate and install dependencies
echo [2/4] Activating virtual environment and installing dependencies...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install llama-cpp-python 2>nul || pip install --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --prefer-binary llama-cpp-python

:: [3/4] Initialize database
echo [3/4] Initializing database (app/database.py)...
python -m app.database

:: [4/4] Launch server and open browser
echo [4/4] Starting FastAPI server on http://localhost:8000
echo.
start http://localhost:8000
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
