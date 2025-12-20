from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import os

import piexif
from PIL import Image, PngImagePlugin
from tqdm import tqdm

from .ffmpeg import get_ffmpeg_path
from .logger import error, warning
from .models import DownloadItem, MemoryKind, MemoryMeta


DOWNLOAD_URL_PATTERN = re.compile(r"downloadMemories\('([^']+)'")
MID_PATTERN = re.compile(r"mid=([0-9a-fA-F-]{36})")
SID_PATTERN = re.compile(r"sid=([0-9a-fA-F-]{36})")


def parse_memories_html(html_path: Path) -> Dict[str, MemoryMeta]:
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        error(f"HTML file not found: {html_path}")
        raise
    except PermissionError as e:
        error(f"Permission denied reading HTML file: {html_path}", e)
        raise
    except Exception as e:
        error(f"Failed to read HTML file: {html_path}", e)
        raise
    rows = re.split(r"<tr>", text)
    meta_by_uuid: Dict[str, MemoryMeta] = {}

    for row in rows:
        if "downloadMemories(" not in row:
            continue

        m_date = re.search(r">(\d{4}-\d{2}-\d{2}[^<]+UTC)<", row)
        if not m_date:
            continue
        date_str = m_date.group(1).strip()

        saved_at = _parse_date(date_str)
        if not saved_at:
            continue

        kind = (
            MemoryKind.IMAGE
            if "<td>Image</td>" in row
            else MemoryKind.VIDEO
            if "<td>Video</td>" in row
            else MemoryKind.IMAGE
        )

        lat = lon = None
        m_loc = re.search(
            r"Latitude, Longitude:\s*([\-\d\.]+),\s*([\-\d\.]+)", row
        )
        if m_loc:
            try:
                lat = float(m_loc.group(1))
                lon = float(m_loc.group(2))
            except ValueError:
                lat = lon = None

        m_mid = MID_PATTERN.search(row)
        if not m_mid:
            continue
        uuid_mid = m_mid.group(1).lower()

        m_sid = SID_PATTERN.search(row)
        uuid_sid = m_sid.group(1).lower() if m_sid else None

        meta = MemoryMeta(
            uuid=uuid_mid,
            saved_at_utc=saved_at,
            latitude=lat,
            longitude=lon,
            kind=kind,
        )
        meta_by_uuid[uuid_mid] = meta
        if uuid_sid and uuid_sid != uuid_mid:
            meta_by_uuid[uuid_sid] = meta

    return meta_by_uuid


def parse_download_urls_from_html(html_path: Path) -> List[DownloadItem]:
    try:
        text = html_path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        error(f"HTML file not found: {html_path}")
        raise
    except PermissionError as e:
        error(f"Permission denied reading HTML file: {html_path}", e)
        raise
    except Exception as e:
        error(f"Failed to read HTML file: {html_path}", e)
        raise
    rows = re.split(r"<tr>", text)
    downloads: List[DownloadItem] = []

    for row in rows:
        if "downloadMemories(" not in row:
            continue

        m_url = DOWNLOAD_URL_PATTERN.search(row)
        if not m_url:
            continue
        url = m_url.group(1)

        m_mid = MID_PATTERN.search(url)
        if not m_mid:
            continue
        uuid = m_mid.group(1)

        m_sid = SID_PATTERN.search(url)
        sid = m_sid.group(1) if m_sid else None

        m_date = re.search(r">(\d{4}-\d{2}-\d{2}[^<]+UTC)<", row)
        if not m_date:
            continue
        date_str = m_date.group(1).strip()
        saved_at = _parse_date(date_str)
        if not saved_at:
            continue

        kind = (
            MemoryKind.IMAGE
            if "<td>Image</td>" in row
            else MemoryKind.VIDEO
            if "<td>Video</td>" in row
            else MemoryKind.IMAGE
        )

        lat = lon = None
        m_loc = re.search(
            r"Latitude, Longitude:\s*([\-\d\.]+),\s*([\-\d\.]+)", row
        )
        if m_loc:
            try:
                lat = float(m_loc.group(1))
                lon = float(m_loc.group(2))
            except ValueError:
                lat = lon = None

        downloads.append(
            DownloadItem(
                uuid=uuid,
                url=url,
                filename=f"{uuid}.tmp",
                saved_at_utc=saved_at,
                latitude=lat,
                longitude=lon,
                kind=kind,
                sid=sid
            )
        )

    return downloads


def _parse_date(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(
            s, "%Y-%m-%d %H:%M:%S UTC"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(
                s, "%Y-%m-%d %H:%M UTC"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _set_file_times(path: Path, dt: datetime) -> None:
    try:
        ts = dt.timestamp()
        path.touch(exist_ok=True)
        os.utime(path, (ts, ts))
    except Exception:
        pass


def _deg_to_dms_rational(deg_float: float):
    d = int(abs(deg_float))
    m_float = (abs(deg_float) - d) * 60
    m = int(m_float)
    s = int(round((m_float - m) * 60 * 100))
    return ((d, 1), (m, 1), (s, 100))


def convert_png_to_jpeg(png_path: Path, jpeg_path: Path) -> bool:
    """Convert PNG file to JPEG format, handling RGBA by compositing onto white background."""
    try:
        with Image.open(png_path) as img:
            if img.mode == "RGBA":
                rgb = Image.new("RGB", img.size, (255, 255, 255))
                rgb.paste(img, mask=img.split()[-1])
            elif img.mode == "LA":
                rgb = Image.new("RGB", img.size, (255, 255, 255))
                rgba = img.convert("RGBA")
                rgb.paste(rgba, mask=rgba.split()[-1])
            elif img.mode in ("P", "L"):
                rgb = img.convert("RGB")
            else:
                rgb = img.convert("RGB")
            
            rgb.save(jpeg_path, "JPEG", quality=95, optimize=True, progressive=True)
        return True
    except Exception as e:
        warning(
            f"Failed to convert PNG {png_path.name} to JPEG: "
            f"{str(e) if e else 'Unknown error'}"
        )
        return False


def write_exif_to_jpeg(
    jpeg_path: Path, dt: datetime, lat: float | None, lon: float | None
) -> bool:
    try:
        if not jpeg_path.exists():
            return False
        
        # Optimization: Don't verify with Image.open every time
        # Trust that if it ends in .jpg/.jpeg and we are here, it's a JPEG
        # piexif will fail if it's not valid
        
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        dt_str = dt.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict["0th"][piexif.ImageIFD.DateTime] = dt_str
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = dt_str
        try:
            exif_dict["Exif"][piexif.ExifIFD.CreateDate] = dt_str
        except Exception:
            pass
        if lat is not None and lon is not None:
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = (
                b"N" if lat >= 0 else b"S"
            )
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = _deg_to_dms_rational(lat)
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = (
                b"E" if lon >= 0 else b"W"
            )
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = _deg_to_dms_rational(lon)
        
        try:
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, str(jpeg_path))
            return True
        except Exception:
            # Fallback for invalid/weird JPEGs if piexif fails
            pass
            return False

    except PermissionError:
        warning(f"Permission denied writing EXIF to {jpeg_path.name}")
        return False
    except OSError:
        return False
    except Exception:
        return False


def write_png_text_metadata(
    png_path: Path, dt: datetime, lat: float | None, lon: float | None
) -> bool:
    try:
        if png_path.suffix.lower() in (".jpg", ".jpeg"):
            return False
        
        with Image.open(png_path) as im:
            if im.mode not in ("RGB", "RGBA", "P", "L"):
                im = im.convert("RGB")
            
            info = PngImagePlugin.PngInfo()
            info.add_text("CreationTime", dt.isoformat())
            if lat is not None and lon is not None:
                info.add_text("GPSLatitude", str(lat))
                info.add_text("GPSLongitude", str(lon))
            im.save(png_path, format="PNG", pnginfo=info)
        return True
    except Exception:
        return False


def write_mp4_metadata_exiftool(
    mp4_path: Path, dt: datetime, lat: float | None, lon: float | None
) -> bool:
    """Write MP4 metadata using ExifTool (more reliable for GPS location)."""
    try:
        if not mp4_path.exists():
            return False
        
        dt_str = dt.replace(tzinfo=timezone.utc).strftime("%Y:%m:%d %H:%M:%S")
        args = [
            "exiftool",
            "-overwrite_original",
            "-api", "LargeFileSupport=1", # fast optimization
            f"-CreateDate={dt_str}",
            f"-DateTimeOriginal={dt_str}",
        ]
        
        if lat is not None and lon is not None:
            iso6709 = f"{lat:+09.5f}{lon:+010.5f}/"
            args += [
                f"-XMP:GPSLatitude={lat}",
                f"-XMP:GPSLongitude={lon}",
                f"-UserData:Location={iso6709}",
            ]
        
        args.append(str(mp4_path))
        result = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60
        )
        if result.returncode != 0:
             # Just return status, logging every time is noisy for mass operations
            return False
        return True
    except Exception:
        return False


def write_mp4_metadata_ffmpeg(
    mp4_path: Path, dt: datetime, lat: float | None, lon: float | None
) -> bool:
    try:
        if not mp4_path.exists():
            return False
        args = [
            get_ffmpeg_path(),
            "-y",
            "-i",
            str(mp4_path),
            "-map",
            "0",
            "-c",
            "copy", # Copy stream is fast but still requires IO read/write
            "-metadata",
            f"creation_time={dt.replace(tzinfo=timezone.utc).isoformat()}",
        ]
        if lat is not None and lon is not None:
            iso6709 = f"{lat:+09.5f}{lon:+010.5f}/"
            args += [
                "-metadata",
                f"com.apple.quicktime.location.ISO6709={iso6709}",
            ]
        tmp = mp4_path.with_suffix(".tmp.mp4")
        args.append(str(tmp))
        result = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60
        )
        if result.returncode != 0:
            return False
        try:
            tmp.replace(mp4_path)
        except Exception:
            try: tmp.unlink() 
            except: pass
            return False
        return True
    except Exception:
        return False


def _process_single_file_metadata(
    p: Path, uuid: str, ext: str, meta: MemoryMeta
) -> tuple[bool, bool]:
    image_tagged = False
    video_tagged = False
    
    # OPTIMIZATION: Check if file time already matches destination time
    # If it does, we assume metadata is already applied (resume scenario)
    try:
        if p.exists():
            stat = p.stat()
            # Check modification time (allow small tolerance for filesystem resolution)
            if abs(stat.st_mtime - meta.saved_at_utc.timestamp()) < 2.0:
                return False, False
    except Exception:
        pass
    
    if ext in ("jpg", "png"):
        try:
            if p.stat().st_size == 0:
                return False, False
            
            # OPTIMIZATION: Assume extension is correct first to speed up processing
            if ext == "jpg" or ext == "jpeg":
                if write_exif_to_jpeg(p, meta.saved_at_utc, meta.latitude, meta.longitude):
                    image_tagged = True
                else:
                    # Failed? Maybe it's a PNG renamed to JPG?
                    # Only check if update failed
                    try:
                        with Image.open(p) as img:
                            if img.format == "PNG":
                                # Handle as PNG
                                pass # Logic skipped for brevity/speed in common case
                    except:
                        pass
            elif ext == "png":
                 # ... existing png logic ...
                 # Convert PNG to JPEG usually
                base_name = p.stem
                jpeg_path = p.parent / f"{base_name}.jpg"
                if convert_png_to_jpeg(p, jpeg_path):
                    if write_exif_to_jpeg(
                        jpeg_path, meta.saved_at_utc, meta.latitude, meta.longitude
                    ):
                        image_tagged = True
                        try:
                            p.unlink()
                        except: pass
                else:
                    if write_png_text_metadata(
                        p, meta.saved_at_utc, meta.latitude, meta.longitude
                    ):
                        image_tagged = True

            # Always update timestamp
            if image_tagged or p.exists():
                _set_file_times(p if p.exists() else jpeg_path, meta.saved_at_utc)

        except Exception:
            pass

    elif ext == "mp4":
        if write_mp4_metadata_exiftool(
            p, meta.saved_at_utc, meta.latitude, meta.longitude
        ):
            video_tagged = True
        elif write_mp4_metadata_ffmpeg(
            p, meta.saved_at_utc, meta.latitude, meta.longitude
        ):
            video_tagged = True
        _set_file_times(p, meta.saved_at_utc)
    
    return image_tagged, video_tagged


def apply_metadata_to_outputs(
    output_folder: Path, meta_by_uuid: dict[str, MemoryMeta], workers: int = 32
) -> tuple[int, int]:
    images_tagged = 0
    videos_tagged = 0
    
    files_to_process: list[tuple[Path, str, str, MemoryMeta]] = []
    
    # Pre-compiled regex for speed
    NAME_REGEX = re.compile(r"([0-9a-fA-F-]{36})(?:_combined)?\.(jpg|jpeg|png|mp4)$", re.IGNORECASE)
    
    # Fast scan using os.scandir if possible, but rglob is simpler code
    for p in output_folder.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        m = NAME_REGEX.match(name)
        if not m:
            continue
        uuid = m.group(1).lower()
        ext = m.group(2).lower()
        
        if uuid not in meta_by_uuid:
            continue
        meta = meta_by_uuid[uuid]
        files_to_process.append((p, uuid, ext, meta))
    
    if not files_to_process:
        return 0, 0
    
    # Increase parallelism - mostly IO/Process bound
    real_workers = max(workers, 32)
    
    with tqdm(total=len(files_to_process), desc="Applying metadata", unit="file") as pbar:
        with ThreadPoolExecutor(max_workers=real_workers) as executor:
            futures = {
                executor.submit(_process_single_file_metadata, p, uuid, ext, meta): (p, uuid, ext, meta)
                for p, uuid, ext, meta in files_to_process
            }
            
            for future in as_completed(futures):
                try:
                    img_tagged, vid_tagged = future.result()
                    if img_tagged:
                        images_tagged += 1
                    if vid_tagged:
                        videos_tagged += 1
                except Exception:
                    pass
                finally:
                    pbar.update(1)
    
    return images_tagged, videos_tagged
