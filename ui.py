"""
Streamlit UI for Snapchat Memories Backuper
"""
from pathlib import Path
from typing import Optional

import streamlit as st

# Try to import tkinter for folder selection (works on Windows/Linux, not macOS headless)
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
    """Streamlit-compatible tqdm wrapper that displays progress bars in the UI."""
    
    def __init__(self, iterable=None, total=None, desc=None, unit=None, **kwargs):
        self.iterable = iterable
        self.total = total if total is not None else (len(iterable) if iterable else 0)
        self.desc = desc or ""
        self.unit = unit or "it"
        self.n = 0
        self.progress_bar = None
        self.status_text = None
        self._iter = None
        
        # Create progress bar and status text
        # These will be displayed in the progress container
        self.progress_bar = st.progress(0.0)
        self.status_text = st.empty()
        
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
        """Update progress by n."""
        self.n += n
        if self.total > 0:
            progress = min(self.n / self.total, 1.0)
            self.progress_bar.progress(progress)
        self._update_display()
    
    def _update_display(self):
        """Update the status text display."""
        if self.total > 0:
            percentage = int((self.n / self.total) * 100)
            status = f"**{self.desc}**: {self.n}/{self.total} {self.unit} ({percentage}%)"
        else:
            status = f"**{self.desc}**: {self.n} {self.unit}"
        self.status_text.markdown(status)
    
    def close(self):
        """Close the progress bar."""
        if self.total > 0:
            self.progress_bar.progress(1.0)
            self.status_text.markdown(f"**{self.desc}**: Complete ✓")
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


class StreamlitLogger(Logger):
    """Logger that writes to Streamlit as well as stdout/stderr."""
    
    def __init__(self, level: LogLevel = LogLevel.NORMAL):
        super().__init__(level)
        self.messages = []
        self.error_messages = []
    
    def error(self, message: str, exc: Optional[Exception] = None) -> None:
        """Print error message to Streamlit."""
        super().error(message, exc)
        error_details = ""
        if exc:
            error_msg = str(exc).strip()
            if error_msg:
                error_details = f": {error_msg}"
        error_text = f"❌ Error: {message}{error_details}"
        self.error_messages.append(error_text)
        st.error(error_text)
    
    def warning(self, message: str) -> None:
        """Print warning message to Streamlit."""
        super().warning(message)
        if self.level.value >= LogLevel.NORMAL.value:
            warning_text = f"⚠️ Warning: {message}"
            self.messages.append(warning_text)
            st.warning(warning_text)
    
    def info(self, message: str) -> None:
        """Print info message to Streamlit."""
        super().info(message)
        if self.level.value >= LogLevel.NORMAL.value:
            self.messages.append(message)
            st.info(message)
    
    def verbose(self, message: str) -> None:
        """Print verbose message to Streamlit."""
        super().verbose(message)
        if self.level.value >= LogLevel.VERBOSE.value:
            verbose_text = f"[verbose] {message}"
            self.messages.append(verbose_text)
            st.text(verbose_text)
    
    def debug(self, message: str) -> None:
        """Print debug message to Streamlit."""
        super().debug(message)
        if self.level.value >= LogLevel.DEBUG.value:
            debug_text = f"[debug] {message}"
            self.messages.append(debug_text)
            st.text(debug_text)
    
    def dry_run(self, message: str) -> None:
        """Print dry-run message to Streamlit."""
        super().dry_run(message)
        if self.level != LogLevel.QUIET:
            dry_run_text = f"DRY RUN: {message}"
            self.messages.append(dry_run_text)
            st.info(dry_run_text)


def check_gpu_status() -> tuple[bool, str]:
    """Check GPU availability and return status."""
    try:
        gpu_info = GPUDetector.detect()
        if gpu_info.available:
            return True, f"GPU available: {gpu_info.codec} ({gpu_info.hwaccel})"
        return False, "GPU not available, using CPU encoding"
    except Exception as e:
        return False, f"Could not detect GPU: {str(e)}"


def get_folder_path() -> Optional[str]:
    """Get folder path using tkinter dialog."""
    try:
        import subprocess
        import tempfile
        import json
        
        script = """
import tkinter as tk
from tkinter import filedialog
import json
import sys

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)

folder_path = filedialog.askdirectory(title="Select Folder")
if folder_path:
    print(json.dumps({"path": folder_path}))
else:
    print(json.dumps({"path": None}))
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
                timeout=30,
                cwd=str(Path.cwd())
            )
            
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                return data.get("path")
        finally:
            try:
                Path(script_path).unlink()
            except:
                pass
    except Exception:
        pass
    return None


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Snapchat Memories Backuper",
        page_icon="📸",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FFFC00;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #FFFC00;
        color: #000;
        font-weight: bold;
        border-radius: 5px;
        padding: 0.75rem 1rem;
        font-size: 1.1rem;
    }
    .stButton>button:hover {
        background-color: #FFE600;
    }
    /* Hide deploy button */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<p class="main-header">📸 Snapchat Memories Backuper</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Download and organize your Snapchat Memories</p>', unsafe_allow_html=True)
    
    # Initialize session state
    if "output_folder" not in st.session_state:
        st.session_state.output_folder = ""
    if "advanced_mode" not in st.session_state:
        st.session_state.advanced_mode = False
    
    # Advanced mode toggle at the top
    col_toggle, _ = st.columns([1, 3])
    with col_toggle:
        advanced_mode = st.checkbox("⚙️ Advanced Mode", value=st.session_state.advanced_mode, key="advanced_checkbox")
        st.session_state.advanced_mode = advanced_mode
    
    # Main 2-column layout
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("### 📄 Select Your Memories File")
        st.markdown("Upload your `memories_history.html` file from your Snapchat data export")
        
        input_file = st.file_uploader(
            "Choose memories_history.html file",
            type=['html'],
            help="Upload the memories_history.html file from your Snapchat data export",
            label_visibility="collapsed"
        )
        
        input_path: Optional[Path] = None
        if input_file is not None:
            # Save uploaded file temporarily
            temp_path = Path("temp_memories_history.html")
            with open(temp_path, "wb") as f:
                f.write(input_file.getvalue())
            st.session_state.temp_html_path = temp_path
            st.session_state.input_file_name = input_file.name
            input_path = temp_path
            st.success(f"✅ **File loaded:** `{input_file.name}`")
        else:
            st.info("💡 **How to get your file:**\n\n1. Open Snapchat → Profile → Settings → My Data\n2. Request your data export\n3. Download and extract the ZIP file\n4. Find `memories_history.html` inside")
            if "input_file_name" in st.session_state:
                del st.session_state.input_file_name
    
    with col_right:
        st.markdown("### 📁 Where to Save Your Memories")
        st.markdown("Choose where you want your memories saved")
        
        # Browse button (if available) or text input (fallback)
        if HAS_TKINTER:
            browse_clicked = st.button("📂 Browse Folder", use_container_width=True, type="secondary")
            
            if browse_clicked:
                folder_path = get_folder_path()
                if folder_path:
                    st.session_state.output_folder = folder_path
                    st.rerun()
        else:
            # Show text input as fallback when folder browser is not available
            st.info("💡 Enter the folder path manually below")
            output_dir = st.text_input(
                "Save memories to folder",
                value=st.session_state.output_folder,
                help="Enter folder path or leave empty for default 'output/' folder",
                key="output_folder_input",
                placeholder="C:\\Users\\YourName\\Pictures\\Memories"
            )
            
            if output_dir:
                st.session_state.output_folder = output_dir
        
        # Show selected folder
        if st.session_state.output_folder:
            output_path = Path(st.session_state.output_folder).resolve()
            st.success(f"✅ **Will save to:** `{output_path}`")
        else:
            output_path = None
            current_dir = Path.cwd()
            if HAS_TKINTER:
                st.info(f"💡 **Default location:** `{current_dir / 'output'}`\n\nClick 'Browse Folder' to choose a different location.")
            else:
                st.info(f"💡 **Default location:** `{current_dir / 'output'}`\n\nOr enter a path above to use a different location.")
    
    # Advanced settings (collapsed by default)
    if advanced_mode:
        with st.expander("⚙️ Advanced Settings", expanded=True):
            col_adv1, col_adv2 = st.columns(2)
            
            with col_adv1:
                st.subheader("🚀 Performance")
                gpu_available, gpu_status = check_gpu_status()
                if gpu_available:
                    st.success(gpu_status)
                else:
                    st.info(gpu_status)
                
                use_gpu = st.checkbox("Use GPU Acceleration", value=gpu_available, disabled=not gpu_available,
                                      help="Faster video processing if GPU is available")
                
                image_workers = st.slider("Image Workers", 1, 32, 8, 
                                          help="Number of parallel workers for image processing")
                video_workers = st.slider("Video Workers", 1, 16, 4,
                                          help="Number of parallel workers for video processing")
                download_workers = st.slider("Download Workers", 1, 64, 32,
                                             help="Number of parallel workers for downloads")
                metadata_workers = st.slider("Metadata Workers", 1, 32, 8,
                                             help="Number of parallel workers for metadata application")
            
            with col_adv2:
                st.subheader("📋 Options")
                dry_run = st.checkbox("Dry Run", value=False,
                                     help="Preview actions without making changes")
                verbose = st.checkbox("Verbose Output", value=False,
                                     help="Show detailed progress information")
                quiet = st.checkbox("Quiet Mode", value=False,
                                   help="Suppress all output except errors")
    else:
        # Use defaults for non-advanced mode
        gpu_available, _ = check_gpu_status()
        use_gpu = gpu_available
        image_workers = 8
        video_workers = 4
        download_workers = 32
        metadata_workers = 8
        dry_run = False
        verbose = False
        quiet = False
    
    # Start button
    st.markdown("---")
    col_btn, _ = st.columns([1, 3])
    with col_btn:
        start_clicked = st.button("🚀 Start Backup", type="primary", use_container_width=True)
    
    if start_clicked:
        if input_path is None or not input_path.exists():
            st.error("❌ **Please select your memories_history.html file first**")
            return
        
        # Initialize logger
        log_level = LogLevel.VERBOSE if verbose else (LogLevel.QUIET if quiet else LogLevel.NORMAL)
        logger = StreamlitLogger(log_level)
        set_logger(logger)
        
        # Build configuration
        cfg = AppConfig(
            dry_run=dry_run,
            image_workers=image_workers,
            video_workers=video_workers,
            download_workers=download_workers,
            metadata_workers=metadata_workers,
            use_gpu=use_gpu,
            use_ffmpeg_gpu=use_gpu,
            verbose=verbose,
            quiet=quiet,
            input_path=input_path.resolve(),
            output_dir=output_path,
            metadata_html=None,
        )
        
        # Create progress container
        progress_container = st.container()
        
        with progress_container:
            st.info("🔄 Processing... Please wait")
            
            # Replace tqdm with StreamlitTqdm for this run
            import snap_memories.download as download_module
            import snap_memories.executors as executors_module
            import snap_memories.metadata as metadata_module
            import snap_memories.pipeline as pipeline_module
            
            # Save original tqdm references
            original_download_tqdm = getattr(download_module, 'tqdm', None)
            original_executors_tqdm = getattr(executors_module, 'tqdm', None)
            original_metadata_tqdm = getattr(metadata_module, 'tqdm', None)
            original_pipeline_tqdm = getattr(pipeline_module, 'tqdm', None)
            
            # Patch tqdm in all modules
            download_module.tqdm = StreamlitTqdm
            executors_module.tqdm = StreamlitTqdm
            metadata_module.tqdm = StreamlitTqdm
            pipeline_module.tqdm = StreamlitTqdm
            
            try:
                # Run pipeline
                pipeline = Pipeline(cfg)
                exit_code = pipeline.run_auto()
                
                if exit_code == 0:
                    st.success("✅ **Processing complete!**")
                    
                    # Show output directory
                    final_output = cfg.output_dir if cfg.output_dir else cfg.input_path.parent / "output"
                    if final_output.exists():
                        st.info(f"📁 **Files saved to:** `{final_output.absolute()}`")
                else:
                    st.error(f"❌ Processing failed with exit code: {exit_code}")
                    
            except KeyboardInterrupt:
                st.warning("⚠️ Operation cancelled by user")
            except Exception as e:
                st.error(f"❌ Unexpected error occurred: {str(e)}")
                if verbose:
                    st.exception(e)
            finally:
                # Restore original tqdm
                if original_download_tqdm is not None:
                    download_module.tqdm = original_download_tqdm
                if original_executors_tqdm is not None:
                    executors_module.tqdm = original_executors_tqdm
                if original_metadata_tqdm is not None:
                    metadata_module.tqdm = original_metadata_tqdm
                if original_pipeline_tqdm is not None:
                    pipeline_module.tqdm = original_pipeline_tqdm


if __name__ == "__main__":
    main()
