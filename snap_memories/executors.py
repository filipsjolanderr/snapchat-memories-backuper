from __future__ import annotations

import shutil
import subprocess
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import requests
from PIL import Image, PngImagePlugin
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip
from proglog import TqdmProgressBarLogger
from tqdm import tqdm

# Suppress moviepy UserWarning about frame reading (benign - handled internally)
# This warning occurs when moviepy reads fewer bytes than expected but uses the last valid frame
warnings.filterwarnings(
    "ignore",
    message=".*bytes wanted but.*bytes read.*",
    category=UserWarning,
    module="moviepy.video.io.ffmpeg_reader",
)

from .config import AppConfig
from .gpu import GPUDetector
from .logger import dry_run as log_dry_run, warning
from .models import CombinePlan, MemoryKind, RenamePlan
from .models import CopyPlan, ExtractZipPlan
from .metadata import (
    apply_metadata_to_outputs,
    parse_memories_html,
    write_exif_to_jpeg,
)
from .utils import ensure_dir


class ZipService:
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
        for p in tqdm(plans, desc="Extracting ZIPs", unit="zip"):
            with zipfile.ZipFile(p.zip_path, "r") as zf:
                zf.extractall(p.dest_folder)
            count += 1
        return count


class CopyService:
    def run(self, plans: List[CopyPlan], dry_run: bool) -> int:
        if not plans:
            return 0
        if dry_run:
            for p in plans:
                log_dry_run(f"would copy '{p.src}' → '{p.dst}'")
            return len(plans)
        done = 0
        for p in tqdm(plans, desc="Copying MP4s", unit="file"):
            p.dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p.src, p.dst)
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
        for p in tqdm(plans, desc="Fixing unnamed files", unit="file"):
            try:
                p.dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p.src, p.dst)
                done += 1
            except OSError:
                pass
        return done


class CombineService:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.gpu_info = GPUDetector.detect() if cfg.use_gpu else None
        # Auto-enable FFmpeg GPU if GPU is available (faster than MoviePy)
        # unless explicitly disabled by user
        self._use_ffmpeg_gpu = cfg.use_ffmpeg_gpu or (
            cfg.use_gpu and self.gpu_info and self.gpu_info.available
        )

    def _get_preset(self, codec: str) -> str:
        """Get the appropriate preset for a given codec."""
        if codec == "libx264":
            return "medium"
        elif codec == "h264_amf":
            # AMF uses integer presets: 0=speed, 1=balanced, 2=quality
            return "0"  # speed
        elif codec in ("h264_nvenc", "h264_qsv", "h264_videotoolbox"):
            # NVENC, QSV, VideoToolbox support: fast, medium, slow, etc.
            return "fast"
        else:
            return "medium"

    def combine_image(
        self, main_path: Path, overlay_path: Path, out_path: Path, dry: bool
    ) -> None:
        if dry:
            log_dry_run(
                f"would combine image "
                f"'{main_path}' + '{overlay_path}' → '{out_path}'"
            )
            return
        out_path.parent.mkdir(parents=True, exist_ok=True)

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
        rgb.save(out_path, "JPEG", quality=95, optimize=True, progressive=True)
        main.close()
        overlay.close()
        combined.close()
        rgb.close()

    def _ffmpeg_overlay(
        self, main_path: Path, overlay_path: Path, out_path: Path
    ) -> None:
        # Safer: loop the PNG overlay and end at main video using -shortest
        # Audio: map 0:a? (optional), encode AAC for compatibility
        codec = (
            self.gpu_info.codec
            if self.gpu_info and self._use_ffmpeg_gpu
            else "libx264"
        )

        preset = self._get_preset(codec)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(main_path),
            "-loop",
            "1",
            "-i",
            str(overlay_path),
            "-filter_complex",
            (
                "[1:v]format=rgba[olorig];"
                "[olorig][0:v]scale2ref=w=iw:h=ih[ol][base];"
                "[base][ol]overlay=0:0:format=auto"
            ),
            "-shortest",
            "-map",
            "0:v",
            "-map",
            "0:a?",
            "-c:v",
            codec,
            "-preset",
            preset,
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600
        )
        if r.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {r.stderr}")

    def _moviepy_overlay(
        self, main_path: Path, overlay_path: Path, out_path: Path
    ) -> None:
        clip = None
        overlay_clip = None
        final_clip = None
        try:
            clip = VideoFileClip(str(main_path))
            overlay_clip = ImageClip(str(overlay_path)).with_duration(
                clip.duration
            )
            overlay_clip = overlay_clip.resized((clip.w, clip.h))
            final_clip = CompositeVideoClip([clip, overlay_clip])

            codec = "libx264"
            if self.cfg.use_gpu and self.gpu_info and self.gpu_info.available:
                codec = self.gpu_info.codec
            preset = self._get_preset(codec)

            final_clip.write_videofile(
                str(out_path),
                codec=codec,
                audio_codec="aac",
                logger=TqdmProgressBarLogger(print_messages=False),
                threads=1,
                preset=preset,
                ffmpeg_params=["-movflags", "+faststart"],
            )
        finally:
            for c in (final_clip, overlay_clip, clip):
                try:
                    if c:
                        c.close()
                except Exception:
                    pass

    def combine_video(
        self, main_path: Path, overlay_path: Path, out_path: Path, dry: bool
    ) -> None:
        if dry:
            log_dry_run(
                f"would combine video "
                f"'{main_path}' + '{overlay_path}' → '{out_path}'"
            )
            return
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Prefer FFmpeg GPU when available (faster, less overhead)
        # Auto-enabled when GPU is detected
        if self._use_ffmpeg_gpu:
            self._ffmpeg_overlay(main_path, overlay_path, out_path)
        else:
            self._moviepy_overlay(main_path, overlay_path, out_path)

    def run(
        self,
        plans: List[CombinePlan],
        dry_run: bool,
        image_workers: int,
        video_workers: int,
    ) -> Tuple[int, int]:
        if not plans:
            return 0, 0

        imgs = [p for p in plans if p.kind == MemoryKind.IMAGE]
        vids = [p for p in plans if p.kind == MemoryKind.VIDEO]
        total = len(plans)
        done_img = 0
        done_vid = 0

        if dry_run:
            for p in plans:
                if p.kind == MemoryKind.IMAGE:
                    self.combine_image(
                        p.main_path, p.overlay_path, p.out_path, dry_run
                    )
                else:
                    self.combine_video(
                        p.main_path, p.overlay_path, p.out_path, dry_run
                    )
            return len(imgs), len(vids)

        bar = tqdm(total=total, desc="Combining", unit="mem")
        futures = []
        with ThreadPoolExecutor(max_workers=max(1, image_workers)) as ipool:
            with ThreadPoolExecutor(max_workers=max(1, video_workers)) as vpool:
                for p in imgs:
                    futures.append(
                        ipool.submit(
                            self.combine_image,
                            p.main_path,
                            p.overlay_path,
                            p.out_path,
                            False,
                        )
                    )
                for p in vids:
                    futures.append(
                        vpool.submit(
                            self.combine_video,
                            p.main_path,
                            p.overlay_path,
                            p.out_path,
                            False,
                        )
                    )
                for f in as_completed(futures):
                    try:
                        f.result()
                    finally:
                        bar.update(1)
        bar.close()
        done_img = len(imgs)
        done_vid = len(vids)
        return done_img, done_vid
