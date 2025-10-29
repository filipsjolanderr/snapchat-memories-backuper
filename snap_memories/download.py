from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import requests
from tqdm import tqdm

from .logger import dry_run as log_dry_run, error, warning
from .metadata import _set_file_times, parse_download_urls_from_html
from .models import DownloadItem, MemoryKind


class Downloader:
    def __init__(self, workers: int = 16) -> None:
        self.workers = workers

    def plan(self, html_path: Path) -> List[DownloadItem]:
        return parse_download_urls_from_html(html_path)

    def download_item(
        self, item: DownloadItem, output_dir: Path, dry_run: bool, session: requests.Session | None = None  # noqa: E501
    ) -> Tuple[bool, MemoryKind]:
        """Download a single item. Returns (success, kind)."""
        if dry_run:
            return True, item.kind

        created_session = False
        if session is None:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    )
                }
            )
            # Optimize connection pooling for faster downloads
            adapter = HTTPAdapter(
                pool_connections=10,
                pool_maxsize=20,
                max_retries=Retry(total=0)  # We handle retries ourselves
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            created_session = True

        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Use GET instead of HEAD to avoid extra request
                    # We'll check content-type from response headers
                    resp = session.get(item.url, stream=True, timeout=30)
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

                    out.parent.mkdir(parents=True, exist_ok=True)
                    # Larger chunk size for faster writes
                    with open(out, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):  # 64KB chunks
                            if chunk:
                                f.write(chunk)

                    # Detect ZIP by magic, correct ext if wrong
                    try:
                        with open(out, "rb") as f:
                            if f.read(4) == b"PK\x03\x04" and out.suffix != ".zip":
                                dst = out.with_suffix(".zip")
                                out.replace(dst)
                                out = dst
                    except Exception:
                        pass

                    _set_file_times(out, item.saved_at_utc)
                    return True, item.kind
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    else:
                        return False, item.kind
        finally:
            if created_session:
                try:
                    session.close()
                except Exception:
                    pass
        return False, item.kind

    def download_all(
        self, items: List[DownloadItem], output_dir: Path, dry_run: bool
    ) -> Tuple[int, int]:
        if dry_run:
            log_dry_run(f"would download {len(items)} files")
            imgs = sum(1 for i in items if i.kind == MemoryKind.IMAGE)
            vids = sum(1 for i in items if i.kind == MemoryKind.VIDEO)
            return imgs, vids

        imgs = 0
        vids = 0
        
        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # Create a session for each thread (thread-safe)
            futures = {
                executor.submit(self.download_item, item, output_dir, False, None): item
                for item in items
            }
            
            with tqdm(total=len(items), desc="Downloading", unit="file") as pbar:
                for future in as_completed(futures):
                    try:
                        success, kind = future.result()
                        if success:
                            if kind == MemoryKind.IMAGE:
                                imgs += 1
                            else:
                                vids += 1
                    except Exception as e:
                        item = futures[future]
                        warning(f"Failed to download {item.uuid}: {e}")
                    finally:
                        pbar.update(1)
        
        return imgs, vids
