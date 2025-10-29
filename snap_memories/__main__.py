from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path for direct execution
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from snap_memories.cli import app

if __name__ == "__main__":
    app()
    sys.exit(0)
