"""BitrateVariant model implementation"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
import uuid
import re

class BitrateVariantBase(BaseModel):
    """Base bitrate variant properties"""
    label: str = Field(..., min_length=1, max_length=20)
    width: int = Field(..., gt=0, le=7680)  # Up to 8K
    height: int = Field(..., gt=0, le=4320)  # Up to 8K
    video_bitrate: str = Field(...)  # e.g., "5M", "2500k"
    max_rate: str = Field(...)
    buffer_size: str = Field(...)
    order_index: int = Field(default=0, ge=0)

    @field_validator("video_bitrate", "max_rate", "buffer_size")
    @classmethod
    def validate_bitrate_format(cls, v: str) -> str:
        """Validate bitrate format (e.g., 5M, 2500k)"""
        pattern = r"^\d+(\.\d+)?[kKmM]$"
        if not re.match(pattern, v):
            raise ValueError(f"Invalid bitrate format: {v}. Use format like '5M' or '2500k'")
        return v

    @field_validator("width", "height")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        """Validate resolution is positive and reasonable"""
        if v <= 0:
            raise ValueError("Resolution must be positive")
        if v > 7680:  # 8K max
            raise ValueError("Resolution exceeds 8K maximum")
        return v

class BitrateVariantCreate(BitrateVariantBase):
    """Properties required to create a bitrate variant"""
    profile_id: str

class BitrateVariantUpdate(BaseModel):
    """Properties that can be updated on a bitrate variant"""
    label: Optional[str] = Field(None, min_length=1, max_length=20)
    width: Optional[int] = Field(None, gt=0, le=7680)
    height: Optional[int] = Field(None, gt=0, le=4320)
    video_bitrate: Optional[str] = None
    max_rate: Optional[str] = None
    buffer_size: Optional[str] = None
    order_index: Optional[int] = Field(None, ge=0)

    @field_validator("video_bitrate", "max_rate", "buffer_size")
    @classmethod
    def validate_bitrate_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate bitrate format if provided"""
        if v is None:
            return v
        pattern = r"^\d+(\.\d+)?[kKmM]$"
        if not re.match(pattern, v):
            raise ValueError(f"Invalid bitrate format: {v}. Use format like '5M' or '2500k'")
        return v

class BitrateVariant(BitrateVariantBase):
    """Complete bitrate variant with database fields"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str

    class Config:
        from_attributes = True

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return self.model_dump()

    @classmethod
    def from_db_row(cls, row: dict) -> "BitrateVariant":
        """Create from database row"""
        return cls(**row)

    def get_resolution_string(self) -> str:
        """Get resolution as string (e.g., '1280x720')"""
        return f"{self.width}x{self.height}"

    def get_ffmpeg_scale_filter(self, use_cuda: bool = False) -> str:
        """Get FFmpeg scale filter for this variant

        Args:
            use_cuda: Whether to use CUDA scaling

        Returns:
            str: FFmpeg scale filter string
        """
        if use_cuda:
            return f"scale_cuda={self.width}:{self.height}"
        return f"scale={self.width}:{self.height}"

    def get_ffmpeg_bitrate_params(self) -> dict:
        """Get FFmpeg bitrate parameters

        Returns:
            dict: FFmpeg bitrate parameters
        """
        return {
            "b:v": self.video_bitrate,
            "maxrate": self.max_rate,
            "bufsize": self.buffer_size
        }