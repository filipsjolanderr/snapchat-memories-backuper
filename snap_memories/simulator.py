from __future__ import annotations

from pathlib import Path
from typing import List

from .logger import dry_run as log_dry_run, info, warning
from .metadata import parse_memories_html
from .models import CombinePlan, CopyPlan, ExtractZipPlan, MemoryKind, RenamePlan


class DryRunSimulator:
    """Simulates operations without actually performing them."""

    def __init__(self) -> None:
        self.stats: dict[str, int] = {}

    def simulate_download(self, items: List) -> tuple[int, int]:
        """Simulate downloading items."""
        imgs = sum(1 for i in items if i.kind == MemoryKind.IMAGE)
        vids = sum(1 for i in items if i.kind == MemoryKind.VIDEO)
        log_dry_run(f"would download {len(items)} files ({imgs} images, {vids} videos)")
        self.stats["downloaded_images"] = imgs
        self.stats["downloaded_videos"] = vids
        return imgs, vids

    def simulate_ensure_dir(self, path: Path) -> None:
        """Simulate creating a directory."""
        log_dry_run(f"would ensure folder '{path}'")

    def simulate_create_temp_dir(self, path: Path) -> None:
        """Simulate creating a temp directory."""
        log_dry_run(f"would create temp folder '{path}'")

    def simulate_fix_zip_files(self, count: int) -> None:
        """Simulate fixing ZIP files."""
        if count > 0:
            log_dry_run(f"would fix {count} ZIP files with wrong extensions")
            self.stats["fixed_zips"] = count

    def simulate_extract_zips(self, plans: List[ExtractZipPlan]) -> None:
        """Simulate extracting ZIP files."""
        if plans:
            info(f"📦 Would extract {len(plans)} ZIP files...")
            for p in plans:
                log_dry_run(f"would extract '{p.zip_path}' → '{p.dest_folder}'")
            self.stats["extracted_zips"] = len(plans)

    def simulate_copy_mp4s(self, plans: List[CopyPlan]) -> None:
        """Simulate copying MP4 files."""
        if plans:
            info(f"📋 Would copy {len(plans)} MP4 files...")
            for p in plans:
                log_dry_run(f"would copy '{p.src}' → '{p.dst}'")
            self.stats["copied_mp4s"] = len(plans)

    def simulate_rename_files(self, plans: List[RenamePlan]) -> None:
        """Simulate renaming files."""
        if plans:
            info(f"📝 Would rename {len(plans)} files...")
            for p in plans:
                log_dry_run(f"would rename '{p.src}' → '{p.dst}'")
            self.stats["renamed_files"] = self.stats.get("renamed_files", 0) + len(plans)

    def simulate_combine_files(
        self, plans: List[CombinePlan], image_workers: int, video_workers: int
    ) -> tuple[int, int]:
        """Simulate combining files."""
        if not plans:
            return 0, 0

        imgs = [p for p in plans if p.kind == MemoryKind.IMAGE]
        vids = [p for p in plans if p.kind == MemoryKind.VIDEO]

        info(f"🔄 Would combine {len(plans)} memories ({len(imgs)} images, {len(vids)} videos)...")
        for p in plans:
            if p.kind == MemoryKind.IMAGE:
                log_dry_run(
                    f"would combine image "
                    f"'{p.main_path}' + '{p.overlay_path}' → '{p.out_path}'"
                )
            else:
                log_dry_run(
                    f"would combine video "
                    f"'{p.main_path}' + '{p.overlay_path}' → '{p.out_path}'"
                )

        self.stats["combined_images"] = len(imgs)
        self.stats["combined_videos"] = len(vids)
        return len(imgs), len(vids)

    def simulate_apply_metadata(self, html_path: Path, output_dir: Path) -> tuple[int, int]:
        """Simulate applying metadata."""
        try:
            meta = parse_memories_html(html_path)
            if meta:
                log_dry_run(
                    f"would apply metadata for {len(meta)} entries found in HTML"
                )
                # Simulate what would happen - count files that would get metadata
                # In dry run, we can't actually check files, so estimate based on metadata
                img_count = sum(1 for m in meta.values() if m.kind == MemoryKind.IMAGE)
                vid_count = sum(1 for m in meta.values() if m.kind == MemoryKind.VIDEO)
                return img_count, vid_count
            return 0, 0
        except Exception as e:
            warning(f"Failed to parse metadata: {e}")
            return 0, 0

    def simulate_remove_zips(self, zip_files: List[Path]) -> None:
        """Simulate removing ZIP files."""
        if zip_files:
            info(f"🗑️ Would remove {len(zip_files)} ZIP files...")
            for zip_file in zip_files:
                log_dry_run(f"would remove ZIP file '{zip_file}'")
            self.stats["removed_zips"] = len(zip_files)

    def get_stats(self) -> dict[str, int]:
        """Get accumulated statistics from simulation."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset simulation statistics."""
        self.stats.clear()
