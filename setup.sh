#!/usr/bin/env bash
# Snapchat Memories Backuper - Auto Setup Script
# This script downloads the repository and launches the web UI

set +e

REPO_NAME="snapchat-memories-backuper"
ZIP_URL="https://github.com/filipsjolanderr/snapchat-memories-backuper/archive/refs/heads/main.zip"
ZIP_FILE="snapchat-memories-backuper.zip"

echo "=============================================="
echo " 📸 Snapchat Memories Backuper - Auto Setup"
echo "=============================================="
echo ""

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
