@echo off
echo ============================================
echo  Transport Extractor - Windows Setup
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Installing Python packages...
pip install -r requirements.txt

echo [3/4] Downloading spaCy language models...
python -m spacy download pl_core_news_sm
python -m spacy download de_core_news_sm

echo [4/4] Creating folders...
if not exist pdfs mkdir pdfs
if not exist utils mkdir utils

echo.
echo ============================================
echo  Setup complete!
echo ============================================
echo.
echo Next steps:
echo   1. Copy your PDF files into the 'pdfs' folder
echo   2. Copy credentials.json into 'utils/' folder
echo   3. Double-click 'run_gui.bat' to start the app
echo.
pause
