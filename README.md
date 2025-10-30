# Snapchat Memories Backuper

A Python tool to restore and organize Snapchat Memories from exported data. **Recommended approach**: Download memories directly from HTML files for the easiest experience.

## 📋 Table of Contents

- [Getting Your Snapchat Data](#getting-your-snapchat-data)
- [Requirements](#requirements)
- [Installation](#installation)
- [Architecture](#architecture)
- [Usage](#usage)
- [Command Reference](#command-reference)
- [What It Does](#what-it-does)
- [Metadata Support](#metadata-support)
- [Performance Tuning](#performance-tuning)
- [Troubleshooting](#troubleshooting)

## 📱 Getting Your Snapchat Data

### Step 1: Request Your Data from Snapchat

1. Open Snapchat and go to your **Profile** screen
2. Tap the ⚙️ **Settings** icon in the top-right corner
3. Scroll down and select **My Data** under the Account Actions section
4. When the data request page appears, make sure to check the box for **"Export Your Memories"**
5. Set the date range to **"All Time"** so that every saved Snap and Story is included
6. Confirm that your email address is correct (this is where Snapchat will send your download link)
7. Tap **Submit Request** to begin the process

> ⏰ **Note**: Once submitted, Snapchat will prepare your data. You'll receive an email with a download link when your file is ready. This process usually takes 2–3 hours (but can take multiple days).

### Step 2: Download Your Snapchat Data

1. Once you receive the email from Snapchat, click the provided link and download the ZIP file containing your Memories
2. Create a dedicated folder for your Snapchat data (e.g., "SnapchatData")
3. Unzip the downloaded file to extract its contents
4. Inside the extracted folder, locate and open the `index.html` file
5. Once the page opens in your browser, navigate to the **Memories** section to view all your saved Snaps and Stories

### Step 3: Get the HTML File (Recommended Method)

**🎯 Direct Download Method (Easiest)**

- Save the `memories_history.html` file from your Snapchat data export
- Use this script to download and process all memories automatically
- **This is the recommended approach** - no manual work needed!

**Alternative: Manual Download Method**

- Download each memory individually from the browser
- Organize files in a folder structure
- Use the traditional processing mode

## 🔧 Requirements

- **Python 3.9+**
- **pip packages** (install via `pip install -r requirements.txt`):
  - `pillow>=11.0.0` (for image processing)
  - `moviepy>=2.2.1` (for video processing)
  - `tqdm>=4.67.1` (for progress bars)
  - `proglog>=0.1.10` (for progress bars)
  - `piexif>=1.1.3` (for EXIF metadata)
  - `requests>=2.32.5` (for direct downloads)
- **FFmpeg** (required for moviepy video writing)

### Installing FFmpeg on Windows

- **Option 1**: Install via winget: `winget install Gyan.FFmpeg` (then restart terminal)
- **Option 2**: Download a build and add its `bin` folder to your PATH

## 🚀 Installation

### Create a Python virtual environment (recommended)

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**macOS/Linux (bash/zsh):**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 🏗️ Architecture

The tool is built with a modular, object-oriented architecture:

- **`cli.py`**: Command-line interface and argument parsing
- **`config.py`**: Configuration management
- **`logger.py`**: Centralized logging system with multiple verbosity levels
- **`pipeline.py`**: Main pipeline orchestrator
- **`planner.py`**: Planning operations
- **`executors.py`**: Execution services:
  - `ZipService`: ZIP file extraction
  - `CopyService`: File copying operations
  - `RenameService`: File renaming operations
  - `CombineService`: Image/video combining
- **`download.py`**: Download management
- **`metadata.py`**: Metadata parsing and writing
- **`fs.py`**: Filesystem utilities
- **`stats.py`**: Statistics and counting functions
- **`utils.py`**: General utilities
- **`gpu.py`**: GPU detection and configuration

## 💻 Usage

The tool automatically detects whether your input is an HTML file or folder - no need to specify different commands!

### 🎯 Basic Usage

```bash
# Download from HTML file (auto-detected)
python -m snap_memories memories_history.html -o output_folder

# Process folder (auto-detected)
python -m snap_memories ./memories -o output_folder

# With metadata file (for folder processing)
python -m snap_memories ./memories -o output_folder -m memories_history.html
```

### 📚 Command Reference

#### Required Arguments

- `INPUT_PATH`: Path to HTML file (`memories_history.html`) or folder containing memories

#### Options

**Input/Output:**

- `-o, --output PATH`: Specify custom output folder (default: `output/` relative to input)
- `-m, --metadata PATH`: Path to `memories_history.html` for metadata (optional, auto-detected when input is HTML)

**Processing:**

- `--dry-run`: Preview all actions without making changes
- `--image-workers N`: Number of parallel workers for image processing (default: 8)
- `--video-workers N`: Number of parallel workers for video processing (default: 4)
- `--download-workers N`: Number of parallel workers for downloads (default: 32)

**GPU:**

- `--use-gpu`: Enable GPU acceleration (default: enabled)
- `--no-gpu`: Force CPU-only processing
- `--ffmpeg-gpu`: Use FFmpeg GPU pipeline for maximum performance

**Logging:**

- `-v, --verbose`: Enable verbose output (shows detailed progress)
- `-q, --quiet`: Suppress all output except errors

### 💡 Examples

```bash
# Download from HTML with verbose output and 64 download workers
python -m snap_memories memories_history.html -o output -v --download-workers 64

# Process folder with GPU disabled and custom workers
python -m snap_memories ./memories -o output --no-gpu --image-workers 16 --video-workers 8

# Preview download with quiet mode (only errors shown)
python -m snap_memories memories_history.html -o output --dry-run -q

# Process with metadata and FFmpeg GPU acceleration
python -m snap_memories ./memories -o output -m memories_history.html --ffmpeg-gpu

# Get help
python -m snap_memories --help
```

## ⚙️ What It Does

### 🎯 HTML Download Mode (when input is an HTML file)

When you provide a `.html` file, the script:

1. **Downloads** all memories from HTML file URLs (parallel, 32 workers by default)
2. **Detects** file types automatically (ZIP, JPG, MP4) from server responses
3. **Fixes** ZIP files with wrong extensions
4. **Extracts** ZIP files containing main + overlay pairs (if any)
5. **Copies** standalone MP4 files that don't need combining
6. **Renames** files without extensions to `.jpg`
7. **Combines** pairs from ZIP contents only:
   - `*-main.jpg` + `*-overlay.png` → `<uuid>_combined.jpg` (with EXIF metadata)
   - `*-main.mp4` + `*-overlay.png` → `<uuid>_combined.mp4` (with MP4 metadata)
8. **Applies** metadata (date/location) from HTML to final outputs
9. **Cleans up** ZIP files and temp folders automatically

> **Note**: Downloaded files are already individual memories, so no combining is needed for them.

### 📁 Folder Processing Mode (when input is a folder)

When you provide a folder, the script:

1. **Copies** standalone MP4 files to output folder
2. **Renames** files without extensions to `.jpg`
3. **Extracts** all `.zip` files found in the input folder
4. **Renames** unnamed files in extracted ZIPs
5. **Combines** pairs:
   - `*-main.jpg` + `*-overlay.png` → `<uuid>_combined.jpg`
   - `*-main.mp4` + `*-overlay.png` → `<uuid>_combined.mp4`
6. **Applies** metadata if HTML file is provided with `-m` flag
7. **Writes** results to output folder (default: `output/` inside input folder)

## 📊 Metadata Support

The script automatically applies metadata when an HTML file is provided:

- **Date/Time**: Original capture date from Snapchat
- **Location**: GPS coordinates (latitude/longitude) if available
- **File Format**:
  - **Images**: EXIF data in JPEG files
  - **Videos**: MP4 metadata atoms

### Metadata Sources

- **🎯 HTML Mode**: Automatically uses the HTML file for metadata
- **📁 Folder Mode**: Use `-m` flag to specify HTML file: `python -m snap_memories process ./memories -m memories_history.html`

## 🚀 Performance Tuning

### Download Performance

- **Default**: 32 parallel downloads
- **Increase**: `--download-workers 64` (for fast connections)
- **Decrease**: `--download-workers 8` (for slow/unstable connections)

### Image Processing Performance

- **Default**: 8 parallel workers
- **Increase**: `--image-workers 16` (for many images, more RAM)
- **Decrease**: `--image-workers 4` (for limited RAM)

### Video Processing Performance

- **Default**: 4 parallel workers
- **Increase**: `--video-workers 8` (for many videos, high RAM/CPU)
- **Decrease**: `--video-workers 1` (for limited resources)

### GPU Acceleration

The tool automatically detects and uses GPU-accelerated video encoding when available, which can significantly speed up video processing:

**Supported GPU Encoding:**

- **NVIDIA**: NVENC (h264_nvenc) - requires NVIDIA GPU with NVENC support
- **AMD**: AMF (h264_amf) - requires AMD GPU with AMF support
- **Intel**: QSV (h264_qsv) - requires Intel GPU with Quick Sync Video
- **Apple**: VideoToolbox (h264_videotoolbox) - macOS only

**GPU acceleration is enabled by default** and will fall back to CPU encoding if GPU is not available.

## 🔍 Troubleshooting

### Common Issues

#### ❌ "FFmpeg not found" or "FFmpeg failed"

**Problem**: FFmpeg is not installed or not in PATH

**Solutions**:

1. Install FFmpeg:
   - Windows: `winget install Gyan.FFmpeg` (then restart terminal)
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg` (Debian/Ubuntu) or `sudo yum install ffmpeg` (RHEL/CentOS)
2. Verify installation: `ffmpeg -version`
3. If installed but not found, add FFmpeg `bin` directory to your PATH environment variable

#### ❌ "Permission denied" errors

**Problem**: Insufficient permissions to create directories or write files

**Solutions**:

1. Run with appropriate permissions (administrator on Windows, sudo on Linux if needed)
2. Check output folder permissions
3. Ensure you have write access to the destination directory
4. Try a different output location with `-o` flag

#### ❌ "ModuleNotFoundError: No module named 'snap_memories'"

**Problem**: Not running from correct directory or virtual environment not activated

**Solutions**:

1. Ensure virtual environment is activated:
   - Windows: `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux: `source .venv/bin/activate`
2. Install dependencies: `pip install -r requirements.txt`
3. Run as module: `python -m snap_memories` (not `python snap_memories.py`)

#### ❌ Downloads failing or timing out

**Problem**: Network issues or Snapchat rate limiting

**Solutions**:

1. Reduce download workers: `--download-workers 8` (from default 32)
2. Check internet connection
3. Wait a few minutes if rate-limited (Snapchat may temporarily block requests)
4. Try again later

#### ❌ GPU encoding errors

**Problem**: GPU acceleration issues or incompatible GPU

**Solutions**:

1. Force CPU encoding: `--no-gpu`
2. Check GPU drivers are up to date
3. Verify FFmpeg GPU support: `ffmpeg -encoders | grep nvenc` (or amf/qsv/videotoolbox)
4. GPU encoding is optional - CPU encoding works fine, just slower

#### ❌ "Invalid data found when processing input" (FFmpeg)

**Problem**: Corrupted video files or invalid format

**Solutions**:

1. Test with `--dry-run` first to identify problematic files
2. Process files individually if possible
3. Some files may be corrupted - the tool will skip them and continue
4. Check if the file is actually a valid video file

#### ❌ Out of memory errors

**Problem**: Too many parallel workers consuming too much RAM

**Solutions**:

1. Reduce workers:
   - `--image-workers 4` (from default 8)
   - `--video-workers 2` (from default 4)
   - `--download-workers 16` (from default 32)
2. Process smaller batches of files
3. Close other applications to free RAM

#### ❌ "ZIP file with wrong extension" warnings

**Problem**: Some ZIP files have incorrect extensions (e.g., `.jpg` instead of `.zip`)

**Solution**: The tool automatically detects and fixes these. This is informational, not an error.

#### ❌ Metadata not applying

**Problem**: HTML file not found or invalid format

**Solutions**:

1. Verify HTML file path is correct
2. Ensure HTML file is the correct `memories_history.html` from Snapchat export
3. Check HTML file is readable: `cat memories_history.html | head -20`
4. In folder mode, use `-m` flag: `python -m snap_memories process ./memories -m memories_history.html`

#### ❌ Dry run shows different results than actual run

**Problem**: File system state changed between dry run and actual run

**Solution**: This is normal if files were modified between runs. Dry run shows what _would_ happen based on current state.

### Debugging Tips

1. **Use verbose mode**: `-v` or `--verbose` shows detailed progress
2. **Use dry run first**: `--dry-run` to preview without making changes
3. **Check logs**: Errors are displayed with ❌ prefix
4. **Process incrementally**: Try processing a small subset first
5. **Verify inputs**: Ensure HTML file and folders are valid

### Getting Help

If you encounter issues not covered here:

1. Run with verbose mode: `python -m snap_memories run input -v`
2. Check error messages carefully - they often indicate the specific problem
3. Verify all requirements are installed correctly
4. Check that input files/folders are valid and accessible

### Performance Issues

If processing is slow:

1. **Enable GPU**: Ensure GPU is detected (check startup message)
2. **Increase workers**: `--image-workers 16 --video-workers 8`
3. **Use FFmpeg GPU**: `--ffmpeg-gpu` for maximum video processing speed
4. **Reduce workers if unstable**: If crashes occur, reduce worker counts
5. **Check disk space**: Ensure enough free space for output files
