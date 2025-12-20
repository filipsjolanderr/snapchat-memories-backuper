#!/usr/bin/env python3
"""
Tests for the Pipeline Stages.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from snap_memories.stages import (
    ProcessingStatus,
    DownloadStage,
    ExtractionStage,
    CombinationStage,
    MetadataStage
)
from snap_memories.state import StateManager, MemoryState
from snap_memories.config import AppConfig

class MockConfig:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.download_workers = 1
        self.image_workers = 1
        self.video_workers = 1
        self.metadata_workers = 1
        self.use_gpu = False
        self.use_ffmpeg_gpu = False

class TestStages(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "state.json"
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def get_manager(self):
        return StateManager(self.state_file)

    @patch('snap_memories.stages.Downloader', autospec=True)
    def test_download_stage_dry_run(self, MockDownloader):
        """Test download stage dry run behavior."""
        mgr = self.get_manager()
        cfg = MockConfig(dry_run=True)
        stage = DownloadStage(mgr, cfg)
        
        # Setup mocks
        mock_downloader = MockDownloader.return_value
        from snap_memories.models import DownloadItem, MemoryKind
        from datetime import datetime
        item = DownloadItem("u1", "url", "f", datetime.now(), None, None, MemoryKind.IMAGE)
        
        # Use patch for parse_download_urls since it's a function not a method on Downloader
        with patch('snap_memories.stages.parse_download_urls_from_html') as mock_parse:
            mock_parse.return_value = [item]
            
            # Run
            import asyncio
            asyncio.run(stage.run(Path("dummy.html"), self.temp_dir))
            
            # Should add to state
            self.assertIn("u1", mgr.state)
            # Should NOT download
            mock_downloader.download_item.assert_not_called()

    @patch('snap_memories.stages.ZipService', autospec=True)
    def test_extraction_stage(self, MockZipService):
        """Test extraction stage logic."""
        mgr = self.get_manager()
        cfg = MockConfig()
        
        # Setup state: 1 zip downloaded, 1 regular file
        mgr.state["zip1"] = MemoryState("zip1", "", ProcessingStatus.DOWNLOADED, local_path=str(self.temp_dir / "test.zip"))
        mgr.state["img1"] = MemoryState("img1", "", ProcessingStatus.DOWNLOADED, local_path=str(self.temp_dir / "test.jpg"))
        mgr.save()
        
        # Touch files
        (self.temp_dir / "test.zip").touch()
        (self.temp_dir / "test.jpg").touch()
        
        stage = ExtractionStage(mgr, cfg)
        
        # Mock wrapper
        mock_zipper = MockZipService.return_value
        mock_zipper.extract_one.return_value = True
        
        stage.run(self.temp_dir)
        
        # img1 should be auto-advanced
        self.assertEqual(mgr.state["img1"].status, ProcessingStatus.EXTRACTED)
        
        # zip1 should call extract_one and update status
        mock_zipper.extract_one.assert_called_once()
        self.assertEqual(mgr.state["zip1"].status, ProcessingStatus.EXTRACTED)

    @patch('snap_memories.stages.CombineService', autospec=True)
    def test_combination_stage(self, MockCombiner):
        """Test combination stage logic."""
        mgr = self.get_manager()
        cfg = MockConfig()
        
        # Setup state
        mgr.state["u1"] = MemoryState("u1", "", ProcessingStatus.EXTRACTED, local_path=str(self.temp_dir / "u1"))
        mgr.save()
        
        # Files for combination
        (self.temp_dir / "u1-main.jpg").touch()
        (self.temp_dir / "u1-overlay.png").touch()
        
        stage = CombinationStage(mgr, cfg)
        mock_combiner = MockCombiner.return_value
        mock_combiner.combine_one.return_value = True
        
        stage.run(self.temp_dir)
        
        # Verification
        mock_combiner.combine_one.assert_called_once()
        # Should update state
        self.assertEqual(mgr.state["u1"].status, ProcessingStatus.COMBINED)
        # Should have updated local_path to final
        self.assertTrue(str(mgr.state["u1"].local_path).endswith("u1.jpg"))

if __name__ == '__main__':
    unittest.main()
