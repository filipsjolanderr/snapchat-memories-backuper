#!/usr/bin/env bash
set -e

echo "=============================================="
echo " Snapchat Memories Backuper - Web UI"
echo "=============================================="
echo ""

# Check for Python
echo "Checking for Python..."
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 not found!"
  echo "👉 Install Python 3.11+ from https://www.python.org/downloads"
  exit 1
fi
echo "✅ Python found: $(python3 --version)"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  if [ $? -ne 0 ]; then
    echo "❌ Could not create a virtual environment."
    exit 1
  fi
  echo "✅ Virtual environment created."
  echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
  echo "❌ Could not activate virtual environment."
  exit 1
fi
echo "✅ Virtual environment activated."
echo ""

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip --quiet
echo ""

# Install dependencies
if [ -f "requirements.txt" ]; then
  echo "Installing required Python packages..."
  echo "(This takes a minute or two, please wait!)"
  pip install -r requirements.txt --quiet
  if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies."
    exit 1
  fi
  echo "✅ Dependencies installed."
else
  echo "⚠️ No requirements.txt found."
  exit 1
fi
echo ""

# Check for FFmpeg (optional but recommended)
echo "Checking for FFmpeg..."
if ! command -v ffmpeg &>/dev/null; then
  echo "⚠️ FFmpeg not found. Video processing may be slower."
  echo "💡 Install it using:"
  echo "   macOS:  brew install ffmpeg"
  echo "   Ubuntu: sudo apt install ffmpeg"
else
  echo "✅ FFmpeg found: $(ffmpeg -version | head -n 1)"
fi
echo ""

# Launch Streamlit UI
echo "=============================================="
echo "✅ Setup Complete!"
echo "🌐 Launching Web UI..."
echo ""
echo "The web interface will open in your browser."
echo "Press Ctrl+C to stop the server."
echo "=============================================="
echo ""

# Run Streamlit
streamlit run ui.py
