#!/usr/bin/env python3
"""
Tests for the Planner component.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from snap_memories.planner import Planner
from snap_memories.models import ExtractZipPlan, CopyPlan, RenamePlan, CombinePlan, MemoryKind


class TestPlanner(unittest.TestCase):
    """Test planning functions for operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.planner = Planner()

    def test_plan_zip_extractions(self):
        """Test ZIP extraction planning."""
        # Create test ZIP files
        (self.temp_dir / "test1.zip").touch()
        (self.temp_dir / "test2.zip").touch()
        
        dest_folder = self.temp_dir / "dest"
        plans = self.planner.plan_zip_extractions(self.temp_dir, dest_folder)
        
        self.assertEqual(len(plans), 2)
        self.assertTrue(all(isinstance(p, ExtractZipPlan) for p in plans))

    def test_plan_copy_standalone_mp4s(self):
        """Test standalone MP4 copy planning."""
        # Create test files
        (self.temp_dir / "subdir").mkdir()
        (self.temp_dir / "video1.mp4").touch()
        (self.temp_dir / "subdir" / "video2.mp4").touch()
        (self.temp_dir / "main-video-main.mp4").touch()  # Should be excluded
        
        output_folder = self.temp_dir / "output"
        plans = self.planner.plan_copy_standalone_mp4s(self.temp_dir, output_folder)
        
        self.assertEqual(len(plans), 2)
        self.assertTrue(all(isinstance(p, CopyPlan) for p in plans))

    def test_iter_standalone_mp4_candidates(self):
        """Test standalone MP4 candidate iteration."""
        # Create test files
        (self.temp_dir / "subdir").mkdir()
        (self.temp_dir / "video1.mp4").touch()
        (self.temp_dir / "subdir" / "video2.mp4").touch()
        (self.temp_dir / "main-video-main.mp4").touch()  # Should be excluded
        
        output_folder = self.temp_dir / "output"
        candidates = list(self.planner.iter_standalone_mp4_candidates(self.temp_dir, output_folder))
        
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(isinstance(c, tuple) and len(c) == 2 for c in candidates))

    def test_plan_unlabeled_renames(self):
        """Test unlabeled file rename planning."""
        # Create test files
        (self.temp_dir / "subdir").mkdir()
        (self.temp_dir / "unnamed1").touch()
        (self.temp_dir / "subdir" / "unnamed2").touch()
        (self.temp_dir / "named.txt").touch()  # Should be excluded
        
        dst_root = self.temp_dir / "dest"
        plans = self.planner.plan_unlabeled_renames(self.temp_dir, dst_root)
        
        self.assertEqual(len(plans), 2)
        self.assertTrue(all(isinstance(p, RenamePlan) for p in plans))
        self.assertTrue(all(p.dst.suffix == ".jpg" for p in plans))

    def test_plan_filesystem_combinations(self):
        """Test filesystem combination planning."""
        # Create test files
        (self.temp_dir / "subdir").mkdir()
        main_img = self.temp_dir / "12345678-1234-1234-1234-123456789abc-main.jpg"
        overlay_img = self.temp_dir / "12345678-1234-1234-1234-123456789abc-overlay.png"
        main_vid = self.temp_dir / "subdir" / "87654321-4321-4321-4321-cba987654321-main.mp4"
        overlay_vid = self.temp_dir / "subdir" / "87654321-4321-4321-4321-cba987654321-overlay.png"
        
        main_img.touch()
        overlay_img.touch()
        main_vid.touch()
        overlay_vid.touch()
        
        output_folder = self.temp_dir / "output"
        plans = self.planner.plan_filesystem_combinations(self.temp_dir, output_folder)
        
        self.assertEqual(len(plans), 2)
        self.assertTrue(all(isinstance(p, CombinePlan) for p in plans))
        
        # Check that we have one image and one video plan
        image_plans = [p for p in plans if p.kind == MemoryKind.IMAGE]
        video_plans = [p for p in plans if p.kind == MemoryKind.VIDEO]
        self.assertEqual(len(image_plans), 1)
        self.assertEqual(len(video_plans), 1)

    def test_plan_unlabeled_renames_with_skip_root(self):
        """Test unlabeled file rename planning with skip root."""
        # Create test files
        skip_root = self.temp_dir / "skip"
        skip_root.mkdir()
        (skip_root / "unnamed1").touch()
        (self.temp_dir / "unnamed2").touch()
        
        dst_root = self.temp_dir / "dest"
        plans = self.planner.plan_unlabeled_renames(self.temp_dir, dst_root, skip_root)
        
        # Should only plan for unnamed2, not unnamed1 in skip_root
        self.assertEqual(len(plans), 1)
        self.assertNotIn(skip_root / "unnamed1", [p.src for p in plans])


if __name__ == '__main__':
    unittest.main()
