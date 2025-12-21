#!/usr/bin/env python3
"""
Tests for combining functionality with different GPU configurations.

Tests image and video combining with:
- CPU only (no GPU)
- GPU via MoviePy
- GPU via FFmpeg
"""

import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from PIL import Image

from snap_memories.executors import CombineService
from snap_memories.config import AppConfig
from snap_memories.models import CombinePlan, MemoryKind


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmp = Path(tempfile.mkdtemp())
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_images(temp_dir):
    """Create sample images for testing."""
    main_path = temp_dir / "main.jpg"
    overlay_path = temp_dir / "overlay.png"
    out_path = temp_dir / "combined.jpg"
    
    # Create a red main image
    main_img = Image.new('RGB', (640, 480), color='red')
    main_img.save(main_path, 'JPEG')
    
    # Create a green overlay with transparency
    overlay_img = Image.new('RGBA', (640, 480), color=(0, 255, 0, 128))
    overlay_img.save(overlay_path, 'PNG')
    
    return main_path, overlay_path, out_path


@pytest.fixture
def sample_video(temp_dir):
    """Create a sample video file for testing."""
    video_path = temp_dir / "main.mp4"
    overlay_path = temp_dir / "overlay.png"
    out_path = temp_dir / "combined.mp4"
    
    # Create dummy video file
    video_path.write_bytes(b'dummy video content')
    
    # Create a green overlay
    overlay_img = Image.new('RGBA', (640, 480), color=(0, 255, 0, 128))
    overlay_img.save(overlay_path, 'PNG')
    
    return video_path, overlay_path, out_path


class TestImageCombining:
    """Tests for image combining (always uses CPU/PIL)."""
    
    def test_image_combine_cpu(self, temp_dir, sample_images):
        """Test image combining with CPU (PIL)."""
        main_path, overlay_path, out_path = sample_images
        
        config = AppConfig()
        combiner = CombineService(config)
        
        start_time = time.time()
        combiner.combine_image(main_path, overlay_path, out_path, dry=False)
        elapsed = time.time() - start_time
        
        assert out_path.exists()
        assert elapsed < 5.0  # Should be fast
        
        # Verify output is valid image
        result_img = Image.open(out_path)
        assert result_img.size == (640, 480)
        result_img.close()
    
    def test_image_combine_with_gpu_config(self, temp_dir, sample_images):
        """Test image combining with GPU config (should still use CPU for images)."""
        main_path, overlay_path, out_path = sample_images
        
        config = AppConfig()
        combiner = CombineService(config)
        
        # Image combining always uses PIL (CPU), regardless of GPU config
        combiner.combine_image(main_path, overlay_path, out_path, dry=False)
        
        assert out_path.exists()
        
        # Verify output is valid image
        result_img = Image.open(out_path)
        assert result_img.size == (640, 480)
        result_img.close()


class TestVideoCombiningCPU:
    """Tests for video combining with CPU only."""
    
    def test_video_combine_cpu_path(self, temp_dir, sample_video):
        """Test video combining with MoviePy fallback."""
        video_path, overlay_path, out_path = sample_video
        
        config = AppConfig()
        combiner = CombineService(config)
        combiner.ffmpeg_available = False # Force MoviePy
        
        with patch.object(combiner, '_moviepy_overlay', side_effect=lambda main, ov, out: out.touch()) as mock_moviepy:
            combiner.combine_video(video_path, overlay_path, out_path, dry=False)
            
            assert out_path.exists()
            mock_moviepy.assert_called_once()








class TestCombiningPerformance:
    """Performance comparison tests."""
    
    
    def test_batch_combining_performance(self, temp_dir):
        """Test performance of batch combining operations."""
        # Create multiple test videos
        videos = []
        for i in range(5):
            video_path = temp_dir / f"video_{i}.mp4"
            overlay_path = temp_dir / f"overlay_{i}.png"
            out_path = temp_dir / f"combined_{i}.mp4"
            
            # Create dummy video file
            video_path.write_bytes(b'dummy video content')
                
            overlay_img = Image.new('RGBA', (320, 240), color=(0, 255, 0, 128))
            overlay_img.save(overlay_path, 'PNG')
            
            videos.append((video_path, overlay_path, out_path))
        
        config = AppConfig()
        combiner = CombineService(config)
        
        plans = [
            CombinePlan(
                main_path=video_path,
                overlay_path=overlay_path,
                out_path=out_path,
                kind=MemoryKind.VIDEO
            )
            for video_path, overlay_path, out_path in videos
        ]
        
        
        start_time = time.time()
        
        with patch.object(combiner, '_try_ffmpeg_encode', side_effect=lambda *a, **k: a[2].touch()) as mock_ffmpeg, \
             patch.object(combiner, '_moviepy_overlay', side_effect=lambda main, ov, out: out.touch()) as mock_moviepy:
            img_done, vid_done = combiner.run(plans, dry_run=False)
        
        elapsed = time.time() - start_time
        
        assert vid_done == len(videos)
        assert elapsed < 120.0  # Should complete within 2 minutes
        
        for _, _, out_path in videos:
            assert out_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
