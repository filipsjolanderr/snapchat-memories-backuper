#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify all files in output folder have location and time metadata.
"""

import subprocess
import json
import sys
from pathlib import Path
from collections import defaultdict

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def check_file_metadata(file_path: Path) -> dict:
    """Check metadata for a single file using ExifTool."""
    try:
        # Use ExifTool to extract metadata in JSON format
        result = subprocess.run(
            ["exiftool", "-j", "-n", str(file_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return {"error": result.stderr[:200]}
        
        data = json.loads(result.stdout)
        if not data:
            return {"error": "No metadata found"}
        
        metadata = data[0]
        
        # Check for time metadata
        has_time = False
        time_fields = []
        for field in ["CreateDate", "DateTimeOriginal", "ModifyDate", "MediaCreateDate"]:
            if field in metadata:
                has_time = True
                time_fields.append(field)
        
        # Check for location metadata
        has_location = False
        location_fields = []
        
        # Check various GPS/location tags
        gps_tags = [
            "GPSLatitude", "GPSLongitude", 
            "XMP:GPSLatitude", "XMP:GPSLongitude",
            "QuickTime:Location", "UserData:Location"
        ]
        
        for tag in gps_tags:
            if tag in metadata:
                has_location = True
                location_fields.append(tag)
        
        return {
            "has_time": has_time,
            "has_location": has_location,
            "time_fields": time_fields,
            "location_fields": location_fields,
            "lat": metadata.get("GPSLatitude") or metadata.get("XMP:GPSLatitude"),
            "lon": metadata.get("GPSLongitude") or metadata.get("XMP:GPSLongitude"),
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    output_folder = Path("output")
    
    if not output_folder.exists():
        print(f"❌ Output folder not found: {output_folder}")
        return
    
    # Find all image and video files
    files = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.mp4"]:
        files.extend(output_folder.rglob(ext))
    
    files = sorted(files)
    
    if not files:
        print(f"❌ No files found in {output_folder}")
        return
    
    print(f"🔍 Checking {len(files)} files for metadata...\n")
    
    stats = defaultdict(int)
    missing_time = []
    missing_location = []
    errors = []
    
    for file_path in files:
        relative_path = file_path.relative_to(output_folder)
        result = check_file_metadata(file_path)
        
        if "error" in result:
            errors.append((relative_path, result["error"]))
            stats["errors"] += 1
            continue
        
        if not result["has_time"]:
            missing_time.append(relative_path)
            stats["missing_time"] += 1
        
        if not result["has_location"]:
            missing_location.append(relative_path)
            stats["missing_location"] += 1
        
        if result["has_time"]:
            stats["has_time"] += 1
        if result["has_location"]:
            stats["has_location"] += 1
    
    # Print results
    print("=" * 70)
    print("METADATA CHECK RESULTS")
    print("=" * 70)
    print(f"\n📊 Statistics:")
    print(f"   Total files checked: {len(files)}")
    print(f"   ✅ Files with time metadata: {stats['has_time']}")
    print(f"   ✅ Files with location metadata: {stats['has_location']}")
    print(f"   ❌ Files missing time metadata: {stats['missing_time']}")
    print(f"   ❌ Files missing location metadata: {stats['missing_location']}")
    print(f"   ⚠️  Files with errors: {stats['errors']}")
    
    if missing_time:
        print(f"\n❌ Files missing time metadata ({len(missing_time)}):")
        for f in missing_time[:10]:  # Show first 10
            print(f"   - {f}")
        if len(missing_time) > 10:
            print(f"   ... and {len(missing_time) - 10} more")
    
    if missing_location:
        print(f"\n❌ Files missing location metadata ({len(missing_location)}):")
        for f in missing_location[:10]:  # Show first 10
            print(f"   - {f}")
        if len(missing_location) > 10:
            print(f"   ... and {len(missing_location) - 10} more")
    
    if errors:
        print(f"\n⚠️  Files with errors ({len(errors)}):")
        for f, err in errors[:5]:  # Show first 5
            print(f"   - {f}: {err}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more")
    
    # Summary
    print("\n" + "=" * 70)
    if stats["missing_time"] == 0 and stats["missing_location"] == 0 and stats["errors"] == 0:
        print("✅ SUCCESS: All files have time and location metadata!")
    else:
        print("⚠️  WARNING: Some files are missing metadata")
        if stats["missing_time"] > 0:
            print(f"   - {stats['missing_time']} files missing time metadata")
        if stats["missing_location"] > 0:
            print(f"   - {stats['missing_location']} files missing location metadata")
        if stats["errors"] > 0:
            print(f"   - {stats['errors']} files had errors")
    print("=" * 70)

if __name__ == "__main__":
    main()
