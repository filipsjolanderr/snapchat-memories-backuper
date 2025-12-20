#!/usr/bin/env python3
"""
Check AMD GPU (AMF) support in FFmpeg.

This script checks if FFmpeg has AMD AMF support and tests basic GPU encoding.
"""

import subprocess
import sys
from pathlib import Path

def check_ffmpeg_amd_support():
    """Check if FFmpeg has AMD AMF support."""
    print("=" * 80)
    print("Checking FFmpeg AMD AMF Support")
    print("=" * 80)
    print()
    
    # Check FFmpeg version
    print("1. Checking FFmpeg version...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"   [OK] FFmpeg found: {version_line}")
        else:
            print("   [FAIL] FFmpeg not working properly")
            return False
    except FileNotFoundError:
        print("   [FAIL] FFmpeg not found in PATH")
        return False
    except Exception as e:
        print(f"   [FAIL] Error checking FFmpeg: {e}")
        return False
    
    print()
    
    # Check for AMF in FFmpeg output
    print("2. Checking for AMD AMF encoder support...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            output_lower = result.stdout.lower()
            if "h264_amf" in output_lower:
                print("   [OK] h264_amf encoder found")
                # Extract the encoder line
                for line in result.stdout.split('\n'):
                    if 'h264_amf' in line.lower():
                        print(f"   {line.strip()}")
            else:
                print("   [FAIL] h264_amf encoder NOT found")
                print("   Available H.264 encoders:")
                for line in result.stdout.split('\n'):
                    if 'h264' in line.lower() and 'encoder' in line.lower():
                        print(f"   {line.strip()}")
                return False
        else:
                print("   [FAIL] Failed to list encoders")
                return False
    except Exception as e:
        print(f"   [FAIL] Error checking encoders: {e}")
        return False
    
    print()
    
    # Check for hardware acceleration
    print("3. Checking hardware acceleration support...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-hwaccels"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            output_lower = result.stdout.lower()
            if "d3d11va" in output_lower:
                print("   [OK] d3d11va (DirectX 11) hardware acceleration found")
            else:
                print("   [WARN] d3d11va not found (required for AMD GPU decoding)")
            
            # Show all available hwaccels
            print("   Available hardware acceleration methods:")
            for line in result.stdout.split('\n'):
                if line.strip() and not line.startswith('Hardware'):
                    print(f"     - {line.strip()}")
        else:
            print("   [FAIL] Failed to list hardware acceleration methods")
    except Exception as e:
        print(f"   [FAIL] Error checking hardware acceleration: {e}")
    
    print()
    
    # Test codec availability
    print("4. Testing h264_amf codec availability...")
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-f", "lavfi",
                "-i", "testsrc=duration=1:size=320x240:rate=1",
                "-c:v", "h264_amf",
                "-frames:v", "1",
                "-f", "null",
                "-"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            print("   [OK] h264_amf codec test PASSED")
            return True
        else:
            print("   [FAIL] h264_amf codec test FAILED")
            print(f"   Error output: {result.stderr[:500]}")
            return False
    except subprocess.TimeoutExpired:
        print("   [FAIL] h264_amf codec test TIMED OUT (codec may hang)")
        return False
    except Exception as e:
        print(f"   [FAIL] h264_amf codec test ERROR: {e}")
        return False


def test_gpu_encoding_with_overlay():
    """Test GPU encoding with video overlay (what the app actually does)."""
    print()
    print("=" * 80)
    print("Testing GPU Encoding with Video Overlay")
    print("=" * 80)
    print()
    
    import tempfile
    from PIL import Image
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Using temporary directory: {temp_dir}")
    
    try:
        # Create test video
        print("\n1. Creating test video...")
        test_video = temp_dir / "test_input.mp4"
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "testsrc=duration=2:size=640x480:rate=30",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                str(test_video)
            ],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            print(f"   [FAIL] Failed to create test video: {result.stderr[:200]}")
            return False
        print("   [OK] Test video created")
        
        # Create overlay image
        print("\n2. Creating overlay image...")
        overlay_img = temp_dir / "overlay.png"
        img = Image.new('RGBA', (640, 480), color=(0, 255, 0, 128))
        img.save(overlay_img, 'PNG')
        print("   [OK] Overlay image created")
        
        # Test GPU encoding with overlay
        print("\n3. Testing GPU encoding with overlay (this is what hangs)...")
        output_video = temp_dir / "test_output_gpu.mp4"
        
        cmd = [
            "ffmpeg", "-y",
            "-hwaccel", "d3d11va",  # AMD GPU hardware acceleration
            "-i", str(test_video),
            "-loop", "1",
            "-i", str(overlay_img),
            "-filter_complex",
            "[1:v]format=rgba[olorig];"
            "[olorig][0:v]scale2ref=w=iw:h=ih[ol][base];"
            "[base][ol]overlay=0:0[overlaid];"
            "[overlaid]format=yuv420p[v]",
            "-map", "[v]",
            "-shortest",
            "-c:v", "h264_amf",
            "-quality", "speed",
            "-rc", "cqp",
            "-qmin", "28",
            "-qmax", "32",
            "-preset", "0",
            str(output_video)
        ]
        
        print(f"   Running: {' '.join(cmd[:10])}... (full command hidden)")
        print("   Waiting up to 30 seconds...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print("   [OK] GPU encoding with overlay PASSED!")
                if output_video.exists():
                    size = output_video.stat().st_size
                    print(f"   Output file size: {size:,} bytes")
                return True
            else:
                print("   [FAIL] GPU encoding with overlay FAILED")
                print(f"   Return code: {result.returncode}")
                print(f"   Error output (first 500 chars):")
                print(f"   {result.stderr[:500]}")
                return False
                
        except subprocess.TimeoutExpired:
            print("   [FAIL] GPU encoding TIMED OUT after 30 seconds")
            print("   This confirms the hanging issue!")
            return False
        except Exception as e:
            print(f"   [FAIL] GPU encoding ERROR: {e}")
            return False
            
    finally:
        # Cleanup
        import shutil
        try:
            shutil.rmtree(temp_dir)
            print(f"\n   Cleaned up temporary directory")
        except:
            pass


if __name__ == "__main__":
    print()
    
    # Check basic support
    has_support = check_ffmpeg_amd_support()
    
    if has_support:
        print()
        print("=" * 80)
        print("Basic AMD AMF support: [OK] AVAILABLE")
        print("=" * 80)
        
        # Ask if user wants to test the actual encoding
        print()
        response = input("Test GPU encoding with overlay? (y/n): ").strip().lower()
        if response == 'y':
            test_gpu_encoding_with_overlay()
    else:
        print()
        print("=" * 80)
        print("Basic AMD AMF support: [FAIL] NOT AVAILABLE")
        print("=" * 80)
        print()
        print("Possible solutions:")
        print("1. Install FFmpeg with AMD AMF support")
        print("2. Update AMD GPU drivers")
        print("3. Check if you're on Windows (AMF requires Windows)")
    
    print()
