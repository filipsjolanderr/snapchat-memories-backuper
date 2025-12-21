from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict

from .config import AppConfig
from .logger import info, error, warning
from .state import StateManager, ProcessingStatus, MemoryState
from .stages import (
    DownloadStage,
    ExtractionStage,
    CombinationStage,
    MetadataStage
)

class Pipeline:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        # Setup Logger
        if cfg.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

    def run_auto(self) -> int:
        inp = self.cfg.input_path
        if not inp:
            error("No input path specified")
            return 2
            
        if not inp.exists():
            error(f"Input path does not exist: {inp}")
            return 2

        if inp.is_file() and inp.suffix.lower() == ".html":
            return self.run_download_mode(inp)
        elif inp.is_dir():
            return self.run_folder_mode(inp)
        else:
            error(f"Input must be an HTML file or a directory: {inp}")
            return 2

    def run_download_mode(self, html_path: Path) -> int:
        output_dir = self.cfg.output_dir or html_path.parent / "memories_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        state_file = output_dir / "memories_state.json"
        monitor = StateManager(state_file)
        
        info(f"📂 Output Directory: {output_dir}")
        info(f"💾 State File: {state_file}")

        # 1. Download Stage
        dl_stage = DownloadStage(monitor, self.cfg)
        import asyncio
        asyncio.run(dl_stage.run(html_path, output_dir))
        
        # 2. Extraction Stage
        ext_stage = ExtractionStage(monitor, self.cfg)
        ext_stage.run(output_dir)
        
        # 3. Combination Stage
        comb_stage = CombinationStage(monitor, self.cfg)
        comb_stage.run(output_dir)
        
        # 4. Metadata Stage
        meta_stage = MetadataStage(monitor, self.cfg)
        meta_stage.run(output_dir)

        # Summary
        failed = monitor.get_failed()
        if failed:
            warning(f"⚠️ {len(failed)} items failed. Check state file for details.")
        else:
            info("✅ All tasks completed successfully!")
            # 5. State File Cleanup
            try:
                if state_file.exists():
                    state_file.unlink()
            except Exception as e:
                verbose(f"Failed to remove state file: {e}")
            
        return 0

    def run_folder_mode(self, input_folder: Path) -> int:
        output_dir = self.cfg.output_dir or input_folder / "processed_memories"
        output_dir.mkdir(parents=True, exist_ok=True)

        state_file = output_dir / "memories_state.json"
        monitor = StateManager(state_file)
        
        # Hydrate metadata if HTML is available
        meta_map = {}
        if self.cfg.metadata_html and self.cfg.metadata_html.exists():
            from .metadata import parse_memories_html
            info(f"📖 Reading metadata from {self.cfg.metadata_html}")
            try:
                meta_map = parse_memories_html(self.cfg.metadata_html)
            except Exception as e:
                warning(f"Failed to parse metadata HTML: {e}")

        # Hydrate state from filesystem if needed
        # We scan the input folder for files to process
        info(f"🔍 Scanning {input_folder} for memories...")
        
        from .utils import iter_files_recursively
        import re
        from collections import defaultdict
        
        # UUID patterns
        UUID_PATTERN = re.compile(r"([0-9a-fA-F-]{36})")
        
        # Pass 1: Scan and Group
        files_by_uuid = defaultdict(list)
        
        for dirpath, files in iter_files_recursively(input_folder):
            # Skip output dir if it's inside input
            if output_dir == dirpath or output_dir in dirpath.parents:
                continue
                
            for name in files:
                m = UUID_PATTERN.search(name)
                if not m:
                    continue
                
                uuid_str = m.group(1).lower()
                files_by_uuid[uuid_str].append(dirpath / name)
                
        discovered_count = 0
        
        # Pass 2: Analyze Status
        for uuid_str, paths in files_by_uuid.items():
            if uuid_str in monitor.state:
                continue
                
            # Analyze what we have
            has_zip = any(p.suffix.lower() == ".zip" for p in paths)
            has_overlay = any("overlay" in p.name.lower() for p in paths)
            has_main = any("-main" in p.name.lower() for p in paths)
            
            # Simple heuristics for "final" files (uuid.jpg / uuid.mp4 without -main)
            final_files = [p for p in paths if p.name.lower() in (f"{uuid_str}.jpg", f"{uuid_str}.mp4")]
            has_final = len(final_files) > 0
            
            status = ProcessingStatus.PENDING
            kind = "image"
            local_path = None
            
            # Determine Status Priority
            if has_zip:
                # If zip exists, we treat it as DOWNLOADED so it gets extracted 
                # (unless we decide extracted files are enough, but zip is safer source)
                status = ProcessingStatus.DOWNLOADED
                # Find the zip path
                zip_path = next(p for p in paths if p.suffix.lower() == ".zip")
                local_path = str(zip_path)
                
            elif has_overlay:
                # If overlay exists, we MUST be in EXTRACTED state to allow combination,
                # even if we have a "final" looking file (which might just be the raw main file renamed)
                status = ProcessingStatus.EXTRACTED
                # Use main file as local_path if possible, else the overlay
                # But stage usually just needs one path to know it exists. 
                # Pick the first one.
                local_path = str(paths[0])
                
            elif has_main:
                # We have -main but no overlay (caught above)? 
                # Still EXTRACTED, maybe waiting for overlay or simple rename
                status = ProcessingStatus.EXTRACTED
                local_path = str(paths[0])
                
            elif has_final:
                # Only final file exists, no zip, no overlay.
                status = ProcessingStatus.COMBINED
                local_path = str(final_files[0])
                if local_path.lower().endswith(".mp4"):
                    kind = "video"
                
            else:
                # Can't determine?
                continue

            # Attempt to refine kind from metadata
            saved_at = None
            lat = None
            lon = None
            if uuid_str in meta_map:
                mm = meta_map[uuid_str]
                saved_at = mm.saved_at_utc.isoformat() if mm.saved_at_utc else None
                lat = mm.latitude
                lon = mm.longitude
                if mm.kind: kind = mm.kind.value

            monitor.state[uuid_str] = MemoryState(
                uuid=uuid_str,
                url="",
                status=status,
                kind=kind,
                saved_at_utc=saved_at,
                latitude=lat,
                longitude=lon,
                local_path=local_path
            )
            monitor._dirty = True
            discovered_count += 1

        if discovered_count > 0:
            monitor.save()
            info(f"Discovered {discovered_count} new items from filesystem.")
        
        # Run Stages
        
        # Extract
        ext_stage = ExtractionStage(monitor, self.cfg)
        ext_stage.run(output_dir)
        
        # Combine
        comb_stage = CombinationStage(monitor, self.cfg)
        comb_stage.run(output_dir)
        
        # Metadata
        meta_stage = MetadataStage(monitor, self.cfg)
        meta_stage.run(output_dir)

        # Summary
        failed = monitor.get_failed()
        if failed:
            warning(f"⚠️ {len(failed)} items failed. Check folder and state file for details.")
        else:
            info("✅ Done processing folder. All tasks completed successfully!")
            # Cleanup state file on 100% success
            try:
                if state_file.exists():
                    state_file.unlink()
            except Exception as e:
                verbose(f"Failed to remove state file: {e}")

        return 0
