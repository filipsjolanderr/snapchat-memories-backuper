#!/usr/bin/env python3
"""
Tests for the Pipeline component (integration tests).
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from snap_memories.pipeline import Pipeline
from snap_memories.config import AppConfig


class TestPipeline(unittest.TestCase):
    """Integration tests for the Pipeline workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def test_run_auto_with_html(self):
        """Test run_auto with HTML file."""
        html_path = self.temp_dir / "memories.html"
        html_path.write_text("<html><body></body></html>")
        
        cfg = AppConfig(
            input_path=html_path,
            output_dir=self.temp_dir / "output",
            dry_run=True
        )
        
        pipeline = Pipeline(cfg)
        result = pipeline.run_auto()
        
        self.assertEqual(result, 0)

    def test_run_auto_with_folder(self):
        """Test run_auto with folder."""
        input_folder = self.temp_dir / "input"
        input_folder.mkdir()
        
        cfg = AppConfig(
            input_path=input_folder,
            output_dir=self.temp_dir / "output",
            dry_run=True
        )
        
        pipeline = Pipeline(cfg)
        result = pipeline.run_auto()
        
        self.assertEqual(result, 0)

    def test_run_download_mode_dry_run(self):
        """Test download mode in dry run."""
        html_path = self.temp_dir / "memories.html"
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
        html_path.write_text(html_content)
        
        cfg = AppConfig(
            input_path=html_path,
            output_dir=self.temp_dir / "output",
            dry_run=True
        )
        
        pipeline = Pipeline(cfg)
        result = pipeline.run_download_mode(html_path)
        
        self.assertEqual(result, 0)

    def test_run_folder_mode_dry_run(self):
        """Test folder mode in dry run."""
        input_folder = self.temp_dir / "input"
        input_folder.mkdir()
        
        # Create test files
        (input_folder / "test.zip").touch()
        (input_folder / "video.mp4").touch()
        (input_folder / "unnamed").touch()
        
        cfg = AppConfig(
            input_path=input_folder,
            output_dir=self.temp_dir / "output",
            dry_run=True
        )
        
        pipeline = Pipeline(cfg)
        result = pipeline.run_folder_mode(input_folder)
        
        self.assertEqual(result, 0)

    def test_run_folder_mode_with_metadata(self):
        """Test folder mode with metadata HTML."""
        input_folder = self.temp_dir / "input"
        input_folder.mkdir()
        
        html_path = self.temp_dir / "memories.html"
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
        html_path.write_text(html_content)
        
        cfg = AppConfig(
            input_path=input_folder,
            output_dir=self.temp_dir / "output",
            metadata_html=html_path,
            dry_run=True
        )
        
        pipeline = Pipeline(cfg)
        result = pipeline.run_folder_mode(input_folder)
        
        self.assertEqual(result, 0)


if __name__ == '__main__':
    unittest.main()
