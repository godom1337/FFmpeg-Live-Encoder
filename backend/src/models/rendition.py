"""
Rendition Model for Multi-Track ABR Support

Defines individual rendition (quality variant) configuration for
Adaptive Bit Rate (ABR) streaming.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class Rendition(BaseModel):
    """
    Configuration for a single rendition/variant in ABR streaming.

    Each rendition represents a different quality level with specific
    encoding parameters (bitrate, resolution, framerate, etc.).
    """

    name: str = Field(..., description="Rendition name/label (e.g., '1080p', '720p', '480p')")

    # Video settings
    video_bitrate: str = Field(..., description="Video bitrate (e.g., '5M', '3000k')")
    video_resolution: str = Field(..., description="Video resolution (e.g., '1920x1080', '1280x720')")
    video_framerate: Optional[int] = Field(None, description="Video framerate in fps")
    video_codec: Optional[str] = Field(default="h264", description="Video codec (h264, h265, av1)")
    video_profile: Optional[str] = Field(None, description="Video profile (baseline, main, high)")

    # Audio settings (typically same across all renditions)
    audio_codec: Optional[str] = Field(default="aac", description="Audio codec")
    audio_bitrate: Optional[str] = Field(default="128k", description="Audio bitrate")
    audio_channels: Optional[int] = Field(default=2, description="Number of audio channels")
    audio_sample_rate: Optional[int] = Field(default=48000, description="Audio sample rate in Hz")
    audio_volume: Optional[int] = Field(None, ge=0, le=100, description="Audio volume percentage (0-100, where 100 is original)")

    # Optional settings
    max_bitrate: Optional[str] = Field(None, description="Maximum bitrate for rate control")
    buffer_size: Optional[str] = Field(None, description="Buffer size for rate control")
    preset: Optional[str] = Field(default="medium", description="Encoding preset (ultrafast, fast, medium, slow)")
    output_url: Optional[str] = Field(None, description="Output URL for UDP/RTMP/SRT (e.g., udp://224.1.1.1:5001)")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate rendition name."""
        if not v or not v.strip():
            raise ValueError("Rendition name cannot be empty")
        # Remove invalid filesystem characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"Rendition name cannot contain '{char}'")
        return v.strip()

    @field_validator("video_bitrate", "audio_bitrate", "max_bitrate", "buffer_size")
    @classmethod
    def validate_bitrate(cls, v: Optional[str]) -> Optional[str]:
        """Validate bitrate format."""
        if v is None:
            return v

        # Check if it ends with valid suffix
        valid_suffixes = ['k', 'K', 'm', 'M', 'g', 'G']
        if not any(v.endswith(suffix) for suffix in valid_suffixes):
            # Check if it's a plain number (bits per second)
            try:
                int(v)
                return v
            except ValueError:
                raise ValueError(f"Bitrate must end with k/K/m/M/g/G or be a number: {v}")

        # Extract number part and validate
        number_part = v[:-1]
        try:
            float(number_part)
        except ValueError:
            raise ValueError(f"Invalid bitrate format: {v}")

        return v

    @field_validator("video_resolution")
    @classmethod
    def validate_resolution(cls, v: str) -> str:
        """Validate resolution format (WIDTHxHEIGHT)."""
        if 'x' not in v:
            raise ValueError(f"Resolution must be in format WIDTHxHEIGHT: {v}")

        parts = v.split('x')
        if len(parts) != 2:
            raise ValueError(f"Resolution must be in format WIDTHxHEIGHT: {v}")

        try:
            width = int(parts[0])
            height = int(parts[1])

            if width <= 0 or height <= 0:
                raise ValueError(f"Resolution dimensions must be positive: {v}")

            # Sanity check for reasonable values
            if width > 7680 or height > 4320:  # 8K max
                raise ValueError(f"Resolution exceeds maximum (7680x4320): {v}")

        except ValueError as e:
            raise ValueError(f"Invalid resolution format: {v}") from e

        return v

    @classmethod
    def from_preset(cls, preset_name: str) -> "Rendition":
        """
        Create a Rendition from a preset definition.

        Args:
            preset_name: Name of the preset (e.g., "1080p", "720p", "480p")

        Returns:
            Rendition instance configured with preset values

        Raises:
            ValueError: If preset_name is not found
        """
        presets = cls.get_presets()
        if preset_name not in presets:
            available = ", ".join(presets.keys())
            raise ValueError(f"Unknown preset: {preset_name}. Available: {available}")

        return cls(**presets[preset_name])

    @classmethod
    def get_presets(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get all available rendition presets.

        Returns:
            Dictionary mapping preset names to their configuration dicts
        """
        return {
            "1080p": {
                "name": "1080p",
                "video_bitrate": "5M",
                "video_resolution": "1920x1080",
                "video_codec": "h264",
                "video_profile": "high",
                "audio_codec": "aac",
                "audio_bitrate": "128k",
                "audio_channels": 2,
                "audio_sample_rate": 48000,
                "preset": "medium"
            },
            "720p": {
                "name": "720p",
                "video_bitrate": "3M",
                "video_resolution": "1280x720",
                "video_codec": "h264",
                "video_profile": "main",
                "audio_codec": "aac",
                "audio_bitrate": "128k",
                "audio_channels": 2,
                "audio_sample_rate": 48000,
                "preset": "medium"
            },
            "540p": {
                "name": "540p",
                "video_bitrate": "2M",
                "video_resolution": "960x540",
                "video_codec": "h264",
                "video_profile": "main",
                "audio_codec": "aac",
                "audio_bitrate": "128k",
                "audio_channels": 2,
                "audio_sample_rate": 48000,
                "preset": "medium"
            },
            "480p": {
                "name": "480p",
                "video_bitrate": "1.5M",
                "video_resolution": "854x480",
                "video_codec": "h264",
                "video_profile": "main",
                "audio_codec": "aac",
                "audio_bitrate": "96k",
                "audio_channels": 2,
                "audio_sample_rate": 48000,
                "preset": "medium"
            },
            "360p": {
                "name": "360p",
                "video_bitrate": "800k",
                "video_resolution": "640x360",
                "video_codec": "h264",
                "video_profile": "baseline",
                "audio_codec": "aac",
                "audio_bitrate": "64k",
                "audio_channels": 2,
                "audio_sample_rate": 48000,
                "preset": "fast"
            },
            "240p": {
                "name": "240p",
                "video_bitrate": "400k",
                "video_resolution": "426x240",
                "video_codec": "h264",
                "video_profile": "baseline",
                "audio_codec": "aac",
                "audio_bitrate": "64k",
                "audio_channels": 2,
                "audio_sample_rate": 48000,
                "preset": "fast"
            }
        }

    class Config:
        json_schema_extra = {
            "example": {
                "name": "1080p",
                "video_bitrate": "5M",
                "video_resolution": "1920x1080",
                "video_framerate": 30,
                "video_codec": "h264",
                "video_profile": "high",
                "audio_codec": "aac",
                "audio_bitrate": "128k",
                "audio_channels": 2,
                "audio_sample_rate": 48000,
                "preset": "medium"
            }
        }


class RenditionCreate(BaseModel):
    """Schema for creating a rendition (used in API requests)."""

    name: str = Field(..., description="Rendition name/label")
    video_bitrate: str = Field(..., description="Video bitrate")
    video_resolution: str = Field(..., description="Video resolution")
    video_framerate: Optional[int] = Field(None, description="Video framerate in fps")
    video_codec: Optional[str] = Field(default="h264", description="Video codec (h264, h265, av1)")
    video_profile: Optional[str] = Field(None, description="Video profile")
    audio_codec: Optional[str] = Field(default="aac", description="Audio codec")
    audio_bitrate: Optional[str] = Field(default="128k", description="Audio bitrate")
    audio_channels: Optional[int] = Field(default=2, description="Audio channels")
    audio_sample_rate: Optional[int] = Field(default=48000, description="Audio sample rate")
    audio_volume: Optional[int] = Field(None, ge=0, le=100, description="Audio volume percentage (0-100, where 100 is original)")
    max_bitrate: Optional[str] = Field(None, description="Maximum bitrate")
    buffer_size: Optional[str] = Field(None, description="Buffer size")
    preset: Optional[str] = Field(default="medium", description="Encoding preset")
    output_url: Optional[str] = Field(None, description="Output URL for UDP/RTMP/SRT")


# Common rendition presets for quick configuration
RENDITION_PRESETS = {
    "1080p_high": Rendition(
        name="1080p",
        video_bitrate="5M",
        video_resolution="1920x1080",
        video_framerate=30,
        video_profile="high",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="medium"
    ),
    "720p_medium": Rendition(
        name="720p",
        video_bitrate="3M",
        video_resolution="1280x720",
        video_framerate=30,
        video_profile="main",
        audio_codec="aac",
        audio_bitrate="128k",
        preset="medium"
    ),
    "480p_low": Rendition(
        name="480p",
        video_bitrate="1.5M",
        video_resolution="854x480",
        video_framerate=30,
        video_profile="main",
        audio_codec="aac",
        audio_bitrate="96k",
        preset="fast"
    ),
    "360p_mobile": Rendition(
        name="360p",
        video_bitrate="800k",
        video_resolution="640x360",
        video_framerate=30,
        video_profile="baseline",
        audio_codec="aac",
        audio_bitrate="64k",
        preset="fast"
    ),
}


def get_preset_rendition(preset_name: str) -> Optional[Rendition]:
    """
    Get a rendition from presets.

    Args:
        preset_name: Name of the preset

    Returns:
        Rendition if found, None otherwise
    """
    return RENDITION_PRESETS.get(preset_name)


def get_available_presets() -> dict:
    """
    Get all available rendition presets.

    Returns:
        Dictionary of preset names to Rendition objects
    """
    return RENDITION_PRESETS.copy()


class ABRLadderPreset(BaseModel):
    """
    Named collection of renditions for ABR bitrate ladder configuration.

    Provides quick-start configurations optimized for different use cases.
    """

    name: str = Field(..., description="Preset name (e.g., 'Standard', 'High Quality')")
    description: str = Field(..., description="Human-readable description of the preset")
    rendition_names: List[str] = Field(..., description="List of rendition preset names to include")

    @classmethod
    def get_standard_presets(cls) -> Dict[str, "ABRLadderPreset"]:
        """
        Get all standard ABR ladder presets.

        Returns:
            Dictionary mapping preset keys to ABRLadderPreset instances
        """
        return {
            "standard": cls(
                name="Standard",
                description="General purpose: 1080p, 720p, 480p",
                rendition_names=["1080p", "720p", "480p"]
            ),
            "high_quality": cls(
                name="High Quality",
                description="Premium content: 1080p, 720p, 540p, 360p",
                rendition_names=["1080p", "720p", "540p", "360p"]
            ),
            "mobile_optimized": cls(
                name="Mobile Optimized",
                description="Low bandwidth: 720p, 480p, 360p, 240p",
                rendition_names=["720p", "480p", "360p", "240p"]
            )
        }

    def get_renditions(self) -> List[Rendition]:
        """
        Get the list of Rendition instances for this preset.

        Returns:
            List of Rendition instances

        Raises:
            ValueError: If any rendition name is invalid
        """
        renditions = []
        for name in self.rendition_names:
            try:
                rendition = Rendition.from_preset(name)
                renditions.append(rendition)
            except ValueError as e:
                raise ValueError(f"Invalid rendition '{name}' in ladder preset '{self.name}': {e}") from e

        return renditions
