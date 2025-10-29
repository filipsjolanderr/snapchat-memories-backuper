#!/usr/bin/env python3
"""
Tests for utility functions.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from snap_memories.utils import (
    is_within_path,
    iter_files_recursively,
    ensure_dir,
    managed_tmp_dir,
)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions for path handling and file operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def test_is_within_path(self):
        """Test path containment checking."""
        parent = self.temp_dir / "parent"
        child = parent / "child" / "file.txt"
        
        # Create the directory structure
        child.parent.mkdir(parents=True)
        child.touch()
        
        self.assertTrue(is_within_path(child, parent))
        self.assertTrue(is_within_path(parent, parent))
        self.assertFalse(is_within_path(parent, child))

    def test_iter_files_recursively(self):
        """Test recursive file iteration."""
        # Create test directory structure
        (self.temp_dir / "subdir").mkdir()
        (self.temp_dir / "file1.txt").touch()
        (self.temp_dir / "subdir" / "file2.txt").touch()
        
        files = list(iter_files_recursively(self.temp_dir))
        self.assertEqual(len(files), 2)  # Two directories
        
        # Check that files are found
        all_files = []
        for dirpath, filenames in files:
            all_files.extend(filenames)
        
        self.assertIn("file1.txt", all_files)
        self.assertIn("file2.txt", all_files)

    def test_ensure_dir_dry_run(self):
        """Test ensure_dir in dry run mode."""
        target_dir = self.temp_dir / "new_dir"
        
        with patch('builtins.print') as mock_print:
            ensure_dir(target_dir, dry_run_flag=True)
        
        self.assertFalse(target_dir.exists())
        mock_print.assert_called_once()

    def test_ensure_dir_real(self):
        """Test ensure_dir creates directory."""
        target_dir = self.temp_dir / "new_dir"
        
        ensure_dir(target_dir, dry_run_flag=False)
        
        self.assertTrue(target_dir.exists())
        self.assertTrue(target_dir.is_dir())

    def test_managed_tmp_dir_dry_run(self):
        """Test managed_tmp_dir in dry run mode."""
        tmp_dir = self.temp_dir / "tmp"
        
        with patch('builtins.print') as mock_print:
            with managed_tmp_dir(tmp_dir, dry_run_flag=True) as path:
                self.assertEqual(path, tmp_dir)
        
        self.assertFalse(tmp_dir.exists())
        mock_print.assert_called_once()

    def test_managed_tmp_dir_real(self):
        """Test managed_tmp_dir creates and cleans up directory."""
        tmp_dir = self.temp_dir / "tmp"
        
        with managed_tmp_dir(tmp_dir, dry_run_flag=False) as path:
            self.assertEqual(path, tmp_dir)
            self.assertTrue(tmp_dir.exists())
            (tmp_dir / "test.txt").touch()
        
        # Directory should be cleaned up after context exit
        self.assertFalse(tmp_dir.exists())


if __name__ == '__main__':
    unittest.main()
