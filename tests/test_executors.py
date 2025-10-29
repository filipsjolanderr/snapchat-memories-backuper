#!/usr/bin/env python3
"""
Tests for executor services (ZipService, CopyService, RenameService, CombineService).
"""

import unittest
import tempfile
import shutil
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from snap_memories.executors import ZipService, CopyService, RenameService, CombineService
from snap_memories.models import ExtractZipPlan, CopyPlan, RenamePlan, CombinePlan, MemoryKind
from snap_memories.config import AppConfig


class TestZipService(unittest.TestCase):
    """Test ZIP extraction service."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.service = ZipService()

    def test_run_zip_extractions_dry_run(self):
        """Test ZIP extraction in dry run mode."""
        # Create a test ZIP file
        zip_path = self.temp_dir / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("test.txt", "test content")
        
        dest_folder = self.temp_dir / "dest"
        plans = [ExtractZipPlan(zip_path=zip_path, dest_folder=dest_folder)]
        
        extracted = self.service.run(plans, dry_run=True)
        self.assertEqual(extracted, 0)  # Dry run doesn't extract
        self.assertFalse(dest_folder.exists())

    def test_run_zip_extractions_real(self):
        """Test actual ZIP extraction."""
        # Create a test ZIP file
        zip_path = self.temp_dir / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("test.txt", "test content")
        
        dest_folder = self.temp_dir / "dest"
        plans = [ExtractZipPlan(zip_path=zip_path, dest_folder=dest_folder)]
        
        extracted = self.service.run(plans, dry_run=False)
        self.assertEqual(extracted, 1)
        self.assertTrue(dest_folder.exists())
        self.assertTrue((dest_folder / "test.txt").exists())

    def test_run_empty_plans(self):
        """Test running with empty plans."""
        extracted = self.service.run([], dry_run=False)
        self.assertEqual(extracted, 0)


class TestCopyService(unittest.TestCase):
    """Test copy service."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.service = CopyService()

    def test_run_copy_plans_dry_run(self):
        """Test copy plans in dry run mode."""
        # Create test files
        src_file = self.temp_dir / "test.mp4"
        src_file.touch()
        dst_file = self.temp_dir / "dest" / "test.mp4"
        
        plans = [CopyPlan(src=src_file, dst=dst_file)]
        
        copied = self.service.run(plans, dry_run=True)
        self.assertEqual(copied, 1)  # Dry run counts planned operations
        self.assertFalse(dst_file.exists())

    def test_run_copy_plans_real(self):
        """Test actual file copying."""
        # Create test files
        src_file = self.temp_dir / "test.mp4"
        src_file.write_text("test content")
        dst_file = self.temp_dir / "dest" / "test.mp4"
        
        plans = [CopyPlan(src=src_file, dst=dst_file)]
        
        copied = self.service.run(plans, dry_run=False)
        self.assertEqual(copied, 1)
        self.assertTrue(dst_file.exists())
        self.assertEqual(dst_file.read_text(), "test content")

    def test_run_empty_plans(self):
        """Test running with empty plans."""
        copied = self.service.run([], dry_run=False)
        self.assertEqual(copied, 0)


class TestRenameService(unittest.TestCase):
    """Test rename service."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.service = RenameService()

    def test_run_rename_plans_dry_run(self):
        """Test rename plans in dry run mode."""
        # Create test files
        src_file = self.temp_dir / "unnamed"
        src_file.touch()
        dst_file = self.temp_dir / "dest" / "unnamed.jpg"
        
        plans = [RenamePlan(src=src_file, dst=dst_file)]
        
        renamed = self.service.run(plans, dry_run=True)
        self.assertEqual(renamed, 1)  # Dry run counts planned operations
        self.assertFalse(dst_file.exists())

    def test_run_rename_plans_real(self):
        """Test actual file renaming/copying."""
        # Create test files
        src_file = self.temp_dir / "unnamed"
        src_file.write_text("test content")
        dst_file = self.temp_dir / "dest" / "unnamed.jpg"
        
        plans = [RenamePlan(src=src_file, dst=dst_file)]
        
        renamed = self.service.run(plans, dry_run=False)
        self.assertEqual(renamed, 1)
        self.assertTrue(dst_file.exists())
        self.assertEqual(dst_file.read_text(), "test content")

    def test_run_empty_plans(self):
        """Test running with empty plans."""
        renamed = self.service.run([], dry_run=False)
        self.assertEqual(renamed, 0)


class TestCombineService(unittest.TestCase):
    """Test combine service."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.cfg = AppConfig()
        self.service = CombineService(self.cfg)

    @patch('snap_memories.executors.Image')
    def test_combine_image_dry_run(self, mock_image):
        """Test image combining in dry run mode."""
        main_path = self.temp_dir / "main.jpg"
        overlay_path = self.temp_dir / "overlay.png"
        out_path = self.temp_dir / "output.jpg"
        
        self.service.combine_image(main_path, overlay_path, out_path, dry=True)
        
        # In dry run, no actual image processing should occur
        mock_image.open.assert_not_called()
        self.assertFalse(out_path.exists())

    @patch('snap_memories.executors.Image')
    def test_combine_image_real(self, mock_image):
        """Test actual image combining."""
        # Mock PIL Image objects
        mock_main = Mock()
        mock_overlay = Mock()
        mock_combined = Mock()
        mock_rgb_image = Mock()
        
        mock_main.size = (100, 100)
        mock_overlay.size = (100, 100)
        
        # Set up the mock chain properly
        mock_image.open.side_effect = [mock_main, mock_overlay]
        mock_main.convert.return_value = mock_main
        mock_overlay.convert.return_value = mock_overlay
        mock_overlay.resize.return_value = mock_overlay
        mock_image.alpha_composite.return_value = mock_combined
        mock_image.new.return_value = mock_rgb_image
        
        main_path = self.temp_dir / "main.jpg"
        overlay_path = self.temp_dir / "overlay.png"
        out_path = self.temp_dir / "output.jpg"
        
        # Create dummy files
        main_path.touch()
        overlay_path.touch()
        
        self.service.combine_image(main_path, overlay_path, out_path, dry=False)
        
        # Verify image processing calls
        self.assertEqual(mock_image.open.call_count, 2)
        mock_rgb_image.save.assert_called_once()

    @patch('snap_memories.executors.subprocess')
    def test_combine_video_dry_run(self, mock_subprocess):
        """Test video combining in dry run mode."""
        main_path = self.temp_dir / "main.mp4"
        overlay_path = self.temp_dir / "overlay.png"
        out_path = self.temp_dir / "output.mp4"
        
        self.service.combine_video(main_path, overlay_path, out_path, dry=True)
        
        # In dry run, no actual video processing should occur
        mock_subprocess.run.assert_not_called()

    @patch('snap_memories.executors.VideoFileClip')
    @patch('snap_memories.executors.ImageClip')
    @patch('snap_memories.executors.CompositeVideoClip')
    def test_combine_video_real_moviepy(self, mock_composite, mock_image_clip, mock_video_clip):
        """Test actual video combining with MoviePy."""
        # Create service with ffmpeg_gpu disabled AND use_gpu disabled to force MoviePy path
        # (because GPU detection would auto-enable ffmpeg_gpu)
        cfg = AppConfig(use_ffmpeg_gpu=False, use_gpu=False)
        service = CombineService(cfg)
        
        # Mock video clip
        mock_clip = Mock()
        mock_clip.duration = 10.0
        mock_clip.w = 1920
        mock_clip.h = 1080
        mock_video_clip.return_value = mock_clip
        
        # Mock image clip
        mock_overlay_clip = Mock()
        mock_image_clip.return_value = mock_overlay_clip
        mock_overlay_clip.with_duration.return_value = mock_overlay_clip
        mock_overlay_clip.resized.return_value = mock_overlay_clip
        
        # Mock composite clip
        mock_final = Mock()
        mock_composite.return_value = mock_final
        
        main_path = self.temp_dir / "main.mp4"
        overlay_path = self.temp_dir / "overlay.png"
        out_path = self.temp_dir / "output.mp4"
        
        # Create dummy files
        main_path.touch()
        overlay_path.touch()
        
        service.combine_video(main_path, overlay_path, out_path, dry=False)
        
        # Verify video processing calls
        mock_video_clip.assert_called_once_with(str(main_path))
        mock_image_clip.assert_called_once_with(str(overlay_path))
        mock_final.write_videofile.assert_called_once()

    def test_run_combine_plans_dry_run(self):
        """Test running combine plans in dry run mode."""
        main_img = self.temp_dir / "main.jpg"
        overlay_img = self.temp_dir / "overlay.png"
        out_img = self.temp_dir / "output.jpg"
        
        plans = [
            CombinePlan(
                main_path=main_img,
                overlay_path=overlay_img,
                out_path=out_img,
                kind=MemoryKind.IMAGE
            )
        ]
        
        with patch.object(self.service, 'combine_image') as mock_combine:
            imgs, vids = self.service.run(plans, dry_run=True, image_workers=1, video_workers=1)
            
        self.assertEqual(imgs, 1)
        self.assertEqual(vids, 0)
        mock_combine.assert_called_once()

    def test_run_empty_plans(self):
        """Test running with empty plans."""
        imgs, vids = self.service.run([], dry_run=False, image_workers=1, video_workers=1)
        self.assertEqual(imgs, 0)
        self.assertEqual(vids, 0)


if __name__ == '__main__':
    unittest.main()
