from __future__ import annotations

import re
from pathlib import Path

from .fs import IMAGE_EXTS, VIDEO_EXT
from .utils import iter_files_recursively
from .fs import should_skip_dir


def count_input_breakdown(input_root: Path, output_folder: Path):
    zips = 0
    noext = 0
    mp4s = 0

    for dirpath, files in iter_files_recursively(input_root):
        if should_skip_dir(dirpath, input_root, output_folder):
            continue
        for name in files:
            lower = name.lower()
            if lower.endswith(".zip"):
                zips += 1
            elif "." not in name:
                noext += 1
            elif lower.endswith(VIDEO_EXT):
                if "-main." in lower:
                    continue
                if "_combined." in lower:
                    continue
                mp4s += 1
    return zips, noext, mp4s, zips + noext + mp4s


def count_output_memories(root: Path) -> int:
    combined = 0
    standalone_mp4 = 0
    standalone_img = 0

    for dirpath, files in iter_files_recursively(root):
        for name in files:
            lower = name.lower()
            if lower.endswith((".jpg", ".mp4")):
                if "-main" in lower or "-overlay" in lower:
                    continue
                if re.match(r"[0-9a-fA-F-]{36}(_combined)?\.(jpg|mp4)$", lower):
                    combined += 1
                elif lower.endswith(".mp4"):
                    standalone_mp4 += 1
                elif lower.endswith(tuple(IMAGE_EXTS)):
                    standalone_img += 1
            elif lower.endswith(tuple(IMAGE_EXTS)):
                if "-main" in lower:
                    continue
                if lower.endswith("-overlay.png"):
                    continue
                standalone_img += 1
    return combined + standalone_mp4 + standalone_img
