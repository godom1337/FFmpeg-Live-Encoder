"""
FFprobe integration for input file metadata extraction.

This module provides functions to probe media files and extract metadata
such as duration, codecs, tracks, resolution, etc.
"""

import asyncio
import json
import logging
from typing import Dict, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


async def probe_input_file(file_path: str) -> Dict:
    """
    Probe media file and return metadata using FFprobe.

    Args:
        file_path: Absolute path to input file

    Returns:
        Dictionary with metadata including:
        - file_path: str
        - duration: float (seconds)
        - format: str (container format)
        - size: int (bytes)
        - bitrate: str
        - tracks: List[Dict] (stream information)
        - probed_at: datetime

    Raises:
        RuntimeError: If FFprobe fails
        FileNotFoundError: If file doesn't exist

    Example:
        >>> metadata = await probe_input_file("/input/video.mp4")
        >>> print(f"Duration: {metadata['duration']}s")
        >>> print(f"Tracks: {len(metadata['tracks'])}")
    """
    # Validate file exists
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Build FFprobe command
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]

    try:
        # Execute FFprobe
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=10  # 10 second timeout for probe
        )

        if proc.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"FFprobe failed: {error_msg}")

        # Parse JSON output
        probe_data = json.loads(stdout.decode())

        # Extract metadata
        format_info = probe_data.get("format", {})
        file_size = file_path_obj.stat().st_size

        metadata = {
            "file_path": file_path,
            "duration": float(format_info.get("duration", 0)),
            "format": format_info.get("format_name"),
            "size": file_size,
            "bitrate": format_info.get("bit_rate"),
            "tracks": extract_track_info(probe_data),
            "probed_at": datetime.utcnow()
        }

        logger.info(f"Probed {file_path}: {len(metadata['tracks'])} tracks, {metadata['duration']}s")
        return metadata

    except asyncio.TimeoutError:
        raise RuntimeError(f"FFprobe timed out after 10 seconds")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse FFprobe output: {e}")
    except Exception as e:
        logger.error(f"Failed to probe {file_path}: {e}")
        raise


def extract_track_info(probe_data: Dict) -> List[Dict]:
    """
    Extract user-friendly track information from FFprobe data.

    Args:
        probe_data: Raw FFprobe JSON output

    Returns:
        List of track dictionaries with type, codec, and metadata

    Example:
        >>> probe_data = {"streams": [...]}
        >>> tracks = extract_track_info(probe_data)
        >>> print(tracks[0]["type"])  # "video"
    """
    tracks = []

    for stream in probe_data.get("streams", []):
        track = {
            "index": stream.get("index", 0),
            "type": stream.get("codec_type", "unknown"),
            "codec": stream.get("codec_name", "unknown"),
            "language": stream.get("tags", {}).get("language", "unknown"),
        }

        # Add video-specific fields
        if stream.get("codec_type") == "video":
            track["width"] = stream.get("width")
            track["height"] = stream.get("height")

            # Parse framerate (format: "30/1" or "24000/1001")
            r_frame_rate = stream.get("r_frame_rate", "0/1")
            try:
                num, den = r_frame_rate.split("/")
                track["fps"] = float(num) / float(den) if float(den) > 0 else 0
            except:
                track["fps"] = 0

        # Add audio-specific fields
        elif stream.get("codec_type") == "audio":
            track["channels"] = stream.get("channels")
            track["sample_rate"] = stream.get("sample_rate")
            track["bitrate"] = stream.get("bit_rate")

        tracks.append(track)

    return tracks
