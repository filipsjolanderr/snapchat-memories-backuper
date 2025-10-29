#!/usr/bin/env python3
"""
Test runner script for snap-memories.py

This script provides convenient ways to run the test suite with different configurations.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_tests(test_type="all", verbose=False, coverage=False, parallel=False):
    """Run tests with specified configuration."""
    import sys
    cmd = [sys.executable, "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=snap_memories", "--cov-report=html", "--cov-report=term"])
    
    if parallel:
        cmd.extend(["-n", "auto"])
    
    if test_type == "unit":
        cmd.extend(["-m", "unit"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type == "fast":
        cmd.extend(["-m", "not slow"])
    
    # Run all test files in the tests directory
    cmd.append(".")
    
    print(f"Running command: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run tests for snap-memories.py")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration", "fast"],
        default="all",
        help="Type of tests to run (default: all)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run with coverage reporting"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (requires pytest-xdist)"
    )
    
    args = parser.parse_args()
    
    # Check if pytest is available
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", "--version"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, "pytest")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: pytest not found. Please install pytest:")
        print("pip install pytest")
        return 1
    
    # Check for coverage if requested
    if args.coverage:
        try:
            result = subprocess.run([sys.executable, "-m", "pytest", "--cov", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, "pytest-cov")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: pytest-cov not found. Please install pytest-cov:")
            print("pip install pytest-cov")
            return 1
    
    # Check for parallel if requested
    if args.parallel:
        try:
            result = subprocess.run([sys.executable, "-m", "pytest", "-n", "--version"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, "pytest-xdist")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: pytest-xdist not found. Please install pytest-xdist:")
            print("pip install pytest-xdist")
            return 1
    
    return run_tests(args.type, args.verbose, args.coverage, args.parallel)


if __name__ == "__main__":
    sys.exit(main())
