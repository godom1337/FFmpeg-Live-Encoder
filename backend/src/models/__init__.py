"""Data models for FFmpeg Encoder"""

from .job import EncodingJob, EncodingJobCreate, EncodingJobUpdate, JobStatus
from .input import InputSource, InputSourceCreate, InputType
from .output import OutputConfiguration, OutputConfigurationCreate, OutputConfigurationUpdate
from .profile import EncodingProfile, EncodingProfileCreate
from .variant import BitrateVariant
from .rendition import Rendition, RenditionCreate, RENDITION_PRESETS, get_preset_rendition
from .stream_info import (
    VideoStreamInfo,
    AudioStreamInfo,
    SubtitleStreamInfo,
    InputAnalysisResult,
    AnalyzeInputRequest,
    StreamType
)
from .presets import (
    EncodingPreset,
    get_preset,
    get_all_presets,
    get_presets_by_category,
    get_presets_by_tag,
    ENCODING_PRESETS
)

__all__ = [
    "EncodingJob",
    "EncodingJobCreate",
    "EncodingJobUpdate",
    "JobStatus",
    "InputSource",
    "InputSourceCreate",
    "InputType",
    "OutputConfiguration",
    "OutputConfigurationCreate",
    "OutputConfigurationUpdate",
    "EncodingProfile",
    "EncodingProfileCreate",
    "BitrateVariant",
    "Rendition",
    "RenditionCreate",
    "RENDITION_PRESETS",
    "get_preset_rendition",
    "VideoStreamInfo",
    "AudioStreamInfo",
    "SubtitleStreamInfo",
    "InputAnalysisResult",
    "AnalyzeInputRequest",
    "StreamType",
    "EncodingPreset",
    "get_preset",
    "get_all_presets",
    "get_presets_by_category",
    "get_presets_by_tag",
    "ENCODING_PRESETS",
]