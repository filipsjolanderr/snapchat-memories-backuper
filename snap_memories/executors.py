from __future__ import annotations

import atexit
import os
import platform
import shutil
import signal
import subprocess
import threading
import warnings
import zipfile
# Add max_workers to ThreadPoolExecutor imports or logic
from concurrent.futures import as_completed, TimeoutError as FutureTimeoutError
from .utils import StreamlitThreadPoolExecutor as ThreadPoolExecutor
from pathlib import Path
from typing import List, Set, Tuple, Optional

# ... imports ...
from PIL import Image, PngImagePlugin
# Keep moviepy for fallback or if we decide to keep it, but we prefer ffmpeg
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip
from proglog import TqdmProgressBarLogger
from tqdm import tqdm

# ... warnings ...
warnings.filterwarnings(
    "ignore",
    message=".*bytes wanted but.*bytes read.*",
    category=UserWarning,
    module="moviepy.video.io.ffmpeg_reader",
)

from .config import AppConfig
from .ffmpeg import get_ffmpeg_path
from .logger import dry_run as log_dry_run, verbose, warning
from .models import CombinePlan, MemoryKind, RenamePlan
from .models import CopyPlan, ExtractZipPlan
# ... metadata imports ...
from .metadata import (
    apply_metadata_to_outputs,
    parse_memories_html,
    write_exif_to_jpeg,
)
from .utils import ensure_dir

# Global set to track active FFmpeg processes for cleanup on interrupt
_active_ffmpeg_processes: Set[subprocess.Popen] = set()
_process_lock = threading.Lock()

def _cleanup_ffmpeg_processes():
    """Terminate all active FFmpeg processes."""
    with _process_lock:
        for proc in _active_ffmpeg_processes.copy():
            try:
                if proc.poll() is None:  # Process is still running
                    if platform.system() == "Windows":
                        # On Windows, use taskkill to terminate process tree
                        try:
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                capture_output=True,
                                timeout=5
                            )
                        except Exception:
                            # Fallback to terminate if taskkill fails
                            proc.terminate()
                    else:
                        # On Unix, terminate the process group
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                        except (ProcessLookupError, OSError):
                            # Process already dead or no process group
                            proc.terminate()
                    
                    # Wait briefly, then kill if still running
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            except Exception:
                pass  # Ignore errors during cleanup
        _active_ffmpeg_processes.clear()

def _signal_handler(signum, frame):
    """Handle interrupt signals (Ctrl+C) by cleaning up FFmpeg processes."""
    _cleanup_ffmpeg_processes()
    # Re-raise the signal to allow normal cleanup
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)

if platform.system() != "Windows":
    # Unix-like systems
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
else:
    # Windows - register cleanup on exit
    atexit.register(_cleanup_ffmpeg_processes)
    try:
        import ctypes
        HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
        def windows_ctrl_handler(dwCtrlType):
            if dwCtrlType in (0, 2):  # CTRL_C_EVENT or CTRL_CLOSE_EVENT
                _cleanup_ffmpeg_processes()
                return False
            return False
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCtrlHandler(HandlerRoutine(windows_ctrl_handler), True)
    except Exception:
        pass


class ZipService:
    def __init__(self) -> None:
        self._merge_lock = threading.Lock()

    def run(self, plans: List[ExtractZipPlan], dry_run: bool) -> int:
        if not plans:
            return 0
        if dry_run:
            for p in plans:
                log_dry_run(
                    f"would extract '{p.zip_path}' → '{p.dest_folder}'"
                )
            return 0
        
    def extract_one(self, p: ExtractZipPlan) -> Optional[List[Path]]:
        """Extract a single ZIP file atomically. Returns list of extracted paths on success, None on failure."""
        
        # Atomic extraction: extract to unique .tmp folder first
        import uuid
        unique_name = f"{p.zip_path.stem}_{uuid.uuid4().hex[:8]}"
        tmp_extract_path = p.dest_folder / f".tmp_extract_{unique_name}"
        
        extracted_paths: List[Path] = []
        
        try:
            if tmp_extract_path.exists():
                shutil.rmtree(tmp_extract_path, ignore_errors=True)
            
            tmp_extract_path.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(p.zip_path, "r") as zf:
                zf.extractall(tmp_extract_path)
                verbose(f"DEBUG_ZIP: Extracted {p.zip_path.name} to {tmp_extract_path}")
            
            # Lock for merging into shared destination
            with self._merge_lock:
                p.dest_folder.mkdir(parents=True, exist_ok=True)
                
                # ... (inner function _merge_directories omitted/kept same)
                def _merge_directories(src: Path, dst: Path):
                    if not dst.exists():
                        dst.mkdir(parents=True, exist_ok=True)
                    for item in src.iterdir():
                        dst_item = dst / item.name
                        if item.is_dir():
                            _merge_directories(item, dst_item)
                        else:
                            if dst_item.exists():
                                try:
                                    if dst_item.is_dir():
                                        shutil.rmtree(dst_item)
                                    else:
                                        dst_item.unlink()
                                except OSError:
                                    pass
                            shutil.move(str(item), str(dst_item))

                items = list(tmp_extract_path.iterdir())
                verbose(f"DEBUG_ZIP: Found {len(items)} items in temp: {[i.name for i in items]}")

                for item in items:
                    dst_path = p.dest_folder / item.name
                    if item.is_dir():
                        _merge_directories(item, dst_path)
                        if dst_path.exists():
                            try:
                                if dst_path.is_dir():
                                    shutil.rmtree(dst_path)
                                else:
                                    dst_path.unlink()
                            except OSError:
                                pass
                        shutil.move(str(item), str(dst_path))
                        extracted_paths.append(dst_path)
                    else:
                        # Handle file
                        if dst_path.exists():
                            try: dst_path.unlink()
                            except: pass
                        shutil.move(str(item), str(dst_path))
                        extracted_paths.append(dst_path)
                        verbose(f"DEBUG_ZIP: Moved {item.name} to {dst_path}")
            
            # Cleanup
            shutil.rmtree(tmp_extract_path, ignore_errors=True)
            return extracted_paths
            
        except Exception as e:
            warning(f"Failed to extract '{p.zip_path.name}': {e}")
            if tmp_extract_path.exists():
                shutil.rmtree(tmp_extract_path, ignore_errors=True)
            # Re-raise to allow caller to handle error state
            raise e

    def run(self, plans: List[ExtractZipPlan], dry_run: bool) -> int:
        if not plans:
            return 0
        if dry_run:
            for p in plans:
                log_dry_run(
                    f"would extract '{p.zip_path}' → '{p.dest_folder}'"
                )
            return 0
        
        count = 0
        skipped = 0
        
        # Helper wrapper for compatibility with existing run logic
        def _safe_extract(p):
            try:
                return self.extract_one(p)
            except Exception:
                return None

        # Use ThreadPoolExecutor for IO-bound zip extraction
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
            futures = {executor.submit(_safe_extract, p): p for p in plans}
            for f in tqdm(as_completed(futures), total=len(plans), desc="Extracting ZIPs", unit="zip"):
                res = f.result()
                if res is not None:
                    count += 1
                else:
                    skipped += 1
                    
        if skipped > 0:
            verbose(f"Skipped {skipped} already extracted ZIP files")
        return count


class CopyService:
    def run(self, plans: List[CopyPlan], dry_run: bool, desc: str = "Copying MP4s") -> int:
        if not plans:
            return 0
        if dry_run:
            for p in plans:
                log_dry_run(f"would copy '{p.src}' → '{p.dst}'")
            return len(plans)
            
        done = 0
        
    def copy_one(self, p: CopyPlan) -> bool:
        """Copy a single file atomically. Returns True on success, False on failure/skip."""
        if p.dst.exists():
            return False
        
        # Atomic copy
        tmp_dst = p.dst.with_suffix(p.dst.suffix + ".tmp")
        try:
            p.dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p.src, tmp_dst)
            
            if p.dst.exists():
                 tmp_dst.unlink()
                 return False
                 
            tmp_dst.replace(p.dst)
            return True
        except Exception as e:
            warning(f"Failed to copy '{p.src.name}': {e}")
            if tmp_dst.exists():
                try: tmp_dst.unlink()
                except: pass
            raise e

    def run(self, plans: List[CopyPlan], dry_run: bool, desc: str = "Copying MP4s") -> int:
        if not plans:
            return 0
        if dry_run:
            for p in plans:
                log_dry_run(f"would copy '{p.src}' → '{p.dst}'")
            return len(plans)
            
        done = 0
        
        def _safe_copy(p):
            try:
                return self.copy_one(p)
            except Exception:
                return False

        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
            futures = {executor.submit(_safe_copy, p): p for p in plans}
            for f in tqdm(as_completed(futures), total=len(plans), desc=desc, unit="file"):
                if f.result():
                    done += 1
        return done


class RenameService:
    def run(self, plans: List[RenamePlan], dry_run: bool) -> int:
        if not plans:
            return 0
        if dry_run:
            for p in plans:
                log_dry_run(f"would rename '{p.src}' → '{p.dst}'")
            return len(plans)
            
        done = 0
        
        def _rename(p: RenamePlan):
            if p.dst.exists():
                return False
                
            # Atomic copy (rename is essentially copy+delete for safety, 
            # though os.replace is atomic on POSIX, on different FS it copies.
            # Using copy2 + delete src is safer for cross-fs moves if needed, 
            # but here plans are usually same drive. We'll use copy2 to .tmp then rename.)
            
            tmp_dst = p.dst.with_suffix(p.dst.suffix + ".tmp")
            try:
                p.dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p.src, tmp_dst)
                
                if p.dst.exists():
                    tmp_dst.unlink()
                    return False
                
                tmp_dst.replace(p.dst)
                # Note: We don't delete source here because 'RenameService' in this pipeline 
                # is actually used as 'Copy to unified structure'. 
                # 'RenamePlan' implies logical rename, but underlying implementation usually copies.
                # If we truly want to move, we should unlink src.
                # However, looking at the usage, it seems these are often used for "fixing" names.
                # Let's stick to copy-based "rename" as implemented before (shutil.copy2).
                return True
            except OSError:
                if tmp_dst.exists():
                    try: tmp_dst.unlink()
                    except: pass
                return False

        with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
            futures = {executor.submit(_rename, p): p for p in plans}
            for f in tqdm(as_completed(futures), total=len(plans), desc="Fixing unnamed files", unit="file"):
                if f.result():
                    done += 1
        return done


class CombineService:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        # Check if ffmpeg is available
        self.ffmpeg_available = False
        try:
            subprocess.run([get_ffmpeg_path(), "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            self.ffmpeg_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.ffmpeg_available = False

    def _is_valid_overlay(self, overlay_path: Path) -> bool:
        """Check if overlay is a valid image file."""
        if not overlay_path.exists() or overlay_path.stat().st_size == 0:
            return False
        try:
            with Image.open(overlay_path) as img:
                img.verify()
            return True
        except Exception:
            return False

    def _fallback_copy(self, main_path: Path, out_path: Path, dry: bool, reason: str) -> None:
        """Fallback to copying main file when combination fails."""
        if dry:
            log_dry_run(f"would copy '{main_path}' → '{out_path}' (fallback: {reason})")
            return
            
        warning(f"Overlay issue: {reason}. Falling back to original.")
        
        if out_path.exists():
            return

        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_out = out_path.with_suffix(".tmp" + out_path.suffix)
        
        try:
            shutil.copy2(main_path, tmp_out)
            if out_path.exists():
                tmp_out.unlink()
            else:
                tmp_out.replace(out_path)
        except Exception:
            if tmp_out.exists():
                try: tmp_out.unlink()
                except: pass
            raise

    def combine_image(
        self, main_path: Path, overlay_path: Path, out_path: Path, dry: bool
    ) -> None:
        if not self._is_valid_overlay(overlay_path):
            self._fallback_copy(main_path, out_path, dry, f"Corrupt/Invalid overlay '{overlay_path.name}'")
            return

        if dry:
            log_dry_run(
                f"would combine image "
                f"'{main_path}' + '{overlay_path}' → '{out_path}'"
            )
            return
            
        if out_path.exists():
            return
            
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_out = out_path.with_suffix(".tmp" + out_path.suffix)

        # Overlay is already verified by _is_valid_overlay check above
        
        try:
            main = Image.open(main_path).convert("RGBA")
            overlay = Image.open(overlay_path).convert("RGBA")
            if overlay.size != main.size:
                overlay = overlay.resize(main.size, Image.LANCZOS)
            combined = Image.alpha_composite(main, overlay)

            rgb = Image.new("RGB", combined.size, (255, 255, 255))
            if combined.mode == "RGBA":
                rgb.paste(combined, mask=combined.split()[-1])
            else:
                rgb.paste(combined)
            
            rgb.save(tmp_out, "JPEG", quality=95, optimize=False, progressive=True)
            if out_path.exists():
                tmp_out.unlink()
            else:
                tmp_out.replace(out_path)
        except Exception as e:
            if tmp_out.exists():
                try: tmp_out.unlink()
                except: pass
            # Fallback on processing error too?
            # Maybe safer to let unexpected processing errors raise, 
            # but here we are specifically targeting overlay issues.
            # If main image is corrupt, we probably can't copy it either or it's garbage.
            raise e
        finally:
            # Clean up potentially open resources (handled by context managers mostly now if we used them, 
            # but Image.open returns object)
            try: main.close()
            except: pass
            try: overlay.close()
            except: pass
            try: combined.close()
            except: pass
            try: rgb.close()
            except: pass


    def _get_preset(self, codec: str) -> str:
        """Get the FFmpeg preset for the given codec."""
        if codec == "libx264":
            # "veryfast" is a good balance for backup/archive where speed matters
            # "ultrafast" is faster but larger files
            return "veryfast"
        return "medium"

    def _ffmpeg_overlay(
        self, main_path: Path, overlay_path: Path, out_path: Path
    ) -> None:
        codec = "libx264"
        preset = self._get_preset(codec)
        
        # Calculate optimal threads per FFmpeg process
        # We want to avoid oversubscribing the CPU
        # If we have N workers and C cores, threads ≈ C/N
        import os
        cpu_count = os.cpu_count() or 4
        # self.cfg.video_workers is the target concurrency
        # Ensure at least 1 thread
        threads = max(1, cpu_count // max(1, self.cfg.video_workers))
        
        try:
            self._try_ffmpeg_encode(
                main_path, overlay_path, out_path, 
                codec, preset, None, None, threads=str(threads)
            )
        except (subprocess.TimeoutExpired, RuntimeError, subprocess.CalledProcessError) as e:
            raise RuntimeError(f"Encoding failed: {e}") from e

    def _try_ffmpeg_encode(
        self, main_path: Path, overlay_path: Path, out_path: Path,
        codec: str, preset: str, hwaccel: str | None, hwaccel_output_format: str | None,
        threads: str = "0"
    ) -> None:
        cmd = [get_ffmpeg_path(), "-y"]
        
        if hwaccel:
            cmd.extend(["-hwaccel", hwaccel])
        
        cmd.extend([
            "-i", str(main_path),
            "-loop", "1",
            "-i", str(overlay_path),
            "-filter_complex",
            (
                "[1:v]format=rgba[olorig];"
                "[olorig][0:v]scale2ref=w=iw:h=ih[ol][base];"
                "[base][ol]overlay=0:0[overlaid];"
                "[overlaid]format=yuv420p[v]"
            ),
            "-map", "[v]",
            "-shortest",
            "-map", "0:a?",
            "-c:v", codec,
        ])
        
        # Optimization flags
        if codec == "libx264":
            cmd.extend(["-preset", preset, "-tune", "fastdecode", "-profile:v", "baseline"])
        
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100", 
            "-ac", "2",
            "-movflags", "+faststart",
            "-threads", threads, 
            str(out_path),
        ])
        
        proc = None
        try:
            timeout = 600
            
            creation_flags = 0
            if platform.system() == "Windows":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    stdin=subprocess.DEVNULL,  # Prevent hanging on input
                    text=True, creationflags=creation_flags
                )
            else:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                    stdin=subprocess.DEVNULL,  # Prevent hanging on input
                    text=True, preexec_fn=os.setsid
                )
            
            with _process_lock:
                _active_ffmpeg_processes.add(proc)
            
            # Simple communicate logic for now, AMF workaround is complex and maybe specific
            # Keeping the simple logic for clarity unless we really need the AMF polling
            stdout, stderr = proc.communicate(timeout=timeout)
            
            with _process_lock:
                 _active_ffmpeg_processes.discard(proc)
                 
            if proc.returncode != 0:
                # FFmpeg stderr can be huge. We want the actual error at the end.
                msg = ""
                if stderr:
                    lines = stderr.strip().split("\n")
                    msg = "\n".join(lines[-10:])
                else:
                    msg = "Unknown error (no stderr output)"
                raise RuntimeError(f"FFmpeg failed (codec={codec}): {msg}")
                
        except KeyboardInterrupt:
            if proc:
                with _process_lock:
                    _active_ffmpeg_processes.discard(proc)
                try:
                    proc.kill()
                    proc.wait(timeout=1)
                except Exception:
                    pass
            raise
        except Exception:
            if proc:
                with _process_lock:
                    _active_ffmpeg_processes.discard(proc)
                try:
                    proc.kill()
                    proc.wait(timeout=1)
                except Exception:
                    pass
            raise
        finally:
             if proc:
                with _process_lock:
                    _active_ffmpeg_processes.discard(proc)
                if proc.poll() is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass

    def combine_video(
        self, main_path: Path, overlay_path: Path, out_path: Path, dry: bool
    ) -> None:
        if not self._is_valid_overlay(overlay_path):
            self._fallback_copy(main_path, out_path, dry, f"Corrupt/Invalid overlay '{overlay_path.name}'")
            return

        if dry:
            log_dry_run(f"would combine video '{main_path}' + '{overlay_path}' → '{out_path}'")
            return
            
        if out_path.exists():
            return

        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        tmp_out = out_path.with_suffix(".tmp" + out_path.suffix)
        
        try:
            # Prefer FFmpeg if available, even for CPU
            if self.ffmpeg_available:
                 self._ffmpeg_overlay(main_path, overlay_path, tmp_out)
            else:
                # Fallback to MoviePy
                self._moviepy_overlay(main_path, overlay_path, tmp_out)
                
            if out_path.exists():
                 tmp_out.unlink()
            else:
                 tmp_out.replace(out_path)
                 
        except Exception:
            if tmp_out.exists():
                try: tmp_out.unlink()
                except: pass
            raise

    def _moviepy_overlay(self, main_path: Path, overlay_path: Path, out_path: Path) -> None:
        # Same MoviePy logic as before, used as fallback
        clip = None
        overlay_clip = None
        final_clip = None
        try:
            clip = VideoFileClip(str(main_path))
            overlay_clip = ImageClip(str(overlay_path)).with_duration(clip.duration)
            overlay_clip = overlay_clip.resized((clip.w, clip.h))
            final_clip = CompositeVideoClip([clip, overlay_clip])
            
            codec = "libx264"
            # MoviePy doesn't easily support hardware enc configs via write_videofile kwargs 
            # in a standard way across versions without ffmpeg_params usage
            # We'll stick to standard libx264 here as it's fallback
            
            final_clip.write_videofile(
                str(out_path),
                codec=codec,
                audio_codec="aac",
                logger=TqdmProgressBarLogger(print_messages=False),
                threads=4, # Use multi-threading
                preset="ultrafast",
                ffmpeg_params=["-movflags", "+faststart"],
            )
        finally:
            for c in (final_clip, overlay_clip, clip):
                try:
                    if c: c.close()
                except Exception:
                    pass

    def combine_one(self, p: CombinePlan, dry_run: bool) -> bool:
        """Combine or move a single item atomically. Returns True on success."""
        try:
            # Handle simple move case (no overlay)
            if not p.overlay_path:
                if dry_run:
                    log_dry_run(f"would move '{p.main_path}' → '{p.out_path}'")
                    return True
                
                if p.out_path.exists():
                    return True
                
                # Try rename first, then copy
                try:
                    p.out_path.parent.mkdir(parents=True, exist_ok=True)
                    p.main_path.replace(p.out_path)
                except OSError:
                    shutil.copy2(p.main_path, p.out_path)
                    try: p.main_path.unlink()
                    except: pass
                return True

            if p.kind == MemoryKind.IMAGE:
                self.combine_image(p.main_path, p.overlay_path, p.out_path, dry_run)
            else:
                self.combine_video(p.main_path, p.overlay_path, p.out_path, dry_run)
            return True
        except Exception as e:
            # combine_image/video might raise or handle cleanup. 
            # We catch here to return status or re-raise if needed.
            # But the caller (stage) will want the exception message for the state log.
            raise e

    def run(
        self,
        plans: List[CombinePlan],
        dry_run: bool,
    ) -> Tuple[int, int]:
        if not plans:
            return 0, 0

        imgs = [p for p in plans if p.kind == MemoryKind.IMAGE]
        vids = [p for p in plans if p.kind == MemoryKind.VIDEO]
        total = len(plans)
        
        if dry_run:
            # ... existing dry run logic ...
            for p in plans:
                if p.kind == MemoryKind.IMAGE:
                    self.combine_image(p.main_path, p.overlay_path, p.out_path, True)
                else:
                    self.combine_video(p.main_path, p.overlay_path, p.out_path, True)
            return len(imgs), len(vids)

        # Execute
        try:
            futures = {}
            with ThreadPoolExecutor(max_workers=max(1, self.cfg.image_workers)) as ipool:
                with ThreadPoolExecutor(max_workers=max(1, self.cfg.video_workers)) as vpool:
                    for p in imgs:
                        future = ipool.submit(self.combine_image, p.main_path, p.overlay_path, p.out_path, False)
                        futures[future] = ("image", p)
                    for p in vids:
                        future = vpool.submit(self.combine_video, p.main_path, p.overlay_path, p.out_path, False)
                        futures[future] = ("video", p)
                    
                    for f in tqdm(as_completed(futures), total=total, desc="Combining", unit="mem"):
                         f.result(timeout=1200) # Increased timeout

        except Exception as e:
            raise e
            
        return len(imgs), len(vids)
