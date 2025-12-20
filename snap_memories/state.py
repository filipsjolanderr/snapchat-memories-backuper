import json
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from .logger import info, verbose


class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADED = "DOWNLOADED"  # Downloaded successfully
    EXTRACTED = "EXTRACTED"  # Zip extracted (if applicable)
    COMBINED = "COMBINED"  # Overlay applied (if applicable)
    COMPLETED = "COMPLETED"  # Metadata applied, fully done
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class MemoryState:
    uuid: str
    url: str
    status: ProcessingStatus = ProcessingStatus.PENDING
    kind: str = "image"  # 'image' or 'video'
    saved_at_utc: Optional[str] = None  # ISO format
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None
    local_path: Optional[str] = None  # Path to the main file (e.g. .mp4 or .jpg)
    updated_at: float = field(default_factory=time.time)


class StateManager:
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state: Dict[str, MemoryState] = {}
        self._lock = threading.Lock()
        self._dirty = False
        self.load()

    def load(self):
        with self._lock:
            if self.state_file.exists():
                try:
                    data = json.loads(self.state_file.read_text(encoding="utf-8"))
                    for uuid, item in data.items():
                        # Convert dict back to MemoryState
                        self.state[uuid] = MemoryState(**item)
                    verbose(f"Loaded state for {len(self.state)} items")
                except Exception as e:
                    info(f"Failed to load state file, starting fresh: {e}")
                    self.state = {}

    def save(self):
        with self._lock:
            if not self._dirty:
                return
            
            # Atomic write
            tmp = self.state_file.with_suffix(".tmp")
            try:
                data = {uuid: asdict(s) for uuid, s in self.state.items()}
                tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
                tmp.replace(self.state_file)
                self._dirty = False
            except Exception as e:
                info(f"Failed to save state: {e}")

    def add_from_downloads(self, items: list):
        """Initialize state from a list of DownloadItems."""
        with self._lock:
            added = 0
            for item in items:
                if item.uuid not in self.state:
                    self.state[item.uuid] = MemoryState(
                        uuid=item.uuid,
                        url=item.url,
                        kind=item.kind.value,
                        saved_at_utc=item.saved_at_utc.isoformat() if item.saved_at_utc else None,
                        latitude=item.latitude,
                        longitude=item.longitude
                    )
                    added += 1
            if added > 0:
                self._dirty = True
            return added

    def update_status(self, uuid: str, status: ProcessingStatus, local_path: Optional[Path] = None, error: Optional[str] = None):
        with self._lock:
            if uuid in self.state:
                s = self.state[uuid]
                s.status = status
                s.updated_at = time.time()
                if local_path:
                    s.local_path = str(local_path)
                if error:
                    s.last_error = str(error)
                    s.error_count += 1
                self._dirty = True
            
                # Auto-save on significant updates or errors could be strategic, 
                # but for now we rely on explicit save() or periodic calls in pipeline
                
    def get_pending(self) -> list[MemoryState]:
        with self._lock:
            return [
                s for s in self.state.values() 
                if s.status not in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED, ProcessingStatus.SKIPPED)
            ]

    def get_failed(self) -> list[MemoryState]:
        with self._lock:
            return [s for s in self.state.values() if s.status == ProcessingStatus.FAILED]
