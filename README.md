# Snapchat Memories Backuper

A Python tool to restore and organize Snapchat Memories from exported data. This script unzips archives, fixes unnamed images, and composites `*-main` with `*-overlay` files for both images and videos, outputting clean, usable memories.

## 📋 Table of Contents

- [Getting Your Snapchat Data](#getting-your-snapchat-data)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [What It Does](#what-it-does)
- [Dry Run Mode](#dry-run-mode)

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

### Step 3: Download Your Memories

**Important**: Before downloading, configure your browser settings:

- **Download Permission**: If using a Chromium-based browser (Chrome, Edge, Brave), allow permission to download multiple files simultaneously
- **Download Location**: Set a designated folder where all files can be saved automatically (avoid being prompted for each file)
- **Organization**: Create a folder named "SnapchatData" and set it as your default download directory

You can choose to download each fileindividually or download them all at once.

> 💡 **Tip**: Even after allowing download permission, you might get the prompt numerous times - this is completely normal.

### Step 4: Understanding Your Downloaded Files

Once all downloads are complete, you'll find Snapchat organizes your data into different file types:

- **ZIP Files**: Contain base media and graphics or overlay elements (text, stickers, filters) that Snapchat uses on top of your images/videos,
- **MP4 Files**: Your videos from Snapchat Memories (playable in any media player)
- **Files with No Extension**: Your image files (photos) from Snapchat Memories (won't be recognized as images without extensions)

Now you're ready to use this script to restore your memories!

## 🔧 Requirements

- **Python 3.9+**
- **pip packages**:
  - `pillow 11.0.0`
  - `moviepy 2.2.1`
  - `tqdm 4.67.1`
  - `proglog 0.1.10`
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

## 💻 Usage

### Basic Syntax

```bash
python snap-memories.py <path-to-memories-folder> [-o <output-folder>] [--dry-run]
# or using flags
python snap-memories.py -i <path-to-memories-folder> -o <output-folder> [--dry-run]
```

### Examples

```bash
# Basic usage - processes memories in current directory
python snap-memories.py ./memories

# Specify custom output folder
python snap-memories.py "C:\\Exports\\Snapchat" -o "C:\\Exports\\Snapchat\\output"

# Preview changes without making them
python snap-memories.py ./memories --dry-run

# Using flags
python snap-memories.py -i ./memories -o ./memories/output
```

## ⚙️ What It Does

The script performs the following operations:

1. **Extracts** all `.zip` files found in the input folder
2. **Adds** `.jpg` extension to files with no extension
3. **Combines** pairs:
   - `*-main.jpg` + `*-overlay.png` → `<uuid>_combined.png`
   - `*-main.mp4` + `*-overlay.png` → `<uuid>_combined.mp4`
4. **Writes** results to `output/` inside the input folder (or your `-o` path)


## 🔍 Dry Run Mode

Use `--dry-run` to preview all actions without extracting, renaming, or writing outputs. It will also inspect ZIP contents to show planned combinations before extraction.

You'll see output like:

```
DRY RUN: would extract '...zip' → '...'
DRY RUN: would rename '.../file' → '.../file.jpg'
DRY RUN: would combine image '...-main.jpg' + '...-overlay.png' → '..._combined.png'
DRY RUN: would combine (inside <zip>) '...-main.mp4' + '...-overlay.png' → '..._combined.mp4'
```

This is perfect for understanding what the script will do before actually processing your files.
