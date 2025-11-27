"""
Pydantic Model Mixins - Single Source of Truth for Encoding Fields

This module defines encoding field mixins that can be inherited by multiple models,
eliminating the need to manually duplicate field definitions across:
- CreateJobRequest
- ValidateJobRequest
- EncodingJob
- OutputConfiguration
- OutputConfigurationCreate

Before: Define each field in 3-5 different models
After: Define each field ONCE in a mixin, all models inherit

Usage:
    class CreateJobRequest(EncodingFieldsMixin, BaseModel):
        # System fields only
        input_file: str
        job_name: Optional[str]
        # All encoding fields inherited automatically!
"""

from typing import Optional
from pydantic import BaseModel, Field


class VideoEncodingMixin(BaseModel):
    """Video encoding fields - inherit this instead of duplicating"""

    # Basic video encoding
    video_codec: Optional[str] = Field(None, alias="videoCodec", description="Video codec (libx264, libx265, etc.)")
    video_bitrate: Optional[str] = Field(None, alias="videoBitrate", description="Video bitrate (e.g., '2500k', '5M')")
    video_profile: Optional[str] = Field(None, alias="videoProfile", description="Video profile (baseline, main, high)")
    video_framerate: Optional[int] = Field(None, alias="fps", description="Target framerate", ge=1, le=120)
    video_resolution: Optional[str] = Field(None, alias="scale", description="Video scaling (e.g., '1280:720')")
    video_filters: Optional[str] = Field(None, alias="videoFilters", description="Additional video filters")
    encoding_preset: Optional[str] = Field(None, alias="preset", description="Encoding preset (ultrafast to veryslow)")

    # Advanced video encoding
    crf: Optional[int] = Field(None, description="Constant Rate Factor (0-51, lower = better quality)")
    keyframe_interval: Optional[int] = Field(None, description="Keyframe interval in frames (GOP size)")
    tune: Optional[str] = Field(None, description="Content tune (film, animation, grain, etc.)")
    two_pass: bool = Field(default=False, description="Enable two-pass encoding")
    rate_control_mode: Optional[str] = Field(None, description="Rate control mode (cbr, vbr, cqp)")
    profile: Optional[str] = Field(None, description="Codec profile")
    level: Optional[str] = Field(None, description="Codec level")
    max_bitrate: Optional[str] = Field(None, description="Maximum bitrate")
    buffer_size: Optional[str] = Field(None, description="VBV buffer size")
    look_ahead: Optional[int] = Field(None, description="Lookahead frames for rate control")
    pixel_format: Optional[str] = Field(None, description="Pixel format (yuv420p, yuv444p, etc.)")

    class Config:
        # Allow this mixin to be inherited
        extra = 'allow'
        populate_by_name = True  # Accept both alias (camelCase) and field name (snake_case)


class AudioEncodingMixin(BaseModel):
    """Audio encoding fields - inherit this instead of duplicating"""

    audio_codec: Optional[str] = Field(None, alias="audioCodec", description="Audio codec (copy, aac, opus, mp3)")
    audio_bitrate: Optional[str] = Field(None, alias="audioBitrate", description="Audio bitrate (e.g., '128k', '256k')")
    audio_channels: Optional[int] = Field(None, alias="audioChannels", description="Number of audio channels (1-8)", ge=1, le=8)
    audio_volume: Optional[int] = Field(None, alias="audioVolume", description="Audio volume adjustment (0-100)", ge=0, le=100)
    audio_stream_index: Optional[int] = Field(None, alias="audioStreamIndex", description="Audio stream index for track selection")

    class Config:
        extra = 'allow'
        populate_by_name = True  # Accept both alias (camelCase) and field name (snake_case)


class HardwareAccelMixin(BaseModel):
    """Hardware acceleration fields - inherit this instead of duplicating"""

    hardware_accel: Optional[str] = Field(None, alias="hardwareAccel", description="Hardware acceleration (none, nvenc, vaapi, videotoolbox)")

    class Config:
        extra = 'allow'
        populate_by_name = True  # Accept both alias (camelCase) and field name (snake_case)


class HLSEncodingMixin(BaseModel):
    """HLS-specific encoding fields - inherit this instead of duplicating"""

    segment_duration: int = Field(default=6, alias="segmentDuration", ge=1, le=60, description="HLS segment duration in seconds")
    playlist_size: int = Field(default=10, alias="playlistSize", ge=1, le=20, description="Number of segments in playlist")
    playlist_type: str = Field(default="live", alias="playlistType", description="Playlist type (vod, event, live)")
    segment_type: str = Field(default="mpegts", alias="segmentType", description="Segment type (mpegts, fmp4)")
    segment_pattern: str = Field(default="segment_%03d.ts", alias="segmentPattern", description="Segment filename pattern")

    class Config:
        extra = 'allow'
        populate_by_name = True  # Accept both alias (camelCase) and field name (snake_case)


class ABREncodingMixin(BaseModel):
    """ABR/Multi-rendition fields - inherit this instead of duplicating"""

    abr_enabled: bool = Field(default=False, alias="abrEnabled", description="Enable adaptive bitrate streaming")
    # NOTE: renditions field is intentionally NOT in this mixin because it has different types:
    # - In OutputConfiguration: List[Rendition] (Python objects)
    # - In database/field_registry: JSON string
    # Each model defines it as needed

    class Config:
        extra = 'allow'
        populate_by_name = True  # Accept both alias (camelCase) and field name (snake_case)


class EncodingFieldsMixin(
    VideoEncodingMixin,
    AudioEncodingMixin,
    HardwareAccelMixin,
    HLSEncodingMixin,
    ABREncodingMixin
):
    """
    Complete encoding fields mixin - ALL encoding fields in ONE place.

    Inherit this to get all encoding fields without manual duplication!

    Example:
        class CreateJobRequest(EncodingFieldsMixin, BaseModel):
            # Just add system fields
            input_file: str
            job_name: Optional[str]
            # All encoding fields inherited automatically!
    """

    class Config:
        extra = 'allow'
        populate_by_name = True  # Accept both alias (camelCase) and field name (snake_case)


# ============================================================================
# For OutputConfiguration - subset of fields
# ============================================================================

class OutputEncodingFieldsMixin(
    VideoEncodingMixin,
    AudioEncodingMixin,
    HLSEncodingMixin,
    ABREncodingMixin
):
    """
    Output configuration encoding fields.

    Everything except hardware_accel (which is in job/input tables only).
    """

    class Config:
        extra = 'allow'
        populate_by_name = True  # Accept both alias (camelCase) and field name (snake_case)
