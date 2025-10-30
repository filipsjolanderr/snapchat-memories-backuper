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


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Snapchat Memories Backuper",
        page_icon="📸",
        layout="centered",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FFFC00;
        text-align: center;
        margin-bottom: 1rem;
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
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #FFE600;
    }
    .main-content {
        max-width: 900px;
        margin: 0 auto;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<p class="main-header">📸 Snapchat Memories Backuper</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Download and organize your Snapchat Memories</p>', unsafe_allow_html=True)
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Mode selection - HTML is the default, folder mode is hidden
        mode = st.radio(
            "Input Mode",
            ["HTML File", "Folder"],
            help="HTML File: Downloads memories from URLs in HTML file\n\nFolder: Process files you've already downloaded"
        )
        
        # Warn about folder mode
        if mode == "Folder":
            st.warning("⚠️ Note: You must have already downloaded your memories to use this mode")
        
        # Performance settings
        st.subheader("🚀 Performance")
        gpu_available, gpu_status = check_gpu_status()
        if gpu_available:
            st.success(gpu_status)
        else:
            st.info(gpu_status)
        
        use_gpu = st.checkbox("Use GPU Acceleration", value=gpu_available, disabled=not gpu_available,
                              help="When enabled, automatically uses FFmpeg GPU pipeline for faster video processing")
        
        image_workers = st.slider("Image Workers", 1, 32, 8, 
                                  help="Number of parallel workers for image processing")
        video_workers = st.slider("Video Workers", 1, 16, 4,
                                  help="Number of parallel workers for video processing")
        download_workers = st.slider("Download Workers", 1, 64, 32,
                                     help="Number of parallel workers for downloads")
        metadata_workers = st.slider("Metadata Workers", 1, 32, 8,
                                     help="Number of parallel workers for metadata application")
        
        # Options
        st.subheader("📋 Options")
        dry_run = st.checkbox("Dry Run", value=False,
                             help="Preview actions without making changes")
        verbose = st.checkbox("Verbose Output", value=False,
                             help="Show detailed progress information")
        quiet = st.checkbox("Quiet Mode", value=False,
                           help="Suppress all output except errors")
    
    # Main content area - Step-by-step flow
    st.markdown("---")
    
    # Step 1: Input Selection
    st.subheader("Step 1: Select Input")
    st.caption("Choose your input file or folder")
    
    if mode == "HTML File":
        input_file = st.file_uploader(
            "Select memories_history.html file",
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
            st.session_state.input_file_name = input_file.name  # Store original name
            input_path = temp_path
            st.success(f"✅ File loaded: `{input_file.name}`")
        else:
            st.info("💡 Upload your `memories_history.html` file from your Snapchat data export")
            # Clear stored filename if no file is selected
            if "input_file_name" in st.session_state:
                del st.session_state.input_file_name
        metadata_path = None
    else:
        # Folder mode - hidden in collapsed expander
        with st.expander("📂 Folder Processing Mode", expanded=False):
            st.info("⚠️ **Note**: You must have already downloaded your memories to use this mode")
            input_folder = st.text_input(
                "Folder Path",
                value="",
                help="Enter the path to the folder containing your memories"
            )
            input_path = Path(input_folder) if input_folder else None
            
            # Metadata file (for folder mode)
            metadata_path: Optional[Path] = None
            metadata_option = st.radio(
                "Metadata File",
                ["None", "Upload HTML file", "Specify path"],
                help="Optional: Provide memories_history.html for metadata"
            )
            
            if metadata_option == "Upload HTML file":
                metadata_file = st.file_uploader(
                    "Select metadata HTML file",
                    type=['html'],
                    key="metadata_upload"
                )
                if metadata_file is not None:
                    temp_path = Path("temp_metadata.html")
                    with open(temp_path, "wb") as f:
                        f.write(metadata_file.getvalue())
                    st.session_state.temp_metadata_path = temp_path
                    metadata_path = temp_path
                    st.success(f"✅ Metadata file loaded: {metadata_file.name}")
            elif metadata_option == "Specify path":
                metadata_input = st.text_input("Metadata HTML File Path", key="metadata_path")
                if metadata_input:
                    metadata_path = Path(metadata_input)
    
    # Show input status
    if input_path and not input_path.exists():
        st.warning(f"⚠️ Input path not found: `{input_path}`")
    
    st.markdown("---")
    
    # Step 2: Output Selection
    st.subheader("Step 2: Select Output Folder")
    st.caption("Choose where to save your processed memories")
    
    # Initialize session state for output folder
    if "output_folder" not in st.session_state:
        st.session_state.output_folder = ""
    
    # Browse button - primary method
    if HAS_TKINTER:
        col_browse1, col_browse2, col_browse3 = st.columns([1, 1, 1])
        with col_browse2:
            browse_clicked = st.button("📁 Browse folder", use_container_width=True,
                                      help="Open folder browser to select output folder",
                                      type="secondary")
        
        if browse_clicked:
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

folder_path = filedialog.askdirectory(title="Select Output Folder")
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
                        import json
                        data = json.loads(result.stdout.strip())
                        if data.get("path"):
                            folder_path = data["path"]
                            st.session_state.output_folder = folder_path
                            if "output_folder_input" in st.session_state:
                                del st.session_state.output_folder_input
                            st.rerun()
                finally:
                    try:
                        Path(script_path).unlink()
                    except:
                        pass
            except Exception as e:
                st.error(f"Could not open folder browser: {str(e)}")
    else:
        st.info("💡 Tip: Copy the folder path from Windows Explorer and paste it below")
    
    # Text input for manual entry
    output_dir = st.text_input(
        "Output Folder Path",
        value=st.session_state.output_folder,
        help="Enter folder path or leave empty for default 'output/' folder",
        key="output_folder_input",
        placeholder="Enter folder path or click Browse..."
    )
    
    if output_dir:
        st.session_state.output_folder = output_dir
    
    # Show selected folder below the input
    if st.session_state.output_folder:
        st.info(f"📁 **Selected output folder:** `{st.session_state.output_folder}`")
        output_dir = st.session_state.output_folder
    else:
        output_dir = None
        current_dir = Path.cwd()
        st.caption(f"💡 Default: `{current_dir / 'output'}`")
    
    # Show folder status
    if output_dir:
        output_path = Path(output_dir).resolve()
        try:
            test_path = Path(output_dir)
            if test_path.exists() and test_path.is_dir():
                st.success(f"✅ Output folder ready")
            elif test_path.exists() and test_path.is_file():
                st.warning(f"⚠️ Path exists but is a file, not a folder")
            else:
                st.info(f"ℹ️ Folder will be created at this location")
        except Exception as e:
            st.error(f"❌ Invalid path: {str(e)}")
    else:
        output_path = None
    
    st.markdown("---")
    
    # Step 3: Start Processing
    st.subheader("Step 3: Start Processing")
    st.caption("Review your settings and click to begin")
    
    # Show summary before processing
    if input_path and input_path.exists():
        summary_col1, summary_col2 = st.columns(2)
        with summary_col1:
            # Show original filename if available, otherwise show path
            if mode == "HTML File" and "input_file_name" in st.session_state:
                display_name = st.session_state.input_file_name
            else:
                display_name = input_path.name if input_path.is_file() else str(input_path)
            st.info(f"📥 **Input:** `{display_name}`")
        with summary_col2:
            if output_path:
                st.info(f"📤 **Output:** `{output_path}`")
            else:
                st.info(f"📤 **Output:** Default folder")
    
    if st.button("🚀 Start Processing", type="primary", use_container_width=True):
        if input_path is None or not input_path.exists():
            st.error("❌ Please select a valid input file or folder")
            return
        
        # Validate metadata path if provided
        if metadata_path is not None and not metadata_path.exists():
            st.error(f"❌ Metadata file not found: {metadata_path}")
            return
        
        # Initialize logger
        log_level = LogLevel.VERBOSE if verbose else (LogLevel.QUIET if quiet else LogLevel.NORMAL)
        logger = StreamlitLogger(log_level)
        set_logger(logger)
        
        # Build configuration
        # When GPU is enabled, automatically use FFmpeg GPU pipeline (faster than MoviePy)
        cfg = AppConfig(
            dry_run=dry_run,
            image_workers=image_workers,
            video_workers=video_workers,
            download_workers=download_workers,
            metadata_workers=metadata_workers,
            use_gpu=use_gpu,
            use_ffmpeg_gpu=use_gpu,  # Auto-enable FFmpeg GPU when GPU is enabled
            verbose=verbose,
            quiet=quiet,
            input_path=input_path.resolve(),
            output_dir=output_path,
            metadata_html=metadata_path.resolve() if metadata_path else None,
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
                    st.success("✅ Processing complete!")
                    
                    # Show output directory
                    final_output = cfg.output_dir if cfg.output_dir else cfg.input_path.parent / "output"
                    if final_output.exists():
                        st.info(f"📁 Output folder: {final_output}")
                        st.success(f"✅ Files saved to: {final_output.absolute()}")
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
    
    # Instructions
    with st.expander("📖 Instructions"):
        st.markdown("""
        ### Getting Your Snapchat Data
        
        1. **Request Your Data**: 
           - Open Snapchat → Profile → Settings → My Data
           - Check "Export Your Memories" and set date range to "All Time"
           - Submit request and wait for email (2-3 hours usually)
        
        2. **Download & Extract**:
           - Download the ZIP file from the email
           - Extract it to a folder
        
        3. **Use This Tool**:
           - **HTML Mode**: Upload the `memories_history.html` file to download all memories
           - **Folder Mode**: Point to the folder containing your downloaded memories
        
        ### Features
        
        - ✅ Automatic download from HTML file
        - ✅ ZIP file extraction and processing
        - ✅ Image/video combining with overlays
        - ✅ Metadata application (date, location)
        - ✅ GPU acceleration support
        - ✅ Parallel processing for fast performance
        
        ### Tips
        
        - Use **Dry Run** first to preview what will happen
        - Increase workers for faster processing (if you have enough RAM)
        - Enable GPU acceleration if available for faster video processing
        - Leave output folder empty to use default location
        """)


if __name__ == "__main__":
    main()
