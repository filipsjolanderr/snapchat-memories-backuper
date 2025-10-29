from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple

from .fs import (
    IMAGE_EXTS,
    VIDEO_EXT,
    enumerate_main_files,
    find_zip_files_top_level,
    should_skip_dir,
    split_uuid_and_ext,
)
from .models import CombinePlan, CopyPlan, ExtractZipPlan, MemoryKind, RenamePlan
from .utils import iter_files_recursively


class Planner:
    def plan_zip_extractions(
        self, input_folder: Path, dest_folder: Path
    ) -> List[ExtractZipPlan]:
        return [
            ExtractZipPlan(zip_path=z, dest_folder=dest_folder)
            for z in find_zip_files_top_level(input_folder)
        ]

    def plan_copy_standalone_mp4s(
        self, input_folder: Path, output_folder: Path
    ) -> List[CopyPlan]:
        plans: List[CopyPlan] = []
        for dirpath, files in iter_files_recursively(input_folder):
            if should_skip_dir(dirpath, input_folder, output_folder):
                continue
            for name in files:
                lower = name.lower()
                if not lower.endswith(VIDEO_EXT):
                    continue
                if "-main." in lower or "_combined." in lower:
                    continue
                src = Path(dirpath) / name
                rel = src.relative_to(input_folder)
                dst = output_folder / rel
                if not dst.exists():
                    plans.append(CopyPlan(src, dst))
        return plans

    def iter_standalone_mp4_candidates(
        self, input_folder: Path, output_folder: Path
    ) -> Iterable[Tuple[Path, Path]]:
        for dirpath, files in iter_files_recursively(input_folder):
            if should_skip_dir(dirpath, input_folder, output_folder):
                continue
            for name in files:
                lower = name.lower()
                if not lower.endswith(VIDEO_EXT) or "-main." in lower:
                    continue
                src = Path(dirpath) / name
                rel = src.relative_to(input_folder)
                dst = output_folder / rel
                yield src, dst

    def plan_unlabeled_renames(
        self, source_root: Path, dst_root: Path, skip_root: Path | None = None
    ) -> List[RenamePlan]:
        plans: List[RenamePlan] = []
        for dirpath, files in iter_files_recursively(source_root):
            if skip_root and (skip_root in dirpath.parents or dirpath == skip_root):
                continue
            for name in files:
                if name.lower().endswith(".zip"):
                    continue
                if "." not in name:
                    src = Path(dirpath) / name
                    rel = src.relative_to(source_root)
                    dst = (dst_root / rel).with_suffix(".jpg")
                    plans.append(RenamePlan(src, dst))
        return plans

    def plan_filesystem_combinations(
        self, scan_folder: Path, output_folder: Path
    ) -> List[CombinePlan]:
        plans: List[CombinePlan] = []
        for main_path in enumerate_main_files(scan_folder):
            uuid_str, ext = split_uuid_and_ext(main_path.name)
            overlay_path = main_path.with_name(f"{uuid_str}-overlay.png")
            if not overlay_path.exists():
                continue

            if ext in IMAGE_EXTS:
                out_path = output_folder / f"{uuid_str}.jpg"
                plans.append(
                    CombinePlan(
                        main_path=main_path,
                        overlay_path=overlay_path,
                        out_path=out_path,
                        kind=MemoryKind.IMAGE,
                    )
                )
            elif ext == ".mp4":
                out_path = output_folder / f"{uuid_str}.mp4"
                plans.append(
                    CombinePlan(
                        main_path=main_path,
                        overlay_path=overlay_path,
                        out_path=out_path,
                        kind=MemoryKind.VIDEO,
                    )
                )
        return plans
