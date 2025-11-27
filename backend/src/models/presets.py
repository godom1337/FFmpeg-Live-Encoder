"""
Encoding Preset Templates

Provides pre-configured encoding templates for common use cases like
HLS streaming, YouTube uploads, adaptive streaming, etc.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from .rendition import Rendition


class EncodingPreset(BaseModel):
    """A complete encoding preset template."""

    id: str = Field(..., description="Unique preset identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Description of the preset")
    category: str = Field(..., description="Category (streaming, upload, archive, etc.)")
    abr_enabled: bool = Field(..., description="Whether this preset uses ABR")
    renditions: List[Rendition] = Field(..., description="List of renditions")

    # Default HLS settings
    segment_duration: int = Field(default=6, description="HLS segment duration in seconds")
    playlist_size: int = Field(default=10, description="Number of segments in playlist")

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags for searching/filtering")
    recommended_for: List[str] = Field(
        default_factory=list,
        description="Recommended use cases"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "hls-720p",
                "name": "HLS 720p",
                "description": "Single quality 720p HLS stream",
                "category": "streaming",
                "abr_enabled": False,
                "renditions": [{
                    "name": "720p",
                    "video_bitrate": "3M",
                    "video_resolution": "1280x720",
                    "video_framerate": 30
                }]
            }
        }


# Pre-defined preset templates
ENCODING_PRESETS: Dict[str, EncodingPreset] = {
    # Single quality presets
    "hls-1080p": EncodingPreset(
        id="hls-1080p",
        name="HLS 1080p High Quality",
        description="Single 1080p stream with high quality settings",
        category="streaming",
        abr_enabled=False,
        renditions=[
            Rendition(
                name="1080p",
                video_bitrate="5M",
                video_resolution="1920x1080",
                video_framerate=30,
                video_codec="libx264",
                video_profile="high",
                audio_codec="aac",
                audio_bitrate="192k",
                preset="medium"
            )
        ],
        segment_duration=6,
        playlist_size=10,
        tags=["hls", "1080p", "high-quality", "single-track"],
        recommended_for=["High quality live streaming", "Professional broadcasts"]
    ),

    "hls-720p": EncodingPreset(
        id="hls-720p",
        name="HLS 720p Standard",
        description="Single 720p stream with balanced settings",
        category="streaming",
        abr_enabled=False,
        renditions=[
            Rendition(
                name="720p",
                video_bitrate="3M",
                video_resolution="1280x720",
                video_framerate=30,
                video_codec="libx264",
                video_profile="main",
                audio_codec="aac",
                audio_bitrate="128k",
                preset="medium"
            )
        ],
        segment_duration=6,
        playlist_size=10,
        tags=["hls", "720p", "standard", "single-track"],
        recommended_for=["Standard live streaming", "Most viewers"]
    ),

    "hls-480p": EncodingPreset(
        id="hls-480p",
        name="HLS 480p Mobile",
        description="Single 480p stream optimized for mobile",
        category="streaming",
        abr_enabled=False,
        renditions=[
            Rendition(
                name="480p",
                video_bitrate="1.5M",
                video_resolution="854x480",
                video_framerate=30,
                video_codec="libx264",
                video_profile="main",
                audio_codec="aac",
                audio_bitrate="96k",
                preset="fast"
            )
        ],
        segment_duration=6,
        playlist_size=10,
        tags=["hls", "480p", "mobile", "single-track"],
        recommended_for=["Mobile streaming", "Low bandwidth viewers"]
    ),

    # ABR presets
    "abr-full-hd": EncodingPreset(
        id="abr-full-hd",
        name="ABR Full HD (4 Qualities)",
        description="Adaptive streaming with 1080p, 720p, 480p, and 360p",
        category="streaming",
        abr_enabled=True,
        renditions=[
            Rendition(
                name="1080p",
                video_bitrate="5M",
                video_resolution="1920x1080",
                video_framerate=30,
                video_codec="libx264",
                video_profile="high",
                audio_codec="aac",
                audio_bitrate="192k",
                preset="medium"
            ),
            Rendition(
                name="720p",
                video_bitrate="3M",
                video_resolution="1280x720",
                video_framerate=30,
                video_codec="libx264",
                video_profile="main",
                audio_codec="aac",
                audio_bitrate="128k",
                preset="medium"
            ),
            Rendition(
                name="480p",
                video_bitrate="1.5M",
                video_resolution="854x480",
                video_framerate=30,
                video_codec="libx264",
                video_profile="main",
                audio_codec="aac",
                audio_bitrate="96k",
                preset="fast"
            ),
            Rendition(
                name="360p",
                video_bitrate="800k",
                video_resolution="640x360",
                video_framerate=30,
                video_codec="libx264",
                video_profile="baseline",
                audio_codec="aac",
                audio_bitrate="64k",
                preset="fast"
            )
        ],
        segment_duration=6,
        playlist_size=10,
        tags=["abr", "adaptive", "multi-quality", "1080p", "mobile-friendly"],
        recommended_for=["Professional live streaming", "Wide audience reach", "Variable network conditions"]
    ),

    "abr-hd": EncodingPreset(
        id="abr-hd",
        name="ABR HD (3 Qualities)",
        description="Adaptive streaming with 720p, 480p, and 360p",
        category="streaming",
        abr_enabled=True,
        renditions=[
            Rendition(
                name="720p",
                video_bitrate="3M",
                video_resolution="1280x720",
                video_framerate=30,
                video_codec="libx264",
                video_profile="main",
                audio_codec="aac",
                audio_bitrate="128k",
                preset="medium"
            ),
            Rendition(
                name="480p",
                video_bitrate="1.5M",
                video_resolution="854x480",
                video_framerate=30,
                video_codec="libx264",
                video_profile="main",
                audio_codec="aac",
                audio_bitrate="96k",
                preset="fast"
            ),
            Rendition(
                name="360p",
                video_bitrate="800k",
                video_resolution="640x360",
                video_framerate=30,
                video_codec="libx264",
                video_profile="baseline",
                audio_codec="aac",
                audio_bitrate="64k",
                preset="fast"
            )
        ],
        segment_duration=6,
        playlist_size=10,
        tags=["abr", "adaptive", "hd", "mobile-friendly"],
        recommended_for=["Standard live streaming", "Good balance of quality and compatibility"]
    ),

    "abr-mobile": EncodingPreset(
        id="abr-mobile",
        name="ABR Mobile (2 Qualities)",
        description="Adaptive streaming optimized for mobile with 480p and 360p",
        category="streaming",
        abr_enabled=True,
        renditions=[
            Rendition(
                name="480p",
                video_bitrate="1.5M",
                video_resolution="854x480",
                video_framerate=30,
                video_codec="libx264",
                video_profile="main",
                audio_codec="aac",
                audio_bitrate="96k",
                preset="fast"
            ),
            Rendition(
                name="360p",
                video_bitrate="800k",
                video_resolution="640x360",
                video_framerate=30,
                video_codec="libx264",
                video_profile="baseline",
                audio_codec="aac",
                audio_bitrate="64k",
                preset="veryfast"
            )
        ],
        segment_duration=4,
        playlist_size=10,
        tags=["abr", "mobile", "low-bandwidth", "fast-encoding"],
        recommended_for=["Mobile-only streaming", "Low bandwidth environments", "Quick encoding"]
    ),

    # YouTube upload preset
    "youtube-1080p": EncodingPreset(
        id="youtube-1080p",
        name="YouTube 1080p Upload",
        description="Optimized for YouTube 1080p uploads",
        category="upload",
        abr_enabled=False,
        renditions=[
            Rendition(
                name="1080p",
                video_bitrate="8M",
                video_resolution="1920x1080",
                video_framerate=30,
                video_codec="libx264",
                video_profile="high",
                audio_codec="aac",
                audio_bitrate="192k",
                preset="slow",
                max_bitrate="12M",
                buffer_size="16M"
            )
        ],
        segment_duration=6,
        playlist_size=10,
        tags=["youtube", "upload", "1080p", "high-quality"],
        recommended_for=["YouTube uploads", "High quality archives"]
    ),

    # Low latency preset
    "low-latency-720p": EncodingPreset(
        id="low-latency-720p",
        name="Low Latency 720p",
        description="720p with short segments for low latency streaming",
        category="streaming",
        abr_enabled=False,
        renditions=[
            Rendition(
                name="720p",
                video_bitrate="3M",
                video_resolution="1280x720",
                video_framerate=30,
                video_codec="libx264",
                video_profile="main",
                audio_codec="aac",
                audio_bitrate="128k",
                preset="veryfast"
            )
        ],
        segment_duration=2,
        playlist_size=6,
        tags=["low-latency", "720p", "fast-encoding", "interactive"],
        recommended_for=["Interactive streaming", "Gaming", "Live events with chat"]
    ),
}


def get_preset(preset_id: str) -> Optional[EncodingPreset]:
    """
    Get a preset by ID.

    Args:
        preset_id: Preset identifier

    Returns:
        EncodingPreset if found, None otherwise
    """
    return ENCODING_PRESETS.get(preset_id)


def get_all_presets() -> Dict[str, EncodingPreset]:
    """
    Get all available presets.

    Returns:
        Dictionary of preset_id -> EncodingPreset
    """
    return ENCODING_PRESETS.copy()


def get_presets_by_category(category: str) -> Dict[str, EncodingPreset]:
    """
    Get presets filtered by category.

    Args:
        category: Category to filter by

    Returns:
        Dictionary of matching presets
    """
    return {
        preset_id: preset
        for preset_id, preset in ENCODING_PRESETS.items()
        if preset.category == category
    }


def get_presets_by_tag(tag: str) -> Dict[str, EncodingPreset]:
    """
    Get presets filtered by tag.

    Args:
        tag: Tag to filter by

    Returns:
        Dictionary of matching presets
    """
    return {
        preset_id: preset
        for preset_id, preset in ENCODING_PRESETS.items()
        if tag in preset.tags
    }
