#!/usr/bin/env bash
# Snapchat Memories Backuper - Auto Setup Script
# This script downloads the repository and launches the web UI

set +e

echo "=============================================="
echo " 📸 Snapchat Memories Backuper - Auto Setup"
echo "=============================================="
echo ""

# Check and install Python if needed
echo "Checking for Python..."
PYTHON_FOUND=false
PYTHON_CMD=""

if command -v python3 &>/dev/null; then
    if python3 --version &>/dev/null; then
        PYTHON_FOUND=true
        PYTHON_CMD="python3"
        echo "✅ Python found: $(python3 --version)"
    fi
fi

if [ "$PYTHON_FOUND" = false ]; then
    if command -v python &>/dev/null; then
        if python --version &>/dev/null; then
            PYTHON_FOUND=true
            PYTHON_CMD="python"
            echo "✅ Python found: $(python --version)"
        fi
    fi
fi

if [ "$PYTHON_FOUND" = false ]; then
    echo "❌ Python not found!"
    echo ""
    echo "Attempting to install Python automatically..."
    
    # Check for package manager and install
    if command -v brew &>/dev/null; then
        echo "Using Homebrew to install Python..."
        echo "This may take a few minutes. Please wait..."
        if brew install python3; then
            echo "✅ Python installed successfully!"
            echo "Please restart your terminal and run this script again."
            exit 0
        else
            echo "⚠️ Automatic installation failed."
        fi
    elif command -v apt-get &>/dev/null; then
        echo "Using apt to install Python..."
        echo "This may require sudo password..."
        if sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv; then
            echo "✅ Python installed successfully!"
            echo "Please restart your terminal and run this script again."
            exit 0
        else
            echo "⚠️ Automatic installation failed."
        fi
    elif command -v yum &>/dev/null; then
        echo "Using yum to install Python..."
        echo "This may require sudo password..."
        if sudo yum install -y python3 python3-pip; then
            echo "✅ Python installed successfully!"
            echo "Please restart your terminal and run this script again."
            exit 0
        else
            echo "⚠️ Automatic installation failed."
        fi
    fi
    
    # Fallback: manual installation instructions
    echo ""
    echo "Please install Python manually:"
    echo "  macOS:  brew install python3"
    echo "  Ubuntu: sudo apt install python3 python3-pip python3-venv"
    echo "  Or download from: https://www.python.org/downloads"
    echo ""
    exit 1
fi

# Check and install FFmpeg if needed
echo ""
echo "Checking for FFmpeg..."
FFMPEG_FOUND=false

if command -v ffmpeg &>/dev/null; then
    FFMPEG_FOUND=true
    echo "✅ FFmpeg found!"
else
    echo "⚠️ FFmpeg not found (optional but recommended)"
    echo ""
    
    # Try to install FFmpeg automatically
    if command -v brew &>/dev/null; then
        echo "Would you like to install FFmpeg automatically? (Y/n)"
        read -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "Installing FFmpeg..."
            if brew install ffmpeg; then
                echo "✅ FFmpeg installed successfully!"
                FFMPEG_FOUND=true
            else
                echo "⚠️ Automatic installation failed. Install manually with: brew install ffmpeg"
            fi
        fi
    elif command -v apt-get &>/dev/null; then
        echo "Would you like to install FFmpeg automatically? (Y/n)"
        read -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "Installing FFmpeg (requires sudo)..."
            if sudo apt-get install -y ffmpeg; then
                echo "✅ FFmpeg installed successfully!"
                FFMPEG_FOUND=true
            else
                echo "⚠️ Automatic installation failed. Install manually with: sudo apt install ffmpeg"
            fi
        fi
    elif command -v yum &>/dev/null; then
        echo "Would you like to install FFmpeg automatically? (Y/n)"
        read -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "Installing FFmpeg (requires sudo)..."
            if sudo yum install -y ffmpeg; then
                echo "✅ FFmpeg installed successfully!"
                FFMPEG_FOUND=true
            else
                echo "⚠️ Automatic installation failed. Install manually with: sudo yum install ffmpeg"
            fi
        fi
    else
        echo "Install FFmpeg manually:"
        echo "  macOS:  brew install ffmpeg"
        echo "  Ubuntu: sudo apt install ffmpeg"
        echo "  Or download from: https://ffmpeg.org/download.html"
    fi
fi

echo ""
echo "=============================================="
echo "Proceeding with repository setup..."
echo "=============================================="
echo ""

REPO_NAME="snapchat-memories-backuper"
ZIP_URL="https://github.com/filipsjolanderr/snapchat-memories-backuper/archive/refs/heads/main.zip"
ZIP_FILE="snapchat-memories-backuper.zip"

# Check if directory already exists
if [ -d "$REPO_NAME" ]; then
    echo "⚠️ Directory '$REPO_NAME' already exists!"
    read -p "Do you want to use the existing directory? (Y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
        echo "Exiting..."
        exit 1
    fi
    echo "Using existing directory..."
else
    # Download ZIP file
    echo "Downloading repository..."
    echo "This may take a moment..."
    
    # Check for curl or wget
    DOWNLOAD_SUCCESS=false
    if command -v curl &>/dev/null; then
        echo "Using curl to download..."
        if curl -L -o "$ZIP_FILE" "$ZIP_URL"; then
            DOWNLOAD_SUCCESS=true
        fi
    elif command -v wget &>/dev/null; then
        echo "Using wget to download..."
        if wget -O "$ZIP_FILE" "$ZIP_URL"; then
            DOWNLOAD_SUCCESS=true
        fi
    else
        echo "❌ Neither curl nor wget found!"
        echo "Please install curl or wget, or download manually from:"
        echo "https://github.com/filipsjolanderr/snapchat-memories-backuper"
        exit 1
    fi
    
    if [ "$DOWNLOAD_SUCCESS" = true ]; then
        echo "✅ Download complete!"
        
        # Check for unzip
        echo ""
        echo "Extracting files..."
        if ! command -v unzip &>/dev/null; then
            echo "❌ unzip not found!"
            echo "Please install unzip:"
            echo "  macOS:  brew install unzip"
            echo "  Ubuntu: sudo apt install unzip"
            rm -f "$ZIP_FILE"
            exit 1
        fi
        
        # Extract ZIP file
        if ! unzip -q "$ZIP_FILE" -d .; then
            echo "❌ Failed to extract ZIP file!"
            rm -f "$ZIP_FILE"
            exit 1
        fi
        
        # Rename extracted folder (GitHub ZIP extracts to snapchat-memories-backuper-main)
        if [ -d "snapchat-memories-backuper-main" ]; then
            mv "snapchat-memories-backuper-main" "$REPO_NAME"
        fi
        
        # Clean up ZIP file
        rm -f "$ZIP_FILE"
        
        echo "✅ Files extracted successfully!"
    else
        echo "❌ Failed to download repository!"
        echo "Please try downloading manually from:"
        echo "https://github.com/filipsjolanderr/snapchat-memories-backuper"
        exit 1
    fi
fi

# Change to repository directory
cd "$REPO_NAME"

# Check if run_ui.sh exists
if [ ! -f "run_ui.sh" ]; then
    echo "❌ run_ui.sh not found in repository!"
    echo "The repository may not have downloaded correctly."
    exit 1
fi

echo ""
echo "=============================================="
echo "✅ Repository ready!"
echo "🚀 Launching setup script..."
echo "=============================================="
echo ""

# Make script executable and run it
chmod +x run_ui.sh
./run_ui.sh
