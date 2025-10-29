#!/usr/bin/env python3
"""
Tests for the Logger component.
"""

import unittest
from io import StringIO
from unittest.mock import patch

from snap_memories.logger import (
    Logger,
    LogLevel,
    debug,
    dry_run,
    error,
    get_logger,
    info,
    set_logger,
    verbose,
    warning,
)


class TestLogger(unittest.TestCase):
    """Test logger functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Save original logger
        self.original_logger = get_logger()
        # Create a fresh logger for each test
        self.logger = Logger(LogLevel.NORMAL)
        set_logger(self.logger)

    def tearDown(self):
        """Restore original logger."""
        set_logger(self.original_logger)

    def test_error_normal_level(self):
        """Test error logging at normal level."""
        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            error("Test error")
            output = mock_stderr.getvalue()
            self.assertIn("❌ Error: Test error", output)

    def test_error_with_exception(self):
        """Test error logging with exception."""
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            with patch('sys.stderr', new=StringIO()) as mock_stderr:
                error("Test error", e)
                output = mock_stderr.getvalue()
                self.assertIn("❌ Error: Test error", output)
                self.assertIn("Test exception", output)

    def test_error_quiet_level(self):
        """Test error logging at quiet level."""
        logger = Logger(LogLevel.QUIET)
        set_logger(logger)
        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            error("Test error")
            output = mock_stderr.getvalue()
            self.assertEqual(output, "")  # Should be empty at QUIET level

    def test_error_debug_level(self):
        """Test error logging at debug level shows traceback."""
        logger = Logger(LogLevel.DEBUG)
        set_logger(logger)
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            with patch('sys.stderr', new=StringIO()) as mock_stderr:
                error("Test error", e)
                output = mock_stderr.getvalue()
                self.assertIn("❌ Error: Test error", output)
                self.assertIn("Traceback", output)

    def test_warning_normal_level(self):
        """Test warning logging at normal level."""
        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            warning("Test warning")
            output = mock_stderr.getvalue()
            self.assertIn("⚠️  Warning: Test warning", output)

    def test_warning_quiet_level(self):
        """Test warning logging at quiet level."""
        logger = Logger(LogLevel.QUIET)
        set_logger(logger)
        with patch('sys.stderr', new=StringIO()) as mock_stderr:
            warning("Test warning")
            output = mock_stderr.getvalue()
            self.assertEqual(output, "")  # Should be empty at QUIET level

    def test_info_normal_level(self):
        """Test info logging at normal level."""
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            info("Test info")
            output = mock_stdout.getvalue()
            self.assertIn("Test info", output)

    def test_info_quiet_level(self):
        """Test info logging at quiet level."""
        logger = Logger(LogLevel.QUIET)
        set_logger(logger)
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            info("Test info")
            output = mock_stdout.getvalue()
            self.assertEqual(output, "")  # Should be empty at QUIET level

    def test_verbose_normal_level(self):
        """Test verbose logging at normal level (should not show)."""
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            verbose("Test verbose")
            output = mock_stdout.getvalue()
            self.assertEqual(output, "")  # Should be empty at NORMAL level

    def test_verbose_verbose_level(self):
        """Test verbose logging at verbose level."""
        logger = Logger(LogLevel.VERBOSE)
        set_logger(logger)
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            verbose("Test verbose")
            output = mock_stdout.getvalue()
            self.assertIn("[verbose] Test verbose", output)

    def test_debug_normal_level(self):
        """Test debug logging at normal level (should not show)."""
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            debug("Test debug")
            output = mock_stdout.getvalue()
            self.assertEqual(output, "")  # Should be empty at NORMAL level

    def test_debug_debug_level(self):
        """Test debug logging at debug level."""
        logger = Logger(LogLevel.DEBUG)
        set_logger(logger)
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            debug("Test debug")
            output = mock_stdout.getvalue()
            self.assertIn("[debug] Test debug", output)

    def test_dry_run_normal_level(self):
        """Test dry-run logging at normal level."""
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            dry_run("would do something")
            output = mock_stdout.getvalue()
            self.assertIn("DRY RUN: would do something", output)

    def test_dry_run_quiet_level(self):
        """Test dry-run logging at quiet level."""
        logger = Logger(LogLevel.QUIET)
        set_logger(logger)
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            dry_run("would do something")
            output = mock_stdout.getvalue()
            self.assertEqual(output, "")  # Should be empty at QUIET level

    def test_get_logger_default(self):
        """Test getting default logger."""
        set_logger(None)
        logger = get_logger()
        self.assertIsNotNone(logger)
        self.assertEqual(logger.level, LogLevel.NORMAL)

    def test_set_logger(self):
        """Test setting custom logger."""
        custom_logger = Logger(LogLevel.VERBOSE)
        set_logger(custom_logger)
        retrieved = get_logger()
        self.assertEqual(retrieved, custom_logger)
        self.assertEqual(retrieved.level, LogLevel.VERBOSE)


if __name__ == '__main__':
    unittest.main()
