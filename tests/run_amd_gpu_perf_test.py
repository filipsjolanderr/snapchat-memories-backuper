#!/usr/bin/env python3
"""
Quick script to run AMD GPU vs CPU performance test.

This script runs only the AMD GPU performance test, making it easy to
test GPU performance vs CPU performance with multiple worker counts.

Usage:
    python tests/run_amd_gpu_perf_test.py
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import snap_memories
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

if __name__ == "__main__":
    print("=" * 80)
    print("AMD GPU vs CPU Performance Test")
    print("=" * 80)
    print("\nThis test will compare:")
    print("  - CPU encoding (libx264) with worker counts: 1, 2, 4, 8, 16, 24, 32")
    print("  - GPU MoviePy pipeline (h264_amf) with worker counts: 1, 2, 4, 8, 16, 24, 32")
    print("  - GPU FFmpeg pipeline (h264_amf) with worker counts: 1, 2, 4, 8, 16, 24, 32")
    print("\nResults will be saved to:")
    print("  - tests/performance_report.txt")
    print("  - tests/performance_report.json")
    print("\n" + "=" * 80 + "\n")
    
    # Run only the AMD GPU test
    exit_code = pytest.main([
        "tests/test_combining_performance.py::test_amd_gpu_vs_cpu_performance",
        "-v",
        "-s",
        "--tb=short"
    ])
    
    sys.exit(exit_code)

