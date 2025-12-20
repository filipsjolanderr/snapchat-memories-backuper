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
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import List, Set, Tuple

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
from .gpu import GPUDetector
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
        
    def extract_one(self, p: ExtractZipPlan) -> bool:
        """Extract a single ZIP file atomically. Returns True on success, False on failure."""
        
        # Atomic extraction: extract to unique .tmp folder first
        import uuid
        unique_name = f"{p.zip_path.stem}_{uuid.uuid4().hex[:8]}"
        tmp_extract_path = p.dest_folder / f".tmp_extract_{unique_name}"
        
        try:
            if tmp_extract_path.exists():
                shutil.rmtree(tmp_extract_path, ignore_errors=True)
            
            tmp_extract_path.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(p.zip_path, "r") as zf:
                zf.extractall(tmp_extract_path)
            
            # Lock for merging into shared destination
            with self._merge_lock:
                p.dest_folder.mkdir(parents=True, exist_ok=True)
                
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

                for item in tmp_extract_path.iterdir():
                    dst_path = p.dest_folder / item.name
                    if item.is_dir():
                        _merge_directories(item, dst_path)
                    else:
                        if dst_path.exists():
                            try:
                                if dst_path.is_dir():
                                    shutil.rmtree(dst_path)
                                else:
                                    dst_path.unlink()
                            except OSError:
                                pass
                        shutil.move(str(item), str(dst_path))
                    
            # Cleanup
            shutil.rmtree(tmp_extract_path, ignore_errors=True)
            return True
            
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
                if res is True:
                    count += 1
                elif res is False:
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
        # Detect GPU if enabled or if we want to determine capabilities
        # We always try to detect now to support 'auto' behavior
        try:
            self.gpu_info = GPUDetector.detect()
        except Exception:
            self.gpu_info = None
        
        # Check if ffmpeg is available
        self.ffmpeg_available = False
        try:
            subprocess.run([get_ffmpeg_path(), "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            self.ffmpeg_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.ffmpeg_available = False

        self._use_ffmpeg_gpu = cfg.use_gpu and self.gpu_info and self.gpu_info.available
        self._gpu_failures = 0
        self._max_gpu_failures = 3
        
        # Proactively probe if GPU encoding actually works
        if self._use_ffmpeg_gpu:
            if not self._probe_gpu_encoding():
                warning("GPU encoding probe failed (GPU or FFmpeg issue). Falling back to CPU for reliable processing.")
                self._use_ffmpeg_gpu = False

    def _probe_gpu_encoding(self) -> bool:
        """
        Attempt to encode a tiny dummy video frame using the detected GPU codec.
        Returns True if successful, False otherwise.
        """
        try:
            # Create a minimal filtergraph similar to real usage:
            # - f=lavfi generates testsrc
            # - scale (mimicking resize)
            # - format=yuv420p (pixel format often needed)
            # This ensures almost the entire pipeline (except file decoding) works.
            
            codec = self.gpu_info.codec
            preset = self._get_preset(codec)
            hwaccel = None
            if codec == "h264_nvenc":
                hwaccel = "cuda"
            elif codec == "h264_qsv":
                hwaccel = "qsv"
            elif codec == "h264_videotoolbox":
                hwaccel = "videotoolbox"

            cmd = [get_ffmpeg_path(), "-y"]
            
            # Note: For synthetic input like testsrc, -hwaccel might not be strictly applicable 
            # or necessary in the same way as decoding, but we want to test if the encoding side works.
            # We'll rely on the encoder check mainly.
            
            cmd.extend([
                "-f", "lavfi", "-i", "testsrc=duration=0.1:size=320x240:rate=1",
                "-c:v", codec
            ])
            
            # Minimal options for speed
            if codec == "h264_nvenc":
                cmd.extend(["-preset", "fast"])
            elif codec == "h264_amf":
                cmd.extend(["-usage", "transcoding"])
            elif codec == "libx264": # Should not happen here but safety
                cmd.extend(["-preset", "ultrafast"])

            cmd.extend([
                "-frames:v", "1",
                "-f", "null", "-"
            ])
            
            # Run with short timeout
            subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                timeout=5, # Should be very fast
                check=True
            )
            return True
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
            verbose(f"GPU Probe failed: {e}")
            return False

    def _get_preset(self, codec: str) -> str:
        """Get the appropriate preset for a given codec (optimized for speed)."""
        if codec == "libx264":
            return "ultrafast"  # Fastest CPU encoding
        elif codec == "h264_amf":
            return "0"  # speed (fastest)
        elif codec == "h264_nvenc":
            return "fast"
        elif codec == "h264_qsv":
            return "veryfast"
        elif codec == "h264_videotoolbox":
            return "fast"
        else:
            return "ultrafast"

    def combine_image(
        self, main_path: Path, overlay_path: Path, out_path: Path, dry: bool
    ) -> None:
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

        if not overlay_path.exists():
            raise FileNotFoundError(f"Overlay file not found: '{overlay_path.name}'")
        
        if overlay_path.stat().st_size == 0:
            raise ValueError(f"Overlay file is empty: '{overlay_path.name}'")

        try:
            test_img = Image.open(overlay_path)
            test_img.verify() 
        except Exception as e:
            # Check for ZIP masquerading as PNG
            try:
                with open(overlay_path, "rb") as f:
                    if f.read(4) == b"PK\x03\x04":
                         raise ValueError(f"Overlay is a ZIP file: {e}")
            except Exception:
                pass
            raise ValueError(
                f"Overlay file '{overlay_path.name}' is not a valid image file: {e}"
            )

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
        try:
            rgb.save(tmp_out, "JPEG", quality=95, optimize=True, progressive=True)
            if out_path.exists():
                tmp_out.unlink()
            else:
                tmp_out.replace(out_path)
        except Exception:
            if tmp_out.exists():
                try: tmp_out.unlink()
                except: pass
            raise
        finally:
            main.close()
            overlay.close()
            combined.close()
            rgb.close()

    def _ffmpeg_overlay(
        self, main_path: Path, overlay_path: Path, out_path: Path
    ) -> None:
        
        use_gpu_codec = (
            self.gpu_info 
            and self._use_ffmpeg_gpu 
            and self.gpu_info.available
            and self._gpu_failures < self._max_gpu_failures
        )
        codec = self.gpu_info.codec if use_gpu_codec else "libx264"
        preset = self._get_preset(codec)

        hwaccel = None
        # Enable hwaccel logic same as before...
        if use_gpu_codec:
            if self.gpu_info.codec == "h264_nvenc":
                hwaccel = "cuda"
            elif self.gpu_info.codec == "h264_qsv":
                hwaccel = "qsv"
            elif self.gpu_info.codec == "h264_videotoolbox":
                hwaccel = "videotoolbox"
            elif "amf" in self.gpu_info.codec:
                hwaccel = "d3d11va"

        try:
            self._try_ffmpeg_encode(main_path, overlay_path, out_path, codec, preset, hwaccel, None, use_gpu=use_gpu_codec)
        except (subprocess.TimeoutExpired, RuntimeError, subprocess.CalledProcessError) as e:
            if use_gpu_codec:
                self._gpu_failures += 1
                if self._gpu_failures >= self._max_gpu_failures:
                    warning(f"GPU encoding failed too many times ({self._gpu_failures}), disabling GPU for future operations.")
                
                warning(f"GPU encoding failed for '{main_path.name}', falling back to CPU encoding: {e}")
                
                # Retry with CPU
                try:
                    self._try_ffmpeg_encode(main_path, overlay_path, out_path, "libx264", "ultrafast", None, None, use_gpu=False)
                except Exception as cpu_e:
                    raise RuntimeError(f"Encoding failed (GPU fallover to CPU also failed): {cpu_e}") from e
            else:
                raise

    def _try_ffmpeg_encode(
        self, main_path: Path, overlay_path: Path, out_path: Path,
        codec: str, preset: str, hwaccel: str | None, hwaccel_output_format: str | None, use_gpu: bool
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
        if codec == "h264_nvenc":
            cmd.extend(["-preset", preset, "-rc:v", "vbr", "-cq:v", "28", "-b:v", "0"])
        elif codec == "h264_amf":
            cmd.extend(["-preset", preset, "-quality", "speed", "-rc", "cqp", "-qmin", "18", "-qmax", "24"])
        elif codec == "h264_qsv":
             cmd.extend(["-preset", preset, "-global_quality", "28", "-async_depth", "4"])
        elif codec == "h264_videotoolbox":
            cmd.extend(["-preset", preset, "-allow_sw", "1"])
        elif codec == "libx264":
            cmd.extend(["-preset", preset, "-tune", "fastdecode", "-profile:v", "baseline"])
        
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100", 
            "-ac", "2",
            "-movflags", "+faststart",
            "-threads", "0", 
            str(out_path),
        ])
        
        proc = None
        try:
            timeout = 60 if use_gpu else 600
            
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
        """Combine a single item atomically. Returns True on success."""
        try:
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
