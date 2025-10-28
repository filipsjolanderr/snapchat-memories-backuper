# snap_memories.py
from __future__ import annotations

import argparse
import os
import shutil
import sys
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple
from uuid import uuid4

from PIL import Image
from moviepy import CompositeVideoClip, ImageClip, VideoFileClip
from proglog import TqdmProgressBarLogger
from tqdm import tqdm

# Suppress noisy frame padding warnings from MoviePy/FFmpeg reader
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module=r".*moviepy\.video\.io\.ffmpeg_reader.*",
)

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXT = ".mp4"


# -----------------------------
# Data classes and enums
# -----------------------------
class MemoryKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


@dataclass(frozen=True)
class ExtractZipPlan:
    zip_path: Path
    dest_folder: Path


@dataclass(frozen=True)
class CopyPlan:
    src: Path
    dst: Path


@dataclass(frozen=True)
class RenamePlan:
    src: Path
    dst: Path


@dataclass(frozen=True)
class CombinePlan:
    main_path: Path
    overlay_path: Path
    out_path: Path
    kind: MemoryKind


# -----------------------------
# Helpers and utilities
# -----------------------------

def is_within_path(child: Path, parent: Path) -> bool:
    """Return True if child is the same as or within parent."""
    try:
        child_abs = child.resolve()
        parent_abs = parent.resolve()
    except FileNotFoundError:
        child_abs = child
        parent_abs = parent
    return parent_abs in child_abs.parents or child_abs == parent_abs


def iter_files_recursively(root: Path) -> Iterator[Tuple[Path, List[str]]]:
    """Yield (dirpath, files) tuples recursively."""
    for dirpath, _, files in os.walk(root):
        yield Path(dirpath), files


def find_zip_files_top_level(folder: Path) -> List[Path]:
    """Zip files at the top level of input (Snapchat export layout)."""
    return [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".zip"]


def split_uuid_and_ext(main_filename: str) -> Tuple[str, str]:
    """Given a '<uuid>-main.ext' filename, return (uuid, .ext)."""
    base_name = Path(main_filename).stem
    ext = Path(main_filename).suffix.lower()
    uuid = base_name.replace("-main", "")
    return uuid, ext


def enumerate_main_files(scan_folder: Path) -> List[Path]:
    """Find all files whose names contain '-main.' in a folder tree."""
    mains: List[Path] = []
    for dirpath, files in iter_files_recursively(scan_folder):
        for name in files:
            if "-main." in name:
                mains.append(dirpath / name)
    return mains


def should_skip_dir(
    current_dir: Path, input_root: Path, output_folder: Path
) -> bool:
    """Skip output subtree if it lives inside input."""
    return is_within_path(output_folder, input_root) and is_within_path(
        current_dir, output_folder
    )


@contextmanager
def managed_tmp_dir(path: Path, dry_run: bool) -> Iterator[Path]:
    """Create and always clean up a temp working directory."""
    if dry_run:
        tqdm.write(f"DRY RUN: would ensure temp folder exists at '{path}'")
    else:
        path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        # Always attempt cleanup to avoid leftover temp content
        shutil.rmtree(path, ignore_errors=True)


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        tqdm.write(f"DRY RUN: would ensure output folder exists at '{path}'")
    else:
        path.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Counting (input/output)
# -----------------------------
@dataclass(frozen=True)
class InputCounts:
    total_relevant: int  # zips + unnamed_no_ext + mp4s (standalone)
    zips: int
    unnamed_no_ext: int
    mp4s: int  # standalone mp4s (excluding -main and excluding output)


def count_input_breakdown(input_root: Path, output_folder: Path) -> InputCounts:
    """Return counts for input tree, skipping the output folder if it is inside
    input. Counts:
      - zips: *.zip
      - unnamed_no_ext: files without '.'
      - mp4s: standalone mp4s (exclude *-main.mp4 and _combined.mp4)
      - total_relevant: sum of the above
    """
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
                continue
            if "." not in name:
                noext += 1
                continue
            if lower.endswith(VIDEO_EXT):
                if "-main." in lower:
                    continue
                if lower.endswith("_combined.mp4"):
                    continue
                mp4s += 1

    total = zips + noext + mp4s
    return InputCounts(total_relevant=total, zips=zips, unnamed_no_ext=noext, mp4s=mp4s)


def count_output_memories(root: Path) -> int:
    """Count output memories:
      - combined: *_combined.png or *_combined.mp4
      - standalone mp4s (not *_combined.mp4)
      - standalone images (jpg/jpeg/png) excluding *_combined and overlays/-main
    """
    combined = 0
    standalone_mp4 = 0
    standalone_img = 0
    for dirpath, files in iter_files_recursively(root):
        for name in files:
            lower = name.lower()
            if lower.endswith(("_combined.png", "_combined.mp4")):
                combined += 1
            elif lower.endswith(".mp4") and not lower.endswith("_combined.mp4"):
                standalone_mp4 += 1
            elif lower.endswith(tuple(IMAGE_EXTS)):
                if lower.endswith("_combined.png"):
                    continue
                if "-main." in lower:
                    continue
                if lower.endswith("-overlay.png"):
                    continue
                standalone_img += 1
    return combined + standalone_mp4 + standalone_img


# -----------------------------
# Planners
# -----------------------------
def plan_zip_extractions(
    input_folder: Path, dest_folder: Path
) -> List[ExtractZipPlan]:
    return [
        ExtractZipPlan(zip_path=z, dest_folder=dest_folder)
        for z in find_zip_files_top_level(input_folder)
    ]


def plan_copy_standalone_mp4s(
    input_folder: Path, output_folder: Path
) -> List[CopyPlan]:
    """Copy mp4s that are not *-main.mp4 into output, preserving structure."""
    plans: List[CopyPlan] = []
    for dirpath, files in iter_files_recursively(input_folder):
        if should_skip_dir(dirpath, input_folder, output_folder):
            continue
        for name in files:
            lower = name.lower()
            if not lower.endswith(VIDEO_EXT):
                continue
            if "-main." in lower or lower.endswith("_combined.mp4"):
                continue
            src = Path(dirpath) / name
            rel = src.relative_to(input_folder)
            dst = output_folder / rel
            if not dst.exists():
                plans.append(CopyPlan(src=src, dst=dst))
    return plans


def count_standalone_mp4_candidates(
    input_folder: Path, output_folder: Path
) -> int:
    """Count standalone MP4s in input that would be eligible for copy, regardless
    of whether the destination file already exists. Skips the output subtree if
    it is within the input folder.
    """
    count = 0
    for dirpath, files in iter_files_recursively(input_folder):
        if should_skip_dir(dirpath, input_folder, output_folder):
            continue
        for name in files:
            lower = name.lower()
            if not lower.endswith(VIDEO_EXT):
                continue
            if "-main." in lower or lower.endswith("_combined.mp4"):
                continue
            count += 1
    return count


def iter_standalone_mp4_candidates(
    input_folder: Path, output_folder: Path
) -> Iterable[Tuple[Path, Path]]:
    """Yield (src, dst) for all eligible standalone MP4s in input, regardless of
    whether the destination already exists. Preserves directory structure.
    Skips the output subtree if it is within input.
    """
    for dirpath, files in iter_files_recursively(input_folder):
        if should_skip_dir(dirpath, input_folder, output_folder):
            continue
        for name in files:
            lower = name.lower()
            if not lower.endswith(VIDEO_EXT):
                continue
            if "-main." in lower or lower.endswith("_combined.mp4"):
                continue
            src = Path(dirpath) / name
            rel = src.relative_to(input_folder)
            dst = output_folder / rel
            yield src, dst


def plan_unlabeled_renames(
    source_root: Path, dst_root: Path, skip_root: Optional[Path] = None
) -> List[RenamePlan]:
    """Plan copying files without extension to dst with '.jpg' appended."""
    plans: List[RenamePlan] = []
    for dirpath, files in iter_files_recursively(source_root):
        if skip_root and is_within_path(dirpath, skip_root):
            continue
        for name in files:
            if name.lower().endswith(".zip"):
                continue
            if "." not in name:
                src = Path(dirpath) / name
                rel = src.relative_to(source_root)
                dst = (dst_root / rel).with_suffix(".jpg")
                plans.append(RenamePlan(src=src, dst=dst))
    return plans


def plan_filesystem_combinations(
    scan_folder: Path, output_folder: Path
) -> List[CombinePlan]:
    plans: List[CombinePlan] = []
    for main_path in enumerate_main_files(scan_folder):
        uuid_str, ext = split_uuid_and_ext(main_path.name)
        overlay_path = main_path.with_name(f"{uuid_str}-overlay.png")
        if not overlay_path.exists():
            continue

        if ext in IMAGE_EXTS:
            out_path = output_folder / f"{uuid_str}_combined.png"
            plans.append(
                CombinePlan(
                    main_path=main_path,
                    overlay_path=overlay_path,
                    out_path=out_path,
                    kind=MemoryKind.IMAGE,
                )
            )
        elif ext == VIDEO_EXT:
            out_path = output_folder / f"{uuid_str}_combined.mp4"
            plans.append(
                CombinePlan(
                    main_path=main_path,
                    overlay_path=overlay_path,
                    out_path=out_path,
                    kind=MemoryKind.VIDEO,
                )
            )
    return plans


def plan_combinations_inside_zips_for_preview(
    input_folder: Path,
) -> List[CombinePlan]:
    """Dry-run helper: inspect each ZIP and build combine plans that would exist
    after extraction (zipname::path for srcs).
    """
    plans: List[CombinePlan] = []
    for zip_path in find_zip_files_top_level(input_folder):
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                entries = [n for n in zf.namelist() if not n.endswith("/")]
                basenames = {Path(n).name for n in entries}
                for main_file in (b for b in basenames if "-main." in b):
                    uuid_str, ext = split_uuid_and_ext(main_file)
                    overlay_file = f"{uuid_str}-overlay.png"
                    if overlay_file not in basenames:
                        continue
                    kind = (
                        MemoryKind.IMAGE
                        if ext in IMAGE_EXTS
                        else MemoryKind.VIDEO
                    )
                    out_name = (
                        f"{uuid_str}_combined.png"
                        if kind == MemoryKind.IMAGE
                        else f"{uuid_str}_combined.mp4"
                    )
                    plans.append(
                        CombinePlan(
                            main_path=Path(f"{zip_path.name}::{main_file}"),
                            overlay_path=Path(
                                f"{zip_path.name}::{overlay_file}"
                            ),
                            out_path=Path(out_name),
                            kind=kind,
                        )
                    )
        except zipfile.BadZipFile:
            tqdm.write(f"Warning: could not read ZIP '{zip_path}'")
    return plans


def plan_unlabeled_renames_inside_zips_for_preview(
    input_folder: Path, output_folder: Path
) -> List[RenamePlan]:
    """Dry-run helper: show unlabeled files inside zips that would become .jpg
    after extraction. This is a preview only.
    """
    plans: List[RenamePlan] = []
    for zip_path in find_zip_files_top_level(input_folder):
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for entry in (n for n in zf.namelist() if not n.endswith("/")):
                    base = Path(entry).name
                    if "." not in base:
                        src = Path(f"{zip_path.name}::{entry}")
                        # Destination mimics 'extract-all-to-tmp' then rename
                        dst = (output_folder / base).with_suffix(".jpg")
                        plans.append(RenamePlan(src=src, dst=dst))
        except zipfile.BadZipFile:
            tqdm.write(f"Warning: could not read ZIP '{zip_path}'")
    return plans


# -----------------------------
# Executors
# -----------------------------
def run_zip_extractions(plans: List[ExtractZipPlan], dry_run: bool) -> int:
    if not plans:
        return 0
    if dry_run:
        for p in plans:
            tqdm.write(
                f"DRY RUN: would extract '{p.zip_path}' → '{p.dest_folder}'"
            )
        return 0

    extracted = 0
    for p in tqdm(plans, desc="Extracting ZIP files", unit="zip"):
        # Extract directly into the shared temp dir, like the original tool
        with zipfile.ZipFile(p.zip_path, "r") as zf:
            zf.extractall(p.dest_folder)
        extracted += 1
    return extracted


def run_copy_plans(plans: List[CopyPlan], dry_run: bool) -> int:
    if not plans:
        return 0
    if dry_run:
        for p in plans:
            tqdm.write(f"DRY RUN: would copy MP4 '{p.src}' → '{p.dst}'")
        return len(plans)

    done = 0
    for p in tqdm(plans, desc="Copying standalone MP4s", unit="file"):
        p.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p.src, p.dst)
        done += 1
    return done


def run_rename_plans(plans: List[RenamePlan], dry_run: bool) -> int:
    if not plans:
        return 0
    if dry_run:
        for p in plans:
            tqdm.write(f"DRY RUN: would rename '{p.src}' → '{p.dst}'")
        return len(plans)

    done = 0
    for p in tqdm(plans, desc="Fixing unnamed image files", unit="file"):
        try:
            p.dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p.src, p.dst)
            done += 1
        except OSError:
            # Ignore issues (e.g., permissions/dupes)
            pass
    return done


def combine_image_memory(
    main_path: Path, overlay_path: Path, out_path: Path, dry_run: bool
) -> None:
    if dry_run:
        tqdm.write(
            "DRY RUN: would combine image "
            f"'{main_path}' + '{overlay_path}' → '{out_path}'"
        )
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure files are closed promptly
    with Image.open(main_path).convert("RGBA") as main_img, Image.open(
        overlay_path
    ).convert("RGBA") as overlay:
        if overlay.size != main_img.size:
            overlay = overlay.resize(main_img.size, Image.LANCZOS)
        combined = Image.alpha_composite(main_img, overlay)
        combined.save(out_path)


def combine_video_memory(
    main_path: Path, overlay_path: Path, out_path: Path, dry_run: bool
) -> None:
    if dry_run:
        tqdm.write(
            "DRY RUN: would combine video "
            f"'{main_path}' + '{overlay_path}' → '{out_path}'"
        )
        return

    clip = VideoFileClip(str(main_path))
    overlay = ImageClip(str(overlay_path)).with_duration(clip.duration)
    overlay = overlay.resized((clip.w, clip.h))
    final = CompositeVideoClip([clip, overlay])

    temp_audio_path = out_path.parent / f"temp-audio-{uuid4().hex}.m4a"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        final.write_videofile(
            str(out_path),
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(temp_audio_path),
            remove_temp=True,
            logger=TqdmProgressBarLogger(print_messages=False),
            threads=os.cpu_count() or 4,
            preset="medium",
        )
    finally:
        # Close resources even if encoding fails
        try:
            overlay.close()
        except Exception:
            pass
        try:
            clip.close()
        except Exception:
            pass
        try:
            final.close()
        except Exception:
            pass


def run_combine_plans(
    plans: List[CombinePlan],
    dry_run: bool,
    image_workers: int,
    video_workers: int,
) -> Tuple[int, int]:
    if not plans:
        return 0, 0

    img_plans = [p for p in plans if p.kind == MemoryKind.IMAGE]
    vid_plans = [p for p in plans if p.kind == MemoryKind.VIDEO]
    total = len(plans)
    images_done = 0
    videos_done = 0

    bar = None if dry_run else tqdm(
        total=total, desc="Combining Memories", unit="memories"
    )

    def _run(plan: CombinePlan) -> MemoryKind:
        if plan.kind == MemoryKind.IMAGE:
            combine_image_memory(
                plan.main_path, plan.overlay_path, plan.out_path, dry_run
            )
            return MemoryKind.IMAGE
        combine_video_memory(
            plan.main_path, plan.overlay_path, plan.out_path, dry_run
        )
        return MemoryKind.VIDEO

    if dry_run:
        for p in plans:
            _ = _run(p)
        return len(img_plans), len(vid_plans)

    futures = []
    with ThreadPoolExecutor(max_workers=max(1, image_workers)) as img_pool, ThreadPoolExecutor(  # noqa: E501
        max_workers=max(1, video_workers)
    ) as vid_pool:
        for p in img_plans:
            futures.append(img_pool.submit(_run, p))
        for p in vid_plans:
            futures.append(vid_pool.submit(_run, p))

        for fut in as_completed(futures):
            try:
                kind = fut.result()
                if kind == MemoryKind.IMAGE:
                    images_done += 1
                else:
                    videos_done += 1
            finally:
                if bar is not None:
                    bar.update(1)

    if bar is not None:
        bar.close()
    return images_done, videos_done


# -----------------------------
# CLI parsing
# -----------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restore Snapchat Memories by extracting zips, fixing unnamed "
            "files, and compositing main + overlay images/videos into an "
            "output folder."
        )
    )
    parser.add_argument(
        "input_folder",
        nargs="?",
        help="Path to folder containing Snapchat export files (positional)",
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input_opt",
        help="Input folder (alternative to positional)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_folder",
        help="Optional output folder (default: <input>/output)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without modifying files or writing outputs",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Max concurrent combines (applies to both images and videos)",
    )
    parser.add_argument(
        "--image-workers",
        type=int,
        default=4,
        help="Max concurrent image combines (default 4)",
    )
    parser.add_argument(
        "--video-workers",
        type=int,
        default=2,
        help="Max concurrent video combines (default 2)",
    )
    parser.add_argument(
        "--leave-originals",
        action="store_true",
        help=(
            "Leave originals untouched (default: True). Always true; "
            "flag kept for parity."
        ),
    )
    return parser.parse_args()


# -----------------------------
# Orchestration
# -----------------------------
def main() -> int:
    args = parse_args()

    chosen_input = args.input_opt or args.input_folder
    if not chosen_input:
        print(
            "Error: no input folder provided. Use positional <input_folder> "
            "or -i/--input."
        )
        return 2

    input_folder = Path(chosen_input).resolve()
    if not input_folder.is_dir():
        print(f"Error: input folder not found: {input_folder}")
        return 1

    output_folder = (
        Path(args.output_folder).resolve()
        if args.output_folder
        else input_folder / "output"
    )

    ensure_dir(output_folder, args.dry_run)

    # Create and always clean temp working dir (also cleaned on dry-run)
    tmp_root = output_folder / ".tmp_work"
    with managed_tmp_dir(tmp_root, args.dry_run) as tmp_root:
        # 1) Plan/copy standalone MP4s from input to output
        copy_mp4_plans = plan_copy_standalone_mp4s(
            input_folder, output_folder
        )
        if args.dry_run:
            for src, dst in iter_standalone_mp4_candidates(
                input_folder, output_folder
            ):
                tqdm.write(f"DRY RUN: would copy MP4 '{src}' → '{dst}'")
            mp4_copied = len(copy_mp4_plans)
            mp4_candidates = count_standalone_mp4_candidates(
                input_folder, output_folder
            )
        else:
            mp4_copied = run_copy_plans(copy_mp4_plans, args.dry_run)
            mp4_candidates = None

        # 2) Plan/copy unnamed files (.jpg) from INPUT to OUTPUT
        rename_input_plans = plan_unlabeled_renames(
            source_root=input_folder,
            dst_root=output_folder,
            skip_root=output_folder
            if is_within_path(output_folder, input_folder)
            else None,
        )
        unnamed_from_input = run_rename_plans(
            rename_input_plans, args.dry_run
        )

        # 3) Extract zips to temp work dir
        extract_plans = plan_zip_extractions(input_folder, tmp_root)
        _ = run_zip_extractions(extract_plans, args.dry_run)

        # 4) Dry-run preview for zip-contained combinations and unnamed
        zip_preview_plans: List[CombinePlan] = []
        if args.dry_run and extract_plans:
            zip_preview_plans = plan_combinations_inside_zips_for_preview(
                input_folder
            )
            for cp in zip_preview_plans:
                zip_name, main_inner = str(cp.main_path).split("::", 1)
                _, overlay_inner = str(cp.overlay_path).split("::", 1)
                tqdm.write(
                    "DRY RUN: would combine (inside "
                    f"{zip_name}) '{main_inner}' + '{overlay_inner}' "
                    f"→ '{cp.out_path}'"
                )
            if zip_preview_plans:
                imgs = sum(1 for p in zip_preview_plans if p.kind == MemoryKind.IMAGE)  # noqa: E501
                vids = sum(1 for p in zip_preview_plans if p.kind == MemoryKind.VIDEO)  # noqa: E501
                tqdm.write(
                    "DRY RUN: found inside zips → planned images: "
                    f"{imgs}, videos: {vids}"
                )

            # Preview unlabeled files inside zips (previously missing)
            rename_zip_preview = plan_unlabeled_renames_inside_zips_for_preview(
                input_folder, output_folder
            )
            for rp in rename_zip_preview:
                zip_name, inner = str(rp.src).split("::", 1)
                tqdm.write(
                    f"DRY RUN: would rename (inside {zip_name}) "
                    f"'{inner}' → '{rp.dst}'"
                )

        # 5) After extraction, handle unnamed files in temp and plan combines
        rename_tmp_plans = plan_unlabeled_renames(
            source_root=tmp_root, dst_root=tmp_root
        )
        _ = run_rename_plans(rename_tmp_plans, args.dry_run)

        combine_plans = plan_filesystem_combinations(tmp_root, output_folder)

        # Workers
        img_workers = args.image_workers
        vid_workers = args.video_workers
        if args.workers is not None:
            img_workers = max(1, args.workers)
            vid_workers = max(1, args.workers)
        else:
            cpu = os.cpu_count() or 4
            img_tasks = sum(1 for p in combine_plans if p.kind == MemoryKind.IMAGE)
            vid_tasks = sum(1 for p in combine_plans if p.kind == MemoryKind.VIDEO)
            img_workers = max(1, min(cpu, img_tasks))
            vid_workers = max(1, min(cpu, vid_tasks))

        # 6) Combine
        images_done, videos_done = run_combine_plans(
            combine_plans, args.dry_run, img_workers, vid_workers
        )

    # -----------------------------
    # Summary
    # -----------------------------
    print("\n✅ Dry run complete." if args.dry_run else "\n✅ All Memories processed!")  # noqa: E501
    print(f"📁 Output folder: {output_folder}")
    print(f"📦 ZIPs {'planned' if args.dry_run else 'extracted'}: {len(extract_plans)}")  # noqa: E501

    total_unlabeled = len(rename_input_plans) + len(rename_tmp_plans)
    print(
        "📄 Unnamed files → .jpg "
        f"{'planned' if args.dry_run else 'done'}: {total_unlabeled}"
    )

    if args.dry_run:
        print(f"🎬 Standalone MP4s planned: {mp4_candidates}")
    else:
        print(f"🎬 Standalone MP4s copied: {mp4_copied}")

    if args.dry_run:
        planned_images = sum(
            1 for p in combine_plans if p.kind == MemoryKind.IMAGE
        )
        planned_videos = sum(
            1 for p in combine_plans if p.kind == MemoryKind.VIDEO
        )
        if planned_images or planned_videos:
            print(
                f"🎨 Image combines planned: {planned_images} | "
                f"🎞️ Video combines planned: {planned_videos}"
            )
        elif zip_preview_plans:
            zi = sum(1 for p in zip_preview_plans if p.kind == MemoryKind.IMAGE)
            zv = sum(1 for p in zip_preview_plans if p.kind == MemoryKind.VIDEO)
            print(f"🎨 Image combines planned: {zi} | 🎞️ Video combines planned: {zv}")  # noqa: E501
        else:
            print("🎨 Image combines planned: 0 | 🎞️ Video combines planned: 0")
    else:
        print(
            f"🎨 Images combined: {images_done} | "
            f"🎞️ Videos combined: {videos_done}"
        )

    # Totals snapshot
    inp = count_input_breakdown(input_folder, output_folder)
    print(
        f"⬆️ Input Memories: {inp.total_relevant}"
        f" (zips: {inp.zips}, unnamed: {inp.unnamed_no_ext}, mp4s: {inp.mp4s})"
    )
    print(f"⬇️ Output Memories: {count_output_memories(output_folder)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
