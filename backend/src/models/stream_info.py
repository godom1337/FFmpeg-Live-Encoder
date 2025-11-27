"""
Stream information models for input analysis.

These models represent the detailed information about media streams
extracted from ffprobe analysis of input sources.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class StreamType(str, Enum):
    """Types of media streams."""
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    DATA = "data"


class VideoStreamInfo(BaseModel):
    """Information about a video stream."""

    index: int = Field(..., description="Stream index in the input file")
    codec_name: str = Field(..., description="Codec name (e.g., h264, hevc, vp9)")
    codec_long_name: Optional[str] = Field(None, description="Full codec name")
    profile: Optional[str] = Field(None, description="Codec profile (e.g., High, Main, Baseline)")
    width: int = Field(..., description="Video width in pixels")
    height: int = Field(..., description="Video height in pixels")
    resolution: str = Field(..., description="Resolution string (e.g., 1920x1080)")
    fps: Optional[float] = Field(None, description="Frames per second")
    bit_rate: Optional[str] = Field(None, description="Bit rate (e.g., 5000000 or '5000k')")
    pix_fmt: Optional[str] = Field(None, description="Pixel format (e.g., yuv420p)")
    color_space: Optional[str] = Field(None, description="Color space")
    color_range: Optional[str] = Field(None, description="Color range (tv/pc)")
    duration: Optional[float] = Field(None, description="Stream duration in seconds")
    nb_frames: Optional[int] = Field(None, description="Total number of frames")

    class Config:
        json_schema_extra = {
            "example": {
                "index": 0,
                "codec_name": "h264",
                "codec_long_name": "H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10",
                "profile": "High",
                "width": 1920,
                "height": 1080,
                "resolution": "1920x1080",
                "fps": 30.0,
                "bit_rate": "5000000",
                "pix_fmt": "yuv420p",
                "duration": 600.5
            }
        }


class AudioStreamInfo(BaseModel):
    """Information about an audio stream."""

    index: int = Field(..., description="Global stream index in the input file (e.g., 0, 1, 2)")
    audio_index: int = Field(..., description="Audio-only stream index for FFmpeg mapping (0:a:N)")
    codec_name: str = Field(..., description="Codec name (e.g., aac, mp3, opus)")
    codec_long_name: Optional[str] = Field(None, description="Full codec name")
    sample_rate: int = Field(..., description="Sample rate in Hz (e.g., 48000)")
    channels: int = Field(..., description="Number of audio channels")
    channel_layout: Optional[str] = Field(None, description="Channel layout (e.g., stereo, 5.1)")
    bit_rate: Optional[str] = Field(None, description="Bit rate (e.g., 128000 or '128k')")
    duration: Optional[float] = Field(None, description="Stream duration in seconds")
    language: Optional[str] = Field(None, description="Language code (e.g., eng, fre)")
    title: Optional[str] = Field(None, description="Track title/description")

    class Config:
        json_schema_extra = {
            "example": {
                "index": 1,
                "codec_name": "aac",
                "codec_long_name": "AAC (Advanced Audio Coding)",
                "sample_rate": 48000,
                "channels": 2,
                "channel_layout": "stereo",
                "bit_rate": "128000",
                "duration": 600.5
            }
        }


class SubtitleStreamInfo(BaseModel):
    """Information about a subtitle stream."""

    index: int = Field(..., description="Stream index in the input file")
    codec_name: str = Field(..., description="Codec name (e.g., subrip, ass, webvtt)")
    codec_long_name: Optional[str] = Field(None, description="Full codec name")
    language: Optional[str] = Field(None, description="Language code (e.g., eng, spa)")
    title: Optional[str] = Field(None, description="Subtitle track title")

    class Config:
        json_schema_extra = {
            "example": {
                "index": 2,
                "codec_name": "subrip",
                "codec_long_name": "SubRip subtitle",
                "language": "eng",
                "title": "English"
            }
        }


class InputAnalysisResult(BaseModel):
    """Complete analysis result from ffprobe."""

    url: str = Field(..., description="Input URL/path that was analyzed")
    format_name: Optional[str] = Field(None, description="Container format (e.g., mov,mp4,m4a)")
    format_long_name: Optional[str] = Field(None, description="Full format name")
    duration: Optional[float] = Field(None, description="Total duration in seconds")
    size: Optional[int] = Field(None, description="File size in bytes (for file inputs)")
    bit_rate: Optional[str] = Field(None, description="Overall bit rate")

    video_streams: List[VideoStreamInfo] = Field(
        default_factory=list,
        description="List of video streams found"
    )
    audio_streams: List[AudioStreamInfo] = Field(
        default_factory=list,
        description="List of audio streams found"
    )
    subtitle_streams: List[SubtitleStreamInfo] = Field(
        default_factory=list,
        description="List of subtitle streams found"
    )

    error: Optional[str] = Field(None, description="Error message if analysis failed")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "udp://239.255.0.1:5000",
                "format_name": "mpegts",
                "format_long_name": "MPEG-TS (MPEG-2 Transport Stream)",
                "duration": 600.5,
                "bit_rate": "6000000",
                "video_streams": [
                    {
                        "index": 0,
                        "codec_name": "h264",
                        "profile": "High",
                        "width": 1920,
                        "height": 1080,
                        "resolution": "1920x1080",
                        "fps": 30.0,
                        "bit_rate": "5000000"
                    }
                ],
                "audio_streams": [
                    {
                        "index": 1,
                        "codec_name": "aac",
                        "sample_rate": 48000,
                        "channels": 2,
                        "channel_layout": "stereo",
                        "bit_rate": "128000"
                    }
                ]
            }
        }


class AnalyzeInputRequest(BaseModel):
    """Request model for input analysis."""

    url: str = Field(..., description="Input URL/path to analyze")
    type: Optional[str] = Field(None, description="Input type hint (udp, http, file)")
    timeout: int = Field(10, ge=1, le=60, description="Analysis timeout in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "udp://239.255.0.1:5000",
                "type": "udp",
                "timeout": 10
            }
        }
