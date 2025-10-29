from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Tuple

from .logger import dry_run


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
