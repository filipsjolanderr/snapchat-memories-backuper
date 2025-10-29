#!/usr/bin/env python3
"""
Tests for statistics counting functions.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from snap_memories.stats import count_input_breakdown, count_output_memories


class TestStatsFunctions(unittest.TestCase):
    """Test counting functions for input/output analysis."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def test_count_input_breakdown(self):
        """Test input file counting."""
        # Create test files
        (self.temp_dir / "test.zip").touch()
        (self.temp_dir / "unnamed_file").touch()  # No extension
        (self.temp_dir / "video.mp4").touch()
        (self.temp_dir / "main-video-main.mp4").touch()  # Should be excluded
        (self.temp_dir / "combined_video_combined.mp4").touch()  # Should be excluded
        
        output_folder = self.temp_dir / "output"
        zips, noext, mp4s, total = count_input_breakdown(self.temp_dir, output_folder)
        
        self.assertEqual(zips, 1)
        self.assertEqual(noext, 1)
        self.assertEqual(mp4s, 1)
        self.assertEqual(total, 3)

    def test_count_output_memories(self):
        """Test output memory counting."""
        # Create test files
        (self.temp_dir / "12345678-1234-1234-1234-123456789abc_combined.jpg").touch()
        (self.temp_dir / "87654321-4321-4321-4321-cba987654321_combined.mp4").touch()
        (self.temp_dir / "standalone.mp4").touch()
        (self.temp_dir / "image.jpg").touch()
        (self.temp_dir / "overlay-overlay.png").touch()  # Should be excluded
        (self.temp_dir / "main-main.jpg").touch()  # Should be excluded
        
        count = count_output_memories(self.temp_dir)
        self.assertEqual(count, 4)  # 2 combined + 1 standalone mp4 + 1 standalone image

    def test_count_output_memories_recursive(self):
        """Test output memory counting in subdirectories."""
        # Create test files in subdirectories
        (self.temp_dir / "subdir").mkdir()
        (self.temp_dir / "12345678-1234-1234-1234-123456789abc_combined.jpg").touch()
        (self.temp_dir / "subdir" / "87654321-4321-4321-4321-cba987654321_combined.mp4").touch()
        
        count = count_output_memories(self.temp_dir)
        self.assertEqual(count, 2)


if __name__ == '__main__':
    unittest.main()
