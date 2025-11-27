"""
Encoding Job Model
Represents a single FFmpeg encoding pipeline instance
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from enum import Enum
from models.mixins import VideoEncodingMixin, AudioEncodingMixin, HardwareAccelMixin


class JobStatus(str, Enum):
    """Encoding job status states"""
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    COMPLETED = "completed"


class EncodingJob(VideoEncodingMixin, AudioEncodingMixin, HardwareAccelMixin, BaseModel):
    """
    Primary entity representing a single FFmpeg encoding pipeline instance.

    Inherits encoding fields from mixins - no manual duplication!
    """
    # System fields
    id: str = Field(default_factory=lambda: str(uuid4()), description="UUID v4 job identifier")
    name: str = Field(..., max_length=100, description="Human-readable job name")
    profile_id: Optional[str] = Field(None, description="References the encoding profile template used")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current job state")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="When FFmpeg process launched")
    stopped_at: Optional[datetime] = Field(None, description="When process terminated")
    pid: Optional[int] = Field(None, description="System process ID when running")
    error_message: Optional[str] = Field(None, description="Captured FFmpeg stderr on failure")
    command: Optional[str] = Field(None, description="Full FFmpeg command for debugging")
    priority: int = Field(default=5, ge=1, le=10, description="Execution priority (1-10, higher = more important)")
    archive_on_complete: bool = Field(default=False, description="Automatically archive job when completed")
    template_id: Optional[str] = Field(None, description="Template ID used to create this job")
    custom_args: Optional[str] = Field(None, description="Custom FFmpeg arguments (JSON serialized list)")

    # Multi-output configuration (User Story 3) - stored as JSON strings
    hls_output_config: Optional[str] = Field(None, description="HLS output configuration (JSON serialized HLSOutput)")
    udp_outputs_config: Optional[str] = Field(None, description="UDP outputs configuration (JSON serialized list of UDPOutput)")
    additional_outputs_config: Optional[str] = Field(None, description="Additional file outputs (JSON serialized list of FileOutput)")

    # NOTE: All encoding fields (video_codec, audio_codec, video_bitrate, audio_bitrate, audio_volume, etc.)
    # are inherited from VideoEncodingMixin, AudioEncodingMixin, and HardwareAccelMixin!

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Main Stream",
                "profile_id": "550e8400-e29b-41d4-a716-446655440001",
                "status": "running",
                "created_at": "2025-01-15T10:30:00",
                "started_at": "2025-01-15T10:31:00",
                "stopped_at": None,
                "pid": 12345,
                "error_message": None,
                "command": "ffmpeg -i udp://239.1.1.1:5000 ...",
                "priority": 5
            }
        }

    def can_start(self) -> bool:
        """Check if job can be started"""
        return self.status in [JobStatus.PENDING, JobStatus.STOPPED, JobStatus.ERROR, JobStatus.COMPLETED]

    def can_stop(self) -> bool:
        """Check if job can be stopped"""
        return self.status == JobStatus.RUNNING

    def can_edit(self) -> bool:
        """Check if job configuration can be edited"""
        return self.status != JobStatus.RUNNING

    def can_delete(self) -> bool:
        """Check if job can be deleted"""
        return self.status != JobStatus.RUNNING


class EncodingJobCreate(BaseModel):
    """Schema for creating a new encoding job"""
    name: str = Field(..., max_length=100, description="Human-readable job name")
    profile_id: Optional[str] = Field(None, description="Encoding profile to use")
    priority: int = Field(default=5, ge=1, le=10, description="Execution priority")
    archive_on_complete: bool = Field(default=False, description="Automatically archive job when completed")


class EncodingJobUpdate(BaseModel):
    """Schema for updating an encoding job"""
    name: Optional[str] = Field(None, max_length=100, description="Human-readable job name")
    profile_id: Optional[str] = Field(None, description="Encoding profile to use")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Execution priority")