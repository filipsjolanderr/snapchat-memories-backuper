from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .logger import LogLevel


@dataclass(frozen=True)
class AppConfig:
    dry_run: bool = False
    image_workers: int = 16
    video_workers: int = 8
    download_workers: int = 4
    metadata_workers: int = 16
    use_gpu: bool = True
    use_ffmpeg_gpu: bool = True
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
