"""
Pytest configuration and fixtures.
"""
import sys
from pathlib import Path

# Add the parent directory to sys.path so we can import snap_memories
tests_dir = Path(__file__).parent
project_root = tests_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
