#!/usr/bin/env python3
"""
Tests for the Downloader component.
"""

import unittest
import tempfile
import shutil
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
        success, kind = self.downloader.download_item(item, output_dir, dry_run=True)
        
        self.assertTrue(success)
        self.assertEqual(kind, MemoryKind.IMAGE)

    @patch('snap_memories.download.requests.Session')
    def test_download_item_real(self, mock_session_class):
        """Test actual file download."""
        # Mock session and response
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.iter_content.return_value = [b'test content']
        mock_response.raise_for_status.return_value = None
        
        mock_session.get.return_value = mock_response
        
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
        
        with patch('snap_memories.download._set_file_times') as mock_times:
            success, kind = self.downloader.download_item(item, output_dir, dry_run=False)
        
        self.assertTrue(success)
        mock_session.get.assert_called_once()
        mock_times.assert_called_once()

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
        imgs, vids = self.downloader.download_all(items, output_dir, dry_run=True)
        
        self.assertEqual(imgs, 1)
        self.assertEqual(vids, 1)

    @patch('snap_memories.download.requests.Session')
    def test_download_all_real(self, mock_session_class):
        """Test actual downloading all items."""
        # Mock session and response
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.iter_content.return_value = [b'test content']
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        
        items = [
            DownloadItem(
                uuid="12345678-1234-1234-1234-123456789abc",
                url="https://example.com/test.jpg",
                filename="test.jpg",
                saved_at_utc=datetime(2024, 1, 15, 14, 30, 25, tzinfo=timezone.utc),
                latitude=37.7749,
                longitude=-122.4194,
                kind=MemoryKind.IMAGE
            )
        ]
        
        output_dir = self.temp_dir / "downloads"
        
        with patch('snap_memories.download._set_file_times'):
            imgs, vids = self.downloader.download_all(items, output_dir, dry_run=False)
        
        self.assertEqual(imgs, 1)
        self.assertEqual(vids, 0)


if __name__ == '__main__':
    unittest.main()
