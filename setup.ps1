# Snapchat Memories Backuper - Auto Setup Script
# This script downloads the repository and launches the web UI

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " 📸 Snapchat Memories Backuper - Auto Setup" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if a command exists
function Test-Command {
    param($Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# Check and install Python if needed
Write-Host "Checking for Python..." -ForegroundColor Cyan
$pythonFound = $false
$pythonCmd = $null

if (Test-Command "python") {
    try {
        $version = python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonFound = $true
            $pythonCmd = "python"
            Write-Host "✅ Python found: $version" -ForegroundColor Green
        }
    } catch {}
}

if (-not $pythonFound) {
    if (Test-Command "py") {
        try {
            $version = py --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                $pythonFound = $true
                $pythonCmd = "py"
                Write-Host "✅ Python found: $version" -ForegroundColor Green
            }
        } catch {}
    }
}

if (-not $pythonFound) {
    Write-Host "❌ Python not found!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Attempting to install Python automatically..." -ForegroundColor Cyan
    
    # Try winget first (Windows 10/11)
    if (Test-Command "winget") {
        Write-Host "Using winget to install Python..." -ForegroundColor Cyan
        Write-Host "This may take a few minutes. Please wait..." -ForegroundColor Yellow
        try {
            winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Python installed successfully!" -ForegroundColor Green
                Write-Host "Please restart PowerShell and run this script again." -ForegroundColor Yellow
                Write-Host ""
                Write-Host "After restarting, Python will be available in your PATH." -ForegroundColor Cyan
                pause
                exit 0
            }
        } catch {
            Write-Host "⚠️ Automatic installation failed. Please install manually:" -ForegroundColor Yellow
        }
    }
    
    # Fallback: manual installation instructions
    Write-Host ""
    Write-Host "Please install Python manually:" -ForegroundColor Yellow
    Write-Host "1. Download from: https://www.python.org/downloads" -ForegroundColor Cyan
    Write-Host "2. During installation, check 'Add Python to PATH'" -ForegroundColor Cyan
    Write-Host "3. Restart PowerShell and run this script again" -ForegroundColor Cyan
    Write-Host ""
    pause
    exit 1
}

# Check and install FFmpeg if needed
Write-Host ""
Write-Host "Checking for FFmpeg..." -ForegroundColor Cyan
$ffmpegFound = Test-Command "ffmpeg"

if (-not $ffmpegFound) {
    Write-Host "⚠️ FFmpeg not found (optional but recommended)" -ForegroundColor Yellow
    Write-Host ""
    
    # Try to install FFmpeg automatically
    if (Test-Command "winget") {
        Write-Host "Would you like to install FFmpeg automatically? (Y/n)" -ForegroundColor Cyan
        $response = Read-Host
        if ($response -ne "n" -and $response -ne "N") {
            Write-Host "Installing FFmpeg..." -ForegroundColor Cyan
            Write-Host "This may take a moment..." -ForegroundColor Yellow
            try {
                winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements --silent
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "✅ FFmpeg installed successfully!" -ForegroundColor Green
                    Write-Host "Note: You may need to restart PowerShell for FFmpeg to be available." -ForegroundColor Yellow
                    $ffmpegFound = $true
                } else {
                    Write-Host "⚠️ Automatic installation failed. You can install manually later:" -ForegroundColor Yellow
                    Write-Host "   winget install Gyan.FFmpeg" -ForegroundColor Cyan
                }
            } catch {
                Write-Host "⚠️ Could not install FFmpeg automatically." -ForegroundColor Yellow
                Write-Host "   Install manually with: winget install Gyan.FFmpeg" -ForegroundColor Cyan
            }
        } else {
            Write-Host "Skipping FFmpeg installation. You can install it later for faster video processing." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Install FFmpeg manually with: winget install Gyan.FFmpeg" -ForegroundColor Cyan
        Write-Host "(Or download from: https://ffmpeg.org/download.html)" -ForegroundColor Cyan
    }
} else {
    Write-Host "✅ FFmpeg found!" -ForegroundColor Green
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Proceeding with repository setup..." -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

$repoName = "snapchat-memories-backuper"
$zipUrl = "https://github.com/filipsjolanderr/snapchat-memories-backuper/archive/refs/heads/main.zip"
$zipFile = "snapchat-memories-backuper.zip"

# Check if directory already exists
if (Test-Path $repoName) {
    Write-Host "⚠️ Directory '$repoName' already exists!" -ForegroundColor Yellow
    $overwrite = Read-Host "Do you want to use the existing directory? (Y/n)"
    if ($overwrite -eq "n" -or $overwrite -eq "N") {
        Write-Host "Exiting..." -ForegroundColor Red
        exit 1
    }
    Write-Host "Using existing directory..." -ForegroundColor Green
} else {
    # Download ZIP file
    Write-Host "Downloading repository..." -ForegroundColor Cyan
    Write-Host "This may take a moment..." -ForegroundColor Yellow
    
    try {
        # Download ZIP file
        $ProgressPreference = 'SilentlyContinue'  # Suppress progress bar for cleaner output
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -ErrorAction Stop
        
        Write-Host "✅ Download complete!" -ForegroundColor Green
        
        # Extract ZIP file
        Write-Host ""
        Write-Host "Extracting files..." -ForegroundColor Cyan
        Expand-Archive -Path $zipFile -DestinationPath . -Force -ErrorAction Stop
        
        # Rename extracted folder (GitHub ZIP extracts to snapchat-memories-backuper-main)
        if (Test-Path "snapchat-memories-backuper-main") {
            Rename-Item -Path "snapchat-memories-backuper-main" -NewName $repoName -Force
        }
        
        # Clean up ZIP file
        Remove-Item -Path $zipFile -Force -ErrorAction SilentlyContinue
        
        Write-Host "✅ Files extracted successfully!" -ForegroundColor Green
    } catch {
        Write-Host "❌ Failed to download or extract repository!" -ForegroundColor Red
        Write-Host "Error: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please try downloading manually from:" -ForegroundColor Yellow
        Write-Host "https://github.com/filipsjolanderr/snapchat-memories-backuper" -ForegroundColor Cyan
        pause
        exit 1
    }
}

# Change to repository directory
Set-Location $repoName

# Check if run_ui.bat exists
if (-not (Test-Path "run_ui.bat")) {
    Write-Host "❌ run_ui.bat not found in repository!" -ForegroundColor Red
    Write-Host "The repository may not have downloaded correctly." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "✅ Repository ready!" -ForegroundColor Green
Write-Host "🚀 Launching setup script..." -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Run the batch file
& .\run_ui.bat
