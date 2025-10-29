#!/usr/bin/env python3
"""
Tests for CLI parsing and argument handling.
"""

import unittest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import typer
from typer.testing import CliRunner

from snap_memories.cli import app, main, _print_gpu_banner
from snap_memories.config import AppConfig


class TestCLI(unittest.TestCase):
    """Test command line interface."""

    def setUp(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_app_exists(self):
        """Test that the CLI app exists."""
        self.assertIsNotNone(app)

    @patch('snap_memories.cli.Pipeline')
    @patch('snap_memories.cli._print_gpu_banner')
    @patch('snap_memories.cli.set_logger')
    @patch('snap_memories.cli.Logger')
    def test_main_with_html_file(self, mock_logger_class, mock_set_logger, mock_banner, mock_pipeline_class):
        """Test main function with HTML file."""
        # Create a temporary HTML file
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body></body></html>')
            html_path = f.name
        
        try:
            mock_pipeline = Mock()
            mock_pipeline.run_auto.return_value = 0
            mock_pipeline_class.return_value = mock_pipeline
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger

            result = self.runner.invoke(app, [html_path, '--output', 'output_folder'])

            self.assertEqual(result.exit_code, 0)
            mock_pipeline_class.assert_called_once()
            mock_pipeline.run_auto.assert_called_once()
        finally:
            os.unlink(html_path)

    @patch('snap_memories.cli.Pipeline')
    @patch('snap_memories.cli._print_gpu_banner')
    @patch('snap_memories.cli.set_logger')
    @patch('snap_memories.cli.Logger')
    def test_main_with_folder(self, mock_logger_class, mock_set_logger, mock_banner, mock_pipeline_class):
        """Test main function with folder."""
        import tempfile
        import os
        temp_dir = tempfile.mkdtemp()
        
        try:
            mock_pipeline = Mock()
            mock_pipeline.run_auto.return_value = 0
            mock_pipeline_class.return_value = mock_pipeline
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger

            result = self.runner.invoke(app, [temp_dir, '--output', 'output_folder'])

            self.assertEqual(result.exit_code, 0)
            mock_pipeline_class.assert_called_once()
            mock_pipeline.run_auto.assert_called_once()
        finally:
            import shutil
            shutil.rmtree(temp_dir)

    @patch('snap_memories.cli.Pipeline')
    @patch('snap_memories.cli._print_gpu_banner')
    @patch('snap_memories.cli.set_logger')
    @patch('snap_memories.cli.Logger')
    def test_main_with_dry_run(self, mock_logger_class, mock_set_logger, mock_banner, mock_pipeline_class):
        """Test main function with dry-run flag."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body></body></html>')
            html_path = f.name
        
        try:
            mock_pipeline = Mock()
            mock_pipeline.run_auto.return_value = 0
            mock_pipeline_class.return_value = mock_pipeline
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger

            result = self.runner.invoke(app, [html_path, '--dry-run', '--output', 'output_folder'])

            self.assertEqual(result.exit_code, 0)
            # Verify dry_run was passed to AppConfig
            cfg = mock_pipeline_class.call_args[0][0]
            self.assertTrue(cfg.dry_run)
        finally:
            os.unlink(html_path)

    @patch('snap_memories.cli.Pipeline')
    @patch('snap_memories.cli._print_gpu_banner')
    @patch('snap_memories.cli.set_logger')
    @patch('snap_memories.cli.Logger')
    def test_main_with_metadata(self, mock_logger_class, mock_set_logger, mock_banner, mock_pipeline_class):
        """Test main function with metadata option."""
        import tempfile
        import os
        temp_dir = tempfile.mkdtemp()
        metadata_file = os.path.join(temp_dir, 'metadata.html')
        with open(metadata_file, 'w') as f:
            f.write('<html><body></body></html>')
        
        try:
            mock_pipeline = Mock()
            mock_pipeline.run_auto.return_value = 0
            mock_pipeline_class.return_value = mock_pipeline
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger

            result = self.runner.invoke(app, [temp_dir, '--metadata', metadata_file])

            self.assertEqual(result.exit_code, 0)
            # Verify metadata_html was passed to AppConfig
            cfg = mock_pipeline_class.call_args[0][0]
            self.assertIsNotNone(cfg.metadata_html)
            self.assertEqual(str(cfg.metadata_html), metadata_file)
        finally:
            import shutil
            shutil.rmtree(temp_dir)

    @patch('snap_memories.cli.Pipeline')
    @patch('snap_memories.cli._print_gpu_banner')
    @patch('snap_memories.cli.set_logger')
    @patch('snap_memories.cli.Logger')
    def test_main_with_workers(self, mock_logger_class, mock_set_logger, mock_banner, mock_pipeline_class):
        """Test main function with worker options."""
        import tempfile
        import os
        temp_dir = tempfile.mkdtemp()
        
        try:
            mock_pipeline = Mock()
            mock_pipeline.run_auto.return_value = 0
            mock_pipeline_class.return_value = mock_pipeline
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger

            result = self.runner.invoke(app, [
                temp_dir,
                '--image-workers', '4',
                '--video-workers', '2',
                '--download-workers', '16'
            ])

            self.assertEqual(result.exit_code, 0)
            cfg = mock_pipeline_class.call_args[0][0]
            self.assertEqual(cfg.image_workers, 4)
            self.assertEqual(cfg.video_workers, 2)
            self.assertEqual(cfg.download_workers, 16)
        finally:
            import shutil
            shutil.rmtree(temp_dir)

    @patch('snap_memories.cli.Pipeline')
    @patch('snap_memories.cli._print_gpu_banner')
    @patch('snap_memories.cli.set_logger')
    @patch('snap_memories.cli.Logger')
    def test_main_invalid_path(self, mock_logger_class, mock_set_logger, mock_banner, mock_pipeline_class):
        """Test main function with invalid path."""
        mock_logger = Mock()
        mock_logger_class.return_value = mock_logger

        result = self.runner.invoke(app, ['/nonexistent/path'])

        self.assertEqual(result.exit_code, 2)
        mock_logger.error.assert_called()
        mock_pipeline_class.assert_not_called()

    @patch('snap_memories.cli.Pipeline')
    @patch('snap_memories.cli._print_gpu_banner')
    @patch('snap_memories.cli.set_logger')
    @patch('snap_memories.cli.Logger')
    def test_main_pipeline_error(self, mock_logger_class, mock_set_logger, mock_banner, mock_pipeline_class):
        """Test main function when pipeline returns error."""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write('<html><body></body></html>')
            html_path = f.name
        
        try:
            mock_pipeline = Mock()
            mock_pipeline.run_auto.return_value = 1
            mock_pipeline_class.return_value = mock_pipeline
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger

            result = self.runner.invoke(app, [html_path])

            self.assertEqual(result.exit_code, 1)
        finally:
            os.unlink(html_path)

    @patch('snap_memories.cli.GPUDetector')
    @patch('snap_memories.cli.info')
    def test_print_gpu_banner_with_gpu(self, mock_info, mock_gpu_detector):
        """Test GPU banner printing when GPU is available."""
        mock_gpu_info = Mock()
        mock_gpu_info.available = True
        mock_gpu_info.codec = "h264_nvenc"
        mock_gpu_detector.detect.return_value = mock_gpu_info

        cfg = AppConfig(
            input_path=Path("test"),
            use_gpu=True,
        )
        _print_gpu_banner(cfg)

        mock_info.assert_called()
        mock_gpu_detector.detect.assert_called_once()

    @patch('snap_memories.cli.info')
    def test_print_gpu_banner_disabled(self, mock_info):
        """Test GPU banner when GPU is disabled."""
        cfg = AppConfig(
            input_path=Path("test"),
            use_gpu=False,
        )
        _print_gpu_banner(cfg)

        mock_info.assert_called_with("GPU encoding disabled by user")


if __name__ == '__main__':
    unittest.main()
