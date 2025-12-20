#!/usr/bin/env python3
"""
Benchmark script to compare CPU and GPU encoding performance for video combining.
Supports both sequential and parallel batch processing.
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
import concurrent.futures
from pathlib import Path
from PIL import Image

# Add repository root to path
sys.path.append(str(Path(__file__).parent.parent))
from snap_memories.executors import CombineService
from snap_memories.config import AppConfig
from snap_memories.ffmpeg import get_ffmpeg_path
from snap_memories.gpu import GPUDetector

def create_sample_assets(temp_dir, duration=60):
    """Create a sample video and overlay image for benchmark."""
    video_path = temp_dir / "bench_main.mp4"
    overlay_path = temp_dir / "bench_overlay.png"
    
    print(f"Generating {duration}s sample assets in {temp_dir}...")
    
    # Generate a test video using FFmpeg
    cmd = [
        get_ffmpeg_path(), "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=1920x1080:rate=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(video_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    
    # Generate a simple overlay with transparency
    overlay_img = Image.new('RGBA', (1920, 1080), color=(0, 255, 0, 80))
    overlay_img.save(overlay_path, 'PNG')
    
    return video_path, overlay_path

def run_batch(mode, video_path, overlay_path, temp_dir, num_videos=4, workers=4):
    """Run parallel benchmark for a specific mode."""
    use_gpu = mode == "GPU"
    config = AppConfig(use_gpu=use_gpu)
    combiner = CombineService(config)
    
    if use_gpu and (not combiner.gpu_info or not combiner.gpu_info.available):
        print(" [!] GPU acceleration not available. Skipping GPU benchmark.")
        return None

    print(f"\nRunning {mode} Batch Benchmark ({num_videos} videos, {workers} workers)...")
    
    start_time = time.time()
    
    def process_one(idx):
        out_path = temp_dir / f"output_{mode.lower()}_batch_{idx}.mp4"
        combiner.combine_video(video_path, overlay_path, out_path, dry=False)
        return out_path.exists()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(process_one, range(num_videos)))
    
    elapsed = time.time() - start_time
    
    if not all(results):
        print(f" [X] Some tasks failed in {mode} mode.")
        return None
        
    print(f"  Total time: {elapsed:.2f}s")
    print(f"  Throughput: {num_videos / elapsed:.2f} videos/sec")
    
    return elapsed

def main():
    print("=" * 80)
    print(" 🚀 GPU vs CPU Parallel Batch Performance Benchmark")
    print("=" * 80)
    
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Determine available GPU
        gpu_info = GPUDetector.detect()
        if gpu_info.available:
            print(f"Detected GPU: {gpu_info.codec} ({gpu_info.hwaccel})")
        else:
            print("No compatible GPU detected. Parallel benchmark might still run on CPU.")

        duration = 60
        num_videos = 16
        workers = 8  # Increased workers to push the CPU harder
        
        video_path, overlay_path = create_sample_assets(temp_dir, duration=duration)

        # Run CPU Batch
        cpu_total = run_batch("CPU", video_path, overlay_path, temp_dir, num_videos, workers)
        
        # Run GPU Batch
        gpu_total = run_batch("GPU", video_path, overlay_path, temp_dir, num_videos, workers)
        
        # Report Results
        print("\n" + "=" * 40)
        print(f" BATCH SUMMARY ({num_videos} videos, {workers} workers)")
        print("=" * 40)
        if cpu_total:
            print(f" Total CPU Time:     {cpu_total:>8.2f}s")
        if gpu_total:
            print(f" Total GPU Time:     {gpu_total:>8.2f}s")
            
        if cpu_total and gpu_total:
            speedup = cpu_total / gpu_total
            print("-" * 40)
            print(f" Speedup:            {speedup:>8.2f}x")
            
            if speedup > 1.1:
                print("\n ✅ GPU is significantly faster in parallel!")
            elif speedup < 0.9:
                print("\n ⚠️ CPU still wins (likely due to decoding bottleneck or GPU limits)")
            else:
                print("\n ℹ️ Performance is comparable for this batch size.")
        print("=" * 40)
        
    finally:
        print(f"\nCleaning up {temp_dir}...")
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
