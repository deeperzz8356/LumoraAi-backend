@echo off
REM Quick start script for Windows to run the Lumora AI backend

echo ============================================
echo Lumora AI Backend - Quick Start
echo ============================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please create .env file with Google Cloud credentials.
    echo See SETUP_GUIDE.md for details.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if dependencies are installed
pip list | findstr fastapi >nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Start the server
echo.
echo ============================================
echo Starting Lumora AI Backend Server...
echo ============================================
echo.
echo Backend will be available at: http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
