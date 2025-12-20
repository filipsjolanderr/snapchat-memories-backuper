#!/usr/bin/env python3
"""
Quick performance test runner - runs only fast GPU tests.
"""

import subprocess
import sys

def main():
    """Run quick performance tests."""
    print("Running quick performance tests (GPU only)...")
    print("=" * 60)
    
    # Run fast tests
    tests = [
        "tests/test_combining_performance.py::test_image_combining_performance",
        "tests/test_combining_performance.py::test_scaling_analysis",
    ]
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-v",
        "--tb=no",
        "-q",
    ] + tests
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("Tests completed! Check tests/performance_report.txt for results.")
    else:
        print("\nTests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()



