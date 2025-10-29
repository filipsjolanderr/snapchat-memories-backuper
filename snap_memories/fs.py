from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Iterator, List, Tuple

from .logger import verbose
from .utils import iter_files_recursively, is_within_path


IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXT = ".mp4"

UUID_IN_NAME = re.compile(r"[0-9a-fA-F-]{36}")


def find_zip_files_top_level(folder: Path) -> List[Path]:
    zips: List[Path] = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() == ".zip":
            zips.append(p)
            continue
        try:
            with open(p, "rb") as f:
                if f.read(4) == b"PK\x03\x04":
                    zips.append(p)
        except Exception:
            continue
    return zips


def detect_and_fix_zip_files(folder: Path) -> int:
    fixed = 0
    for file in folder.iterdir():
        if not file.is_file():
            continue
        if file.suffix.lower() == ".zip":
            continue
        try:
            is_zip = False
            with open(file, "rb") as f:
                if f.read(4) == b"PK\x03\x04":
                    is_zip = True
            # File is now closed, safe to rename
            if is_zip:
                dst = file.with_suffix(".zip")
                if dst.exists():
                    continue
                file.rename(dst)
                fixed += 1
                verbose(
                    f"Detected ZIP (wrong extension), "
                    f"renamed: {file.name} → {dst.name}"
                )
        except Exception:
            continue
    return fixed


def enumerate_main_files(scan_folder: Path) -> List[Path]:
    out: List[Path] = []
    for d, files in iter_files_recursively(scan_folder):
        for n in files:
            if "-main." in n:
                out.append(d / n)
    return out


def split_uuid_and_ext(main_filename: str) -> Tuple[str, str]:
    p = Path(main_filename)
    base = p.stem
    ext = p.suffix.lower()
    uuid = base.replace("-main", "")
    return uuid, ext


def should_skip_dir(
    current_dir: Path, input_root: Path, output_folder: Path
) -> bool:
    return is_within_path(output_folder, input_root) and is_within_path(
        current_dir, output_folder
    )
