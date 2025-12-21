from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Tuple

from .logger import dry_run


def get_cpu_count() -> int:
    """Get the number of CPU cores available."""
    try:
        # os.cpu_count() returns None if undetermined, fallback to 1
        count = os.cpu_count() or 1
        return max(1, count)
    except Exception:
        return 1


def optimize_image_workers(cpu_count: int | None = None) -> int:
    """Optimize image worker count based on CPU cores.
    
    Image processing scales well with CPU cores. Use CPU count * 2 for optimal throughput.
    """
    if cpu_count is None:
        cpu_count = get_cpu_count()
    # Image processing is CPU-bound and scales well
    # Use 2x CPU cores for optimal throughput (accounting for I/O wait)
    return min(max(cpu_count * 2, 4), 32)  # Between 4 and 32 workers


def optimize_video_workers_cpu(cpu_count: int | None = None) -> int:
    """Optimize video worker count for CPU encoding.
    
    CPU video encoding is CPU-intensive. Use CPU count for optimal performance.
    """
    if cpu_count is None:
        cpu_count = get_cpu_count()
    # CPU video encoding is very CPU-intensive
    # Use CPU count directly, but cap at reasonable max
    return min(max(cpu_count, 2), 16)  # Between 2 and 16 workers




def optimize_download_workers(cpu_count: int | None = None) -> int:
    """Optimize download worker count based on CPU cores.
    
    Downloads are network I/O bound. Use CPU count * 4-8 for optimal throughput.
    """
    if cpu_count is None:
        cpu_count = get_cpu_count()
    # Downloads are network I/O bound, can handle many parallel connections
    return min(max(cpu_count * 4, 8), 64)  # Between 8 and 64 workers


def optimize_metadata_workers(cpu_count: int | None = None) -> int:
    """Optimize metadata worker count based on CPU cores.
    
    Metadata processing is CPU-bound. Use CPU count * 2 for optimal throughput.
    """
    if cpu_count is None:
        cpu_count = get_cpu_count()
    # Metadata processing is CPU-bound
    return min(max(cpu_count * 2, 4), 32)  # Between 4 and 32 workers


def is_within_path(child: Path, parent: Path) -> bool:
    try:
        c = child.resolve()
        p = parent.resolve()
    except FileNotFoundError:
        c = child
        p = parent
    return p in c.parents or c == p


def iter_files_recursively(root: Path) -> Iterator[Tuple[Path, List[str]]]:
    for dirpath, _, files in os.walk(root):
        yield Path(dirpath), files


def ensure_dir(path: Path, dry_run_flag: bool) -> None:
    if dry_run_flag:
        dry_run(f"would ensure folder '{path}'")
        return
    try:
        path.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        from .logger import error
        error(f"Cannot create directory: {path}", e)
        raise


@contextmanager
def managed_tmp_dir(path: Path, dry_run_flag: bool) -> Iterator[Path]:
    if dry_run_flag:
        dry_run(f"would create temp folder '{path}'")
        yield path
        return
    try:
        path.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        from .logger import error
        error(f"Cannot create temp directory: {path}", e)
        raise
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
