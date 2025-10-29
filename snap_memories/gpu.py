"""GPU acceleration detection and utilities."""

import subprocess
import platform
from typing import Tuple, List

from .models import GPUInfo


class GPUDetector:
    @staticmethod
    def detect() -> GPUInfo:
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return GPUInfo(False, "libx264", "")
            out = result.stdout.lower()

            # NVIDIA
            if "nvenc" in out:
                if GPUDetector._test_codec("h264_nvenc"):
                    return GPUInfo(True, "h264_nvenc", "cuda")

            # AMD
            if "amf" in out:
                if GPUDetector._test_codec("h264_amf"):
                    return GPUInfo(True, "h264_amf", "amf")

            # Intel
            if "qsv" in out:
                if GPUDetector._test_codec("h264_qsv"):
                    return GPUInfo(True, "h264_qsv", "qsv")

            # Apple
            if platform.system() == "Darwin" and "videotoolbox" in out:
                if GPUDetector._test_codec("h264_videotoolbox"):
                    return GPUInfo(True, "h264_videotoolbox", "videotoolbox")
        except Exception:
            pass
        return GPUInfo(False, "libx264", "")

    @staticmethod
    def _test_codec(codec: str) -> bool:
        try:
            r = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=1:size=320x240:rate=1",
                    "-c:v",
                    codec,
                    "-frames:v", "1",
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                timeout=10,
            )
            return r.returncode == 0
        except Exception:
            return False


def detect_gpu_acceleration() -> Tuple[bool, str, str]:
    """Detect available GPU acceleration options.
    
    Returns:
        Tuple of (has_gpu_acceleration, codec, hwaccel_type)
    """
    try:
        # Check if FFmpeg is available
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        if result.returncode != 0:
            return False, "libx264", ""
        
        ffmpeg_output = result.stdout.lower()
        
        # Check for NVIDIA NVENC support
        if "nvenc" in ffmpeg_output:
            # Test if NVENC actually works
            test_result = subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                "-c:v", "h264_nvenc", "-f", "null", "-"
            ], capture_output=True, timeout=10)
            if test_result.returncode == 0:
                return True, "h264_nvenc", "cuvid"
        
        # Check for AMD AMF support
        if "amf" in ffmpeg_output:
            test_result = subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                "-c:v", "h264_amf", "-f", "null", "-"
            ], capture_output=True, timeout=10)
            if test_result.returncode == 0:
                return True, "h264_amf", "d3d11va"
        
        # Check for Intel QSV support
        if "qsv" in ffmpeg_output:
            test_result = subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                "-c:v", "h264_qsv", "-f", "null", "-"
            ], capture_output=True, timeout=10)
            if test_result.returncode == 0:
                return True, "h264_qsv", "qsv"
        
        # Check for Apple VideoToolbox (macOS)
        if platform.system() == "Darwin" and "videotoolbox" in ffmpeg_output:
            test_result = subprocess.run([
                "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
                "-c:v", "h264_videotoolbox", "-f", "null", "-"
            ], capture_output=True, timeout=10)
            if test_result.returncode == 0:
                return True, "h264_videotoolbox", "videotoolbox"
        
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Fallback to CPU encoding
    return False, "libx264", ""


def get_gpu_ffmpeg_params(use_gpu: bool, codec: str, hwaccel_type: str) -> List[str]:
    """Get FFmpeg parameters for GPU acceleration.
    
    Args:
        use_gpu: Whether to use GPU acceleration
        codec: Video codec to use
        hwaccel_type: Hardware acceleration type (not used for output encoding)
    
    Returns:
        List of FFmpeg parameters for output encoding
    """
    params = []
    
    # For GPU-accelerated encoding, we only need the GPU codec
    # Hardware acceleration parameters (-hwaccel) are for input decoding only
    # The GPU codec itself handles the hardware acceleration for encoding
    
    return params
