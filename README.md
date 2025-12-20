# 📸 Snapchat Memories Backuper

A simple tool to **download, restore, and organize your Snapchat Memories**. Note: This tool works on **Windows, macOS, and Linux**.

---

## ✨ Why use this?

- **📥 Downloads Everything**: Grabs all your photos and videos from Snapchat.
- **⏸️ Resume Anytime**: Internet cut out? Need to turn off your computer? No problem! Close the tool and run it again later—it picks up exactly where it left off.
- **📅 Fixes Dates & Locations**: Restores the original date, time, and location for every memory.
- **🎞️ Combines Edits**: Automatically merges your overlay text and stickers back into your photos and videos.
- **📁 Smart Organizing**: Sorts deeply buried files into a clean, easy-to-browse folder.

---

## 🚀 Easy Start (Recommended)

### 1. Request Your Data
1. Go to [accounts.snapchat.com](https://accounts.snapchat.com) and log in.
2. Click **My Data**.
3. Select **"Export Your Memories"** and choose **"Request Only Memories"**.
4. Set Date Range to **All Time** and click **Submit**.
5. Wait for the email from Snapchat (this can take a while!).

### 2. Download Your Data
1. Click the link in the email to download your data.
2. **Extract (Unzip)** the file you downloaded.
3. Look for the file `memories_history.html` inside the `html` folder—you'll need this!

### 3. Run the Tool

#### 🪟 Windows
Right-click your **Start button**, choose **Windows PowerShell**, paste this, and hit Enter:
```powershell
cd $env:USERPROFILE\Downloads; Invoke-WebRequest -Uri "https://raw.githubusercontent.com/filipsjolanderr/snapchat-memories-backuper/main/setup.ps1" -OutFile "setup.ps1"; .\setup.ps1
```

#### 🍎 macOS / 🐧 Linux
Open your **Terminal**, paste this, and hit Enter:
```bash
curl -O https://raw.githubusercontent.com/filipsjolanderr/snapchat-memories-backuper/main/setup.sh && chmod +x setup.sh && ./setup.sh
```

**That's it!** The tool will install everything it needs and open a beautiful Web UI to guide you through the rest.

---

## 🛠️ For Advanced Users

If you prefer using the command line or have specific needs, you can use the tool directly.

### Installation
Requires Python 3.11+.

```bash
git clone https://github.com/filipsjolanderr/snapchat-memories-backuper
cd snapchat-memories-backuper
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
```

### Usage

**Standard Mode (Download from HTML):**
```bash
python -m snap_memories memories_history.html
```

**Folder Mode (Process downloaded files):**
Got a folder full of zips or half-processed files? Just point the tool at it. It will recursively find everything, figure out what's done, and finish the job.
```bash
python -m snap_memories ./my_memories_folder
```

### Options
- `-o output_folder`: Specify where to save the files.
- `--dry-run`: See what would happen without doing anything.
- `-v`: Verbose mode (see more details).
