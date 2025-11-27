"""
Configuration Mapper Service
Feature: 001-edit-api-simplification

Maps between unified configuration format and legacy three-object format
for backward compatibility during migration period.
"""

from typing import Dict, Any, Optional, List
import json
import logging

logger = logging.getLogger(__name__)


class ConfigMapper:
    """
    Handles conversion between unified and legacy configuration formats.

    Legacy format: Three separate objects (job, input, output)
    Unified format: Single flat configuration object
    """

    @staticmethod
    def _simplify_codec(codec: str) -> str:
        """
        Convert FFmpeg codec names to simplified format.

        Args:
            codec: FFmpeg codec name (libx264, libx265, etc.)

        Returns:
            Simplified codec name (h264, h265, etc.)
        """
        codec_map = {
            'libx264': 'h264',
            'libx265': 'h265',
            'libvpx-vp9': 'vp9',
            'libaom-av1': 'av1'
        }
        return codec_map.get(codec, codec)

    @staticmethod
    def to_unified_format(job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert legacy three-object format to unified configuration.

        Args:
            job_data: Dictionary with keys: 'job', 'input', 'output'

        Returns:
            Unified configuration dictionary

        Example:
            Input:
                {
                    'job': {'id': '123', 'name': 'My Job', 'status': 'pending', ...},
                    'input': {'file_path': '/input/video.mp4', 'loop_enabled': False, ...},
                    'output': {'video_codec': 'h264', 'video_bitrate': '5M', ...}
                }
            Output:
                {
                    'id': '123',
                    'jobName': 'My Job',
                    'inputFile': '/input/video.mp4',
                    'videoCodec': 'h264',
                    'videoBitrate': '5M',
                    ...
                }
        """
        job = job_data.get('job', {})
        input_source = job_data.get('input', {})
        output = job_data.get('output', {})

        # Build unified configuration
        unified = {
            # Job metadata
            'id': job.get('id'),
            'jobName': job.get('name'),
            'status': job.get('status'),
            # Convert datetime to ISO string for JSON serialization
            'createdAt': job.get('created_at').isoformat() if job.get('created_at') and hasattr(job.get('created_at'), 'isoformat') else job.get('created_at'),
            'updatedAt': job.get('updated_at').isoformat() if job.get('updated_at') and hasattr(job.get('updated_at'), 'isoformat') else job.get('updated_at'),

            # Input configuration
            'inputFile': input_source.get('url') or input_source.get('file_path', ''),
            'loopInput': input_source.get('loop_enabled', False),
            'startTime': input_source.get('start_time'),
            'duration': input_source.get('duration'),

            # Video encoding - simplify codec names (libx264 → h264)
            'videoCodec': ConfigMapper._simplify_codec(output.get('video_codec') or job.get('video_codec', 'libx264')),
            'videoBitrate': output.get('video_bitrate') or job.get('video_bitrate', ''),
            'videoResolution': output.get('video_resolution'),
            'videoFrameRate': output.get('video_framerate'),
            'videoPreset': output.get('encoding_preset'),
            'videoProfile': output.get('video_profile') or output.get('profile'),
            'videoLevel': output.get('level'),

            # Hardware acceleration
            'hardwareAccel': output.get('hardware_accel') or job.get('hardware_accel'),
            'hardwareDevice': output.get('hardware_device'),

            # Audio encoding
            'audioCodec': output.get('audio_codec') or job.get('audio_codec', ''),
            'audioBitrate': output.get('audio_bitrate') or job.get('audio_bitrate', ''),
            'audioSampleRate': output.get('audio_sample_rate'),
            'audioChannels': output.get('audio_channels'),
            'audioVolume': output.get('audio_volume') or job.get('audio_volume'),

            # Output configuration
            'outputFormat': output.get('output_type', 'hls'),
            'outputDir': output.get('base_path', ''),
            'outputUrl': output.get('output_url'),

            # HLS-specific
            'hlsSegmentDuration': output.get('segment_duration', 6),
            'hlsPlaylistType': output.get('playlist_type', 'vod'),
            'hlsPlaylistSize': output.get('playlist_size', 5),
            'hlsSegmentType': output.get('segment_type', 'mpegts'),
            'hlsSegmentFilename': output.get('segment_pattern', 'segment_%03d.ts'),

            # ABR configuration
            'abrEnabled': output.get('abr_enabled', False),
            'abrLadder': ConfigMapper._parse_renditions(output.get('renditions')),

            # Track selection (stream mapping)
            'streamMaps': ConfigMapper._parse_stream_maps(output.get('stream_maps')),

            # Advanced options
            'customFFmpegArgs': job.get('custom_args'),
            'maxRetries': job.get('max_retries'),

            # Generated
            'ffmpegCommand': job.get('command'),
        }

        # Remove None values for cleaner response
        return {k: v for k, v in unified.items() if v is not None}

    @staticmethod
    def _expand_codec(codec: str) -> str:
        """
        Convert simplified codec names back to FFmpeg format.

        Args:
            codec: Simplified codec name (h264, h265, vp9, av1)

        Returns:
            FFmpeg codec name (libx264, libx265, etc.)
        """
        codec_map = {
            'h264': 'libx264',
            'h265': 'libx265',
            'vp9': 'libvpx-vp9',
            'av1': 'libaom-av1'
        }
        return codec_map.get(codec, codec)

    @staticmethod
    def to_legacy_format(unified: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert unified configuration to legacy three-object format.

        Args:
            unified: Unified configuration dictionary

        Returns:
            Dictionary with keys: 'job', 'input', 'output'

        Example:
            Input:
                {
                    'jobName': 'My Job',
                    'inputFile': '/input/video.mp4',
                    'videoCodec': 'h264',
                    ...
                }
            Output:
                {
                    'job': {'name': 'My Job', 'video_codec': 'h264', ...},
                    'input': {'file_path': '/input/video.mp4', ...},
                    'output': {'video_codec': 'h264', 'video_bitrate': '5M', ...}
                }
        """
        job_id = unified.get('id')

        # Job object
        job = {
            'id': job_id,
            'name': unified.get('jobName'),
            'status': unified.get('status', 'pending'),
            'created_at': unified.get('createdAt'),
            'updated_at': unified.get('updatedAt'),
            'command': unified.get('ffmpegCommand'),
            'video_codec': ConfigMapper._expand_codec(unified.get('videoCodec', 'h264')),  # h264 → libx264
            'audio_codec': unified.get('audioCodec'),
            'video_bitrate': unified.get('videoBitrate'),
            'audio_bitrate': unified.get('audioBitrate'),
            'audio_volume': unified.get('audioVolume'),
            'hardware_accel': unified.get('hardwareAccel'),
            'custom_args': unified.get('customFFmpegArgs'),
            # Note: max_retries not in current schema, omit for now
        }

        # Input object
        input_source = {
            'job_id': job_id,
            'type': 'file',  # Default to file type
            'url': unified.get('inputFile', ''),
            'loop_enabled': unified.get('loopInput', False),
            # Note: start_time and duration not in current schema
        }

        # Output object (only columns that exist in actual schema)
        # Determine output type: use 'file' for file outputs, 'hls' otherwise
        output_format = unified.get('outputFormat', 'hls')

        # Convert format-specific types (mp4, mkv, webm, etc.) to generic 'file' type
        if output_format in ['mp4', 'mkv', 'webm', 'avi', 'mov']:
            output_format = 'file'

        # Auto-detect based on path if not specified
        if output_format == 'hls':
            output_dir = unified.get('outputDir', '')
            output_url = unified.get('outputUrl', '')
            if output_dir.startswith('/output/files/') or output_url.endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
                output_format = 'file'

        output = {
            'job_id': job_id,
            'output_type': output_format,
            'base_path': unified.get('outputDir', ''),
            'output_url': unified.get('outputUrl'),

            # Video encoding (columns that exist) - expand codec names back to FFmpeg format
            'video_codec': ConfigMapper._expand_codec(unified.get('videoCodec', 'h264')),
            'video_bitrate': unified.get('videoBitrate'),
            'video_resolution': unified.get('videoResolution'),
            'video_framerate': unified.get('videoFrameRate'),
            'encoding_preset': unified.get('videoPreset'),
            'video_profile': unified.get('videoProfile'),
            'profile': unified.get('videoProfile'),  # Also exists as 'profile' column
            'level': unified.get('videoLevel'),

            # Audio encoding (columns that exist)
            'audio_codec': unified.get('audioCodec'),
            'audio_bitrate': unified.get('audioBitrate'),
            'audio_channels': unified.get('audioChannels'),
            'audio_volume': unified.get('audioVolume'),
            # Note: audio_sample_rate not in schema, handled by FFmpeg defaults
            # Note: hardware_accel is in job table only, not output table

            # HLS (columns that exist)
            'segment_duration': unified.get('hlsSegmentDuration', 6),
            'playlist_type': unified.get('hlsPlaylistType', 'vod'),
            'playlist_size': unified.get('hlsPlaylistSize', 5),
            'segment_type': unified.get('hlsSegmentType', 'mpegts'),
            'segment_pattern': unified.get('hlsSegmentFilename', 'segment_%03d.ts'),

            # ABR (columns that exist)
            'abr_enabled': unified.get('abrEnabled', False),
            'renditions': ConfigMapper._stringify_renditions(unified.get('abrLadder')),

            # Track selection (stream mapping)
            'stream_maps': ConfigMapper._stringify_stream_maps(unified.get('streamMaps')),
        }

        # Remove None values
        job = {k: v for k, v in job.items() if v is not None}
        input_source = {k: v for k, v in input_source.items() if v is not None}
        output = {k: v for k, v in output.items() if v is not None}

        return {
            'job': job,
            'input': input_source,
            'output': output
        }

    @staticmethod
    def _parse_renditions(renditions_json: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        """
        Parse renditions from JSON string to list of dictionaries.

        Args:
            renditions_json: JSON string containing renditions array

        Returns:
            List of rendition dictionaries or None
        """
        if not renditions_json:
            return None

        try:
            if isinstance(renditions_json, str):
                renditions = json.loads(renditions_json)
            else:
                renditions = renditions_json

            # Convert legacy format to unified format
            # Legacy: {resolution, bitrate, name}
            # Unified: {name, videoBitrate, videoResolution}
            unified_renditions = []
            for r in renditions:
                unified_rendition = {
                    'name': r.get('name', ''),
                    'videoBitrate': r.get('bitrate') or r.get('video_bitrate') or r.get('videoBitrate', ''),
                    'videoResolution': r.get('resolution') or r.get('video_resolution') or r.get('videoResolution', ''),
                }

                # Optional fields
                if 'videoFrameRate' in r or 'video_framerate' in r:
                    unified_rendition['videoFrameRate'] = r.get('videoFrameRate') or r.get('video_framerate')

                if 'audioCodec' in r or 'audio_codec' in r:
                    unified_rendition['audioCodec'] = r.get('audioCodec') or r.get('audio_codec')

                if 'audioBitrate' in r or 'audio_bitrate' in r:
                    unified_rendition['audioBitrate'] = r.get('audioBitrate') or r.get('audio_bitrate')

                unified_renditions.append(unified_rendition)

            return unified_renditions if unified_renditions else None

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse renditions JSON: {e}")
            return None

    @staticmethod
    def _stringify_renditions(renditions: Optional[List[Dict[str, Any]]]) -> Optional[str]:
        """
        Convert renditions list to JSON string for legacy format.

        Args:
            renditions: List of rendition dictionaries

        Returns:
            JSON string or None
        """
        if not renditions:
            return None

        try:
            # Convert unified format to legacy format
            # Unified: {name, videoBitrate, videoResolution}
            # Legacy: {name, bitrate, resolution}
            legacy_renditions = []
            for r in renditions:
                legacy_rendition = {
                    'name': r.get('name', ''),
                    'bitrate': r.get('videoBitrate', ''),
                    'video_bitrate': r.get('videoBitrate', ''),
                    'resolution': r.get('videoResolution', ''),
                    'video_resolution': r.get('videoResolution', ''),
                }

                # Optional fields
                if 'videoFrameRate' in r:
                    legacy_rendition['video_framerate'] = r['videoFrameRate']

                if 'audioCodec' in r:
                    legacy_rendition['audio_codec'] = r['audioCodec']

                if 'audioBitrate' in r:
                    legacy_rendition['audio_bitrate'] = r['audioBitrate']

                legacy_renditions.append(legacy_rendition)

            return json.dumps(legacy_renditions)

        except (TypeError, AttributeError) as e:
            logger.error(f"Failed to stringify renditions: {e}")
            return None

    @staticmethod
    def _parse_stream_maps(stream_maps_json: Optional[str]) -> Optional[List[Dict[str, str]]]:
        """
        Parse stream maps from JSON string to list of dictionaries.

        Args:
            stream_maps_json: JSON string containing stream maps array

        Returns:
            List of stream map dictionaries or None
        """
        if not stream_maps_json:
            return None

        try:
            if isinstance(stream_maps_json, str):
                stream_maps = json.loads(stream_maps_json)
            else:
                stream_maps = stream_maps_json

            # Ensure each stream map has the required fields
            validated_maps = []
            for sm in stream_maps:
                if 'input_stream' in sm and 'output_label' in sm:
                    validated_maps.append({
                        'input_stream': sm['input_stream'],
                        'output_label': sm['output_label']
                    })

            return validated_maps if validated_maps else None

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse stream_maps JSON: {e}")
            return None

    @staticmethod
    def _stringify_stream_maps(stream_maps: Optional[List[Dict[str, str]]]) -> Optional[str]:
        """
        Convert stream maps list to JSON string for legacy format.

        Args:
            stream_maps: List of stream map dictionaries

        Returns:
            JSON string or None
        """
        if not stream_maps:
            return None

        try:
            return json.dumps(stream_maps)
        except (TypeError, AttributeError) as e:
            logger.error(f"Failed to stringify stream_maps: {e}")
            return None

    @staticmethod
    def flatten_config(job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten three-object format into a single dictionary (simplified version).

        This is a simpler version of to_unified_format for quick flattening.

        Args:
            job_data: Dictionary with keys: 'job', 'input', 'output'

        Returns:
            Flattened dictionary with all fields merged
        """
        return {
            **job_data.get('job', {}),
            **job_data.get('input', {}),
            **job_data.get('output', {})
        }

    @staticmethod
    async def populate_full_config(db_connection, job_id: str, job_data: Dict[str, Any]) -> bool:
        """
        Populate full_config cache for a job (lazy migration helper).

        This method is used during migration to populate the full_config column
        for legacy jobs that don't have it populated yet.

        Args:
            db_connection: Database connection object
            job_id: Job identifier
            job_data: Dictionary with keys: 'job', 'input', 'output'

        Returns:
            True if successful, False otherwise

        Example:
            >>> job_data = await get_job_with_config(job_id)
            >>> success = await config_mapper.populate_full_config(db, job_id, job_data)

        Feature: 008-migrate-unified-db (completes migration from feature 007)
        """
        try:
            # Convert legacy format to unified format
            unified = ConfigMapper.to_unified_format(job_data)

            # Handle datetime serialization
            def json_serializer(obj):
                """Custom JSON serializer for datetime objects"""
                from datetime import datetime
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            # Write to full_config column
            await db_connection.execute(
                "UPDATE encoding_jobs SET full_config = ? WHERE id = ?",
                (json.dumps(unified, default=json_serializer), job_id)
            )
            await db_connection.commit()

            logger.info(f"✓ Populated full_config for job {job_id}: {unified.get('jobName')}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to populate full_config for job {job_id}: {e}")
            return False


# Create singleton instance
config_mapper = ConfigMapper()
