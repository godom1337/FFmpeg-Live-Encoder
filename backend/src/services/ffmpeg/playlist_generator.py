"""
HLS Master Playlist Generator

Generates RFC 8216 compliant HLS master playlists for Adaptive Bitrate (ABR) streaming.
"""

from typing import List
from pathlib import Path
from enum import Enum

from models.rendition import Rendition


class PlaylistType(Enum):
    """HLS Playlist types according to RFC 8216."""
    LIVE = "LIVE"     # No explicit tag - default for live streams
    EVENT = "EVENT"   # #EXT-X-PLAYLIST-TYPE:EVENT - event-style playlist
    VOD = "VOD"       # #EXT-X-PLAYLIST-TYPE:VOD - video on demand


def generate_master_playlist(renditions: List[Rendition], output_dir: Path) -> Path:
    """
    Generate HLS master playlist (master.m3u8) with EXT-X-STREAM-INF tags.

    Creates a master playlist that references all variant playlists with
    proper BANDWIDTH, RESOLUTION, and CODECS attributes.

    Args:
        renditions: List of Rendition objects representing quality variants
        output_dir: Base output directory path

    Returns:
        Path to the generated master playlist file

    Raises:
        ValueError: If renditions list is empty or invalid
        IOError: If playlist file cannot be written

    Example:
        >>> from models.rendition import Rendition
        >>> from pathlib import Path
        >>>
        >>> renditions = [
        ...     Rendition(name="1080p", video_bitrate="5M", video_resolution="1920x1080"),
        ...     Rendition(name="720p", video_bitrate="3M", video_resolution="1280x720")
        ... ]
        >>> playlist_path = generate_master_playlist(renditions, Path("/output/job-001"))
        >>> print(playlist_path)
        /output/job-001/master.m3u8
    """
    if not renditions:
        raise ValueError("Cannot generate master playlist: renditions list is empty")

    # Ensure output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    master_path = output_dir / "master.m3u8"

    with open(master_path, "w", encoding="utf-8") as f:
        # Write header
        f.write("#EXTM3U\n")
        f.write("#EXT-X-VERSION:3\n")

        # Write variant playlists
        for rendition in renditions:
            # Calculate total bandwidth (video + audio)
            bandwidth = calculate_total_bandwidth(rendition)

            # Parse resolution
            resolution = rendition.video_resolution  # e.g., "1920x1080"

            # Generate codec string (RFC 6381 format)
            codecs = generate_codec_string(rendition)

            # Write EXT-X-STREAM-INF tag
            f.write(
                f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},"
                f"RESOLUTION={resolution},CODECS=\"{codecs}\"\n"
            )

            # Write variant playlist path (relative)
            f.write(f"{rendition.name}/index.m3u8\n")

    return master_path


def calculate_total_bandwidth(rendition: Rendition) -> int:
    """
    Calculate total bandwidth for a rendition (video + audio).

    Args:
        rendition: Rendition object with video_bitrate and audio_bitrate

    Returns:
        Total bandwidth in bits per second

    Example:
        >>> rendition = Rendition(
        ...     name="1080p",
        ...     video_bitrate="5M",
        ...     audio_bitrate="128k",
        ...     video_resolution="1920x1080"
        ... )
        >>> calculate_total_bandwidth(rendition)
        5128000
    """
    video_bps = bitrate_to_bps(rendition.video_bitrate)
    audio_bps = bitrate_to_bps(rendition.audio_bitrate or "0")

    return video_bps + audio_bps


def bitrate_to_bps(bitrate: str) -> int:
    """
    Convert bitrate string to bits per second.

    Supports suffixes: k/K (kilobits), m/M (megabits), g/G (gigabits)

    Args:
        bitrate: Bitrate string (e.g., "5M", "3000k", "1500000")

    Returns:
        Bitrate in bits per second

    Example:
        >>> bitrate_to_bps("5M")
        5000000
        >>> bitrate_to_bps("3000k")
        3000000
        >>> bitrate_to_bps("1500000")
        1500000
    """
    if not bitrate or bitrate == "0":
        return 0

    suffix = bitrate[-1].lower()

    if suffix == 'k':
        return int(float(bitrate[:-1]) * 1000)
    elif suffix == 'm':
        return int(float(bitrate[:-1]) * 1000000)
    elif suffix == 'g':
        return int(float(bitrate[:-1]) * 1000000000)
    else:
        # Plain number (bits per second)
        return int(bitrate)


def generate_codec_string(rendition: Rendition) -> str:
    """
    Generate RFC 6381 codec string for HLS EXT-X-STREAM-INF tag.

    Returns codec identifiers for video and audio codecs in the format
    required by the HLS specification.

    Args:
        rendition: Rendition object with codec information

    Returns:
        Comma-separated codec string (e.g., "avc1.640028,mp4a.40.2")

    Example:
        >>> rendition = Rendition(
        ...     name="1080p",
        ...     video_bitrate="5M",
        ...     video_resolution="1920x1080",
        ...     video_codec="h264",
        ...     video_profile="high",
        ...     audio_codec="aac"
        ... )
        >>> generate_codec_string(rendition)
        'avc1.640028,mp4a.40.2'
    """
    video_codec = rendition.video_codec or "h264"
    audio_codec = rendition.audio_codec or "aac"
    video_profile = rendition.video_profile or "main"

    # Normalize FFmpeg encoder names to codec names for RFC 6381 compliance
    codec_mapping = {
        "libx264": "h264",
        "libx265": "h265",
        "libaom-av1": "av1",
        "libvpx": "vp8",
        "libvpx-vp9": "vp9",
    }
    video_codec = codec_mapping.get(video_codec, video_codec)

    # Video codec strings (RFC 6381)
    video_codecs = {
        "h264": {
            "baseline": "avc1.42001e",  # Baseline Profile Level 3.0
            "main": "avc1.64001f",      # Main Profile Level 3.1
            "high": "avc1.640028",      # High Profile Level 4.0
        },
        "h265": {
            "main": "hvc1.1.6.L120.90",  # Main Profile, Level 4
            "main10": "hvc1.2.4.L120.90"  # Main 10 Profile
        },
        "av1": {
            "main": "av01.0.05M.08",  # Main Profile, Level 3.1
        }
    }

    # Audio codec strings
    audio_codecs = {
        "aac": "mp4a.40.2",    # AAC-LC
        "mp3": "mp4a.69",       # MP3
        "opus": "opus",         # Opus
        "ac3": "ac-3",          # AC-3
        "eac3": "ec-3"          # E-AC-3
    }

    # Get video codec string
    if video_codec in video_codecs:
        video_str = video_codecs[video_codec].get(video_profile, list(video_codecs[video_codec].values())[0])
    else:
        # Fallback for unknown codecs
        video_str = f"{video_codec}.unknown"

    # Get audio codec string
    audio_str = audio_codecs.get(audio_codec, "mp4a.40.2")

    return f"{video_str},{audio_str}"


def validate_master_playlist(master_path: Path) -> bool:
    """
    Validate that a master playlist file exists and has proper format.

    Args:
        master_path: Path to master playlist file

    Returns:
        True if playlist is valid, False otherwise

    Example:
        >>> from pathlib import Path
        >>> validate_master_playlist(Path("/output/job-001/master.m3u8"))
        True
    """
    if not master_path.exists():
        return False

    try:
        with open(master_path, "r", encoding="utf-8") as f:
            content = f.read()

            # Check for required headers
            if "#EXTM3U" not in content:
                return False

            # Check for at least one stream info tag
            if "#EXT-X-STREAM-INF" not in content:
                return False

            return True

    except (IOError, UnicodeDecodeError):
        return False


def finalize_variant_playlist(playlist_path: Path, playlist_type: PlaylistType) -> None:
    """
    Update a variant playlist with the appropriate playlist type tags.

    Adds #EXT-X-PLAYLIST-TYPE tag for EVENT and VOD playlists.
    Adds #EXT-X-ENDLIST tag for VOD playlists to indicate completion.

    Args:
        playlist_path: Path to the variant playlist file (e.g., 1080p/index.m3u8)
        playlist_type: Type of playlist (LIVE, EVENT, or VOD)

    Raises:
        FileNotFoundError: If playlist file doesn't exist
        IOError: If playlist cannot be read or written

    Example:
        >>> from pathlib import Path
        >>> finalize_variant_playlist(
        ...     Path("/output/job-001/1080p/index.m3u8"),
        ...     PlaylistType.VOD
        ... )
    """
    if not playlist_path.exists():
        raise FileNotFoundError(f"Variant playlist not found: {playlist_path}")

    # Read existing playlist
    with open(playlist_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # For LIVE playlists, no modification needed
    if playlist_type == PlaylistType.LIVE:
        return

    # Find insertion point for playlist type tag (after #EXT-X-VERSION or #EXTM3U)
    modified_lines = []
    type_tag_inserted = False

    for line in lines:
        modified_lines.append(line)

        # Insert playlist type tag after version tag or M3U header
        if not type_tag_inserted and (
            line.startswith("#EXT-X-VERSION") or
            (line.startswith("#EXTM3U") and not any(l.startswith("#EXT-X-VERSION") for l in lines))
        ):
            modified_lines.append(f"#EXT-X-PLAYLIST-TYPE:{playlist_type.value}\n")
            type_tag_inserted = True

    # For VOD and EVENT (completed), ensure #EXT-X-ENDLIST is at the end
    # LIVE playlists should NOT have ENDLIST (they're ongoing)
    if playlist_type in (PlaylistType.VOD, PlaylistType.EVENT):
        # Remove any existing #EXT-X-ENDLIST
        modified_lines = [line for line in modified_lines if not line.startswith("#EXT-X-ENDLIST")]

        # Add #EXT-X-ENDLIST at the end
        if modified_lines and not modified_lines[-1].endswith("\n"):
            modified_lines[-1] += "\n"
        modified_lines.append("#EXT-X-ENDLIST\n")

    # Write modified playlist back
    with open(playlist_path, "w", encoding="utf-8") as f:
        f.writelines(modified_lines)


def finalize_all_variant_playlists(
    output_dir: Path,
    renditions: List[Rendition],
    playlist_type: PlaylistType
) -> None:
    """
    Finalize all variant playlists for a job with the appropriate playlist type.

    This function should be called after FFmpeg has finished generating the HLS
    segments and playlists to add the proper type tags.

    Args:
        output_dir: Base output directory containing rendition subdirectories
        renditions: List of renditions that were generated
        playlist_type: Type of playlist (LIVE, EVENT, or VOD)

    Raises:
        FileNotFoundError: If any variant playlist is missing
        IOError: If playlists cannot be processed

    Example:
        >>> from pathlib import Path
        >>> from models.rendition import Rendition
        >>>
        >>> renditions = [
        ...     Rendition(name="1080p", video_bitrate="5M", video_resolution="1920x1080"),
        ...     Rendition(name="720p", video_bitrate="3M", video_resolution="1280x720")
        ... ]
        >>> finalize_all_variant_playlists(
        ...     Path("/output/job-001"),
        ...     renditions,
        ...     PlaylistType.VOD
        ... )
    """
    for rendition in renditions:
        variant_playlist = output_dir / rendition.name / "index.m3u8"
        finalize_variant_playlist(variant_playlist, playlist_type)
