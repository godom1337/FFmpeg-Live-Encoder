"""
FFmpeg command validation service.

This module provides dry-run validation and hardware acceleration checks
to catch errors before job creation.
"""

import asyncio
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


async def dry_run_ffmpeg(cmd: List[str], timeout: int = 2) -> Tuple[bool, str]:
    """
    Validate FFmpeg command by running with null output and 1-second limit.

    This executes a short version of the command to validate:
    - Command syntax is correct
    - Input file is accessible
    - Codec options are compatible
    - No obvious configuration errors

    Args:
        cmd: FFmpeg command as list of strings
        timeout: Maximum seconds to wait for validation (default: 2s, most validations finish in <1s)

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if command is valid, False otherwise
        - error_message: Empty string if valid, error details if invalid

    Example:
        >>> cmd = ["ffmpeg", "-i", "input.mp4", "-c:v", "libx264", "output.mp4"]
        >>> is_valid, error = await dry_run_ffmpeg(cmd)
        >>> if is_valid:
        >>>     print("Command is valid!")
    """
    try:
        # Build dry-run command
        # Strategy: Use -f null output with -t 1 (1 second duration limit)
        dry_run_cmd = ["ffmpeg"]

        # Find input position
        try:
            input_idx = cmd.index("-i")
        except ValueError:
            return False, "No input file specified in command"

        # Copy up to and including input file
        dry_run_cmd.extend(cmd[1:input_idx + 2])

        # Add 1-second duration limit to avoid long processing
        dry_run_cmd.extend(["-t", "1"])

        # Copy encoding options (between input and output)
        output_path = cmd[-1]
        encoding_opts = cmd[input_idx + 2:-1]
        dry_run_cmd.extend(encoding_opts)

        # Check if this is HLS output (has -f hls flag)
        is_hls = '-f' in encoding_opts and 'hls' in encoding_opts

        if is_hls:
            # For HLS, we can't use null output - skip dry-run validation
            # HLS validation requires actual directory creation which we don't want in preview
            logger.info("Skipping dry-run for HLS output (requires directory creation)")
            return True, ""
        else:
            # Use null output (no actual file written)
            dry_run_cmd.extend(["-f", "null", "-"])

        logger.debug(f"Dry-run command: {' '.join(dry_run_cmd)}")

        # Execute dry-run
        proc = await asyncio.create_subprocess_exec(
            *dry_run_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout
        )

        if proc.returncode == 0:
            logger.info("Dry-run validation passed")
            return True, ""
        else:
            # Parse FFmpeg error message
            error = extract_ffmpeg_error(stderr.decode())
            logger.warning(f"Dry-run validation failed: {error}")
            return False, error

    except asyncio.TimeoutError:
        return False, "Validation timed out (>2s). Command may be invalid or processing is too slow."
    except Exception as e:
        logger.error(f"Dry-run validation error: {e}")
        return False, f"Validation error: {str(e)}"


def extract_ffmpeg_error(stderr: str) -> str:
    """
    Extract user-friendly error message from FFmpeg stderr output.

    FFmpeg outputs verbose information to stderr. This function
    extracts the relevant error message.

    Args:
        stderr: FFmpeg stderr output

    Returns:
        Extracted error message (or last line if no obvious error)

    Example:
        >>> stderr = "ffmpeg version...\\nUnknown encoder 'badcodec'\\n"
        >>> error = extract_ffmpeg_error(stderr)
        >>> print(error)  # "Unknown encoder 'badcodec'"
    """
    if not stderr:
        return "Unknown FFmpeg error"

    # FFmpeg errors usually contain these keywords
    error_keywords = ["error", "invalid", "unknown", "failed", "not found"]

    # Search for lines containing error keywords (reversed to get most recent)
    lines = stderr.strip().split('\n')
    for line in reversed(lines):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in error_keywords):
            return line.strip()

    # If no obvious error, return last non-empty line
    for line in reversed(lines):
        if line.strip() and not line.strip().startswith("ffmpeg version"):
            return line.strip()

    return "Unknown FFmpeg error"


async def check_hwaccel_available(hwaccel: str) -> bool:
    """
    Check if hardware acceleration is available on the system.

    Tests hardware acceleration by attempting to use it with FFmpeg.
    Uses a short test to avoid delays.

    Args:
        hwaccel: Hardware acceleration type (none, nvenc, vaapi)

    Returns:
        True if hardware acceleration is available, False otherwise

    Example:
        >>> is_available = await check_hwaccel_available("nvenc")
        >>> if is_available:
        >>>     print("NVENC available, can use GPU encoding")
    """
    # 'none' is always available (software encoding)
    if hwaccel == "none" or not hwaccel:
        return True

    try:
        # Test command with testsrc (synthetic test video)
        # This checks if hwaccel works without needing a real input file
        test_cmd = [
            "ffmpeg",
            "-hwaccel", hwaccel,
            "-f", "lavfi",
            "-i", "testsrc=duration=1:size=640x480:rate=1",
            "-f", "null",
            "-"
        ]

        proc = await asyncio.create_subprocess_exec(
            *test_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=2  # Reduced from 5s to 2s for faster preview feedback
        )

        if proc.returncode == 0:
            logger.info(f"Hardware acceleration '{hwaccel}' is available")
            return True
        else:
            logger.info(f"Hardware acceleration '{hwaccel}' is not available")
            return False

    except asyncio.TimeoutError:
        logger.warning(f"Hardware acceleration check for '{hwaccel}' timed out (>2s)")
        return False
    except Exception as e:
        logger.error(f"Error checking hardware acceleration '{hwaccel}': {e}")
        return False
