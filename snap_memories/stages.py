from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import as_completed
from .utils import StreamlitThreadPoolExecutor as ThreadPoolExecutor
from pathlib import Path
from typing import List

import aiohttp
from tqdm import tqdm as std_tqdm 
from tqdm.asyncio import tqdm

from .download import Downloader
from .logger import info, warning, error, verbose
from .models import DownloadItem, MemoryKind, ExtractZipPlan, CombinePlan
from .state import StateManager, ProcessingStatus, MemoryState
from .executors import ZipService, CombineService
from .metadata import apply_metadata_to_outputs, _process_single_file_metadata, parse_download_urls_from_html
from .fs import find_zip_files_recursively

class BaseStage(ABC):
    def __init__(self, state_manager: StateManager, config):
        self.state_manager = state_manager
        self.config = config

    @abstractmethod
    def run(self):
        pass


class DownloadStage(BaseStage):
    def __init__(self, state_manager: StateManager, config):
        super().__init__(state_manager, config)
        self.downloader = Downloader(workers=config.download_workers)

    async def run(self, html_path: Path, output_dir: Path):
        info("🚀 Starting Download Stage")
        
        # 1. Parse HTML to get all potential items
        try:
            items = parse_download_urls_from_html(html_path)
            # Filter duplicates if any? parse_download_urls_from_html returns list
        except Exception as e:
            error(f"Failed to parse HTML: {e}")
            return
            
        # 2. Add to state
        new_count = self.state_manager.add_from_downloads(items)
        if new_count > 0:
            info(f"Added {new_count} new items to state")
        self.state_manager.save()

        # 3. Filter pending items
        pending_states = self.state_manager.get_pending()
        
        # Map UUID back to DownloadItem
        uuid_to_item = {item.uuid: item for item in items}
        
        to_download = []
        for state in pending_states:
             if state.status in (ProcessingStatus.PENDING, ProcessingStatus.FAILED):
                 if state.uuid in uuid_to_item:
                     to_download.append(uuid_to_item[state.uuid])
                 else:
                     # This might happen if state has items from old HTML
                     pass

        if not to_download:
            return

        if self.config.dry_run:
            info(f"[Dry Run] Would download {len(to_download)} files")
            return

        # 4. Execute Download
        chunk_size = 50 # Unused now for saving, but kept if needed
        processed_since_save = 0
        import time
        last_save_time = time.time()
        
        semaphore = asyncio.Semaphore(self.config.download_workers)
        connector = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)
        
        async with aiohttp.ClientSession(
            headers={"User-Agent": "SnapchatMemoriesBackup/2.0"}, 
            connector=connector
        ) as session:
            
            tasks = []
            
            async def _process_item(item: DownloadItem):
                nonlocal processed_since_save
                try:
                    success, kind, path = await self.downloader.download_item(
                        session, item, output_dir, semaphore, False
                    )
                    if success:
                        self.state_manager.update_status(
                            item.uuid, 
                            ProcessingStatus.DOWNLOADED, 
                            local_path=path
                        )
                    else:
                        self.state_manager.update_status(
                            item.uuid,
                            ProcessingStatus.FAILED,
                            error="Download failed (retries exhausted)"
                        )
                except Exception as e:
                    self.state_manager.update_status(
                        item.uuid,
                        ProcessingStatus.FAILED,
                        error=str(e)
                    )
                
                processed_since_save += 1
                
                # OPTIMIZATION: Save based on time, not just count, to avoid frequent IO on fast connections
                # Save at most every 2 seconds
                nonlocal last_save_time
                now = time.time()
                if now - last_save_time > 2.0:
                    self.state_manager.save()
                    last_save_time = now


            for item in to_download:
                tasks.append(_process_item(item))

            for f in tqdm.as_completed(tasks, desc="Downloading", unit="file"):
                await f

        self.state_manager.save()


class ExtractionStage(BaseStage):
    def __init__(self, state_manager: StateManager, config):
        super().__init__(state_manager, config)
        self.zipper = ZipService()

    def run(self, output_dir: Path):
        # We also pick up EXTRACTED items for self-healing in case they were advanced incorrectly
        items = [s for s in self.state_manager.get_pending() if s.status in [ProcessingStatus.DOWNLOADED, ProcessingStatus.EXTRACTED, ProcessingStatus.FAILED]]
        if not items:
            return

        to_extract = []
        auto_advance = []

        for s in items:
            path = Path(s.local_path) if s.local_path else None
            
            # Self-healing: if path points to non-existent .mp4/.jpg but .zip exists, use .zip
            if (not path or not path.exists()) and (output_dir / f"{s.uuid}.zip").exists():
                path = output_dir / f"{s.uuid}.zip"
                self.state_manager.update_status(s.uuid, s.status, local_path=path)

            if path and path.exists() and path.suffix.lower() == ".zip":
                to_extract.append(s)
            elif s.status == ProcessingStatus.DOWNLOADED:
                auto_advance.append(s)

        if auto_advance:
            info(f"⏩ Auto-advancing {len(auto_advance)} non-zip items...")
            for s in auto_advance:
                self.state_manager.update_status(s.uuid, ProcessingStatus.EXTRACTED)
        
        if not to_extract:
            self.state_manager.save()
            return

        info(f"📂 Processing {len(to_extract)} items for extraction...")
        
        if self.config.dry_run:
            info(f"[Dry Run] Would extract {len(to_extract)} zips")
            return

        # 2. Extract Zips
        def _process_extract(s: MemoryState):
            if not s.local_path: return
            p = ExtractZipPlan(zip_path=Path(s.local_path), dest_folder=output_dir)
            
            # Debug zip content
            try:
                import zipfile
                zp = p.zip_path
                sz = zp.stat().st_size
                info(f"DEBUG: Inspecting zip {zp.name} (size: {sz} bytes)")
                if sz > 0:
                    try:
                        with zipfile.ZipFile(zp, 'r') as zf:
                            info(f"DEBUG: Zip {zp.name} contents: {zf.namelist()}")
                    except zipfile.BadZipFile:
                         warning(f"DEBUG: {zp.name} is NOT a valid zip file!")
            except Exception as e:
                warning(f"DEBUG: Failed to inspect zip {p.zip_path}: {e}")

            try:

                extracted = self.zipper.extract_one(p)
                if extracted:
                    # Renormalization logic:
                    # Rename extracted files to match UUID if they don't match.
                    # Files inside zip might be named differently (e.g. random guid-main.mp4)
                    # We want them to be {s.uuid}-main.mp4 or {s.uuid}-overlay.png
                    
                    for fpath in extracted:
                        info(f"DEBUG: ExtractionStage checking extracted item: {fpath}")
                        fname = fpath.name
                        lower_name = fname.lower()
                        
                        target_stem = s.uuid
                        suffix = fpath.suffix.lower()
                        new_name = None
                        
                        if "-main" in lower_name:
                             new_name = f"{target_stem}-main{suffix}"
                        elif "-overlay" in lower_name:
                             new_name = f"{target_stem}-overlay{suffix}"
                        elif "overlay" in lower_name: # fallback
                             new_name = f"{target_stem}-overlay{suffix}"
                        else:
                             # Assume main if ambiguous and big? Or just main if single file?
                             # Safest is to treat as main if not overlay
                             new_name = f"{target_stem}-main{suffix}"
                        
                        if new_name and new_name != fname:
                            try:
                                new_path = fpath.parent / new_name
                                # Handle collision unique
                                if new_path.exists():
                                    try: new_path.unlink()
                                    except: pass
                                fpath.replace(new_path)
                                info(f"EXTRACT: Renamed {fpath.name} -> {new_name} in {fpath.parent}")
                            except Exception as e:
                                warning(f"Failed to rename {fpath.name} to {new_name}: {e}")

                    self.state_manager.update_status(s.uuid, ProcessingStatus.EXTRACTED)
                   # optionally remove zip? kept for safety for now
                elif extracted is not None:
                    # Not None but empty list (or False in old logic, but extract_one returns list or None now)
                    # Means skipped/empty.
                    self.state_manager.update_status(s.uuid, ProcessingStatus.EXTRACTED)
            except Exception as e:
                self.state_manager.update_status(s.uuid, ProcessingStatus.FAILED, error=str(e))

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(std_tqdm(executor.map(_process_extract, to_extract), total=len(to_extract), desc="Extracting", unit="zip"))

        self.state_manager.save()


class CombinationStage(BaseStage):
    def __init__(self, state_manager: StateManager, config):
        super().__init__(state_manager, config)
        self.combiner = CombineService(config)

    def run(self, output_dir: Path):
        all_pending = [s for s in self.state_manager.get_pending() if s.status in (ProcessingStatus.EXTRACTED, ProcessingStatus.FAILED)]
        if not all_pending:
            return

        pending = []
        for s in all_pending:
            # Check if final file already exists in output_dir
            final_jpg = output_dir / f"{s.uuid}.jpg"
            final_mp4 = output_dir / f"{s.uuid}.mp4"
            if final_jpg.exists():
                self.state_manager.update_status(s.uuid, ProcessingStatus.COMBINED, local_path=final_jpg)
            elif final_mp4.exists():
                self.state_manager.update_status(s.uuid, ProcessingStatus.COMBINED, local_path=final_mp4)
            else:
                pending.append(s)

        if not pending:
            return

        info(f"🎬 Processing {len(pending)} items for combination...")
        
        to_combine = []
        auto_advance = []
        
        # Scan for overlay/main pairs
        # This part is tricky because exact filenames vary. 
        # But generally: uuid-main.jpg/mp4 + uuid-overlay.png -> uuid.jpg/mp4
        # Or if just single file, it's already there?
        
        for s in pending:
            # Check if we need to combine
            # Look for -main and -overlay in output_dir matching this UUID (or SID)
            
            uuid_stem = s.uuid
            sid_stem = s.sid
            
            # 1. Main check with uuid (recursive)
            def _find_file(stem: str, ext: str) -> Optional[Path]:
                # Try direct first (optimization)
                direct = output_dir / f"{stem}{ext}"
                if direct.exists():
                    return direct
                # Then recursive (e.g. if extracted to a subfolder)
                matches = list(output_dir.rglob(f"{stem}{ext}"))
                if matches:
                    self.logger.verbose(f"Found {stem}{ext} recursively at: {matches[0]}")
                    return matches[0]
                return None

            main_jpg = _find_file(f"{uuid_stem}-main", ".jpg")
            main_mp4 = _find_file(f"{uuid_stem}-main", ".mp4")
            overlay = _find_file(f"{uuid_stem}-overlay", ".png")
            
            # 2. Fallback check with sid
            if not overlay and sid_stem:
                # We reuse matches from uuid if found, but if not we search sid
                main_jpg = main_jpg or _find_file(f"{sid_stem}-main", ".jpg")
                main_mp4 = main_mp4 or _find_file(f"{sid_stem}-main", ".mp4")
                overlay = _find_file(f"{sid_stem}-overlay", ".png")
            
            plan = None
            if overlay and overlay.exists():
                if main_jpg and main_jpg.exists():
                    plan = CombinePlan(main_path=main_jpg, overlay_path=overlay, out_path=output_dir / f"{uuid_stem}.jpg", kind=MemoryKind.IMAGE)
                elif main_mp4 and main_mp4.exists():
                    plan = CombinePlan(main_path=main_mp4, overlay_path=overlay, out_path=output_dir / f"{uuid_stem}.mp4", kind=MemoryKind.VIDEO)
            
            if plan:
                to_combine.append((s, plan))
            else:
                # Fallback for simple files (no overlay)
                # Create a "Move Loop" plan so it shows up in progress bar
                
                # Determine source and destination
                uuid_main_jpg = output_dir / f"{uuid_stem}.jpg"
                uuid_main_mp4 = output_dir / f"{uuid_stem}.mp4"
                
                src_path = None
                dst_path = None
                kind = MemoryKind.IMAGE
                
                if uuid_main_jpg.exists(): 
                     # Already exists? Update state only? 
                     # Actually if it exists, logic at start of loop (lines 206-210) should have caught it.
                     # But if we are here, it means we scanned and found "final" file logic was bypassed or 
                     # maybe we are looking at fragments.
                     pass 
                
                if main_jpg and main_jpg.exists():
                    src_path = main_jpg
                    dst_path = uuid_main_jpg
                    kind = MemoryKind.IMAGE
                elif main_mp4 and main_mp4.exists():
                    src_path = main_mp4
                    dst_path = uuid_main_mp4
                    kind = MemoryKind.VIDEO
                elif sid_stem:
                    # Check sid fragments
                     sid_jpg = output_dir / f"{sid_stem}.jpg"
                     sid_mp4 = output_dir / f"{sid_stem}.mp4"
                     if sid_jpg.exists():
                         src_path = sid_jpg
                         dst_path = uuid_main_jpg
                         kind = MemoryKind.IMAGE
                     elif sid_mp4.exists():
                         src_path = sid_mp4
                         dst_path = uuid_main_mp4
                         kind = MemoryKind.VIDEO
                if s.local_path and Path(s.local_path).exists() and not s.local_path.lower().endswith(".zip"):
                    # Use local_path as source if it's not a zip (e.g. folder mode direct file)
                    p = Path(s.local_path)
                    src_path = p
                    if p.suffix.lower() == ".mp4":
                         dst_path = uuid_main_mp4
                         kind = MemoryKind.VIDEO
                    else:
                         dst_path = uuid_main_jpg
                         kind = MemoryKind.IMAGE
                
                if src_path and dst_path:
                    # Create a "move" plan
                    plan = CombinePlan(main_path=src_path, overlay_path=None, out_path=dst_path, kind=kind)
                    to_combine.append((s, plan))
                else:
                    # Could not find file?
                    warning(f"COMBINE: Could not find extracted files for uuid='{uuid_stem}' (len={len(uuid_stem)}). Checked main_jpg={main_jpg}, main_mp4={main_mp4}")
                    
                    # Debug strict existence check
                    mp4_name = f"{uuid_stem}-main.mp4"
                    mp4_path = output_dir / mp4_name
                    warning(f"DEBUG: Explicit check {mp4_path} exists? {mp4_path.exists()}")
                    
                    # Debug directory listing for matches
                    matches = list(output_dir.glob(f"*{uuid_stem}*"))
                    warning(f"DEBUG: Glob *{uuid_stem}* found: {[m.name for m in matches]}")
                    pass
            
            # Additional fallback: If we found an overlay but failed to make a plan because main was missing,
            # check if the "final" file exists and treat it as main (e.g. raw image named as uuid.jpg)
            if not plan and overlay and overlay.exists():
                fallback_main = output_dir / f"{uuid_stem}.jpg"
                if fallback_main.exists():
                    plan = CombinePlan(main_path=fallback_main, overlay_path=overlay, out_path=output_dir / f"{uuid_stem}.jpg", kind=MemoryKind.IMAGE)
                    to_combine.append((s, plan))
                else:
                    fallback_main_mp4 = output_dir / f"{uuid_stem}.mp4"
                    if fallback_main_mp4.exists():
                        plan = CombinePlan(main_path=fallback_main_mp4, overlay_path=overlay, out_path=output_dir / f"{uuid_stem}.mp4", kind=MemoryKind.VIDEO)
                        to_combine.append((s, plan))
        
        if not to_combine:
            self.state_manager.save()
            return

        if self.config.dry_run:
            info(f"[Dry Run] Would combine {len(to_combine)} items")
            return

        def _process_combine(args):
            state, plan = args
            try:
                self.combiner.combine_one(plan, False)
                self.state_manager.update_status(state.uuid, ProcessingStatus.COMBINED, local_path=plan.out_path)
                
                # Cleanup parts
                try: 
                    if plan.main_path.exists(): plan.main_path.unlink()
                    if plan.overlay_path.exists(): plan.overlay_path.unlink()
                except: pass
                
            except Exception as e:
                self.state_manager.update_status(state.uuid, ProcessingStatus.FAILED, error=f"Combine failed: {e}")

        # Parallel combine
        with ThreadPoolExecutor(max_workers=self.config.image_workers) as executor:
            list(std_tqdm(executor.map(_process_combine, to_combine), total=len(to_combine), desc="Combining", unit="mem"))

        self.state_manager.save()


class MetadataStage(BaseStage):
    def run(self, output_dir: Path):
        pending = [s for s in self.state_manager.get_pending() if s.status == ProcessingStatus.COMBINED]
        if not pending:
            return

        info(f"📅 Apply metadata for {len(pending)} items...")
        
        if self.config.dry_run:
            return

        items = []
        for s in pending:
            if s.local_path and Path(s.local_path).exists():
                # We need to reconstruct MemoryMeta
                from .models import MemoryMeta
                meta = MemoryMeta(
                     uuid=s.uuid,
                     saved_at_utc=s.saved_at_utc, 
                     latitude=s.latitude, 
                     longitude=s.longitude,
                     kind=MemoryKind.VIDEO if s.kind == 'video' else MemoryKind.IMAGE
                )
                
                # Assuming lat/lon not critically needed or stored in state? 
                # Implementation plan didn't explicitly add lat/lon to MemoryState to keep it light, 
                # but metadata logic relies on it.
                # Ideally we should populate lat/lon in StateManager or re-parse?
                # For now let's rely on what we have. If missing, we skip GPS.
                
                items.append((Path(s.local_path), s.uuid, Path(s.local_path).suffix.strip('.').lower(), meta, s))
            else:
                self.state_manager.update_status(s.uuid, ProcessingStatus.FAILED, error="File missing for metadata")

        def _apply(args):
            p, uuid, ext, meta, state = args
            try:
                # Debug specific item
                if uuid.lower().startswith("b9c129eb"):
                    warning(f"DEBUG STAGE: Processing {uuid}, lat={meta.latitude}, lon={meta.longitude}, path={p}")

                tagged_img, tagged_vid = _process_single_file_metadata(p, uuid, ext, meta)
                
                # Double check timestamp even if tagging reported false (fallback)
                if not (tagged_img or tagged_vid):
                     from .metadata import _set_file_times
                     try: _set_file_times(p, meta.saved_at_utc)
                     except: pass
                
                self.state_manager.update_status(state.uuid, ProcessingStatus.COMPLETED)
                
                # Cleanup original zip and fragments
                try:
                    # 1. Zip
                    zip_path = output_dir / f"{uuid}.zip"
                    try: zip_path.unlink(missing_ok=True)
                    except: pass
                    
                    # 2. Fragments - Direct lookup instead of slow rglob
                    # We know the possible extensions for main/overlay
                    for ext in [".jpg", ".mp4", ".png"]:
                        try: (output_dir / f"{uuid}-main{ext}").unlink(missing_ok=True)
                        except: pass
                        try: (output_dir / f"{uuid}-overlay{ext}").unlink(missing_ok=True)
                        except: pass
                    
                    # 3. Fallback fragments for sid
                    if state.sid:
                        for ext in [".jpg", ".mp4", ".png"]:
                            try: (output_dir / f"{state.sid}-main{ext}").unlink(missing_ok=True)
                            except: pass
                            try: (output_dir / f"{state.sid}-overlay{ext}").unlink(missing_ok=True)
                            except: pass
                except Exception as e:
                    verbose(f"Cleanup failed for {uuid}: {e}")
                    
            except Exception as e:
                self.state_manager.update_status(state.uuid, ProcessingStatus.FAILED, error=f"Metadata failed: {e}")

        with ThreadPoolExecutor(max_workers=32) as executor:
            list(std_tqdm(executor.map(_apply, items), total=len(items), desc="Metadata", unit="file"))

        self.state_manager.save()
