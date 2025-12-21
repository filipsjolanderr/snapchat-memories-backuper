
import pytest
import shutil
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from snap_memories.config import AppConfig
from snap_memories.state import StateManager, ProcessingStatus, MemoryState
from snap_memories.stages import ExtractionStage, CombinationStage, MetadataStage
from snap_memories.models import MemoryKind, CombinePlan

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

def create_dummy_zip(path: Path, items: int):
    import zipfile
    with zipfile.ZipFile(path, 'w') as zf:
        for i in range(items):
            zf.writestr(f"file_{i}.txt", f"content {i}")

def create_dummy_images(output_dir: Path, count: int):
    from PIL import Image
    for i in range(count):
        uuid = f"00000000-0000-0000-0000-{i:012d}"
        
        # Main
        img = Image.new('RGB', (100, 100), color='red')
        img.save(output_dir / f"{uuid}-main.jpg")
        
        # Overlay
        ovl = Image.new('RGBA', (100, 100), color=(0, 255, 0, 128))
        ovl.save(output_dir / f"{uuid}-overlay.png")

def test_benchmark_extraction(benchmark, benchmark_env):
    tmp_dir, output_dir, manager, cfg = benchmark_env
    
    # Setup
    count = 50
    for i in range(count):
        uuid = f"00000000-0000-0000-0000-{i:012d}"
        zip_path = output_dir / f"{uuid}.zip"
        create_dummy_zip(zip_path, 2) # small zip
        
        manager.state[uuid] = MemoryState(
            uuid=uuid,
            url="",
            status=ProcessingStatus.DOWNLOADED,
            kind="image",
            local_path=str(zip_path)
        )
    
    stage = ExtractionStage(manager, cfg)
    
    def run_stage():
        # Reset status for benchmark
        for s in manager.state.values():
            s.status = ProcessingStatus.DOWNLOADED
        stage.run(output_dir)

    # We benchmark the run method
    # Note: validation will fail if run multiple times without reset, so we use a wrapper
    # But benchmark runs multiple times. We need to ensure it's idempotent or reset.
    # pytest-benchmark creates a loop.
    
    # Ideally standard benchmark: just run once with timing
    start = time.perf_counter()
    run_stage()
    end = time.perf_counter()
    print(f"\nExtraction ({count} items): {end - start:.4f}s")
    
    # Verify
    assert (output_dir / "file_0.txt").exists()

def test_benchmark_combination(benchmark_env):
    tmp_dir, output_dir, manager, cfg = benchmark_env
    
    # Setup
    count = 20
    create_dummy_images(output_dir, count)
    
    for i in range(count):
        uuid = f"00000000-0000-0000-0000-{i:012d}"
        manager.state[uuid] = MemoryState(
            uuid=uuid,
            url="",
            status=ProcessingStatus.EXTRACTED,
            kind="image",
            local_path=str(output_dir / f"{uuid}-main.jpg") 
        )
    
    # Add one simple case (no overlay) to verify fix
    simple_uuid = "00000000-0000-0000-getSimple-000000000000"
    (output_dir / f"{simple_uuid}-main.jpg").touch()
    manager.state[simple_uuid] = MemoryState(
        uuid=simple_uuid,
        url="",
        status=ProcessingStatus.EXTRACTED,
        kind="image",
        local_path=str(output_dir / f"{simple_uuid}-main.jpg")
    )
    # create_dummy_images doesn't create this one's overlay, so it should trigger fallback logic

        
    stage = CombinationStage(manager, cfg)
    
    start = time.perf_counter()
    stage.run(output_dir)
    end = time.perf_counter()
    print(f"\nCombination ({count} items): {end - start:.4f}s")

@patch("snap_memories.metadata.write_exif_to_jpeg")
@patch("snap_memories.metadata.write_mp4_metadata_exiftool")
def test_benchmark_metadata_cleanup_bottleneck(mock_vid, mock_img, benchmark_env):
    """
    Specifically benchmark the cleanup logic by mocking the actual metadata writing.
    This reveals if the loop overhead (rglob) is the issue.
    """
    tmp_dir, output_dir, manager, cfg = benchmark_env
    mock_img.return_value = True
    
    # Setup many items to exaggerate O(N^2) effects
    count = 100 
    
    # Create "combined" files
    for i in range(count):
        uuid = f"00000000-0000-0000-0000-{i:012d}"
        (output_dir / f"{uuid}.jpg").touch()
        
        # Create debris to clean
        (output_dir / f"{uuid}-main.jpg").touch()
        (output_dir / f"{uuid}-overlay.png").touch()
        
        manager.state[uuid] = MemoryState(
            uuid=uuid,
            url="",
            status=ProcessingStatus.COMBINED,
            kind="image",
            saved_at_utc=datetime.now(timezone.utc).isoformat(),
            latitude=0.0,
            longitude=0.0,
            local_path=str(output_dir / f"{uuid}.jpg")
        )
        
    stage = MetadataStage(manager, cfg)
    
    start = time.perf_counter()
    stage.run(output_dir)
    end = time.perf_counter()
    
    print(f"\nMetadata+Cleanup ({count} items): {end - start:.4f}s")
    print(f"Rate: {count / (end - start):.2f} items/sec")
    
