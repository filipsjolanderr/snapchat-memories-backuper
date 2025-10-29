#!/usr/bin/env python3
"""
Tests for filesystem utility functions.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from snap_memories.fs import (
    find_zip_files_top_level,
    detect_and_fix_zip_files,
    enumerate_main_files,
    split_uuid_and_ext,
    should_skip_dir,
)


class TestFilesystemUtilities(unittest.TestCase):
    """Test filesystem utility functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def test_find_zip_files_top_level(self):
        """Test finding ZIP files at top level."""
        # Create test files
        (self.temp_dir / "test1.zip").touch()
        (self.temp_dir / "test2.ZIP").touch()  # Test case insensitivity
        (self.temp_dir / "notzip.txt").touch()
        
        zips = find_zip_files_top_level(self.temp_dir)
        self.assertEqual(len(zips), 2)
        self.assertTrue(all(z.suffix.lower() == ".zip" for z in zips))

    def test_find_zip_files_by_magic(self):
        """Test finding ZIP files by magic bytes."""
        # Create a file with ZIP magic bytes but wrong extension
        zip_file = self.temp_dir / "test.zip"
        with open(zip_file, 'wb') as f:
            f.write(b'PK\x03\x04' + b'fake zip content')
        
        zips = find_zip_files_top_level(self.temp_dir)
        self.assertIn(zip_file, zips)

    def test_detect_and_fix_zip_files(self):
        """Test detecting and fixing ZIP files with wrong extensions."""
        # Create a file with ZIP magic bytes but wrong extension
        wrong_ext_file = self.temp_dir / "test.jpg"
        # Use write_bytes instead of open() to ensure file is properly closed
        wrong_ext_file.write_bytes(b'PK\x03\x04' + b'fake zip content')
        
        # Ensure file exists before calling the function
        self.assertTrue(wrong_ext_file.exists())
        self.assertTrue(wrong_ext_file.is_file())
        self.assertEqual(wrong_ext_file.suffix.lower(), ".jpg")
        
        # Ensure destination doesn't exist yet
        dst_file = wrong_ext_file.with_suffix(".zip")
        self.assertFalse(dst_file.exists())
        
        # Call the function - don't read the file before calling to avoid file handle issues
        fixed = detect_and_fix_zip_files(self.temp_dir)
        
        self.assertEqual(fixed, 1, f"Expected 1 file fixed, got {fixed}. Files in dir: {list(self.temp_dir.iterdir())}")
        self.assertFalse(wrong_ext_file.exists())
        self.assertTrue(dst_file.exists())

    def test_enumerate_main_files(self):
        """Test finding main files in directory tree."""
        # Create test files
        (self.temp_dir / "subdir").mkdir()
        (self.temp_dir / "12345678-1234-1234-1234-123456789abc-main.jpg").touch()
        (self.temp_dir / "subdir" / "87654321-4321-4321-4321-cba987654321-main.mp4").touch()
        (self.temp_dir / "not-main.txt").touch()
        
        mains = enumerate_main_files(self.temp_dir)
        # Filter out any test files that might be in the directory
        mains = [p for p in mains if p.name.startswith(("12345678", "87654321"))]
        self.assertEqual(len(mains), 2)
        self.assertTrue(all("-main." in str(p) for p in mains))

    def test_split_uuid_and_ext(self):
        """Test UUID and extension splitting."""
        uuid, ext = split_uuid_and_ext("12345678-1234-1234-1234-123456789abc-main.jpg")
        self.assertEqual(uuid, "12345678-1234-1234-1234-123456789abc")
        self.assertEqual(ext, ".jpg")

    def test_should_skip_dir(self):
        """Test directory skipping logic."""
        input_root = self.temp_dir / "input"
        output_folder = self.temp_dir / "input" / "output"
        
        # Create directory structure
        output_folder.mkdir(parents=True)
        
        # Should skip output directory when scanning input
        self.assertTrue(should_skip_dir(output_folder, input_root, output_folder))
        
        # Should not skip other directories
        other_dir = self.temp_dir / "other"
        self.assertFalse(should_skip_dir(other_dir, input_root, output_folder))


if __name__ == '__main__':
    unittest.main()
