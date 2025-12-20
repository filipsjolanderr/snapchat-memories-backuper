#!/usr/bin/env python3
"""
Tests for the Downloader component.
"""

import unittest
import tempfile
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from snap_memories.download import Downloader
from snap_memories.models import DownloadItem, MemoryKind


class TestDownloader(unittest.TestCase):
    """Test download functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.downloader = Downloader(workers=4)

    def test_plan(self):
        """Test planning downloads from HTML."""
        html_content = """
        <html>
        <body>
        <table>
        <tr>
            <td>2024-01-15 14:30:25 UTC</td>
            <td>Image</td>
            <td>Latitude, Longitude: 37.7749, -122.4194</td>
            <td><a onclick="downloadMemories('https://example.com/download?mid=12345678-1234-1234-1234-123456789abc')">Download</a></td>
        </tr>
        </table>
        </body>
        </html>
        """
        
        html_path = self.temp_dir / "memories.html"
        html_path.write_text(html_content)
        
        items = self.downloader.plan(html_path)
        
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].uuid, "12345678-1234-1234-1234-123456789abc")


    def test_download_item_dry_run(self):
        """Test file download in dry run mode."""
        item = DownloadItem(
            uuid="12345678-1234-1234-1234-123456789abc",
            url="https://example.com/test.jpg",
            filename="test.jpg",
            saved_at_utc=datetime(2024, 1, 15, 14, 30, 25, tzinfo=timezone.utc),
            latitude=37.7749,
            longitude=-122.4194,
            kind=MemoryKind.IMAGE
        )
        
        output_dir = self.temp_dir / "downloads"
        
        # Async method requires session and semaphore, but they are not used in dry_run
        # We can pass None or mocks
        async def run_test():
             return await self.downloader.download_item(Mock(), item, output_dir, Mock(), dry_run=True)

        success, kind = asyncio.run(run_test())
        
        self.assertTrue(success)
        self.assertEqual(kind, MemoryKind.IMAGE)


    def test_download_all_dry_run(self):
        """Test downloading all items in dry run mode."""
        items = [
            DownloadItem(
                uuid="12345678-1234-1234-1234-123456789abc",
                url="https://example.com/test.jpg",
                filename="test.jpg",
                saved_at_utc=datetime(2024, 1, 15, 14, 30, 25, tzinfo=timezone.utc),
                latitude=37.7749,
                longitude=-122.4194,
                kind=MemoryKind.IMAGE
            ),
            DownloadItem(
                uuid="87654321-4321-4321-4321-cba987654321",
                url="https://example.com/test.mp4",
                filename="test.mp4",
                saved_at_utc=datetime(2024, 1, 16, 15, 45, 30, tzinfo=timezone.utc),
                latitude=None,
                longitude=None,
                kind=MemoryKind.VIDEO
            )
        ]
        
        output_dir = self.temp_dir / "downloads"
        
        async def run_test():
            return await self.downloader.download_all(items, output_dir, dry_run=True)
            
        imgs, vids = asyncio.run(run_test())
        
        self.assertEqual(imgs, 1)
        self.assertEqual(vids, 1)




if __name__ == '__main__':
    unittest.main()
