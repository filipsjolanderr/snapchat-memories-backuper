from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class MemoryKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


# Plans
@dataclass(frozen=True)
class ExtractZipPlan:
    zip_path: Path
    dest_folder: Path


@dataclass(frozen=True)
class CopyPlan:
    src: Path
    dst: Path


@dataclass(frozen=True)
class RenamePlan:
    src: Path
    dst: Path


@dataclass(frozen=True)
class CombinePlan:
    main_path: Path
    overlay_path: Path
    out_path: Path
    kind: MemoryKind


# Metadata and downloads
@dataclass(frozen=True)
class MemoryMeta:
    uuid: str
    saved_at_utc: datetime
    latitude: Optional[float]
    longitude: Optional[float]
    kind: MemoryKind


@dataclass(frozen=True)
class DownloadItem:
    uuid: str
    url: str
    filename: str
    saved_at_utc: datetime
    latitude: Optional[float]
    longitude: Optional[float]
    kind: MemoryKind


@dataclass(frozen=True)
class GPUInfo:
    available: bool
    codec: str
    hwaccel: str  # informational
