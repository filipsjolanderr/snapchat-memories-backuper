"""FFmpeg path provider using imageio-ffmpeg."""

import imageio_ffmpeg
import shutil
import os
from pathlib import Path

def get_ffmpeg_path() -> str:
    """Get the path to the FFmpeg executable.
    
    Tries to use the static binary from imageio-ffmpeg first,
    then falls back to the system's 'ffmpeg' in PATH.
    """
    try:
        # Get path from imageio-ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
        
    # Fallback to system ffmpeg
    fallback = shutil.which("ffmpeg")
    if fallback:
        return fallback
        
    # Default to just 'ffmpeg' and hope it works in the shell
    return "ffmpeg"
