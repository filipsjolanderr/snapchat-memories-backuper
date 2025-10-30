from __future__ import annotations

import sys
from pathlib import Path

import typer

from .config import AppConfig
from .gpu import GPUDetector
from .logger import Logger, LogLevel, set_logger, info
from .pipeline import Pipeline

app = typer.Typer(
    name="snap-memories",
    help="Snapchat Memories Backuper - Download and organize your Snapchat Memories",
    add_completion=False,
)


def _print_gpu_banner(cfg: AppConfig) -> None:
    """Print GPU availability information."""
    if not cfg.use_gpu:
        info("GPU encoding disabled by user")
        return
    gpu_info = GPUDetector.detect()
    if gpu_info.available:
        mode = "FFmpeg pipeline (auto-enabled)"
        info(f"GPU available: {gpu_info.codec} ({mode})")
    else:
        info("GPU not available, using CPU encoding (libx264)")


@app.command()
def main(
    input_path: str = typer.Argument(
        ...,
        help="Path to HTML file (memories_history.html) or folder containing memories",
    ),
    output: str | None = typer.Option(
        None,
        "-o",
        "--output",
        help="Output folder (default: 'output/' relative to input)",
    ),
    metadata: str | None = typer.Option(
        None,
        "-m",
        "--metadata",
        help="Path to memories_history.html for metadata (optional for folder mode)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview all actions without making changes",
    ),
    image_workers: int = typer.Option(
        8,
        "--image-workers",
        help="Number of parallel workers for image processing",
    ),
    video_workers: int = typer.Option(
        4,
        "--video-workers",
        help="Number of parallel workers for video processing",
    ),
    download_workers: int = typer.Option(
        32,
        "--download-workers",
        help="Number of parallel workers for downloads",
    ),
    metadata_workers: int = typer.Option(
        8,
        "--metadata-workers",
        help="Number of parallel workers for metadata application",
    ),
    use_gpu: bool = typer.Option(
        True,
        "--use-gpu/--no-gpu",
        help="Enable/disable GPU acceleration",
    ),
    ffmpeg_gpu: bool = typer.Option(
        False,
        "--ffmpeg-gpu",
        help="Use FFmpeg GPU pipeline for maximum performance",
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Enable verbose output (shows detailed progress)",
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Suppress all output except errors",
    ),
) -> None:
    """
    Snapchat Memories Backuper
    
    Automatically detects whether input is an HTML file or folder:
    - HTML file: Downloads memories from URLs in the HTML file
    - Folder: Processes existing files in the folder
    
    Examples:
    
    \b
    # Download from HTML file
    python -m snap_memories memories_history.html -o output_folder
    
    \b
    # Process folder
    python -m snap_memories ./memories -o output_folder
    
    \b
    # Process folder with metadata
    python -m snap_memories ./memories -o output_folder -m memories_history.html
    
    \b
    # Preview without making changes
    python -m snap_memories memories_history.html -o output_folder --dry-run
    """
    # Initialize logger
    logger = Logger(
        LogLevel.VERBOSE if verbose else (LogLevel.QUIET if quiet else LogLevel.NORMAL)
    )
    set_logger(logger)

    # Validate input path
    input_path_obj = Path(input_path)
    if not input_path_obj.exists():
        logger.error(f"Input path does not exist: {input_path}")
        raise typer.Exit(code=2)

    # Build configuration
    cfg = AppConfig(
        dry_run=dry_run,
        image_workers=image_workers,
        video_workers=video_workers,
        download_workers=download_workers,
        metadata_workers=metadata_workers,
        use_gpu=use_gpu,
        use_ffmpeg_gpu=ffmpeg_gpu,
        verbose=verbose,
        quiet=quiet,
        input_path=input_path_obj.resolve(),
        output_dir=Path(output).resolve() if output else None,
        metadata_html=Path(metadata).resolve() if metadata else None,
    )

    # Print GPU banner
    _print_gpu_banner(cfg)

    # Run pipeline
    try:
        pipeline = Pipeline(cfg)
        exit_code = pipeline.run_auto()
        raise typer.Exit(code=exit_code)
    except typer.Exit:
        # Re-raise typer.Exit to allow normal exit with status codes
        raise
    except KeyboardInterrupt:
        logger.error("Operation cancelled by user")
        raise typer.Exit(code=130)
    except Exception as e:
        logger.error("Unexpected error occurred", e)
        raise typer.Exit(code=1)


def run() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    app()
