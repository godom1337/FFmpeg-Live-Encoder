"""EncodingProfile model implementation"""

from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import uuid

class EncodingProfileBase(BaseModel):
    """Base encoding profile properties"""
    name: str = Field(..., min_length=1, max_length=50)
    codec: Literal["h264", "h265", "av1"]
    encoder: Literal["cpu", "cuda", "nvenc", "vulkan"]
    audio_codec: Literal["aac", "ac3", "copy"]
    segment_format: Literal["ts", "m4s"]
    segment_duration: int = Field(default=6, ge=1, le=60)
    playlist_size: int = Field(default=10, ge=3, le=100)
    delete_segments: bool = Field(default=True)
    is_default: bool = Field(default=False)

    @field_validator("segment_duration")
    @classmethod
    def validate_segment_duration(cls, v: int) -> int:
        """Validate segment duration is reasonable"""
        if v < 1 or v > 60:
            raise ValueError("Segment duration must be between 1 and 60 seconds")
        return v

    @field_validator("playlist_size")
    @classmethod
    def validate_playlist_size(cls, v: int) -> int:
        """Validate playlist size is reasonable"""
        if v < 3 or v > 100:
            raise ValueError("Playlist size must be between 3 and 100 segments")
        return v

class EncodingProfileCreate(EncodingProfileBase):
    """Properties required to create an encoding profile"""
    pass

class EncodingProfileUpdate(BaseModel):
    """Properties that can be updated on an encoding profile"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    codec: Optional[Literal["h264", "h265", "av1"]] = None
    encoder: Optional[Literal["cpu", "cuda", "nvenc", "vulkan"]] = None
    audio_codec: Optional[Literal["aac", "ac3", "copy"]] = None
    segment_format: Optional[Literal["ts", "m4s"]] = None
    segment_duration: Optional[int] = Field(None, ge=1, le=60)
    playlist_size: Optional[int] = Field(None, ge=3, le=100)
    delete_segments: Optional[bool] = None
    is_default: Optional[bool] = None

class EncodingProfile(EncodingProfileBase):
    """Complete encoding profile with database fields"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    variants: List["BitrateVariant"] = []

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        data = self.model_dump(exclude={"variants"})
        # Convert datetime to string for SQLite
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_db_row(cls, row: dict, variants: List["BitrateVariant"] = None) -> "EncodingProfile":
        """Create from database row"""
        # Parse datetime strings
        if isinstance(row.get("created_at"), str):
            row["created_at"] = datetime.fromisoformat(row["created_at"])
        if isinstance(row.get("updated_at"), str):
            row["updated_at"] = datetime.fromisoformat(row["updated_at"])

        # Create profile instance
        profile = cls(**row)
        if variants:
            profile.variants = variants
        return profile

# Import at bottom to avoid circular dependency
from .variant import BitrateVariant