"""
Pydantic models for FFmpeg encoding settings.

This module defines all data models used for job creation, including
codec enumerations, output configurations, and request/response models.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re
from models.mixins import EncodingFieldsMixin
from models.rendition import RenditionCreate


class VideoCodec(str, Enum):
    """Supported video codecs"""
    LIBX264 = "libx264"      # H.264 (most compatible)
    LIBX265 = "libx265"      # H.265/HEVC (better compression)

    AV1 = "libaom-av1"       # AV1 (future codec, best compression)

    @property
    def display_name(self) -> str:
        """Human-readable name"""
        names = {
            self.LIBX264: "H.264 (AVC)",
            self.LIBX265: "H.265 (HEVC)",

            self.AV1: "AV1",
        }
        return names[self]

    @property
    def compatible_hwaccels(self) -> List[str]:
        """Hardware acceleration options compatible with this codec"""
        compat = {
            self.LIBX264: ["none", "nvenc", "vaapi", "videotoolbox"],
            self.LIBX265: ["none", "nvenc", "vaapi", "videotoolbox"],
            # Note: VideoToolbox does not support AV1 encoding
            self.AV1: ["none", "nvenc", "vaapi"],
        }
        return compat[self]


class AudioCodec(str, Enum):
    """Supported audio codecs"""
    COPY = "copy"           # Copy audio stream (no re-encoding)
    AAC = "aac"             # AAC (most compatible)
    OPUS = "libopus"        # Opus (best quality/bitrate)
    MP3 = "libmp3lame"      # MP3 (legacy compatibility)

    @property
    def display_name(self) -> str:
        """Human-readable name"""
        names = {
            self.COPY: "Copy (no re-encode)",
            self.AAC: "AAC",
            self.OPUS: "Opus",
            self.MP3: "MP3",
        }
        return names[self]


class CreateJobRequest(EncodingFieldsMixin, BaseModel):
    """
    Request body for POST /jobs/create

    Inherits ALL encoding fields from EncodingFieldsMixin.
    Only system/control fields are defined here.
    """

    # Required fields
    input_file: str = Field(
        ...,
        description="Input source: file path (/input/*, /data/*) or network URL (http://, udp://, rtsp://, rtmp://, srt://, rtp://, tcp://)"
    )

    # Job metadata
    job_name: Optional[str] = Field(None, description="Human-readable job name", max_length=100)

    # Optional output (auto-generated if not provided)
    output_file: Optional[str] = Field(None, description="Absolute path to output file")

    # Input options
    loop_input: bool = Field(default=False, description="Loop input file continuously (for live streaming)")
    input_format: Optional[str] = Field(None, description="Input format (e.g., avfoundation, v4l2, dshow)")
    input_args: List[str] = Field(default_factory=list, description="Additional input arguments")

    # Codec enums with defaults
    video_codec: VideoCodec = Field(default=VideoCodec.LIBX264, description="Video codec")
    audio_codec: AudioCodec = Field(default=AudioCodec.COPY, description="Audio codec")

    # Multi-output settings (User Story 3)
    hls_output: Optional['HLSOutput'] = Field(None, description="HLS streaming output configuration")
    udp_outputs: List['UDPOutput'] = Field(default_factory=list, description="UDP streaming outputs")
    rtmp_outputs: List['RTMPOutput'] = Field(default_factory=list, description="RTMP streaming outputs")
    additional_outputs: List['FileOutput'] = Field(default_factory=list, description="Additional file outputs")

    # ABR settings (can be used with HLS, UDP, or File outputs)
    abr_enabled: bool = Field(default=False, description="Enable Adaptive Bitrate for multi-quality outputs")
    abr_renditions: Optional[List['RenditionCreate']] = Field(default=None, description="ABR quality variants")

    # Stream mapping settings (User Story 7)
    stream_maps: List['StreamMap'] = Field(
        default_factory=list,
        description="Stream mapping configuration for selecting specific tracks from multi-track input"
    )

    # NOTE: All encoding fields (video_bitrate, audio_bitrate, audio_volume, video_framerate, encoding_preset, crf, etc.)
    # are inherited from EncodingFieldsMixin - no need to duplicate them here!

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "input_file": "/input/video.mp4",
                "output_file": "/output/output.mp4",
                "video_codec": "libx264",
                "audio_codec": "copy",
                "video_bitrate": "2500k",
                "video_framerate": 30,
                "audio_bitrate": "128k"
            }
        }


class CreateJobResponse(BaseModel):
    """Response from POST /jobs/create"""
    job_id: int = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status (pending, running, completed, failed)")
    command: str = Field(..., description="Generated FFmpeg command")
    created_at: datetime = Field(..., description="Job creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": 123,
                "status": "pending",
                "command": "ffmpeg -i /input/video.mp4 -c:v libx264 -c:a copy /output/output.mp4",
                "created_at": "2025-10-20T10:00:00Z"
            }
        }


# ============================================================================
# Validation Models (User Story 6)
# ============================================================================


class ValidationWarning(BaseModel):
    """Single validation warning"""
    code: str = Field(..., description="Warning code (e.g., 'hwaccel_unavailable')")
    message: str = Field(..., description="Human-readable warning message")
    severity: str = Field(..., description="error, warning, info")


class ValidateJobRequest(EncodingFieldsMixin, BaseModel):
    """
    Request body for POST /jobs/validate

    Inherits ALL encoding fields from EncodingFieldsMixin.
    Same fields as CreateJobRequest.
    """
    input_file: str = Field(..., description="Absolute path to input file")
    job_name: Optional[str] = Field(None, max_length=100)
    output_file: Optional[str] = Field(None, description="Absolute path to output file")
    loop_input: bool = Field(default=False, description="Loop input file")
    input_format: Optional[str] = Field(None, description="Input format (e.g., avfoundation, v4l2, dshow)")
    input_args: List[str] = Field(default_factory=list, description="Additional input arguments")
    video_codec: VideoCodec = Field(default=VideoCodec.LIBX264, description="Video codec")
    audio_codec: AudioCodec = Field(default=AudioCodec.COPY, description="Audio codec")

    # Multi-output settings
    hls_output: Optional['HLSOutput'] = None
    udp_outputs: List['UDPOutput'] = Field(default_factory=list)
    rtmp_outputs: List['RTMPOutput'] = Field(default_factory=list)
    additional_outputs: List['FileOutput'] = Field(default_factory=list)

    # Stream mapping settings
    stream_maps: List['StreamMap'] = Field(default_factory=list)

    # ABR settings (top-level, applies to all output types)
    abr_enabled: bool = Field(default=False, description="Enable ABR (Adaptive Bitrate)")
    abr_renditions: List[Dict[str, Any]] = Field(default_factory=list, description="ABR renditions configuration")

    # NOTE: All encoding fields inherited from EncodingFieldsMixin!

    class Config:
        use_enum_values = True


class ValidateJobResponse(BaseModel):
    """Response from POST /jobs/validate"""
    valid: bool = Field(..., description="Whether the job configuration is valid")
    warnings: List[ValidationWarning] = Field(default_factory=list, description="Validation warnings")
    command: str = Field(..., description="Generated FFmpeg command")
    estimated_duration: Optional[float] = Field(None, description="Estimated encoding time in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "valid": True,
                "warnings": [
                    {
                        "code": "hwaccel_unavailable",
                        "message": "Hardware acceleration 'nvenc' not available, will use software encoding",
                        "severity": "warning"
                    }
                ],
                "command": "ffmpeg -i /input/video.mp4 -c:v libx264 -c:a copy /output/output.mp4",
                "estimated_duration": 120.5
            }
        }


# ============================================================================
# Metadata Models (User Story 6)
# ============================================================================


class TrackInfo(BaseModel):
    """Information about a media track"""
    index: int = Field(..., description="Stream index")
    type: str = Field(..., description="Track type: video, audio, subtitle")
    codec: str = Field(..., description="Codec name")
    language: Optional[str] = Field(default="unknown", description="Language code")

    # Video-specific fields
    width: Optional[int] = Field(None, description="Video width in pixels")
    height: Optional[int] = Field(None, description="Video height in pixels")
    fps: Optional[float] = Field(None, description="Frames per second")

    # Audio-specific fields
    channels: Optional[int] = Field(None, description="Number of audio channels")
    sample_rate: Optional[int] = Field(None, description="Audio sample rate")
    bitrate: Optional[str] = Field(None, description="Track bitrate")


class InputFileMetadata(BaseModel):
    """Metadata extracted from input file via FFprobe"""
    file_path: str = Field(..., description="Path to input file")
    duration: Optional[float] = Field(None, description="Duration in seconds")
    format: Optional[str] = Field(None, description="Container format")
    size: Optional[int] = Field(None, description="File size in bytes")
    bitrate: Optional[str] = Field(None, description="Overall bitrate")
    tracks: List[TrackInfo] = Field(default_factory=list, description="List of tracks")
    probed_at: datetime = Field(default_factory=datetime.utcnow, description="When file was probed")


# ============================================================================
# Stream Mapping Models (User Story 7)
# ============================================================================


class StreamMap(BaseModel):
    """
    Stream mapping configuration for selecting specific tracks.

    Uses FFmpeg stream specifier syntax:
    - 0:v:0 = first video stream from input 0
    - 0:a:1 = second audio stream from input 0
    - 0:s:0 = first subtitle stream from input 0
    - 0:v = all video streams from input 0
    - 0:2 = stream index 2 from input 0
    """
    input_stream: str = Field(
        ...,
        description="FFmpeg stream specifier (e.g., '0:v:0', '0:a:1', '0:s:0')"
    )
    output_label: str = Field(
        ...,
        description="Output label: 'v' (video), 'a' (audio), 's' (subtitle), or numeric index"
    )

    @validator('input_stream')
    def validate_stream_specifier(cls, v):
        """
        Validate FFmpeg stream specifier format.

        Valid formats:
        - 0:v:0 (input:type:index)
        - 0:v (input:type)
        - 0:2 (input:index)

        Rejects:
        - Empty strings
        - Special characters (injection prevention)
        - Negative indices
        - Invalid separators
        """
        if not v or not isinstance(v, str):
            raise ValueError("Invalid FFmpeg stream specifier: empty or not a string")

        # Check for dangerous characters (command injection prevention)
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in v for char in dangerous_chars):
            raise ValueError(f"Invalid FFmpeg stream specifier: contains dangerous characters")

        # Valid patterns:
        # - 0:v:0 (input:type:index)
        # - 0:v (input:type)
        # - 0:2 (input:index)
        # - 0:v (input:all-of-type)
        pattern = r'^(\d+):([vasi]|\d+)(:\d+)?$'
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid FFmpeg stream specifier format: '{v}'. "
                "Expected format: '0:v:0', '0:a:1', '0:s:0', '0:2', or '0:v'"
            )

        # Reject negative indices
        if '-' in v:
            raise ValueError("Invalid FFmpeg stream specifier: negative indices not allowed")

        return v

    @validator('output_label')
    def validate_output_label(cls, v):
        """
        Validate output label.

        Valid: 'v', 'a', 's', or numeric indices '0', '1', etc.
        """
        if not v or not isinstance(v, str):
            raise ValueError("Output label must be a non-empty string")

        # Allow single letter types or numeric indices
        if not re.match(r'^[vas\d]+$', v):
            raise ValueError(
                f"Invalid output label: '{v}'. "
                "Expected: 'v' (video), 'a' (audio), 's' (subtitle), or numeric index"
            )

        return v


# ============================================================================
# Multi-Output Models (User Story 3)
# ============================================================================


class HLSOutput(BaseModel):
    """HLS output configuration"""
    output_dir: str = Field(..., alias="outputDir", description="Directory for HLS segments and playlist")
    playlist_name: str = Field(default="master.m3u8", alias="playlistName", description="Master playlist filename")
    segment_duration: int = Field(default=6, alias="segmentDuration", ge=1, le=60, description="Segment duration in seconds")
    segment_pattern: str = Field(default="segment_%03d.ts", alias="segmentPattern", description="Segment filename pattern")
    playlist_type: str = Field(default="live", alias="playlistType", description="Playlist type: 'vod' for on-demand, 'event' or 'live' for streaming")
    playlist_size: int = Field(default=5, alias="playlistSize", ge=1, le=20, description="Number of segments in live playlist (rolling window)")
    segment_type: str = Field(default="mpegts", alias="segmentType", description="Segment container: 'mpegts' (TS, universal) or 'fmp4' (fragmented MP4, required for HEVC/AV1)")

    # ABR configuration
    abr_enabled: bool = Field(default=False, alias="abrEnabled", description="Enable Adaptive Bitrate streaming")
    renditions: Optional[List['RenditionCreate']] = Field(default=None, description="List of quality variants for ABR")

    class Config:
        populate_by_name = True  # Accept both camelCase and snake_case

    @validator('output_dir')
    def validate_output_dir(cls, v):
        """Resolve and return the output directory path"""
        from pathlib import Path
        return str(Path(v).resolve())


class UDPOutput(BaseModel):
    """UDP streaming output configuration"""
    address: str = Field(..., description="Destination IP address")
    port: int = Field(..., ge=1024, le=65535, description="Destination port")
    ttl: int = Field(default=16, ge=1, le=255, description="Time-to-live for multicast")
    pkt_size: int = Field(default=1316, ge=188, le=65507, alias="pktSize", description="UDP packet size (default 1316 for MPEG-TS)")

    class Config:
        populate_by_name = True  # Accept both camelCase and snake_case

    @validator('address')
    def validate_address(cls, v):
        """Validate IP address format"""
        # Basic IP validation (IPv4)
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(pattern, v):
            raise ValueError("Invalid IP address format")

        # Validate octets
        octets = v.split('.')
        if any(int(o) > 255 for o in octets):
            raise ValueError("Invalid IP address (octet > 255)")

        return v

    @property
    def url(self) -> str:
        """Generate UDP URL for FFmpeg with multicast parameters"""
        return f"udp://{self.address}:{self.port}?ttl={self.ttl}&pkt_size={self.pkt_size}"


class RTMPOutput(BaseModel):
    """RTMP streaming output configuration (e.g., YouTube, Twitch)"""
    url: str = Field(..., description="RTMP URL (e.g., rtmp://a.rtmp.youtube.com/live2)")
    stream_key: str = Field(..., alias="streamKey", description="Stream key")

    class Config:
        populate_by_name = True  # Accept both camelCase and snake_case

    @property
    def full_url(self) -> str:
        """Generate full RTMP URL including stream key"""
        # Handle cases where stream key is already part of the URL
        if self.stream_key in self.url:
            return self.url
        
        # Ensure URL ends with slash if needed
        base_url = self.url
        if not base_url.endswith('/'):
            base_url += '/'
            
        return f"{base_url}{self.stream_key}"


class FileOutput(BaseModel):
    """Additional file output configuration"""
    output_file: str = Field(..., alias="outputFile", description="Output file path")
    video_codec: Optional[str] = Field(None, alias="videoCodec", description="Override video codec for this output")
    audio_codec: Optional[str] = Field(None, alias="audioCodec", description="Override audio codec for this output")
    video_bitrate: Optional[str] = Field(None, alias="videoBitrate")
    audio_bitrate: Optional[str] = Field(None, alias="audioBitrate")
    scale: Optional[str] = None

    class Config:
        populate_by_name = True  # Accept both camelCase and snake_case

    @validator('output_file')
    def validate_output_file(cls, v):
        """Ensure output file is in allowed directory"""
        from pathlib import Path
        p = Path(v).resolve()
        allowed = [Path("/output").resolve()]
        if not any(str(p).startswith(str(d)) for d in allowed):
            raise ValueError("Output file must be in /output directory")
        return str(p)
