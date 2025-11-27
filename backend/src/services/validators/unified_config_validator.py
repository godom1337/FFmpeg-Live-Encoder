"""
Unified Configuration Validator
Feature: 001-edit-api-simplification

Provides validation functions for unified job configuration.
"""

from typing import Dict, Any, List, Tuple, Optional
import re
from pathlib import Path


class ValidationError:
    """Represents a validation error"""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format for API responses"""
        return {"field": self.field, "message": self.message}


class UnifiedConfigValidator:
    """Validator for unified job configuration"""

    # Required fields that must be present in every configuration
    REQUIRED_FIELDS = [
        'jobName',
        'inputFile',
        'videoCodec',
        'audioCodec',
        'audioBitrate',
        'outputFormat'
        # Note: outputDir is conditionally required based on outputFormat
        # Note: videoBitrate is optional - FFmpeg will use default quality settings if not specified
    ]

    # Valid codec values
    VALID_VIDEO_CODECS = ['h264', 'h265', 'av1']
    VALID_AUDIO_CODECS = ['aac', 'mp3', 'opus', 'vorbis', 'copy']  # 'copy' = stream copy (no re-encoding)
    VALID_OUTPUT_FORMATS = ['hls', 'dash', 'mp4', 'webm', 'mkv', 'avi', 'mov', 'rtmp', 'udp', 'srt']
    VALID_HARDWARE_ACCEL = ['none', 'nvenc', 'qsv', 'vaapi', 'videotoolbox']

    # Patterns
    BITRATE_PATTERN = re.compile(r'^\d+(\.\d+)?[KMG]$', re.IGNORECASE)  # Allow decimals: 1.5M, 2.5M
    RESOLUTION_PATTERN = re.compile(r'^\d+x\d+$')
    TIME_PATTERN = re.compile(r'^\d{2}:\d{2}:\d{2}$')

    @classmethod
    def validate(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate a unified configuration object.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors: List[ValidationError] = []

        # Validate required fields
        errors.extend(cls._validate_required_fields(config))

        # Validate field formats and values
        errors.extend(cls._validate_bitrate_fields(config))
        errors.extend(cls._validate_codec_fields(config))
        errors.extend(cls._validate_resolution_field(config))
        errors.extend(cls._validate_time_fields(config))
        errors.extend(cls._validate_output_format(config))
        errors.extend(cls._validate_hardware_accel(config))

        # Validate ABR configuration
        errors.extend(cls._validate_abr_config(config))

        # Validate numeric ranges
        errors.extend(cls._validate_numeric_ranges(config))

        # Validate output configuration (conditional requirements)
        errors.extend(cls._validate_output_config(config))

        return errors

    @classmethod
    def _validate_required_fields(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Check all required fields are present and non-empty"""
        errors = []

        for field in cls.REQUIRED_FIELDS:
            if field not in config or not config[field]:
                errors.append(ValidationError(
                    field=field,
                    message=f"{field} is required"
                ))

        return errors

    @classmethod
    def _validate_bitrate_fields(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate bitrate format for video and audio"""
        errors = []

        # Video bitrate
        if 'videoBitrate' in config and config['videoBitrate']:
            if not cls.BITRATE_PATTERN.match(config['videoBitrate']):
                errors.append(ValidationError(
                    field='videoBitrate',
                    message="Invalid bitrate format. Use format like '5M', '1.5M', '2500k', or '128K'"
                ))

        # Audio bitrate
        if 'audioBitrate' in config and config['audioBitrate']:
            if not cls.BITRATE_PATTERN.match(config['audioBitrate']):
                errors.append(ValidationError(
                    field='audioBitrate',
                    message="Invalid bitrate format. Use format like '128k', '1.5M', or '192K'"
                ))

        return errors

    @classmethod
    def _validate_codec_fields(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate codec selections"""
        errors = []

        # Video codec
        if 'videoCodec' in config and config['videoCodec']:
            if config['videoCodec'] not in cls.VALID_VIDEO_CODECS:
                errors.append(ValidationError(
                    field='videoCodec',
                    message=f"Invalid video codec. Must be one of: {', '.join(cls.VALID_VIDEO_CODECS)}"
                ))

        # Audio codec
        if 'audioCodec' in config and config['audioCodec']:
            if config['audioCodec'] not in cls.VALID_AUDIO_CODECS:
                errors.append(ValidationError(
                    field='audioCodec',
                    message=f"Invalid audio codec. Must be one of: {', '.join(cls.VALID_AUDIO_CODECS)}"
                ))

        return errors

    @classmethod
    def _validate_resolution_field(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate video resolution format"""
        errors = []

        if 'videoResolution' in config and config['videoResolution']:
            if not cls.RESOLUTION_PATTERN.match(config['videoResolution']):
                errors.append(ValidationError(
                    field='videoResolution',
                    message="Invalid resolution format. Use format like '1920x1080'"
                ))

        return errors

    @classmethod
    def _validate_time_fields(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate time format fields (startTime, duration)"""
        errors = []

        # Start time
        if 'startTime' in config and config['startTime']:
            if not cls.TIME_PATTERN.match(config['startTime']):
                errors.append(ValidationError(
                    field='startTime',
                    message="Invalid time format. Use HH:MM:SS format (e.g., '00:01:30')"
                ))

        # Duration
        if 'duration' in config and config['duration']:
            if not cls.TIME_PATTERN.match(config['duration']):
                errors.append(ValidationError(
                    field='duration',
                    message="Invalid time format. Use HH:MM:SS format (e.g., '00:10:00')"
                ))

        return errors

    @classmethod
    def _validate_output_format(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate output format selection"""
        errors = []

        if 'outputFormat' in config and config['outputFormat']:
            if config['outputFormat'] not in cls.VALID_OUTPUT_FORMATS:
                errors.append(ValidationError(
                    field='outputFormat',
                    message=f"Invalid output format. Must be one of: {', '.join(cls.VALID_OUTPUT_FORMATS)}"
                ))

        return errors

    @classmethod
    def _validate_hardware_accel(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate hardware acceleration selection"""
        errors = []

        if 'hardwareAccel' in config and config['hardwareAccel']:
            if config['hardwareAccel'] not in cls.VALID_HARDWARE_ACCEL:
                errors.append(ValidationError(
                    field='hardwareAccel',
                    message=f"Invalid hardware acceleration. Must be one of: {', '.join(cls.VALID_HARDWARE_ACCEL)}"
                ))

        return errors

    @classmethod
    def _validate_abr_config(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate ABR (Adaptive Bitrate) configuration"""
        errors = []

        abr_enabled = config.get('abrEnabled', False)

        if abr_enabled:
            # ABR ladder is required when ABR is enabled
            if 'abrLadder' not in config or not config['abrLadder']:
                errors.append(ValidationError(
                    field='abrLadder',
                    message="ABR ladder is required when abrEnabled is true"
                ))
            else:
                # Validate each rendition
                ladder = config['abrLadder']

                if not isinstance(ladder, list):
                    errors.append(ValidationError(
                        field='abrLadder',
                        message="ABR ladder must be an array of rendition configurations"
                    ))
                else:
                    # Check for at least one rendition
                    if len(ladder) == 0:
                        errors.append(ValidationError(
                            field='abrLadder',
                            message="ABR ladder must contain at least one rendition"
                        ))

                    # Validate each rendition
                    rendition_names = []
                    for i, rendition in enumerate(ladder):
                        # Validate rendition structure
                        if not isinstance(rendition, dict):
                            errors.append(ValidationError(
                                field=f'abrLadder[{i}]',
                                message=f"Rendition at index {i} must be an object"
                            ))
                            continue

                        # Required fields
                        if 'name' not in rendition or not rendition['name']:
                            errors.append(ValidationError(
                                field=f'abrLadder[{i}].name',
                                message=f"Rendition name is required"
                            ))
                        else:
                            rendition_names.append(rendition['name'])

                        if 'videoBitrate' not in rendition or not rendition['videoBitrate']:
                            errors.append(ValidationError(
                                field=f'abrLadder[{i}].videoBitrate',
                                message=f"Rendition videoBitrate is required"
                            ))
                        elif not cls.BITRATE_PATTERN.match(rendition['videoBitrate']):
                            errors.append(ValidationError(
                                field=f'abrLadder[{i}].videoBitrate',
                                message=f"Invalid bitrate format: {rendition['videoBitrate']}. Use format like '5M', '1.5M', or '2500k'"
                            ))

                        if 'videoResolution' not in rendition or not rendition['videoResolution']:
                            errors.append(ValidationError(
                                field=f'abrLadder[{i}].videoResolution',
                                message=f"Rendition videoResolution is required"
                            ))
                        elif not cls.RESOLUTION_PATTERN.match(rendition['videoResolution']):
                            errors.append(ValidationError(
                                field=f'abrLadder[{i}].videoResolution',
                                message=f"Invalid resolution format: {rendition['videoResolution']}"
                            ))

                    # Check for duplicate rendition names
                    if len(rendition_names) != len(set(rendition_names)):
                        duplicates = [name for name in rendition_names if rendition_names.count(name) > 1]
                        errors.append(ValidationError(
                            field='abrLadder',
                            message=f"Duplicate rendition names found: {', '.join(set(duplicates))}"
                        ))

        return errors

    @classmethod
    def _validate_numeric_ranges(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate numeric field ranges"""
        errors = []

        # Video frame rate
        if 'videoFrameRate' in config and config['videoFrameRate'] is not None:
            fr = config['videoFrameRate']
            if not isinstance(fr, int) or fr < 1 or fr > 120:
                errors.append(ValidationError(
                    field='videoFrameRate',
                    message="Video frame rate must be between 1 and 120 fps"
                ))

        # Audio sample rate
        if 'audioSampleRate' in config and config['audioSampleRate'] is not None:
            sr = config['audioSampleRate']
            valid_rates = [22050, 44100, 48000, 96000]
            if sr not in valid_rates:
                errors.append(ValidationError(
                    field='audioSampleRate',
                    message=f"Audio sample rate must be one of: {', '.join(map(str, valid_rates))}"
                ))

        # Audio channels
        if 'audioChannels' in config and config['audioChannels'] is not None:
            ch = config['audioChannels']
            if not isinstance(ch, int) or ch < 1 or ch > 8:
                errors.append(ValidationError(
                    field='audioChannels',
                    message="Audio channels must be between 1 and 8"
                ))

        # HLS segment duration
        if 'hlsSegmentDuration' in config and config['hlsSegmentDuration'] is not None:
            sd = config['hlsSegmentDuration']
            if not isinstance(sd, int) or sd < 1 or sd > 60:
                errors.append(ValidationError(
                    field='hlsSegmentDuration',
                    message="HLS segment duration must be between 1 and 60 seconds"
                ))

        # Max retries
        if 'maxRetries' in config and config['maxRetries'] is not None:
            mr = config['maxRetries']
            if not isinstance(mr, int) or mr < 0 or mr > 10:
                errors.append(ValidationError(
                    field='maxRetries',
                    message="Max retries must be between 0 and 10"
                ))

        return errors

    @classmethod
    def _validate_output_config(cls, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate output configuration (conditional requirements)"""
        errors = []

        output_format = config.get('outputFormat', '')

        # File-based outputs need outputDir, streaming outputs need outputUrl
        file_based_formats = ['hls', 'dash', 'mp4', 'webm']
        streaming_formats = ['rtmp', 'udp', 'srt', 'file']  # 'file' is legacy

        if output_format in file_based_formats:
            # outputDir is required for file-based outputs
            if 'outputDir' not in config or not config['outputDir']:
                errors.append(ValidationError(
                    field='outputDir',
                    message=f"outputDir is required for {output_format} output format"
                ))
        elif output_format in streaming_formats:
            # outputUrl is required for streaming outputs
            if 'outputUrl' not in config or not config['outputUrl']:
                errors.append(ValidationError(
                    field='outputUrl',
                    message=f"outputUrl is required for {output_format} output format (e.g., udp://239.1.1.1:5000)"
                ))

        return errors

    @classmethod
    def validate_and_raise(cls, config: Dict[str, Any]) -> None:
        """
        Validate configuration and raise ValueError if invalid.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If validation fails, with details of all errors
        """
        errors = cls.validate(config)

        if errors:
            error_messages = [f"{e.field}: {e.message}" for e in errors]
            raise ValueError(
                f"Configuration validation failed:\n" + "\n".join(error_messages)
            )

    @classmethod
    def can_edit_job(cls, status: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a job can be edited based on its status.

        Args:
            status: Current job status

        Returns:
            Tuple of (can_edit: bool, error_message: Optional[str])
        """
        editable_statuses = ['pending', 'completed', 'error', 'stopped']

        if status in editable_statuses:
            return True, None
        elif status == 'running':
            return False, "Job is running and cannot be edited. Stop the job before editing."
        else:
            return False, f"Job with status '{status}' cannot be edited"

    @classmethod
    def validate_create_request(cls, config: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]]]:
        """
        Validate a unified configuration for job creation.

        This is similar to validate() but tailored for CREATE operations where
        certain fields (id, status, timestamps) are optional and will be generated.

        Args:
            config: Configuration dictionary for new job

        Returns:
            Tuple of (is_valid: bool, errors: List[Dict])
            errors is list of dicts with 'field' and 'message' keys

        Feature: 001-edit-api-simplification (Phase 7)
        """
        errors = cls.validate(config)

        # Convert ValidationError objects to dicts
        error_dicts = [e.to_dict() for e in errors]

        # Filter out errors for fields that will be auto-generated
        auto_generated_fields = {'id', 'status', 'createdAt', 'updatedAt', 'ffmpegCommand'}
        filtered_errors = [
            e for e in error_dicts
            if e['field'] not in auto_generated_fields
        ]

        is_valid = len(filtered_errors) == 0

        return is_valid, filtered_errors


# Create a singleton instance for easy imports
validator = UnifiedConfigValidator()
