#!/usr/bin/env python3
"""
Tests for the StateManager component.
"""

import unittest
import tempfile
import shutil
import json
import time
from pathlib import Path
from snap_memories.state import StateManager, ProcessingStatus, MemoryState

class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "memories_state.json"
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_init_creates_empty(self):
        """Test that initializing on missing file works."""
        mgr = StateManager(self.state_file)
        self.assertEqual(len(mgr.state), 0)
        
    def test_add_from_downloads(self):
        """Test adding download items to state."""
        mgr = StateManager(self.state_file)
        
        # Mock download items (simple objects)
        from collections import namedtuple
        from datetime import datetime, timezone
        MockItem = namedtuple('MockItem', ['uuid', 'url', 'kind', 'saved_at_utc', 'latitude', 'longitude', 'sid'])
        
        items = [
            MockItem("uuid1", "http://url1", type("Enum", (), {"value": "image"}), datetime.now(timezone.utc), 1.0, 1.0, None),
            MockItem("uuid2", "http://url2", type("Enum", (), {"value": "video"}), None, None, None, None)
        ]
        
        count = mgr.add_from_downloads(items)
        self.assertEqual(count, 2)
        self.assertIn("uuid1", mgr.state)
        self.assertIn("uuid2", mgr.state)
        self.assertEqual(mgr.state["uuid1"].status, ProcessingStatus.PENDING)
        
        # Test idempotency
        count = mgr.add_from_downloads(items)
        self.assertEqual(count, 0)

    def test_save_and_load(self):
        """Test persistence."""
        mgr = StateManager(self.state_file)
        mgr.state["test_uuid"] = MemoryState(uuid="test_uuid", url="url", status=ProcessingStatus.DOWNLOADED)
        mgr._dirty = True
        mgr.save()
        
        self.assertTrue(self.state_file.exists())
        
        # Reload
        mgr2 = StateManager(self.state_file)
        self.assertIn("test_uuid", mgr2.state)
        self.assertEqual(mgr2.state["test_uuid"].status, ProcessingStatus.DOWNLOADED)

    def test_update_status(self):
        """Test status updates."""
        mgr = StateManager(self.state_file)
        mgr.state["u1"] = MemoryState(uuid="u1", url="url")
        
        mgr.update_status("u1", ProcessingStatus.EXTRACTED, local_path=Path("/tmp/path"))
        
        self.assertEqual(mgr.state["u1"].status, ProcessingStatus.EXTRACTED)
        self.assertEqual(mgr.state["u1"].local_path, str(Path("/tmp/path")))
        
    def test_get_pending(self):
        """Test filtering pending items."""
        mgr = StateManager(self.state_file)
        mgr.state["p1"] = MemoryState(uuid="p1", url="", status=ProcessingStatus.PENDING)
        mgr.state["d1"] = MemoryState(uuid="d1", url="", status=ProcessingStatus.DOWNLOADED)
        mgr.state["c1"] = MemoryState(uuid="c1", url="", status=ProcessingStatus.COMPLETED)
        mgr.state["f1"] = MemoryState(uuid="f1", url="", status=ProcessingStatus.FAILED)
        
        # Pending should return everything NOT completed/failed/skipped
        pending = mgr.get_pending()
        uuids = {s.uuid for s in pending}
        self.assertIn("p1", uuids)
        self.assertIn("d1", uuids)
        self.assertNotIn("c1", uuids)
        self.assertNotIn("f1", uuids)

if __name__ == '__main__':
    unittest.main()
