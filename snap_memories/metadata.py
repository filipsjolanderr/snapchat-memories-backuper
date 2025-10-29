from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import piexif
from PIL import Image, PngImagePlugin
from tqdm import tqdm

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
        import os

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
            # Convert to RGB, handling transparency by compositing onto white background
            if img.mode == "RGBA":
                rgb = Image.new("RGB", img.size, (255, 255, 255))
                rgb.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
            elif img.mode == "LA":
                # Grayscale with alpha - composite onto white background
                rgb = Image.new("RGB", img.size, (255, 255, 255))
                # Convert LA to RGBA first, then composite
                rgba = img.convert("RGBA")
                rgb.paste(rgba, mask=rgba.split()[-1])
            elif img.mode in ("P", "L"):
                # Palette or grayscale - convert to RGB
                rgb = img.convert("RGB")
            else:
                rgb = img.convert("RGB")
            
            # Save as JPEG with high quality
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
        # Check if file exists and is accessible
        if not jpeg_path.exists():
            warning(f"Failed to write EXIF to {jpeg_path.name}: File does not exist")
            return False
        
        # Validate file is readable and actually a JPEG before attempting write
        # This also ensures any file handles from previous operations are released
        try:
            with Image.open(jpeg_path) as img:
                img_format = img.format
            if img_format not in ("JPEG", "JPG"):
                warning(
                    f"Failed to write EXIF to {jpeg_path.name}: "
                    f"File format is {img_format}, not JPEG"
                )
                return False
        except Exception as img_err:
            error_msg = str(img_err).strip() if img_err else ""
            error_type = type(img_err).__name__
            if error_msg:
                warning(
                    f"Failed to write EXIF to {jpeg_path.name}: "
                    f"Cannot read image file ({error_type}: {error_msg})"
                )
            else:
                warning(
                    f"Failed to write EXIF to {jpeg_path.name}: "
                    f"Cannot read image file ({error_type})"
                )
            return False
        
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
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(jpeg_path))
        return True
    except PermissionError:
        warning(
            f"Failed to write EXIF to {jpeg_path.name}: "
            f"Permission denied (file may be read-only or locked)"
        )
        return False
    except OSError as e:
        error_msg = str(e).strip() if e else ""
        error_type = type(e).__name__
        if error_msg:
            warning(
                f"Failed to write EXIF to {jpeg_path.name}: "
                f"{error_type}: {error_msg}"
            )
        else:
            warning(
                f"Failed to write EXIF to {jpeg_path.name}: "
                f"{error_type} (file may be locked or inaccessible)"
            )
        return False
    except Exception as e:
        error_msg = str(e).strip() if e else ""
        error_type = type(e).__name__
        if error_msg:
            warning(
                f"Failed to write EXIF to {jpeg_path.name}: "
                f"{error_type}: {error_msg}"
            )
        else:
            warning(
                f"Failed to write EXIF to {jpeg_path.name}: "
                f"{error_type} (no error message)"
            )
        return False


def write_png_text_metadata(
    png_path: Path, dt: datetime, lat: float | None, lon: float | None
) -> bool:
    try:
        # Check file extension - don't write PNG metadata to JPEG files
        if png_path.suffix.lower() in (".jpg", ".jpeg"):
            return False
        
        with Image.open(png_path) as im:
            # Ensure image is in a compatible mode for PNG
            # PNG supports: RGB, RGBA, P (palette), L (grayscale)
            if im.mode not in ("RGB", "RGBA", "P", "L"):
                # Convert to RGB if not in a PNG-compatible mode
                if im.mode in ("CMYK", "LAB", "HSV"):
                    im = im.convert("RGB")
                else:
                    # Try RGB as fallback
                    im = im.convert("RGB")
            
            info = PngImagePlugin.PngInfo()
            info.add_text("CreationTime", dt.isoformat())
            if lat is not None and lon is not None:
                info.add_text("GPSLatitude", str(lat))
                info.add_text("GPSLongitude", str(lon))
            # Explicitly save as PNG format to avoid mode conflicts
            im.save(png_path, format="PNG", pnginfo=info)
        return True
    except Exception as e:
        warning(
            f"Failed to write PNG metadata to {png_path.name}: "
            f"{str(e) if e else 'Unknown error'}"
        )
        return False


def write_mp4_metadata_ffmpeg(
    mp4_path: Path, dt: datetime, lat: float | None, lon: float | None
) -> bool:
    try:
        if not mp4_path.exists():
            return False
        args = [
            "ffmpeg",
            "-y",
            "-i",
            str(mp4_path),
            "-map",
            "0",
            "-c",
            "copy",
            "-metadata",
            f"creation_time={dt.replace(tzinfo=timezone.utc).isoformat()}",
        ]
        if lat is not None and lon is not None:
            iso6709 = f"{lat:+09.5f}{lon:+010.6f}/"
            args += [
                "-metadata",
                f"com.apple.quicktime.location.ISO6709={iso6709}",
            ]
        tmp = mp4_path.with_suffix(".tmp.mp4")
        args.append(str(tmp))
        result = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30
        )
        if result.returncode != 0:
            return False
        try:
            tmp.replace(mp4_path)
        except Exception:
            try:
                tmp.unlink()
            except Exception:
                pass
            return False
        return True
    except Exception:
        return False


def apply_metadata_to_outputs(
    output_folder: Path, meta_by_uuid: dict[str, MemoryMeta]
) -> tuple[int, int]:
    images_tagged = 0
    videos_tagged = 0
    for p in output_folder.rglob("*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        m = re.match(r"([0-9a-fA-F-]{36})(?:_combined)?\.(jpg|png|mp4)$", name)
        if not m:
            continue
        uuid = m.group(1).lower()
        ext = m.group(2)
        if uuid not in meta_by_uuid:
            continue
        meta = meta_by_uuid[uuid]
        if ext in ("jpg", "png"):
            try:
                if p.stat().st_size == 0:
                    warning(f"Skipping empty file {p.name}")
                    continue
                converted_to_jpeg = False
                jpeg_path = None
                with Image.open(p) as img:
                    # Check actual image format first, not just extension
                    # Some files may have wrong extensions (e.g., .jpg but actually PNG)
                    img_format = img.format
                    if img_format in ("JPEG", "JPG"):
                        # JPEG file - write EXIF metadata
                        if write_exif_to_jpeg(
                            p, meta.saved_at_utc, meta.latitude, meta.longitude
                        ):
                            images_tagged += 1
                    elif img_format == "PNG":
                        # PNG file - convert to JPEG and write EXIF metadata
                        # Preserve _combined suffix if present
                        base_name = p.stem  # e.g., "uuid_combined" or "uuid"
                        jpeg_path = p.parent / f"{base_name}.jpg"
                        if convert_png_to_jpeg(p, jpeg_path):
                            # Apply metadata to the converted JPEG
                            if write_exif_to_jpeg(
                                jpeg_path, meta.saved_at_utc, meta.latitude, meta.longitude
                            ):
                                images_tagged += 1
                                # Delete the original PNG file
                                try:
                                    p.unlink()
                                    converted_to_jpeg = True
                                except Exception:
                                    pass
                        else:
                            # If conversion failed, fall back to PNG metadata
                            if write_png_text_metadata(
                                p, meta.saved_at_utc, meta.latitude, meta.longitude
                            ):
                                images_tagged += 1
                    else:
                        # Fallback to extension if format is unknown
                        if ext == "jpg":
                            if write_exif_to_jpeg(
                                p, meta.saved_at_utc, meta.latitude, meta.longitude
                            ):
                                images_tagged += 1
                        elif ext == "png":
                            # Convert PNG to JPEG based on extension
                            # Preserve _combined suffix if present
                            base_name = p.stem  # e.g., "uuid_combined" or "uuid"
                            jpeg_path = p.parent / f"{base_name}.jpg"
                            if convert_png_to_jpeg(p, jpeg_path):
                                # Apply metadata to the converted JPEG
                                if write_exif_to_jpeg(
                                    jpeg_path, meta.saved_at_utc, meta.latitude, meta.longitude
                                ):
                                    images_tagged += 1
                                    # Delete the original PNG file
                                    try:
                                        p.unlink()
                                        converted_to_jpeg = True
                                    except Exception:
                                        pass
                            else:
                                # If conversion failed, fall back to PNG metadata
                                if write_png_text_metadata(
                                    p, meta.saved_at_utc, meta.latitude, meta.longitude
                                ):
                                    images_tagged += 1
                        else:
                            warning(
                                f"Unsupported image format "
                                f"{img_format or 'unknown'} for {p.name}"
                            )
                # Set file times on the processed file (either original or converted)
                if converted_to_jpeg and jpeg_path:
                    processed_path = jpeg_path
                else:
                    processed_path = p
                if processed_path.exists():
                    _set_file_times(processed_path, meta.saved_at_utc)
            except Exception as e:
                # Set file times even if metadata application failed
                # Try to determine the correct path based on what might have been converted
                if ext == "png":
                    base_name = p.stem
                    processed_path = p.parent / f"{base_name}.jpg"
                    if not processed_path.exists():
                        processed_path = p
                else:
                    processed_path = p
                if processed_path.exists():
                    _set_file_times(processed_path, meta.saved_at_utc)
        elif ext == "mp4":
            if write_mp4_metadata_ffmpeg(
                p, meta.saved_at_utc, meta.latitude, meta.longitude
            ):
                videos_tagged += 1
            _set_file_times(p, meta.saved_at_utc)
    return images_tagged, videos_tagged
