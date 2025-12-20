from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .logger import LogLevel


@dataclass(frozen=True)
class AppConfig:
    dry_run: bool = False
    
    @property
    def _cpu_count(self) -> int:
        return os.cpu_count() or 4

    @property
    def image_workers(self) -> int:
        return self._cpu_count * 4

    @property
    def video_workers(self) -> int:
        return self._cpu_count * 4

    @property
    def download_workers(self) -> int:
        return self._cpu_count * 4

    @property
    def metadata_workers(self) -> int:
        return self._cpu_count * 4

    use_gpu: bool = True
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
