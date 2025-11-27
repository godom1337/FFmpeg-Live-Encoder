"""
Input Source Model
Input configuration for encoding jobs
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
import re


class InputType(str, Enum):
    """Input source types"""
    UDP = "udp"
    HTTP = "http"
    FILE = "file"


class HardwareAcceleration(BaseModel):
    """Hardware acceleration settings"""
    type: str = Field(..., description="Hardware acceleration type (cuda, nvenc, vulkan, qsv)")
    device: Optional[int] = Field(0, description="Device index for multi-GPU systems")
    output_format: Optional[str] = Field(None, description="Output pixel format")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "cuda",
                "device": 0,
                "output_format": "cuda"
            }
        }


class InputSource(BaseModel):
    """
    Input configuration for encoding job (one-to-one with EncodingJob)
    """
    job_id: str = Field(..., description="References parent EncodingJob")
    type: InputType = Field(..., description="Input source type")
    url: str = Field(..., description="Full input URL or file path")
    loop_enabled: bool = Field(default=False, description="Loop file inputs continuously")
    hardware_accel: Optional[Dict[str, Any]] = Field(None, description="Hardware acceleration settings")

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "type": "http",
                "url": "http://10.0.21.232:5004/auto/v2.1",
                "loop_enabled": False,
                "hardware_accel": {
                    "type": "cuda",
                    "device": 0,
                    "output_format": "cuda"
                }
            }
        }

    @validator('url')
    def validate_url(cls, v, values):
        """Validate URL format based on input type"""
        if 'type' not in values:
            return v

        input_type = values['type']

        if input_type == InputType.UDP:
            # Validate UDP URL format
            if not re.match(r'^udp://[^:]+:\d+$', v):
                raise ValueError(f"Invalid UDP URL format. Expected: udp://host:port, got: {v}")

        elif input_type == InputType.HTTP:
            # Validate HTTP/HTTPS URL format
            if not re.match(r'^https?://[^\s]+$', v):
                raise ValueError(f"Invalid HTTP URL format. Expected: http(s)://host[:port]/path, got: {v}")

        elif input_type == InputType.FILE:
            # For file inputs, just check it's not empty
            if not v or v.strip() == "":
                raise ValueError("File path cannot be empty")

        return v

    @validator('loop_enabled')
    def validate_loop(cls, v, values):
        """Loop is only valid for file inputs"""
        if v and 'type' in values and values['type'] != InputType.FILE:
            raise ValueError("Loop option is only valid for file inputs")
        return v

    def get_ffmpeg_input_args(self) -> list:
        """Generate FFmpeg input arguments"""
        args = []

        # Add hardware acceleration if configured
        if self.hardware_accel:
            hw = self.hardware_accel
            if hw.get('type') == 'cuda':
                args.extend(['-hwaccel', 'cuda'])
                if hw.get('device') is not None:
                    args.extend(['-hwaccel_device', str(hw['device'])])
                if hw.get('output_format'):
                    args.extend(['-hwaccel_output_format', hw['output_format']])
            elif hw.get('type') == 'nvenc':
                args.extend(['-hwaccel', 'cuda'])
            elif hw.get('type') == 'qsv':
                args.extend(['-hwaccel', 'qsv'])
                if hw.get('device') is not None:
                    args.extend(['-hwaccel_device', str(hw['device'])])
                if hw.get('output_format'):
                    args.extend(['-hwaccel_output_format', hw['output_format']])
            elif hw.get('type') == 'vulkan':
                args.extend(['-hwaccel', 'vulkan'])

        # Add loop option for file inputs
        if self.type == InputType.FILE and self.loop_enabled:
            args.extend(['-stream_loop', '-1'])

        # Add re-connection options for network inputs
        if self.type in [InputType.UDP, InputType.HTTP]:
            args.extend(['-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5'])

        # Add the input URL
        args.extend(['-i', self.url])

        return args


class InputSourceCreate(BaseModel):
    """Schema for creating an input source"""
    type: InputType = Field(..., description="Input source type")
    url: str = Field(..., description="Full input URL or file path")
    loop_enabled: bool = Field(default=False, description="Loop file inputs continuously")
    hardware_accel: Optional[Dict[str, Any]] = Field(None, description="Hardware acceleration settings")


class InputSourceUpdate(BaseModel):
    """Schema for updating an input source"""
    type: Optional[InputType] = Field(None, description="Input source type")
    url: Optional[str] = Field(None, description="Full input URL or file path")
    loop_enabled: Optional[bool] = Field(None, description="Loop file inputs continuously")
    hardware_accel: Optional[Dict[str, Any]] = Field(None, description="Hardware acceleration settings")