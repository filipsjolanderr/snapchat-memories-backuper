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
        
        # UUID patterns
        UUID_PATTERN = re.compile(r"([0-9a-fA-F-]{36})")
        
        discovered_count = 0
        
        for dirpath, files in iter_files_recursively(input_folder):
            # Skip output dir if it's inside input
            if output_dir == dirpath or output_dir in dirpath.parents:
                continue
                
            for name in files:
                p = dirpath / name
                m = UUID_PATTERN.search(name)
                if not m:
                    continue
                
                uuid_str = m.group(1).lower()
                
                # Determine state based on file type
                # .zip -> DOWNLOADED (needs extraction)
                # -main.xyz -> EXTRACTED (needs combination)
                # .jpg/.mp4 (no -main) -> COMBINED (needs metadata) or COMPLETED? 
                # Difficulity: Input folder might be a mess of raw downloads AND processed files.
                # Only add if not already in state? Or update?
                
                if uuid_str not in monitor.state:
                    status = ProcessingStatus.PENDING
                    kind = "image" # Default, refine below
                    
                    lower_name = name.lower()
                    if lower_name.endswith(".zip"):
                        status = ProcessingStatus.DOWNLOADED
                    elif "-main." in lower_name:
                         # Likely extracted
                         status = ProcessingStatus.EXTRACTED
                         kind = "video" if ".mp4" in lower_name else "image"
                    elif lower_name.endswith(".mp4"):
                        status = ProcessingStatus.COMBINED
                        kind = "video"
                    elif lower_name.endswith((".jpg", ".jpeg", ".png")):
                        status = ProcessingStatus.COMBINED
                        kind = "image"
                    
                    # Try to get metadata
                    saved_at = None
                    lat = None
                    lon = None
                    if uuid_str in meta_map:
                        mm = meta_map[uuid_str]
                        saved_at = mm.saved_at_utc.isoformat() if mm.saved_at_utc else None
                        lat = mm.latitude
                        lon = mm.longitude
                        if mm.kind: kind = mm.kind.value

                    # Directly create state since update_status doesn't create
                    monitor.state[uuid_str] = MemoryState(
                        uuid=uuid_str,
                        url="", # Unknown source URL when hydrating from folder
                        status=status,
                        kind=kind,
                        saved_at_utc=saved_at,
                        latitude=lat,
                        longitude=lon,
                        local_path=str(p)
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
