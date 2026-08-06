#!/bin/bash
# Quick start script for macOS/Linux to run the Lumora AI backend

echo "============================================"
echo "Lumora AI Backend - Quick Start"
echo "============================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo "Please create .env file with Google Cloud credentials."
    echo "See SETUP_GUIDE.md for details."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check if dependencies are installed
pip list | grep -q fastapi
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the server
echo ""
echo "============================================"
echo "Starting Lumora AI Backend Server..."
echo "============================================"
echo ""
echo "Backend will be available at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
