"""
Streamlit UI for Snapchat Memories Backuper
"""
from pathlib import Path
from typing import Optional
import time

import streamlit as st

# Try to import tkinter for folder selection
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

from snap_memories.config import AppConfig
from snap_memories.gpu import GPUDetector
from snap_memories.logger import Logger, LogLevel, set_logger
from snap_memories.pipeline import Pipeline


class StreamlitTqdm:
    """Streamlit-compatible tqdm wrapper."""
    
    def __init__(self, iterable=None, total=None, desc=None, unit=None, **kwargs):
        self.iterable = iterable
        self.total = total if total is not None else (len(iterable) if iterable else 0)
        self.desc = desc or "Processing"
        self.unit = unit or "it"
        self.n = 0
        self.progress_bar = st.progress(0.0)
        self.status_text = st.empty()
        self._iter = None
        self._update_display()
    
    def __iter__(self):
        if self.iterable is not None:
            self._iter = iter(self.iterable)
        return self
    
    def __next__(self):
        if self._iter is None:
            if self.iterable is None:
                raise StopIteration
            self._iter = iter(self.iterable)
        try:
            item = next(self._iter)
            self.update(1)
            return item
        except StopIteration:
            self.close()
            raise
    
    def update(self, n=1):
        self.n += n
        if self.total > 0:
            progress = min(self.n / self.total, 1.0)
            self.progress_bar.progress(progress)
        self._update_display()
    
    def _update_display(self):
        if self.total > 0:
            percentage = int((self.n / self.total) * 100)
            status = f"**{self.desc}** ({self.n}/{self.total} {self.unit})"
        else:
            status = f"**{self.desc}** ({self.n} {self.unit})"
        self.status_text.markdown(status)
    
    def close(self):
        if self.total > 0:
            self.progress_bar.progress(1.0)
        # We don't clear the text so the user sees what finished
        
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


class StreamlitLogger(Logger):
    """Logger that writes to Streamlit container."""
    
    def __init__(self, level: LogLevel = LogLevel.NORMAL, container=None):
        super().__init__(level)
        self.container = container
    
    def _log(self, emoji: str, msg: str, color: str = "black"):
        if self.container:
            self.container.markdown(f"{emoji} {msg}")
        else:
            st.write(f"{emoji} {msg}")

    def error(self, message: str, exc: Optional[Exception] = None) -> None:
        super().error(message, exc)
        details = f": {str(exc)}" if exc else ""
        if self.container:
            self.container.error(f"{message}{details}")
        else:
            st.error(f"{message}{details}")
    
    def warning(self, message: str) -> None:
        super().warning(message)
        if self.level.value >= LogLevel.NORMAL.value:
            if self.container:
                self.container.warning(message)
            else:
                st.warning(message)
    
    def info(self, message: str) -> None:
        super().info(message)
        if self.level.value >= LogLevel.NORMAL.value:
            self._log("ℹ️", message)
    
    def verbose(self, message: str) -> None:
        super().verbose(message)
        # Skip verbose in UI to keep it clean, unless requested?
        # For now let's skip to avoid clutter
        pass 
        
    def debug(self, message: str) -> None:
        super().debug(message)
        pass 


def check_gpu_status() -> tuple[bool, str]:
    try:
        gpu_info = GPUDetector.detect()
        if gpu_info.available:
            return True, f"GPU Active: {gpu_info.codec} ({gpu_info.hwaccel})"
        return False, "No GPU detected (Using CPU)"
    except Exception as e:
        return False, f"GPU Check Failed: {str(e)}"


def get_folder_path() -> Optional[str]:
    """Helper to open a local folder picker dialog."""
    try:
        import subprocess
        import tempfile
        import json
        
        # We run a tiny isolated script to open the dialog
        # This prevents main thread blocking issues in some envs
        script = """
import tkinter as tk
from tkinter import filedialog
import json
import sys

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
folder_path = filedialog.askdirectory(title="Select Folder")
print(json.dumps({"path": folder_path if folder_path else None}))
root.destroy()
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name
        
        try:
            result = subprocess.run(
                ["python", script_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(Path.cwd())
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                return data.get("path")
        finally:
            try: Path(script_path).unlink() 
            except: pass
    except Exception:
        pass
    return None


def main():
    st.set_page_config(
        page_title="Snapchat Memories Backuper",
        page_icon="📸",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    # Custom styling
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; }
        .stButton>button { width: 100%; border-radius: 8px; height: 3em; }
        .big-font { font-size: 1.2rem !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📸 Snapchat Memories Backuper")
    st.caption("Download, organize, and fix your Snapchat memories easily.")

    # -- STATE MANAGEMENT --
    if "input_folder" not in st.session_state: st.session_state.input_folder = ""
    if "output_folder" not in st.session_state: st.session_state.output_folder = ""
    if "metadata_html_path" not in st.session_state: st.session_state.metadata_html_path = None

    # -- TABS FOR MODES --
    tab_download, tab_folder = st.tabs(["☁️ Download (HTML)", "📂 Process Folder"])

    input_path = None
    process_mode = "html"
    metadata_html_provided = None

    # --- TAB 1: DOWNLOAD ---
    with tab_download:
        st.markdown("##### 1. Upload `memories_history.html`")
        st.info("Log in to accounts.snapchat.com → My Data → Submit Request. Download the ZIP and find the HTML file inside.")
        
        uploaded_file = st.file_uploader("Select File", type=['html'], label_visibility="collapsed")
        
        if uploaded_file:
            temp_path = Path("temp_memories_history.html")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            input_path = temp_path
            st.success(f"File loaded: {uploaded_file.name}")

    # --- TAB 2: FOLDER ---
    with tab_folder:
        process_mode = "folder"
        st.markdown("##### 1. Select Memories Folder")
        st.caption("Choose a folder that contains your `memories_history.html` or downloaded files.")
        
        col_f1, col_f2 = st.columns([3, 1])
        with col_f1:
            folder_input = st.text_input("Folder Path", value=st.session_state.input_folder, placeholder="C:\\Path\\To\\Memories", label_visibility="collapsed")
            if folder_input:
                st.session_state.input_folder = folder_input
        
        with col_f2:
            if HAS_TKINTER:
                if st.button("Browse..."):
                    path = get_folder_path()
                    if path:
                        st.session_state.input_folder = path
                        st.rerun()
        
        if st.session_state.input_folder:
            p = Path(st.session_state.input_folder)
            if p.exists() and p.is_dir():
                input_path = p
                st.success(f"Valid folder selected: {p.name}")
            else:
                st.error("Folder not found.")
        
        st.markdown("##### 2. (Optional) Metadata HTML")
        st.caption("If your folder doesn't have metadata, upload the HTML file here to apply dates/locations.")
        meta_file = st.file_uploader("Metadata HTML", type=['html'], key="meta_uploader")
        if meta_file:
            temp_meta = Path("temp_metadata.html")
            with open(temp_meta, "wb") as f:
                f.write(meta_file.getvalue())
            metadata_html_provided = temp_meta
            st.success("Metadata file loaded.")

    st.markdown("---")

    # -- OUTPUT SECTION (Shared) --
    st.markdown("##### 📍 Output Location")
    col_o1, col_o2 = st.columns([3, 1])
    with col_o1:
        out_input = st.text_input("Output Path", value=st.session_state.output_folder, placeholder="Output folder (leave empty for default)", label_visibility="collapsed")
        if out_input: st.session_state.output_folder = out_input
    with col_o2:
        if HAS_TKINTER:
            if st.button("Browse...", key="out_browse"):
                path = get_folder_path()
                if path:
                    st.session_state.output_folder = path
                    st.rerun()

    output_path = Path(st.session_state.output_folder).resolve() if st.session_state.output_folder else None


    # -- SETTINGS --
    with st.expander("⚙️ Advanced Settings"):
        gpu_ok, gpu_msg = check_gpu_status()
        st.caption(f"System Status: {gpu_msg}")
        
        c1, c2 = st.columns(2)
        with c1:
            use_gpu = st.checkbox("Use GPU Acceleration", value=gpu_ok, disabled=not gpu_ok)
            use_ffmpeg_gpu = st.checkbox("Force FFmpeg GPU", value=False, disabled=not gpu_ok, help="Experimental: Force full GPU piping.")
        with c2:

            dry_run = st.checkbox("Dry Run (Test Mode)", value=False)


    # -- RUN BUTTON --
    st.markdown("###")
    if st.button("🚀 Start Processing", type="primary"):
        # Validation
        current_tab_mode = "html" if input_path and input_path.is_file() else "folder"
        
        # If user is in Tab 1 but input_path is None
        if not input_path:
             st.error("Please select an input file or folder first.")
             return

        # Prepare Config
        cfg = AppConfig(
            dry_run=dry_run,
            input_path=input_path,
            output_dir=output_path,
            metadata_html=metadata_html_provided,
            use_gpu=use_gpu,
            use_ffmpeg_gpu=use_ffmpeg_gpu,

            verbose=True
        )

        st.markdown("---")
        status_container = st.container()
        
        # Setup Logging
        logger = StreamlitLogger(LogLevel.NORMAL, container=status_container)
        set_logger(logger)
        
        # Patch TQDM
        import snap_memories.download as dm
        import snap_memories.executors as em
        import snap_memories.metadata as mm
        import snap_memories.pipeline as pm
        
        # Save originals
        od, oe, om, op = dm.tqdm, em.tqdm, mm.tqdm, pm.tqdm
        
        # Patch
        dm.tqdm = StreamlitTqdm
        em.tqdm = StreamlitTqdm
        mm.tqdm = StreamlitTqdm
        pm.tqdm = StreamlitTqdm
        
        try:
            with st.spinner("Processing..."):
                pipeline = Pipeline(cfg)
                if current_tab_mode == "html" and input_path.suffix == ".html":
                    res = pipeline.run_download_mode(input_path)
                else:
                    res = pipeline.run_folder_mode(input_path)
                
                if res == 0:
                    st.success("✅ Task Completed Successfully!")
                    st.balloons()
                else:
                    st.error(f"❌ Completed with errors (Code {res})")
        except Exception as e:
            st.error(f"Error: {e}")
        finally:
            # Restore
            dm.tqdm, em.tqdm, mm.tqdm, pm.tqdm = od, oe, om, op

if __name__ == "__main__":
    main()
