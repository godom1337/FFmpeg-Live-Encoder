"""
Security utilities for FFmpeg job creation.

This module provides functions for validating file paths and sanitizing
user inputs to prevent command injection and unauthorized file access.
"""

from pathlib import Path
from typing import List
from urllib.parse import urlparse
import re
import shlex


# Dangerous patterns for custom argument sanitization
DANGEROUS_PATTERNS = [
    r'[;&|`$()]',      # Shell metacharacters
    r'>\s*/dev',       # Device redirects
    r'\$\(',           # Command substitution
]


# Supported network protocols for input streams
SUPPORTED_NETWORK_PROTOCOLS = [
    'http', 'https',   # HTTP streaming
    'udp', 'rtp',      # UDP/RTP streaming
    'rtsp', 'rtsps',   # RTSP streaming
    'rtmp', 'rtmps',   # RTMP streaming
    'srt',             # SRT (Secure Reliable Transport)
    'tcp',             # TCP streaming
    'file',            # File protocol (explicit)
]


def _is_network_input(path: str) -> bool:
    """
    Check if the input path is a network URL.

    Args:
        path: Input path or URL

    Returns:
        True if path is a network URL, False otherwise
    """
    try:
        parsed = urlparse(path)
        return parsed.scheme.lower() in SUPPORTED_NETWORK_PROTOCOLS
    except Exception:
        return False


def validate_input_path(path: str) -> str:
    """
    Validate input file path or network URL.

    For network inputs (http://, udp://, rtsp://, etc.), validates URL format.
    For file paths, ensures file exists and is within allowed directories.

    Args:
        path: Path to input file or network URL

    Returns:
        Validated path or URL

    Raises:
        ValueError: If file doesn't exist, URL is invalid, or path is outside allowed directories
    """
    # Check if this is a network input
    if _is_network_input(path):
        # Validate network URL format
        try:
            parsed = urlparse(path)
            if not parsed.scheme or not (parsed.netloc or parsed.path):
                raise ValueError(f"Invalid network URL format: {path}")
            return path  # Return original URL unchanged
        except Exception as e:
            raise ValueError(f"Invalid network URL: {path}. Error: {e}")

    # Handle file paths
    p = Path(path).resolve()

    # Check file exists
    if not p.exists() or not p.is_file():
        raise ValueError(f"Input file does not exist: {path}")

    # Check within allowed input directories
    allowed_dirs = [Path("/input").resolve(), Path("/data").resolve()]
    if not any(p.is_relative_to(d) for d in allowed_dirs):
        raise ValueError(f"Input file must be in /input or /data directories")

    return str(p)


def validate_output_path(path: str) -> str:
    """
    Validate output file path and ensure it's within allowed directories.

    Args:
        path: Path to output file

    Returns:
        Absolute path to validated output location

    Raises:
        ValueError: If path is outside allowed directories
    """
    p = Path(path).resolve()

    # Check within allowed output directories
    allowed_dirs = [Path("/output").resolve(), Path("/data").resolve()]
    if not any(p.is_relative_to(d) for d in allowed_dirs):
        raise ValueError(f"Output file must be in /output or /data directories")

    # Ensure parent directory exists
    p.parent.mkdir(parents=True, exist_ok=True)

    return str(p)


def sanitize_custom_args(args: List[str]) -> List[str]:
    """
    Validate and sanitize custom FFmpeg arguments.

    Args:
        args: List of custom arguments

    Returns:
        Validated list of arguments

    Raises:
        ValueError: If dangerous patterns detected
    """
    if not args:
        return []

    # Check for dangerous patterns in each argument
    for arg in args:
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, arg):
                raise ValueError(
                    f"Dangerous pattern detected in argument: {arg}. "
                    f"Pattern: {pattern}"
                )

    # Validate each token doesn't contain shell metacharacters
    for token in args:
        if any(char in token for char in ['&', '|', ';', '`', '$', '(', ')']):
            raise ValueError(f"Invalid character in argument: {token}")

    return args


def parse_custom_args_string(args_string: str) -> List[str]:
    """
    Safely parse custom arguments string into list.

    Args:
        args_string: Space-separated custom arguments

    Returns:
        List of parsed arguments

    Raises:
        ValueError: If parsing fails or dangerous patterns detected
    """
    try:
        parsed = shlex.split(args_string)
    except ValueError as e:
        raise ValueError(f"Invalid argument syntax: {e}")

    return sanitize_custom_args(parsed)
