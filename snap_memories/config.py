from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .logger import LogLevel


from .utils import (
    optimize_download_workers,
    optimize_image_workers,
    optimize_metadata_workers,
    optimize_video_workers_cpu,
)


@dataclass(frozen=True)
class AppConfig:
    dry_run: bool = False
    
    @property
    def image_workers(self) -> int:
        return optimize_image_workers()

    @property
    def video_workers(self) -> int:
        return optimize_video_workers_cpu()

    @property
    def download_workers(self) -> int:
        return optimize_download_workers()

    @property
    def metadata_workers(self) -> int:
        return optimize_metadata_workers()


    verbose: bool = False
    quiet: bool = False
    # Derived/inputs
    input_path: Path | None = None
    output_dir: Path | None = None
    metadata_html: Path | None = None
    
    @property
    def log_level(self) -> LogLevel:
        """Get the log level based on verbose/quiet flags."""
        if self.quiet:
            return LogLevel.QUIET
        if self.verbose:
            return LogLevel.VERBOSE
        return LogLevel.NORMAL
