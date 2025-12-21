
import pytest
import shutil
import tempfile
import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from snap_memories.config import AppConfig
from snap_memories.state import StateManager, ProcessingStatus, MemoryState
from snap_memories.stages import DownloadStage
from snap_memories.models import DownloadItem, MemoryKind

@pytest.fixture
def benchmark_env():
    tmp_dir = Path(tempfile.mkdtemp())
    output_dir = tmp_dir / "output"
    output_dir.mkdir()
    state_file = output_dir / "state.json"
    manager = StateManager(state_file)
    cfg = AppConfig()
    
    yield tmp_dir, output_dir, manager, cfg
    
    shutil.rmtree(tmp_dir)

@pytest.mark.asyncio
async def test_benchmark_download_stage_overhead(benchmark_env):
    """
    Benchmarks the overhead of the DownloadStage loop (state updating, task scheduling),
    mocking the actual network IO to be near-instant.
    This reveals if the python/asyncio loop is the bottleneck for high-throughput connections.
    """
    tmp_dir, output_dir, manager, cfg = benchmark_env
    
    count = 1000
    items = []
    from datetime import datetime
    
    # Create fake items
    for i in range(count):
        uuid = f"00000000-0000-0000-0000-{i:012d}"
        items.append(DownloadItem(
            uuid=uuid,
            url=f"http://example.com/{uuid}",
            filename=f"{uuid}.jpg",
            saved_at_utc=datetime.now(),
            latitude=0, longitude=0,
            kind=MemoryKind.IMAGE
        ))
        
    # Populate state as PENDING so stage picks them up
    manager.add_from_downloads(items)
    
    stage = DownloadStage(manager, cfg)
    
    # Mock the downloader to return instantly
    # We patch the downloader instance on the stage
    async def mock_download(*args, **kwargs):
        # Simulate tiny IO delay
        await asyncio.sleep(0.001) 
        return True, "image", Path("dummy/path")

    with patch.object(stage.downloader, 'download_item', side_effect=mock_download):
        start = time.perf_counter()
        await stage.run(Path("dummy.html"), output_dir)
        end = time.perf_counter()
        
    duration = end - start
    print(f"\nDownload Loop Overhead ({count} items): {duration:.4f}s")
    print(f"Rate: {count / duration:.2f} items/sec")
