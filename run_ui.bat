@echo off
title Snapchat Memories Backuper - Web UI Launcher
color 0B

echo ==============================================
echo   Snapchat Memories Backuper - Web UI
echo ==============================================
echo.

REM Check for Python (try multiple commands)
echo Checking for Python...
set PYTHON_CMD=
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
) else (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=py
    ) else (
        python3 --version >nul 2>&1
        if not errorlevel 1 (
            set PYTHON_CMD=python3
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo Python not found!
    echo.
    echo Attempting to install Python automatically...
    
    REM Check if winget is available
    where winget >nul 2>&1
    if not errorlevel 1 (
        echo Using winget to install Python...
        echo This may take a few minutes. Please wait...
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
        if not errorlevel 1 (
            echo Python installed successfully!
            echo Please restart PowerShell and run this script again.
            echo After restarting, Python will be available in your PATH.
            pause
            exit /b 0
        ) else (
            echo Automatic installation failed.
        )
    )
    
    echo.
    echo Please install Python manually:
    echo 1. Download from: https://www.python.org/downloads
    echo 2. During installation, check "Add Python to PATH"
    echo 3. Restart PowerShell and run this script again
    echo.
    pause
    exit /b 1
)
echo Python found!
%PYTHON_CMD% --version
echo.

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating Python virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Could not create a virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo Could not activate virtual environment.
    pause
    exit /b 1
)
echo Virtual environment activated.
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
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
    echo Dependencies installed.
) else (
    echo No requirements.txt file found.
    pause
    exit /b 1
)
echo.

REM Check for FFmpeg (optional but recommended)
echo Checking for FFmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo FFmpeg not found. Video processing may be slower.
    echo.
    
    REM Try to install FFmpeg automatically
    where winget >nul 2>&1
    if not errorlevel 1 (
        echo Would you like to install FFmpeg automatically? (Y/n)
        set /p INSTALL_FFMPEG=
        if /i not "%INSTALL_FFMPEG%"=="n" (
            echo Installing FFmpeg...
            echo This may take a moment...
            winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements --silent
            if not errorlevel 1 (
                echo FFmpeg installed successfully!
                echo Note: You may need to restart PowerShell for FFmpeg to be available.
            ) else (
                echo Automatic installation failed. Install manually with:
                echo   winget install Gyan.FFmpeg
            )
        ) else (
            echo Skipping FFmpeg installation. Install later with: winget install Gyan.FFmpeg
        )
    ) else (
        echo Install FFmpeg manually with: winget install Gyan.FFmpeg
        echo Or download from: https://ffmpeg.org/download.html
    )
) else (
    echo FFmpeg found!
)
echo.

REM Launch Streamlit UI
echo ==============================================
echo Setup Complete!
echo Launching Web UI...
echo.
echo The web interface will open in your browser.
echo Press Ctrl+C to stop the server.
echo ==============================================
echo.

REM Run Streamlit
streamlit run ui.py

pause
