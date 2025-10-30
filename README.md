# 📸 Snapchat Memories Backuper

A simple tool to **download, restore, and organize your Snapchat Memories** using the data Snapchat lets you export.

It works on **Windows, macOS, and Linux**, and you don't need to know anything about coding or Python!

---

## 📥 Step 1: Request Your Snapchat Data

1. Open your browser (Chrome, Edge, or Safari) and go to:  
   👉 [https://accounts.snapchat.com](https://accounts.snapchat.com) or use the Snapchat App
2. Log in with your Snapchat username and password
3. Click your **profile icon** in the top‑left corner (top‑right in the app)
4. Choose **Account Settings**
5. Scroll down and click **My Data**
6. Check ✅ the box **“Export Your Memories”** and click **"Request Only Memories"**
7. Under **Date Range**, select **All Time** to include every snap you’ve ever saved
8. Make sure your email address is correct — Snapchat will send your download link there
9. Click **Submit**

> ⏳ **Note:** It can take a few hours.  
> You’ll get an email with a download link once your data is ready.

---

## 💾 Step 2: Download and Extract Your Data

Do this **from a computer or laptop** using Snapchat’s website — **not** from your phone.

1. When you receive the email from Snapchat, click **"click here"**
2. Click **"See exports"** → then click **"Download"**
3. Save the ZIP file and **extract** (unzip) it:
   - On **Windows:** Right‑click → “Extract All...”
   - On **Mac:** Double‑click the file
4. Inside the extracted folder, go into the **html** folder and find  
   **`memories_history.html`** → that’s the important file!

---

## 🚀 Step 3: Start the Backuper

### 🪟 **Windows**

1. **Open PowerShell:**

   - Press the **Windows key** (or click Start)
   - Type **"PowerShell"**
   - Click **"Windows PowerShell"** (or press Enter)

2. **Copy and paste this ONE command, then press Enter:**

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/filipsjolanderr/snapchat-memories-backuper/main/setup.ps1" -OutFile "setup.ps1"; .\setup.ps1
```

That's it! The script will:

- ✅ Download everything automatically
- ✅ Install all required packages
- ✅ Open the web interface in your browser

---

### 🐧 **macOS / Linux**

1. **Open Terminal:**

   - **macOS:** Press `Cmd + Space`, type "Terminal", press Enter
   - **Linux:** Press `Ctrl + Alt + T` or search for "Terminal" in your applications

2. **Copy and paste this ONE command, then press Enter:**

```bash
curl -O https://raw.githubusercontent.com/filipsjolanderr/snapchat-memories-backuper/main/setup.sh && chmod +x setup.sh && ./setup.sh
```

That's it! The script will:

- ✅ Download everything automatically
- ✅ Install all required packages
- ✅ Open the web interface in your browser

---

## 🌐 Step 4: Use the Web UI

Once the web interface opens:

1. **Upload** your `memories_history.html` file
2. **Choose** where to save your processed memories
3. **Click** "Start Processing"

Done! 🎉

---

## 🧰 What This Tool Does

This program helps you:

✅ Download all your Snaps and Stories from your official Snapchat data export  
✅ Fix Snapchat’s messy file names and missing extensions  
✅ Combine overlay stickers and text back into your photos/videos  
✅ Recover the correct **date and location metadata** for each memory  
✅ Automatically organize everything into a nice, clean folder

---

### 🌐 Using the Web UI

Once the web interface opens:

1. **Upload** your `memories_history.html` file
2. **Choose** where to save your processed memories
3. **Configure** performance settings (optional)
4. **Click** "Start Processing" and watch it work!

The web UI provides:

- 📊 Real-time progress bars
- ⚙️ Easy configuration options
- 🎨 Beautiful, user-friendly interface
- 📁 Simple file/folder selection

That’s it — no command line needed!

---

## 🧩 Alternative: Manual Installation (If You Prefer)

If you prefer to install manually instead of using the one-click launcher:

1. [Install Python 3.11+](https://www.python.org/downloads)
   - Make sure to check ✅ **Add Python to PATH** on Windows!
2. Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

- **Windows:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **macOS/Linux:**
  ```bash
  source .venv/bin/activate
  ```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

---

## ▶️ Step 4: Run the Tool

### 🌐 **Option A – Web UI (Recommended)**

#### 🪟 **Windows**

Just double‑click **`run_ui.bat`**

It automatically:

- ✅ Checks that Python is installed
- ✅ Creates and activates the virtual environment
- ✅ Installs all required packages
- ✅ Checks for FFmpeg
- ✅ **Opens the beautiful web interface in your browser!**

---

#### 🐧 **macOS / Linux**

Run this in your Terminal from the project folder:

```bash
chmod +x run_ui.sh
./run_ui.sh
```

---

### 💻 **Option B – Command Line Interface**

If you prefer using the command line:
#### HTML File Mode 

```bash
python -m snap_memories memories_history.html -o output_folder
```

✅ The tool will:

- Download all your Memories automatically
- Combine any images or videos with overlays
- Add the correct date/time and location metadata
- Save your organized files into `output_folder`

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
python -m snap_memories memories_history.html -o output_folder
```

**macOS/Linux:**

```bash
source .venv/bin/activate
python -m snap_memories memories_history.html -o output_folder
```

---

#### Folder Mode

If you already downloaded the memories manually into a folder:

```bash
python -m snap_memories ./memories -o output_folder -m memories_history.html
```

---

#### ⚙️ Optional Settings

| Option                  | Description                                              |
| ----------------------- | -------------------------------------------------------- |
| `--dry-run`             | Preview what will happen without actually making changes |
| `-v`                    | Verbose mode (see detailed progress)                     |
| `--no-gpu`              | Disable GPU acceleration if needed                       |
| `--download-workers 64` | Faster downloads (if you have good internet)             |

**Example:**

```bash
python -m snap_memories memories_history.html -o output -v --download-workers 64
```

---

## 🎨 Step 5: Sit Back and Let It Work!

You’ll see progress bars as it:

- ⬇️ Downloads your files
- 🗂️ Organizes and renames them
- 🎞️ Merges overlay images/videos
- 🗺️ Adds date/time/location metadata

When it’s done, open the **output** folder —  
you’ll find all your Memories neatly restored and sorted!

---

## 🧩 Common Issues & Fixes

| Problem                             | Solution                                               |
| ----------------------------------- | ------------------------------------------------------ |
| **FFmpeg not found**                | Install FFmpeg (see below)                             |
| **Permission denied**               | Try a different output folder or run terminal as admin |
| **Module not found: snap_memories** | Make sure your virtual environment is active           |
| **Slow or failing downloads**       | Reduce parallel workers: `--download-workers 8`        |

---

## 🎬 Installing FFmpeg (for Video Support)

If you don’t have FFmpeg yet, install it as follows:

- **Windows:**
  ```bash
  winget install Gyan.FFmpeg
  ```
  Then restart your terminal.
- **macOS:**
  ```bash
  brew install ffmpeg
  ```
- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt install ffmpeg
  ```

---

## ⚡ Optional – GPU Support

If you have a supported GPU, FFmpeg uses it to speed up video processing:

- **NVIDIA:** NVENC (`h264_nvenc`)
- **AMD:** AMF (`h264_amf`)
- **Intel:** QSV (`h264_qsv`)
- **Apple:** VideoToolbox (`h264_videotoolbox`)

If GPU isn’t available, it automatically uses CPU mode (slower but still fine).

---

## 🧠 Advanced: What the Launcher Scripts Do

### 📁 `run_ui.bat` (Windows)

The Windows batch script (`run_ui.bat`) performs these steps:

1. ✅ Checks for Python installation
2. ✅ Creates virtual environment (`.venv`) if it doesn't exist
3. ✅ Activates the virtual environment
4. ✅ Upgrades pip to the latest version
5. ✅ Installs all required packages from `requirements.txt`
6. ✅ Checks for FFmpeg (warns if missing)
7. ✅ Launches Streamlit web UI (`streamlit run ui.py`)

The web interface automatically opens in your default browser!

---

### 🐧 `run_ui.sh` (macOS/Linux)

The shell script (`run_ui.sh`) does the same steps:

1. ✅ Checks for Python 3 installation
2. ✅ Creates virtual environment (`.venv`) if it doesn't exist
3. ✅ Activates the virtual environment
4. ✅ Upgrades pip to the latest version
5. ✅ Installs all required packages from `requirements.txt`
6. ✅ Checks for FFmpeg (warns if missing)
7. ✅ Launches Streamlit web UI (`streamlit run ui.py`)

The web interface automatically opens in your default browser!

---

### 🔄 Running Again Later

Once you've run the script once, the virtual environment is created. You can:

- **Option 1:** Just run `run_ui.bat` (Windows) or `./run_ui.sh` (macOS/Linux) again — it's smart enough to reuse the existing environment
- **Option 2:** Manually activate and run:

  ```bash
  # Windows
  .\.venv\Scripts\Activate.ps1
  streamlit run ui.py

  # macOS/Linux
  source .venv/bin/activate
  streamlit run ui.py
  ```

---

## 🎉 That’s It!

You’ve successfully backed up your entire Snapchat history —  
all your Snaps, Stories, and videos restored with original data and neatly organized. 💛

If you ever need to reprocess your Snaps later:

1. Just run `run_ui.bat` (Windows) or `./run_ui.sh` (macOS/Linux) again
2. Or use the command line interface from Step 4

> 💬 **Tip:** Use the web UI's "Dry Run" option to preview actions before running for real.

---

**Made with care to keep your Snapchat memories safe, clear, and easy to restore 📷 💛**
