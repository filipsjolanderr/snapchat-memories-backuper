#!/usr/bin/env python3
"""
Tests for the DryRunSimulator class.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from snap_memories.simulator import DryRunSimulator
from snap_memories.models import (
    DownloadItem,
    ExtractZipPlan,
    CopyPlan,
    RenamePlan,
    CombinePlan,
    MemoryKind,
    MemoryMeta,
)


class TestDryRunSimulator(unittest.TestCase):
    """Test DryRunSimulator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.simulator = DryRunSimulator()

    def test_init(self):
        """Test simulator initialization."""
        self.assertIsInstance(self.simulator.stats, dict)
        self.assertEqual(len(self.simulator.stats), 0)

    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_download(self, mock_log):
        """Test simulating downloads."""
        items = [
            DownloadItem(
                uuid="uuid1",
                url="http://example.com/img1.jpg",
                filename="img1.jpg",
                saved_at_utc=datetime.now(),
                latitude=None,
                longitude=None,
                kind=MemoryKind.IMAGE,
            ),
            DownloadItem(
                uuid="uuid2",
                url="http://example.com/vid1.mp4",
                filename="vid1.mp4",
                saved_at_utc=datetime.now(),
                latitude=None,
                longitude=None,
                kind=MemoryKind.VIDEO,
            ),
            DownloadItem(
                uuid="uuid3",
                url="http://example.com/img2.jpg",
                filename="img2.jpg",
                saved_at_utc=datetime.now(),
                latitude=None,
                longitude=None,
                kind=MemoryKind.IMAGE,
            ),
        ]

        imgs, vids = self.simulator.simulate_download(items)

        self.assertEqual(imgs, 2)
        self.assertEqual(vids, 1)
        self.assertEqual(self.simulator.stats["downloaded_images"], 2)
        self.assertEqual(self.simulator.stats["downloaded_videos"], 1)
        mock_log.assert_called_once()
        self.assertIn("would download 3 files (2 images, 1 videos)", mock_log.call_args[0][0])

    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_download_empty(self, mock_log):
        """Test simulating downloads with empty list."""
        imgs, vids = self.simulator.simulate_download([])

        self.assertEqual(imgs, 0)
        self.assertEqual(vids, 0)
        self.assertEqual(self.simulator.stats["downloaded_images"], 0)
        self.assertEqual(self.simulator.stats["downloaded_videos"], 0)
        mock_log.assert_called_once()

    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_ensure_dir(self, mock_log):
        """Test simulating directory creation."""
        path = self.temp_dir / "test_dir"
        self.simulator.simulate_ensure_dir(path)

        mock_log.assert_called_once_with(f"would ensure folder '{path}'")
        self.assertFalse(path.exists())

    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_create_temp_dir(self, mock_log):
        """Test simulating temp directory creation."""
        path = self.temp_dir / "temp"
        self.simulator.simulate_create_temp_dir(path)

        mock_log.assert_called_once_with(f"would create temp folder '{path}'")
        self.assertFalse(path.exists())

    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_fix_zip_files(self, mock_log):
        """Test simulating ZIP file fixes."""
        self.simulator.simulate_fix_zip_files(3)

        mock_log.assert_called_once_with("would fix 3 ZIP files with wrong extensions")
        self.assertEqual(self.simulator.stats["fixed_zips"], 3)

    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_fix_zip_files_zero(self, mock_log):
        """Test simulating ZIP file fixes with zero count."""
        self.simulator.simulate_fix_zip_files(0)

        mock_log.assert_not_called()
        self.assertNotIn("fixed_zips", self.simulator.stats)

    @patch('snap_memories.simulator.log_dry_run')
    @patch('snap_memories.simulator.info')
    def test_simulate_extract_zips(self, mock_info, mock_log):
        """Test simulating ZIP extraction."""
        zip_path1 = self.temp_dir / "zip1.zip"
        zip_path2 = self.temp_dir / "zip2.zip"
        dest_folder = self.temp_dir / "dest"

        plans = [
            ExtractZipPlan(zip_path=zip_path1, dest_folder=dest_folder),
            ExtractZipPlan(zip_path=zip_path2, dest_folder=dest_folder),
        ]

        self.simulator.simulate_extract_zips(plans)

        mock_info.assert_called_once_with("📦 Would extract 2 ZIP files...")
        self.assertEqual(mock_log.call_count, 2)
        self.assertEqual(self.simulator.stats["extracted_zips"], 2)

    @patch('snap_memories.simulator.info')
    def test_simulate_extract_zips_empty(self, mock_info):
        """Test simulating ZIP extraction with empty list."""
        self.simulator.simulate_extract_zips([])

        mock_info.assert_not_called()
        self.assertNotIn("extracted_zips", self.simulator.stats)

    @patch('snap_memories.simulator.log_dry_run')
    @patch('snap_memories.simulator.info')
    def test_simulate_copy_mp4s(self, mock_info, mock_log):
        """Test simulating MP4 copying."""
        src1 = self.temp_dir / "vid1.mp4"
        src2 = self.temp_dir / "vid2.mp4"
        dst1 = self.temp_dir / "dest" / "vid1.mp4"
        dst2 = self.temp_dir / "dest" / "vid2.mp4"

        plans = [
            CopyPlan(src=src1, dst=dst1),
            CopyPlan(src=src2, dst=dst2),
        ]

        self.simulator.simulate_copy_mp4s(plans)

        mock_info.assert_called_once_with("📋 Would copy 2 MP4 files...")
        self.assertEqual(mock_log.call_count, 2)
        self.assertEqual(self.simulator.stats["copied_mp4s"], 2)

    @patch('snap_memories.simulator.info')
    def test_simulate_copy_mp4s_empty(self, mock_info):
        """Test simulating MP4 copying with empty list."""
        self.simulator.simulate_copy_mp4s([])

        mock_info.assert_not_called()
        self.assertNotIn("copied_mp4s", self.simulator.stats)

    @patch('snap_memories.simulator.log_dry_run')
    @patch('snap_memories.simulator.info')
    def test_simulate_rename_files(self, mock_info, mock_log):
        """Test simulating file renaming."""
        src1 = self.temp_dir / "unnamed1"
        src2 = self.temp_dir / "unnamed2"
        dst1 = self.temp_dir / "renamed1.jpg"
        dst2 = self.temp_dir / "renamed2.mp4"

        plans = [
            RenamePlan(src=src1, dst=dst1),
            RenamePlan(src=src2, dst=dst2),
        ]

        self.simulator.simulate_rename_files(plans)

        mock_info.assert_called_once_with("📝 Would rename 2 files...")
        self.assertEqual(mock_log.call_count, 2)
        self.assertEqual(self.simulator.stats["renamed_files"], 2)

    @patch('snap_memories.simulator.info')
    def test_simulate_rename_files_empty(self, mock_info):
        """Test simulating file renaming with empty list."""
        self.simulator.simulate_rename_files([])

        mock_info.assert_not_called()
        self.assertNotIn("renamed_files", self.simulator.stats)

    @patch('snap_memories.simulator.log_dry_run')
    @patch('snap_memories.simulator.info')
    def test_simulate_rename_files_accumulates(self, mock_info, mock_log):
        """Test that rename stats accumulate across multiple calls."""
        plans1 = [RenamePlan(src=Path("a"), dst=Path("b"))]
        plans2 = [RenamePlan(src=Path("c"), dst=Path("d"))]

        self.simulator.simulate_rename_files(plans1)
        self.simulator.simulate_rename_files(plans2)

        self.assertEqual(self.simulator.stats["renamed_files"], 2)

    @patch('snap_memories.simulator.log_dry_run')
    @patch('snap_memories.simulator.info')
    def test_simulate_combine_files(self, mock_info, mock_log):
        """Test simulating file combining."""
        main_img = self.temp_dir / "main-img.jpg"
        overlay_img = self.temp_dir / "overlay-img.png"
        out_img = self.temp_dir / "combined-img.jpg"

        main_vid = self.temp_dir / "main-vid.mp4"
        overlay_vid = self.temp_dir / "overlay-vid.png"
        out_vid = self.temp_dir / "combined-vid.mp4"

        plans = [
            CombinePlan(
                main_path=main_img,
                overlay_path=overlay_img,
                out_path=out_img,
                kind=MemoryKind.IMAGE,
            ),
            CombinePlan(
                main_path=main_vid,
                overlay_path=overlay_vid,
                out_path=out_vid,
                kind=MemoryKind.VIDEO,
            ),
            CombinePlan(
                main_path=self.temp_dir / "main-img2.jpg",
                overlay_path=self.temp_dir / "overlay-img2.png",
                out_path=self.temp_dir / "combined-img2.jpg",
                kind=MemoryKind.IMAGE,
            ),
        ]

        img_count, vid_count = self.simulator.simulate_combine_files(plans, 4, 2)

        self.assertEqual(img_count, 2)
        self.assertEqual(vid_count, 1)
        self.assertEqual(self.simulator.stats["combined_images"], 2)
        self.assertEqual(self.simulator.stats["combined_videos"], 1)
        mock_info.assert_called_once()
        self.assertIn("Would combine 3 memories (2 images, 1 videos)", mock_info.call_args[0][0])
        self.assertEqual(mock_log.call_count, 3)

    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_combine_files_empty(self, mock_log):
        """Test simulating file combining with empty list."""
        img_count, vid_count = self.simulator.simulate_combine_files([], 4, 2)

        self.assertEqual(img_count, 0)
        self.assertEqual(vid_count, 0)
        mock_log.assert_not_called()
        self.assertNotIn("combined_images", self.simulator.stats)

    @patch('snap_memories.simulator.parse_memories_html')
    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_apply_metadata(self, mock_log, mock_parse):
        """Test simulating metadata application."""
        html_path = self.temp_dir / "memories.html"
        output_dir = self.temp_dir / "output"

        # Mock metadata parsing - returns Dict[str, MemoryMeta]
        mock_meta = {
            "uuid1": MemoryMeta(
                uuid="uuid1",
                saved_at_utc=datetime.now(),
                latitude=None,
                longitude=None,
                kind=MemoryKind.IMAGE,
            ),
            "uuid2": MemoryMeta(
                uuid="uuid2",
                saved_at_utc=datetime.now(),
                latitude=None,
                longitude=None,
                kind=MemoryKind.IMAGE,
            ),
            "uuid3": MemoryMeta(
                uuid="uuid3",
                saved_at_utc=datetime.now(),
                latitude=None,
                longitude=None,
                kind=MemoryKind.VIDEO,
            ),
        }
        mock_parse.return_value = mock_meta

        img_count, vid_count = self.simulator.simulate_apply_metadata(html_path, output_dir)

        self.assertEqual(img_count, 2)
        self.assertEqual(vid_count, 1)
        mock_parse.assert_called_once_with(html_path)
        mock_log.assert_called_once_with(
            "would apply metadata for 3 entries found in HTML"
        )

    @patch('snap_memories.simulator.parse_memories_html')
    @patch('snap_memories.simulator.log_dry_run')
    def test_simulate_apply_metadata_empty(self, mock_log, mock_parse):
        """Test simulating metadata application with empty metadata."""
        html_path = self.temp_dir / "memories.html"
        output_dir = self.temp_dir / "output"

        mock_parse.return_value = {}

        img_count, vid_count = self.simulator.simulate_apply_metadata(html_path, output_dir)

        self.assertEqual(img_count, 0)
        self.assertEqual(vid_count, 0)
        mock_log.assert_not_called()

    @patch('snap_memories.simulator.parse_memories_html')
    @patch('snap_memories.simulator.warning')
    def test_simulate_apply_metadata_error(self, mock_warning, mock_parse):
        """Test simulating metadata application with parsing error."""
        html_path = self.temp_dir / "memories.html"
        output_dir = self.temp_dir / "output"

        mock_parse.side_effect = Exception("Parse error")

        img_count, vid_count = self.simulator.simulate_apply_metadata(html_path, output_dir)

        self.assertEqual(img_count, 0)
        self.assertEqual(vid_count, 0)
        mock_warning.assert_called_once()

    @patch('snap_memories.simulator.log_dry_run')
    @patch('snap_memories.simulator.info')
    def test_simulate_remove_zips(self, mock_info, mock_log):
        """Test simulating ZIP file removal."""
        zip1 = self.temp_dir / "zip1.zip"
        zip2 = self.temp_dir / "zip2.zip"
        zip_files = [zip1, zip2]

        self.simulator.simulate_remove_zips(zip_files)

        mock_info.assert_called_once_with("🗑️ Would remove 2 ZIP files...")
        self.assertEqual(mock_log.call_count, 2)
        self.assertEqual(self.simulator.stats["removed_zips"], 2)

    @patch('snap_memories.simulator.info')
    def test_simulate_remove_zips_empty(self, mock_info):
        """Test simulating ZIP file removal with empty list."""
        self.simulator.simulate_remove_zips([])

        mock_info.assert_not_called()
        self.assertNotIn("removed_zips", self.simulator.stats)

    def test_get_stats(self):
        """Test getting simulation statistics."""
        # Add some stats
        self.simulator.stats["test1"] = 5
        self.simulator.stats["test2"] = 10

        stats = self.simulator.get_stats()

        self.assertEqual(stats["test1"], 5)
        self.assertEqual(stats["test2"], 10)
        # Should return a copy, not reference
        self.assertIsNot(stats, self.simulator.stats)
        stats["test3"] = 15
        self.assertNotIn("test3", self.simulator.stats)

    def test_reset_stats(self):
        """Test resetting simulation statistics."""
        self.simulator.stats["test1"] = 5
        self.simulator.stats["test2"] = 10

        self.simulator.reset_stats()

        self.assertEqual(len(self.simulator.stats), 0)

    def test_stats_tracking_across_operations(self):
        """Test that stats accumulate correctly across different operations."""
        # Simulate some operations
        items = [
            DownloadItem(
                uuid="uuid1",
                url="http://example.com/img.jpg",
                filename="img.jpg",
                saved_at_utc=datetime.now(),
                latitude=None,
                longitude=None,
                kind=MemoryKind.IMAGE,
            ),
        ]
        self.simulator.simulate_download(items)

        plans = [
            ExtractZipPlan(
                zip_path=self.temp_dir / "zip.zip",
                dest_folder=self.temp_dir / "dest",
            ),
        ]
        self.simulator.simulate_extract_zips(plans)

        self.simulator.simulate_fix_zip_files(2)

        # Check all stats are tracked
        stats = self.simulator.get_stats()
        self.assertEqual(stats["downloaded_images"], 1)
        self.assertEqual(stats["downloaded_videos"], 0)
        self.assertEqual(stats["extracted_zips"], 1)
        self.assertEqual(stats["fixed_zips"], 2)


if __name__ == '__main__':
    unittest.main()
