"""
Centralized logging and output system for user-friendly messages.
"""
from __future__ import annotations

import sys
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """Log levels for controlling output verbosity."""
    QUIET = 0  # Only errors
    NORMAL = 1  # Normal user output (default)
    VERBOSE = 2  # Verbose output including debug info
    DEBUG = 3  # Maximum verbosity including tracebacks


class Logger:
    """Centralized logger for consistent user output."""
    
    def __init__(self, level: LogLevel = LogLevel.NORMAL):
        self.level = level
    
    def error(self, message: str, exc: Optional[Exception] = None) -> None:
        """Print error message. Always shown unless level is QUIET."""
        if self.level == LogLevel.QUIET:
            return
        if exc and self.level.value >= LogLevel.DEBUG.value:
            import traceback
            print(f"❌ Error: {message}", file=sys.stderr)
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        else:
            error_details = ""
            if exc:
                error_msg = str(exc).strip()
                if error_msg:
                    error_details = f": {error_msg}"
            print(f"❌ Error: {message}{error_details}", file=sys.stderr)
    
    def warning(self, message: str) -> None:
        """Print warning message. Shown for NORMAL and above."""
        if self.level.value >= LogLevel.NORMAL.value:
            print(f"⚠️  Warning: {message}", file=sys.stderr)
    
    def info(self, message: str) -> None:
        """Print info message. Shown for NORMAL and above."""
        if self.level.value >= LogLevel.NORMAL.value:
            print(message)
    
    def verbose(self, message: str) -> None:
        """Print verbose message. Shown for VERBOSE and above."""
        if self.level.value >= LogLevel.VERBOSE.value:
            print(f"[verbose] {message}")
    
    def debug(self, message: str) -> None:
        """Print debug message. Shown for DEBUG level only."""
        if self.level.value >= LogLevel.DEBUG.value:
            print(f"[debug] {message}")
    
    def dry_run(self, message: str) -> None:
        """Print dry-run message. Always shown unless QUIET."""
        if self.level == LogLevel.QUIET:
            return
        print(f"DRY RUN: {message}")


# Global logger instance (will be initialized by CLI)
_logger: Optional[Logger] = None


def get_logger() -> Logger:
    """Get the global logger instance."""
    if _logger is None:
        return Logger(LogLevel.NORMAL)
    return _logger


def set_logger(logger: Logger) -> None:
    """Set the global logger instance."""
    global _logger
    _logger = logger


def error(message: str, exc: Optional[Exception] = None) -> None:
    """Convenience function for error logging."""
    get_logger().error(message, exc)


def warning(message: str) -> None:
    """Convenience function for warning logging."""
    get_logger().warning(message)


def info(message: str) -> None:
    """Convenience function for info logging."""
    get_logger().info(message)


def verbose(message: str) -> None:
    """Convenience function for verbose logging."""
    get_logger().verbose(message)


def debug(message: str) -> None:
    """Convenience function for debug logging."""
    get_logger().debug(message)


def dry_run(message: str) -> None:
    """Convenience function for dry-run logging."""
    get_logger().dry_run(message)
