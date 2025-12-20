from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import List, Tuple

import aiofiles
import aiohttp
from tqdm.asyncio import tqdm

from .logger import dry_run as log_dry_run, warning
from .metadata import _set_file_times, parse_download_urls_from_html
from .models import DownloadItem, MemoryKind


class Downloader:
    def __init__(self, workers: int = 16) -> None:
        self.workers = workers

    def plan(self, html_path: Path) -> List[DownloadItem]:
        return parse_download_urls_from_html(html_path)

    async def download_item(
        self,
        session: aiohttp.ClientSession,
        item: DownloadItem,
        output_dir: Path,
        semaphore: asyncio.Semaphore,
        dry_run: bool,
    ) -> Tuple[bool, MemoryKind]:
        """Download a single item. Returns (success, kind)."""
        if dry_run:
            return True, item.kind

        async with semaphore:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with session.get(item.url, timeout=30) as resp:
                        resp.raise_for_status()

                        ctype = resp.headers.get("content-type", "").lower()
                        if "zip" in ctype:
                            ext = ".zip"
                        elif "jpeg" in ctype or "jpg" in ctype:
                            ext = ".jpg"
                        elif "mp4" in ctype or "video" in ctype:
                            ext = ".mp4"
                        else:
                            ext = ".jpg" if item.kind == MemoryKind.IMAGE else ".mp4"

                        out = output_dir / f"{item.uuid}{ext}"
                        if out.exists():
                            return True, item.kind

                        # Atomic download: write to .part file first
                        part_file = out.with_suffix(f"{ext}.part")
                        out.parent.mkdir(parents=True, exist_ok=True)
                        
                        try:
                            # Use aiofiles for async file writing
                            async with aiofiles.open(part_file, "wb") as f:
                                async for chunk in resp.content.iter_chunked(65536):
                                    await f.write(chunk)

                            # Check for ZIP masquerading (sync check on local file)
                            is_zip_mask = False
                            try:
                                with open(part_file, "rb") as f:
                                    if f.read(4) == b"PK\x03\x04" and ext != ".zip":
                                        is_zip_mask = True
                            except Exception:
                                pass
                                
                            if is_zip_mask:
                                final_ext = ".zip"
                                # Update final target path
                                out = output_dir / f"{item.uuid}{final_ext}"
                                # If the target .zip already exists, we are done
                                if out.exists():
                                    try:
                                        part_file.unlink()
                                    except Exception:
                                        pass
                                    return True, item.kind

                            # Atomic rename
                            part_file.replace(out)
                                    
                            # Set file times (sync operation, but fast)
                            _set_file_times(out, item.saved_at_utc)
                            return True, item.kind
                            
                        except Exception:
                            # Cleanup partial file on failure
                            try:
                                if part_file.exists():
                                    part_file.unlink()
                            except Exception:
                                pass
                            raise # Re-raise to trigger retry logic

                except Exception as e:
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        await asyncio.sleep(0.5 * (attempt + 1))
                    else:
                        warning(f"Failed to download {item.uuid}: {e}")
                        return False, item.kind
            return False, item.kind

    async def download_all(
        self, items: List[DownloadItem], output_dir: Path, dry_run: bool
    ) -> Tuple[int, int]:
        if dry_run:
            log_dry_run(f"would download {len(items)} files")
            imgs = sum(1 for i in items if i.kind == MemoryKind.IMAGE)
            vids = sum(1 for i in items if i.kind == MemoryKind.VIDEO)
            return imgs, vids

        imgs = 0
        vids = 0
        
        # Limit concurrency
        semaphore = asyncio.Semaphore(self.workers)
        
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            )
        }
        
        connector = aiohttp.TCPConnector(limit=None, ttl_dns_cache=300)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            tasks = [
                self.download_item(session, item, output_dir, semaphore, False)
                for item in items
            ]
            
            # Use tqdm for progress bar
            for f in tqdm.as_completed(tasks, desc="Downloading", unit="file"):
                try:
                    success, kind = await f
                    if success:
                        if kind == MemoryKind.IMAGE:
                            imgs += 1
                        else:
                            vids += 1
                except Exception as e:
                    warning(f"Unexpected error in download task: {e}")

        return imgs, vids
