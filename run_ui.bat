@echo off
title Snapchat Memories Backuper - Web UI Launcher
color 0B

echo ==============================================
echo   📸 Snapchat Memories Backuper - Web UI
echo ==============================================
echo.

REM Check for Python
echo Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found!
    echo 👉 Install Python 3.11+ from https://www.python.org/downloads
    echo (Check "Add Python to PATH" during install!)
    echo.
    pause
    exit /b 1
)
echo ✅ Python found.
python --version
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ Could not create a virtual environment.
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created.
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ Could not activate virtual environment.
    pause
    exit /b 1
)
echo ✅ Virtual environment activated.
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet
echo.

REM Install dependencies
if exist requirements.txt (
    echo Installing required Python packages...
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo ❌ Failed to install dependencies.
        pause
        exit /b 1
    )
    echo ✅ Dependencies installed.
) else (
    echo ⚠️ No requirements.txt file found.
    pause
    exit /b 1
)
echo.

REM Check for FFmpeg (optional but recommended)
echo Checking for FFmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo ⚠️ FFmpeg not found. Video processing may be slower.
    echo 💡 Install it with: winget install Gyan.FFmpeg
) else (
    echo ✅ FFmpeg found!
)
echo.

REM Launch Streamlit UI
echo ==============================================
echo ✅ Setup Complete!
echo 🌐 Launching Web UI...
echo.
echo The web interface will open in your browser.
echo Press Ctrl+C to stop the server.
echo ==============================================
echo.

REM Run Streamlit
streamlit run ui.py

pause
