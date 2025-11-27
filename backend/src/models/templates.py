"""
Pydantic models for encoding templates.

Templates provide predefined configurations for common encoding scenarios,
allowing users to quickly set up jobs without manually configuring every option.
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TemplateId(str, Enum):
    """Template identifiers for predefined encoding configurations"""
    WEB_STREAMING = "web_streaming"
    HIGH_QUALITY = "high_quality_archive"
    LOW_BANDWIDTH = "low_bandwidth_mobile"
    FOUR_K_HDR = "4k_hdr"
    FAST_PREVIEW = "fast_preview"

    @property
    def display_name(self) -> str:
        """Human-readable template name"""
        names = {
            self.WEB_STREAMING: "Standard Web Streaming",
            self.HIGH_QUALITY: "High-Quality Archive",
            self.LOW_BANDWIDTH: "Low-Bandwidth Mobile",
            self.FOUR_K_HDR: "4K HDR",
            self.FAST_PREVIEW: "Fast Preview",
        }
        return names[self]


class Template(BaseModel):
    """
    Encoding template with predefined settings.

    Templates allow users to quickly apply common encoding configurations
    without manually setting each parameter.
    """
    id: TemplateId = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Human-readable template name")
    description: str = Field(..., description="Template description and use case")

    # Encoding settings (matching CreateJobRequest fields)
    video_codec: str = Field(..., description="Video codec")
    audio_codec: str = Field(..., description="Audio codec")
    video_bitrate: Optional[str] = Field(None, description="Video bitrate (e.g., '2500k')")
    audio_bitrate: Optional[str] = Field(None, description="Audio bitrate (e.g., '128k')")
    video_profile: Optional[str] = Field(None, description="Video profile (baseline, main, high)")
    video_framerate: Optional[int] = Field(None, alias="fps", description="Target framerate")
    video_resolution: Optional[str] = Field(None, alias="scale", description="Video scaling (e.g., '1280:720')")
    encoding_preset: Optional[str] = Field(None, alias="preset", description="Encoding preset")
    hardware_accel: Optional[str] = Field(None, description="Hardware acceleration")

    # Use case and metadata
    recommended_use: str = Field(..., description="When to use this template")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")

    class Config:
        use_enum_values = True
        populate_by_name = True  # Accept both alias (fps/scale/preset) and field name
        json_schema_extra = {
            "example": {
                "id": "web_streaming",
                "name": "Standard Web Streaming",
                "description": "Balanced quality and file size for web delivery",
                "video_codec": "libx264",
                "audio_codec": "aac",
                "video_bitrate": "2500k",
                "audio_bitrate": "128k",
                "video_profile": "baseline",
                "fps": 30,
                "preset": "medium",
                "recommended_use": "General web streaming and social media",
                "tags": ["web", "streaming", "balanced"]
            }
        }

    def apply_to_job(self, job_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply template settings to a job request.

        Args:
            job_request: Existing job request data (dict form)

        Returns:
            Updated job request with template settings applied

        Note:
            Only applies settings that are not already explicitly set in job_request.
            User-specified values always take precedence over template values.
        """
        template_settings = {
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "video_bitrate": self.video_bitrate,
            "audio_bitrate": self.audio_bitrate,
            "video_profile": self.video_profile,
            "video_framerate": self.video_framerate,
            "video_resolution": self.video_resolution,
            "encoding_preset": self.encoding_preset,
            "hardware_accel": self.hardware_accel,
        }

        # Apply template settings, but don't override user-specified values
        for key, value in template_settings.items():
            if value is not None and job_request.get(key) is None:
                job_request[key] = value

        # Store template ID for tracking
        job_request["template_id"] = self.id

        return job_request


class TemplateSummary(BaseModel):
    """
    Lightweight template summary for listing templates.

    Used by GET /templates endpoint to avoid sending full template details.
    """
    id: TemplateId = Field(..., description="Template identifier")
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Short description")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    recommended_use: str = Field(..., description="When to use this template")

    class Config:
        use_enum_values = True
