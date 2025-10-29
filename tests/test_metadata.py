#!/usr/bin/env python3
"""
Tests for metadata parsing and writing functions.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from snap_memories.metadata import (
    parse_memories_html,
    parse_download_urls_from_html,
    write_exif_to_jpeg,
    write_png_text_metadata,
    write_mp4_metadata_ffmpeg,
    apply_metadata_to_outputs,
    _deg_to_dms_rational,
    _parse_date,
)
from snap_memories.models import MemoryKind, MemoryMeta


class TestMetadataParsing(unittest.TestCase):
    """Test metadata parsing functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def test_parse_memories_html(self):
        """Test parsing memories HTML file."""
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
        <tr>
            <td>2024-01-16 15:45:30 UTC</td>
            <td>Video</td>
            <td>No location data</td>
            <td><a onclick="downloadMemories('https://example.com/download?mid=87654321-4321-4321-4321-cba987654321')">Download</a></td>
        </tr>
        </table>
        </body>
        </html>
        """
        
        html_path = self.temp_dir / "memories.html"
        html_path.write_text(html_content)
        
        meta_by_uuid = parse_memories_html(html_path)
        
        self.assertEqual(len(meta_by_uuid), 2)
        
        # Check first memory
        meta1 = meta_by_uuid["12345678-1234-1234-1234-123456789abc"]
        self.assertEqual(meta1.kind, MemoryKind.IMAGE)
        self.assertEqual(meta1.latitude, 37.7749)
        self.assertEqual(meta1.longitude, -122.4194)
        
        # Check second memory
        meta2 = meta_by_uuid["87654321-4321-4321-4321-cba987654321"]
        self.assertEqual(meta2.kind, MemoryKind.VIDEO)
        self.assertIsNone(meta2.latitude)
        self.assertIsNone(meta2.longitude)

    def test_parse_download_urls_from_html(self):
        """Test parsing download URLs from HTML."""
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
        
        downloads = parse_download_urls_from_html(html_path)
        
        self.assertEqual(len(downloads), 1)
        download = downloads[0]
        self.assertEqual(download.uuid, "12345678-1234-1234-1234-123456789abc")
        self.assertEqual(download.url, "https://example.com/download?mid=12345678-1234-1234-1234-123456789abc")
        self.assertEqual(download.filename, "12345678-1234-1234-1234-123456789abc.tmp")
        self.assertEqual(download.kind, MemoryKind.IMAGE)

    def test_parse_date(self):
        """Test date parsing."""
        # Test standard format
        dt = _parse_date("2024-01-15 14:30:25 UTC")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 15)
        
        # Test format without seconds
        dt2 = _parse_date("2024-01-15 14:30 UTC")
        self.assertIsNotNone(dt2)
        
        # Test invalid format
        dt3 = _parse_date("invalid date")
        self.assertIsNone(dt3)

    def test_deg_to_dms_rational(self):
        """Test degree to DMS rational conversion."""
        result = _deg_to_dms_rational(37.7749)
        
        # Check that result is a tuple of tuples
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(isinstance(x, tuple) and len(x) == 2 for x in result))


class TestMetadataWriting(unittest.TestCase):
    """Test metadata writing functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)

    @patch('snap_memories.metadata.piexif')
    @patch('snap_memories.metadata.Image')
    def test_write_exif_to_jpeg(self, mock_image, mock_piexif):
        """Test EXIF writing to JPEG."""
        jpeg_path = self.temp_dir / "test.jpg"
        jpeg_path.touch()
        
        # Mock PIL Image to allow opening
        mock_img = Mock()
        mock_img.format = "JPEG"
        mock_img.__enter__ = Mock(return_value=mock_img)
        mock_img.__exit__ = Mock(return_value=False)
        mock_image.open.return_value = mock_img
        
        dt = datetime(2024, 1, 15, 14, 30, 25, tzinfo=timezone.utc)
        lat, lon = 37.7749, -122.4194
        
        result = write_exif_to_jpeg(jpeg_path, dt, lat, lon)
        
        self.assertTrue(result)
        # Verify piexif calls
        mock_piexif.dump.assert_called_once()
        mock_piexif.insert.assert_called_once()

    @patch('snap_memories.metadata.Image')
    def test_write_png_text_metadata(self, mock_image):
        """Test PNG text metadata writing."""
        png_path = self.temp_dir / "test.png"
        png_path.touch()
        
        # Mock PIL Image
        mock_im = Mock()
        mock_im.mode = "RGB"
        mock_im.__enter__ = Mock(return_value=mock_im)
        mock_im.__exit__ = Mock(return_value=False)
        mock_image.open.return_value = mock_im
        
        dt = datetime(2024, 1, 15, 14, 30, 25, tzinfo=timezone.utc)
        lat, lon = 37.7749, -122.4194
        
        result = write_png_text_metadata(png_path, dt, lat, lon)
        
        self.assertTrue(result)
        # Verify image operations
        mock_image.open.assert_called_once_with(png_path)
        mock_im.save.assert_called_once()

    @patch('snap_memories.metadata.subprocess')
    def test_write_mp4_metadata_ffmpeg(self, mock_subprocess):
        """Test MP4 metadata writing with ffmpeg."""
        mp4_path = self.temp_dir / "test.mp4"
        mp4_path.touch()
        
        dt = datetime(2024, 1, 15, 14, 30, 25, tzinfo=timezone.utc)
        lat, lon = 37.7749, -122.4194
        
        # Create the temp file path that ffmpeg would create
        tmp_path = mp4_path.with_suffix(".tmp.mp4")
        
        # Mock successful subprocess run and create temp file when called
        mock_result = Mock()
        mock_result.returncode = 0
        
        def create_temp_file(*args, **kwargs):
            # Simulate ffmpeg creating the temp file
            tmp_path.touch()
            return mock_result
        
        mock_subprocess.run.side_effect = create_temp_file
        
        result = write_mp4_metadata_ffmpeg(mp4_path, dt, lat, lon)
        
        self.assertTrue(result)
        # Verify subprocess call
        mock_subprocess.run.assert_called_once()
        args = mock_subprocess.run.call_args[0][0]
        self.assertIn("ffmpeg", args)
        self.assertIn(str(mp4_path), args)

    def test_apply_metadata_to_outputs(self):
        """Test applying metadata to output files."""
        # Create test files
        output_folder = self.temp_dir / "output"
        output_folder.mkdir()
        
        # Create files with the exact pattern the regex expects
        # Write minimal valid content so files aren't skipped (empty files are skipped)
        jpg_file = output_folder / "12345678-1234-1234-1234-123456789abc_combined.jpg"
        mp4_file = output_folder / "87654321-4321-4321-4321-cba987654321_combined.mp4"
        # Write minimal JPEG header (FF D8 FF) and MP4 header (00 00 00)
        jpg_file.write_bytes(b'\xFF\xD8\xFF\xE0\x00\x10JFIF')  # Minimal valid JPEG header
        mp4_file.write_bytes(b'\x00\x00\x00\x20ftyp')  # Minimal MP4 header
        
        # Create metadata
        meta_by_uuid = {
            "12345678-1234-1234-1234-123456789abc": MemoryMeta(
                uuid="12345678-1234-1234-1234-123456789abc",
                saved_at_utc=datetime(2024, 1, 15, 14, 30, 25, tzinfo=timezone.utc),
                latitude=37.7749,
                longitude=-122.4194,
                kind=MemoryKind.IMAGE
            ),
            "87654321-4321-4321-4321-cba987654321": MemoryMeta(
                uuid="87654321-4321-4321-4321-cba987654321",
                saved_at_utc=datetime(2024, 1, 16, 15, 45, 30, tzinfo=timezone.utc),
                latitude=None,
                longitude=None,
                kind=MemoryKind.VIDEO
            )
        }
        
        with patch('snap_memories.metadata.write_exif_to_jpeg') as mock_exif, \
             patch('snap_memories.metadata.write_mp4_metadata_ffmpeg') as mock_mp4, \
             patch('snap_memories.metadata._set_file_times') as mock_times, \
             patch('snap_memories.metadata.Image') as mock_image:
            
            # Mock PIL Image to allow opening the test files
            mock_img_obj = Mock()
            mock_img_obj.format = 'JPEG'
            mock_img_obj.__enter__ = Mock(return_value=mock_img_obj)
            mock_img_obj.__exit__ = Mock(return_value=False)
            mock_image.open.return_value = mock_img_obj
            
            images_tagged, videos_tagged = apply_metadata_to_outputs(output_folder, meta_by_uuid)
            
            # The function should find and process both files
            self.assertEqual(images_tagged, 1)
            self.assertEqual(videos_tagged, 1)
            mock_exif.assert_called_once()
            mock_mp4.assert_called_once()
            self.assertEqual(mock_times.call_count, 2)


if __name__ == '__main__':
    unittest.main()
