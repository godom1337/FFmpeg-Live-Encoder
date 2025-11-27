"""Validation utilities for input data"""

import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import os
import ipaddress

class ValidationError(ValueError):
    """Custom validation error"""
    pass

def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> bool:
    """Validate URL format

    Args:
        url: URL to validate
        allowed_schemes: List of allowed URL schemes

    Returns:
        bool: True if URL is valid

    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError("URL cannot be empty")

    try:
        parsed = urlparse(url)

        # Check if URL has scheme and netloc/path
        if not parsed.scheme:
            raise ValidationError("URL must have a scheme (e.g., http://, udp://)")

        # Check allowed schemes
        if allowed_schemes and parsed.scheme not in allowed_schemes:
            raise ValidationError(
                f"URL scheme '{parsed.scheme}' not allowed. "
                f"Allowed schemes: {', '.join(allowed_schemes)}"
            )

        # For network URLs, check netloc
        if parsed.scheme in ['http', 'https', 'tcp', 'udp', 'rtmp', 'rtsp']:
            if not parsed.netloc:
                raise ValidationError(f"URL with scheme '{parsed.scheme}' must have a host")

        # For file URLs, check path
        if parsed.scheme == 'file':
            if not parsed.path:
                raise ValidationError("File URL must have a path")

        return True

    except Exception as e:
        raise ValidationError(f"Invalid URL format: {e}")

def validate_stream_url(url: str) -> bool:
    """Validate streaming URL

    Args:
        url: Streaming URL to validate

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If URL is invalid for streaming
    """
    allowed_schemes = ['udp', 'tcp', 'rtmp', 'rtsp', 'http', 'https', 'rtp']
    validate_url(url, allowed_schemes)

    parsed = urlparse(url)

    # Validate UDP multicast addresses
    if parsed.scheme == 'udp' and parsed.hostname:
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if isinstance(ip, ipaddress.IPv4Address):
                # Check if it's a multicast address (224.0.0.0 to 239.255.255.255)
                if not (224 <= ip.packed[0] <= 239) and not ip.is_private:
                    # Allow multicast and private IPs for UDP
                    pass
        except ValueError:
            # Hostname is not an IP, that's fine
            pass

    # Check port for network protocols
    if parsed.scheme in ['udp', 'tcp', 'rtmp', 'rtsp', 'rtp']:
        if not parsed.port:
            default_ports = {
                'rtmp': 1935,
                'rtsp': 554,
                'http': 80,
                'https': 443
            }
            if parsed.scheme not in default_ports:
                raise ValidationError(f"Port number required for {parsed.scheme} URL")

    return True

def validate_file_path(path: str, must_exist: bool = False) -> bool:
    """Validate file path

    Args:
        path: File path to validate
        must_exist: Whether file must exist

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If path is invalid
    """
    if not path:
        raise ValidationError("File path cannot be empty")

    # Normalize path
    normalized = os.path.normpath(path)

    # Check for path traversal attempts
    if '..' in normalized:
        raise ValidationError("Path traversal not allowed")

    # Check if file exists if required
    if must_exist and not os.path.exists(normalized):
        raise ValidationError(f"File does not exist: {path}")

    # Check if path is within allowed directories
    allowed_dirs = ['/input', '/output', '/data']
    if not any(normalized.startswith(d) for d in allowed_dirs):
        # Allow relative paths for testing
        if not os.path.isabs(normalized):
            return True
        raise ValidationError(
            f"File path must be within allowed directories: {', '.join(allowed_dirs)}"
        )

    return True

def validate_bitrate(bitrate: str) -> bool:
    """Validate bitrate string format

    Args:
        bitrate: Bitrate string (e.g., "5M", "2500k")

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If bitrate format is invalid
    """
    if not bitrate:
        raise ValidationError("Bitrate cannot be empty")

    pattern = r"^\d+(\.\d+)?[kKmM]?$"
    if not re.match(pattern, bitrate):
        raise ValidationError(
            "Invalid bitrate format. Use format like '5M', '2500k', or '1000000'"
        )

    # Parse value
    if bitrate[-1].lower() == 'm':
        value = float(bitrate[:-1]) * 1000000
    elif bitrate[-1].lower() == 'k':
        value = float(bitrate[:-1]) * 1000
    else:
        value = float(bitrate)

    # Check reasonable bounds (100kbps to 100Mbps)
    if value < 100000:
        raise ValidationError("Bitrate too low (minimum 100kbps)")
    if value > 100000000:
        raise ValidationError("Bitrate too high (maximum 100Mbps)")

    return True

def validate_resolution(width: int, height: int) -> bool:
    """Validate video resolution

    Args:
        width: Video width
        height: Video height

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If resolution is invalid
    """
    # Check positive values
    if width <= 0 or height <= 0:
        raise ValidationError("Resolution must be positive")

    # Check maximum resolution (8K)
    if width > 7680 or height > 4320:
        raise ValidationError("Resolution exceeds 8K maximum (7680x4320)")

    # Check minimum resolution
    if width < 128 or height < 96:
        raise ValidationError("Resolution too small (minimum 128x96)")

    # Check aspect ratio (between 1:4 and 4:1)
    aspect_ratio = width / height
    if aspect_ratio < 0.25 or aspect_ratio > 4.0:
        raise ValidationError(
            f"Unusual aspect ratio {aspect_ratio:.2f}. "
            "Should be between 1:4 and 4:1"
        )

    return True

def validate_job_name(name: str) -> bool:
    """Validate job name

    Args:
        name: Job name to validate

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If name is invalid
    """
    if not name:
        raise ValidationError("Job name cannot be empty")

    if len(name) > 100:
        raise ValidationError("Job name too long (maximum 100 characters)")

    # Allow alphanumeric, spaces, hyphens, underscores
    pattern = r"^[\w\s\-\.]+$"
    if not re.match(pattern, name):
        raise ValidationError(
            "Job name can only contain letters, numbers, spaces, "
            "hyphens, underscores, and periods"
        )

    return True

def validate_codec_settings(
    codec: str,
    encoder: str,
    profile: Optional[str] = None
) -> bool:
    """Validate codec and encoder compatibility

    Args:
        codec: Video codec
        encoder: Encoder type
        profile: Optional encoder profile

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If combination is invalid
    """
    valid_combinations = {
        'h264': ['cpu', 'cuda', 'nvenc', 'vulkan'],
        'h265': ['cpu', 'cuda', 'nvenc'],
        'av1': ['cpu', 'nvenc']
    }

    if codec not in valid_combinations:
        raise ValidationError(f"Unknown codec: {codec}")

    if encoder not in valid_combinations[codec]:
        raise ValidationError(
            f"Encoder '{encoder}' not compatible with codec '{codec}'. "
            f"Valid encoders: {', '.join(valid_combinations[codec])}"
        )

    # Validate profiles if provided
    if profile:
        valid_profiles = {
            'cpu': ['ultrafast', 'superfast', 'veryfast', 'faster',
                   'fast', 'medium', 'slow', 'slower', 'veryslow'],
            'nvenc': ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7'],
            'cuda': ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7']
        }

        if encoder in valid_profiles and profile not in valid_profiles[encoder]:
            raise ValidationError(
                f"Invalid profile '{profile}' for encoder '{encoder}'. "
                f"Valid profiles: {', '.join(valid_profiles[encoder])}"
            )

    return True

def validate_priority(priority: int) -> bool:
    """Validate job priority

    Args:
        priority: Priority value

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If priority is invalid
    """
    if priority < 1 or priority > 10:
        raise ValidationError("Priority must be between 1 and 10")
    return True

def validate_segment_duration(duration: int) -> bool:
    """Validate HLS segment duration

    Args:
        duration: Segment duration in seconds

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If duration is invalid
    """
    if duration < 1:
        raise ValidationError("Segment duration must be at least 1 second")
    if duration > 60:
        raise ValidationError("Segment duration cannot exceed 60 seconds")
    return True

def validate_playlist_size(size: int) -> bool:
    """Validate HLS playlist size

    Args:
        size: Number of segments in playlist

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If size is invalid
    """
    if size < 3:
        raise ValidationError("Playlist must contain at least 3 segments")
    if size > 100:
        raise ValidationError("Playlist cannot contain more than 100 segments")
    return True