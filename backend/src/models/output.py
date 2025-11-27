"""
Output Configuration Model
Output settings for encoding jobs
"""

from typing import Dict, Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import os

from .rendition import Rendition, RenditionCreate
from .mixins import OutputEncodingFieldsMixin


class OutputType(str, Enum):
    """Output type enumeration"""
    HLS = "hls"
    FILE = "file"
    UDP = "udp"
    RTMP = "rtmp"
    SRT = "srt"


class OutputConfiguration(OutputEncodingFieldsMixin, BaseModel):
    """
    Output settings for encoding job (one-to-one with EncodingJob)

    Inherits ALL encoding fields from OutputEncodingFieldsMixin - ONE source of truth!
    """
    # System fields
    job_id: str = Field(..., description="References parent EncodingJob")

    # Output type and destination
    output_type: OutputType = Field(default=OutputType.HLS, description="Output protocol/type")
    output_url: Optional[str] = Field(None, description="Output URL for UDP/RTMP/SRT")

    # HLS-specific system fields
    base_path: Optional[str] = Field(None, description="Root output directory for HLS")
    variant_paths: Dict[str, str] = Field(default_factory=dict, description="Map of variant to directory for HLS")
    nginx_served: bool = Field(default=True, description="Whether Nginx is serving this output (HLS only)")
    manifest_url: Optional[str] = Field(None, description="URL to master playlist (HLS only)")

    # ABR/Multi-rendition
    renditions: List[Rendition] = Field(
        default_factory=list,
        description="List of renditions for ABR (empty if ABR disabled)"
    )

    # Stream mapping (track selection)
    stream_maps: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Stream mapping configuration for track selection"
    )

    # NOTE: All encoding fields (video_codec, audio_codec, video_bitrate, audio_bitrate, audio_volume,
    # segment_duration, segment_type, playlist_type, crf, keyframe_interval, tune, two_pass, etc.)
    # are inherited from OutputEncodingFieldsMixin - NO DUPLICATION!

    @field_validator("renditions")
    @classmethod
    def validate_renditions(cls, v: List[Rendition]) -> List[Rendition]:
        """
        Validate rendition list for ABR.

        Checks:
        - Minimum 2 renditions when ABR is enabled
        - Maximum 6 renditions
        - No duplicate resolutions
        - Bitrate ordering matches resolution hierarchy

        Args:
            v: List of renditions

        Returns:
            Validated list of renditions

        Raises:
            ValueError: If validation fails
        """
        if not v:
            return v

        # Minimum renditions check
        if len(v) < 2:
            raise ValueError("ABR requires at least 2 renditions")

        # Maximum renditions check
        if len(v) > 6:
            raise ValueError("Maximum 6 renditions supported")

        # Check for duplicate resolutions
        resolutions = [r.video_resolution for r in v]
        if len(resolutions) != len(set(resolutions)):
            raise ValueError("Duplicate resolutions not allowed")

        # Validate bitrate ordering (higher resolution = higher bitrate)
        def resolution_to_pixels(resolution: str) -> int:
            """Convert resolution string to pixel count."""
            width, height = resolution.split('x')
            return int(width) * int(height)

        def bitrate_to_bps(bitrate: str) -> int:
            """Convert bitrate string to bits per second."""
            if bitrate[-1].lower() == 'k':
                return int(float(bitrate[:-1]) * 1000)
            elif bitrate[-1].lower() == 'm':
                return int(float(bitrate[:-1]) * 1000000)
            elif bitrate[-1].lower() == 'g':
                return int(float(bitrate[:-1]) * 1000000000)
            else:
                return int(bitrate)

        sorted_by_resolution = sorted(v, key=lambda r: resolution_to_pixels(r.video_resolution), reverse=True)
        sorted_by_bitrate = sorted(v, key=lambda r: bitrate_to_bps(r.video_bitrate), reverse=True)

        if sorted_by_resolution != sorted_by_bitrate:
            raise ValueError("Bitrate must decrease as resolution decreases")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "base_path": "/output/hls/550e8400-e29b-41d4-a716-446655440000",
                "variant_paths": {
                    "720p": "/output/hls/550e8400-e29b-41d4-a716-446655440000/720p",
                    "480p": "/output/hls/550e8400-e29b-41d4-a716-446655440000/480p",
                    "360p": "/output/hls/550e8400-e29b-41d4-a716-446655440000/360p"
                },
                "nginx_served": True,
                "manifest_url": "http://localhost/hls/550e8400-e29b-41d4-a716-446655440000/master.m3u8"
            }
        }

    def get_variant_path(self, variant_label: str) -> str:
        """Get the full path for a specific variant"""
        if variant_label in self.variant_paths:
            return self.variant_paths[variant_label]
        # Default to subdirectory under base_path
        return os.path.join(self.base_path, variant_label)

    def get_master_playlist_path(self) -> str:
        """Get the path for the master playlist"""
        return os.path.join(self.base_path, "master.m3u8")

    def get_variant_playlist_path(self, variant_label: str) -> str:
        """Get the path for a variant playlist"""
        variant_dir = self.get_variant_path(variant_label)
        return os.path.join(variant_dir, "index.m3u8")

    def get_segment_pattern(self, variant_label: str) -> str:
        """Get the segment filename pattern for FFmpeg"""
        variant_dir = self.get_variant_path(variant_label)
        return os.path.join(variant_dir, "segment_%05d.ts")

    def get_preview_url(self, variant_label: Optional[str] = None) -> Optional[str]:
        """Get the preview URL for the stream"""
        if not self.nginx_served or not self.manifest_url:
            return None

        if variant_label:
            # Return variant-specific playlist
            base_url = self.manifest_url.rsplit('/', 1)[0]
            return f"{base_url}/{variant_label}/index.m3u8"

        # Return master playlist
        return self.manifest_url

    def to_ffmpeg_output_args(self, profile, variants) -> list:
        """Generate FFmpeg output arguments for HLS"""
        args = []

        # Basic HLS format settings
        args.extend(['-f', 'hls'])
        args.extend(['-hls_time', str(profile.segment_duration)])
        args.extend(['-hls_list_size', str(profile.playlist_size)])

        # Segment format
        if profile.segment_format == 'm4s':
            args.extend(['-hls_segment_type', 'fmp4'])
            args.extend(['-hls_fmp4_init_filename', 'init.mp4'])
        else:
            args.extend(['-hls_segment_type', 'mpegts'])

        # Enable segment deletion if configured
        if profile.delete_segments:
            args.extend(['-hls_flags', 'delete_segments+append_list'])
        else:
            args.extend(['-hls_flags', 'append_list'])

        # Add start number
        args.extend(['-start_number', '1'])

        return args


class OutputConfigurationCreate(OutputEncodingFieldsMixin, BaseModel):
    """
    Schema for creating an output configuration

    Inherits ALL encoding fields from OutputEncodingFieldsMixin - ONE source of truth!
    """
    # System fields
    output_type: OutputType = Field(default=OutputType.HLS, description="Output protocol/type")
    output_url: Optional[str] = Field(None, description="Output URL for UDP/RTMP/SRT")

    # HLS-specific system fields
    base_path: Optional[str] = Field(None, description="Root output directory for HLS")
    variant_paths: Optional[Dict[str, str]] = Field(None, description="Map of variant to directory for HLS")
    nginx_served: bool = Field(default=True, description="Whether Nginx is serving this output")

    # ABR configuration
    renditions: Optional[List[RenditionCreate]] = Field(None, description="List of renditions for ABR")

    # Stream mapping
    stream_maps: Optional[List[Dict[str, str]]] = Field(None, description="Stream mapping configuration")

    # NOTE: All encoding fields (video_codec, audio_codec, video_bitrate, audio_bitrate, audio_volume,
    # segment_duration, segment_type, crf, keyframe_interval, etc.) inherited from OutputEncodingFieldsMixin!

    def generate_paths(self, job_id: str) -> 'OutputConfiguration':
        """Generate default paths based on job ID and output type"""
        # Convert RenditionCreate to Rendition objects
        renditions_list = []
        if self.renditions:
            for r in self.renditions:
                renditions_list.append(Rendition(**r.dict()))

        # For HLS output, generate paths
        if self.output_type == OutputType.HLS:
            # Always use job_id for HLS paths to ensure consistency
            base = f"/output/hls/{job_id}"

            # Generate variant paths for ABR renditions
            variant_paths = self.variant_paths or {}
            if self.abr_enabled and renditions_list:
                for rendition in renditions_list:
                    if rendition.name not in variant_paths:
                        variant_paths[rendition.name] = os.path.join(base, rendition.name)

            hls_base_url = os.getenv("HLS_BASE_URL", "http://localhost")
            # Always use master.m3u8
            playlist_name = "master.m3u8"
            manifest_url = f"{hls_base_url}/hls/{job_id}/{playlist_name}" if self.nginx_served else None
        else:
            # For UDP/RTMP/SRT, paths are not used
            base = None
            variant_paths = {}
            manifest_url = None

        # Use dict unpacking to automatically pass ALL encoding fields from mixin
        # This eliminates manual enumeration - new fields work automatically!
        config_dict = self.dict(exclude={'renditions', 'variant_paths'})

        return OutputConfiguration(
            job_id=job_id,
            base_path=base,
            variant_paths=variant_paths,
            manifest_url=manifest_url,
            renditions=renditions_list,
            nginx_served=self.nginx_served if self.output_type == OutputType.HLS else False,
            **config_dict  # Automatically includes ALL encoding fields from mixin!
        )


class OutputConfigurationUpdate(BaseModel):
    """Schema for updating an output configuration"""
    base_path: Optional[str] = Field(None, description="Root output directory")
    variant_paths: Optional[Dict[str, str]] = Field(None, description="Map of variant to directory")
    nginx_served: Optional[bool] = Field(None, description="Whether Nginx is serving this output")
    segment_type: Optional[str] = Field(None, description="HLS segment container: 'mpegts' (TS, universal) or 'fmp4' (fragmented MP4, required for HEVC/AV1)")
    segment_pattern: Optional[str] = Field(None, description="HLS segment filename pattern (e.g., 'segment_%03d.ts', 'chunk_%04d.m4s')")