"""
Job Manager Service
Handles encoding job lifecycle orchestration
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from uuid import uuid4

from models.job import EncodingJob, EncodingJobCreate, EncodingJobUpdate, JobStatus
from models.input import InputSource, InputSourceCreate
from models.output import OutputConfiguration, OutputConfigurationCreate
from models.profile import EncodingProfile
from services.storage import db_service
from services.config_mapper import config_mapper
# OLD: from config.field_registry import get_output_table_fields, get_job_table_fields (DELETED - Phase 7)

logger = logging.getLogger(__name__)


class JobManager:
    """Manages encoding job lifecycle"""

    def __init__(self):
        """Initialize job manager"""
        self.db = db_service
        self.active_jobs: Dict[str, EncodingJob] = {}

    async def get_job(self, job_id: str) -> Optional[EncodingJob]:
        """Get a job by ID

        Args:
            job_id: Job ID

        Returns:
            Optional[EncodingJob]: Job if found
        """
        row = await self.db.fetch_one(
            "SELECT * FROM encoding_jobs WHERE id = ?",
            (job_id,)
        )

        if row:
            return self._row_to_job(row)
        return None

    async def get_job_by_name(self, job_name: str) -> Optional[EncodingJob]:
        """Get a job by name (for duplicate checking)

        Args:
            job_name: Job name

        Returns:
            Optional[EncodingJob]: Job if found, None otherwise

        Feature: 008-migrate-unified-db (FR-009: duplicate name checking)
        """
        row = await self.db.fetch_one(
            "SELECT * FROM encoding_jobs WHERE name = ?",
            (job_name,)
        )

        if row:
            return self._row_to_job(row)
        return None

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[EncodingJob]:
        """List encoding jobs

        Args:
            status: Filter by status (optional)
            limit: Maximum number of results
            offset: Skip this many results

        Returns:
            List[EncodingJob]: List of jobs
        """
        query = """
            SELECT * FROM encoding_jobs
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY priority DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self.db.fetch_all(query, tuple(params))
        return [self._row_to_job(row) for row in rows]

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job

        Args:
            job_id: Job ID

        Returns:
            bool: True if deleted

        Raises:
            ValueError: If job is running
        """
        # Get job
        job = await self.get_job(job_id)
        if not job:
            return False

        # Check if job can be deleted
        if not job.can_delete():
            raise ValueError(f"Job {job_id} is running and cannot be deleted")

        # Delete from database (cascades to related tables)
        await self.db.execute(
            "DELETE FROM encoding_jobs WHERE id = ?",
            (job_id,)
        )

        logger.info(f"Deleted job {job_id}")
        return True

    async def reset_job_status(self, job_id: str) -> Optional[EncodingJob]:
        """Reset job status to PENDING from ERROR/STOPPED/COMPLETED

        Clears error messages, stopped_at timestamp, and resets status.
        Allows restarting jobs that have finished or failed.

        Args:
            job_id: Job ID

        Returns:
            Optional[EncodingJob]: Updated job if successful

        Raises:
            ValueError: If job is running or already pending
        """
        from models.job import JobStatus

        # Get job
        job = await self.get_job(job_id)
        if not job:
            return None

        # Validate job can be reset
        if job.status == JobStatus.RUNNING:
            raise ValueError(f"Cannot reset status of running job {job_id}")

        if job.status == JobStatus.PENDING:
            raise ValueError(f"Job {job_id} is already in PENDING status")

        # Reset the job
        await self.db.execute(
            """
            UPDATE encoding_jobs
            SET status = ?,
                error_message = NULL,
                stopped_at = NULL,
                pid = NULL
            WHERE id = ?
            """,
            (JobStatus.PENDING, job_id)
        )

        logger.info(f"Reset job {job_id} from {job.status} to PENDING")

        # Return updated job
        return await self.get_job(job_id)

    async def get_job_with_config(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job with full configuration including input and output

        Args:
            job_id: Job ID

        Returns:
            Optional[Dict]: Job with input/output config if found
        """
        # Get job
        job = await self.get_job(job_id)
        if not job:
            return None

        # Get input source
        input_row = await self.db.fetch_one(
            "SELECT * FROM input_sources WHERE job_id = ?",
            (job_id,)
        )

        # Get output config
        output_row = await self.db.fetch_one(
            "SELECT * FROM output_configurations WHERE job_id = ?",
            (job_id,)
        )

        result = {
            "job": job.dict(),
            "input": None,
            "output": None
        }

        # Debug logging
        logger.info(f"[DEBUG] Job {job_id} - job.dict() keys: {list(job.dict().keys())}")
        logger.info(f"[DEBUG] Job {job_id} - job.video_bitrate={job.video_bitrate}, job.hardware_accel={job.hardware_accel}")

        if input_row:
            # Validate loop_enabled - it's only valid for file inputs
            # If corrupted data exists, reset it to False for non-file inputs
            loop_enabled = input_row["loop_enabled"]
            if input_row["type"] != "file" and loop_enabled:
                loop_enabled = False

            input_source = InputSource(
                job_id=input_row["job_id"],
                type=input_row["type"],
                url=input_row["url"],
                loop_enabled=loop_enabled,
                hardware_accel=json.loads(input_row["hardware_accel"]) if input_row["hardware_accel"] else None
            )
            result["input"] = input_source.dict()

        if output_row:
            # Build output config with all available fields
            output_data = {
                "job_id": output_row["job_id"],
                "base_path": output_row["base_path"],
                "variant_paths": json.loads(output_row["variant_paths"]),
                "nginx_served": output_row["nginx_served"],
                "manifest_url": output_row["manifest_url"]
            }

            # Add output type fields if they exist
            if "output_type" in output_row.keys():
                output_data["output_type"] = output_row.get("output_type", "hls")
            if "output_url" in output_row.keys():
                output_data["output_url"] = output_row.get("output_url")

            # Load all output configuration fields (simplified - Phase 7)
            # Hardcoded field list replaces field_registry automatic extraction
            output_fields = [
                'output_type', 'output_url', 'hls_config', 'udp_config', 'file_config',
                'segment_duration', 'playlist_size', 'playlist_type', 'segment_type', 'segment_pattern',
                'video_codec', 'video_bitrate', 'video_resolution', 'video_framerate',
                'audio_codec', 'audio_bitrate', 'audio_channels', 'audio_volume', 'audio_stream_index',
                'encoding_preset', 'crf', 'keyframe_interval', 'tune', 'two_pass',
                'rate_control_mode', 'profile', 'video_profile', 'level',
                'max_bitrate', 'buffer_size', 'look_ahead', 'pixel_format',
                'abr_enabled', 'renditions', 'stream_maps'
            ]

            for field_name in output_fields:
                if field_name in output_row.keys():
                    value = output_row.get(field_name)

                    # Handle JSON fields
                    if field_name in ['hls_config', 'udp_config', 'file_config', 'renditions', 'stream_maps'] and value:
                        try:
                            output_data[field_name] = json.loads(value) if isinstance(value, str) else value
                        except (json.JSONDecodeError, TypeError):
                            logger.warning(f"Failed to parse JSON field {field_name}")
                            output_data[field_name] = value
                    # Handle boolean fields
                    elif field_name in ['nginx_served', 'abr_enabled', 'two_pass'] and value is not None:
                        output_data[field_name] = bool(value)
                    # All other fields
                    elif value is not None:
                        output_data[field_name] = value

            logger.info(f"Loaded {len(output_data)} output fields for job {job_id}")

            output_config = OutputConfiguration(**output_data)
            result["output"] = output_config.dict()

            # Debug logging for ABR and encoding params
            logger.info(f"Loaded job {job_id} - ABR enabled: {output_config.abr_enabled}, renditions: {len(output_config.renditions)}")
            logger.info(f"[DEBUG] Job {job_id} - output.video_bitrate={output_config.video_bitrate}, output.video_framerate={output_config.video_framerate}")

        return result

    async def _get_profile(self, profile_id: str) -> Optional[EncodingProfile]:
        """Get encoding profile by ID

        Args:
            profile_id: Profile ID

        Returns:
            Optional[EncodingProfile]: Profile if found
        """
        row = await self.db.fetch_one(
            "SELECT * FROM encoding_profiles WHERE id = ?",
            (profile_id,)
        )

        if row:
            return EncodingProfile(**row)
        return None

    def _row_to_job(self, row: dict) -> EncodingJob:
        """Convert database row to EncodingJob

        Args:
            row: Database row

        Returns:
            EncodingJob: Job instance
        """
        job = EncodingJob(
            id=row["id"],
            name=row["name"],
            profile_id=row["profile_id"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            stopped_at=datetime.fromisoformat(row["stopped_at"]) if row["stopped_at"] else None,
            pid=row["pid"],
            error_message=row["error_message"],
            command=row["command"],
            priority=row["priority"],
            archive_on_complete=bool(row.get("archive_on_complete", False)),
            # Encoding parameters from job table
            video_codec=row.get("video_codec"),
            audio_codec=row.get("audio_codec"),
            video_bitrate=row.get("video_bitrate"),
            audio_bitrate=row.get("audio_bitrate"),
            audio_volume=row.get("audio_volume"),  # FIXED: Was missing!
            hardware_accel=row.get("hardware_accel"),
            template_id=row.get("template_id"),
            custom_args=row.get("custom_args")
        )

        return job

    async def save_job_unified(
        self,
        job_data: dict,
        job_id: str = None,
        is_update: bool = False
    ) -> EncodingJob:
        """
        Unified method to save (create or update) a job with all its configurations.

        Phase 7 Rewrite: Now delegates to create_job_unified() or update_job_unified()
        instead of using deleted _prepare_* methods.

        Args:
            job_data: Dictionary containing all job data (job fields, input config, output config)
            job_id: Job ID (None for create, required for update)
            is_update: Boolean flag indicating if this is an update operation

        Returns:
            EncodingJob: Created or updated job
        """
        if is_update and job_id:
            # UPDATE: Use update_job_unified()
            # Convert job_data format to unified format if needed
            unified_config = self._convert_to_unified_format(job_data)
            unified_config['id'] = job_id
            await self.update_job_unified(job_id, unified_config)
            return await self.get_job(job_id)
        else:
            # CREATE: Use create_job_unified()
            unified_config = self._convert_to_unified_format(job_data)
            new_job_id = await self.create_job_unified(unified_config)
            return await self.get_job(new_job_id)

    def _convert_to_unified_format(self, job_data: dict) -> dict:
        """
        Convert CreateJobRequest-style data to unified configuration format.

        Handles snake_case to camelCase conversion and field mapping.
        Phase 7 helper method.
        """
        unified = {}

        # Codec simplification helper
        def simplify_codec(codec):
            """Convert FFmpeg codec names to simplified format"""
            if not codec:
                return codec
            codec_map = {
                'libx264': 'h264',
                'libx265': 'h265',
                'libvpx-vp9': 'vp9',
                'libaom-av1': 'av1',
                'h264_nvenc': 'h264',
                'hevc_nvenc': 'h265',
                'h265_nvenc': 'h265'
            }
            return codec_map.get(codec, codec)

        # Map snake_case to camelCase
        field_mapping = {
            'job_name': 'jobName',
            'input_file': 'inputFile',
            'output_file': 'outputFile',
            'loop_input': 'loopInput',
            'video_resolution': 'videoResolution',
            'video_framerate': 'videoFrameRate',
            'encoding_preset': 'videoPreset',
            'video_profile': 'videoProfile',
            'video_level': 'videoLevel',
            'hardware_accel': 'hardwareAccel',
            'video_bitrate': 'videoBitrate',
            'audio_bitrate': 'audioBitrate',
            'audio_channels': 'audioChannels',
            'audio_volume': 'audioVolume',
            'custom_args': 'customFFmpegArgs',
            'input_format': 'inputFormat',
            'input_args': 'inputArgs',
        }

        for old_key, new_key in field_mapping.items():
            if old_key in job_data and job_data[old_key] is not None:
                unified[new_key] = job_data[old_key]

        # Handle codec conversion
        if 'video_codec' in job_data:
            unified['videoCodec'] = simplify_codec(job_data['video_codec'])
            logger.info(f"[codec_convert] video_codec '{job_data['video_codec']}' → videoCodec '{unified['videoCodec']}'")
        if 'audio_codec' in job_data:
            unified['audioCodec'] = job_data['audio_codec']

        # Handle HLS output
        if 'hls_output' in job_data and job_data['hls_output']:
            hls = job_data['hls_output']
            unified['outputFormat'] = 'hls'
            unified['outputDir'] = hls.get('output_dir', '/output/hls')
            unified['hlsSegmentDuration'] = hls.get('segment_duration', 6)
            unified['hlsPlaylistType'] = hls.get('playlist_type', 'vod')
            unified['hlsSegmentType'] = hls.get('segment_type', 'mpegts')
            unified['hlsSegmentFilename'] = hls.get('segment_pattern', 'segment_%03d.ts')

            # ABR configuration
            if hls.get('abr_enabled') and hls.get('renditions'):
                unified['abrEnabled'] = True
                unified['abrLadder'] = []
                for r in hls['renditions']:
                    unified['abrLadder'].append({
                        'name': r.get('name', ''),
                        'videoBitrate': r.get('video_bitrate', ''),
                        'videoResolution': r.get('video_resolution', ''),
                        'videoCodec': r.get('video_codec'),
                        'videoProfile': r.get('video_profile'),
                        'audioCodec': r.get('audio_codec'),
                        'audioBitrate': r.get('audio_bitrate'),
                    })

        # Handle UDP output
        elif 'udp_outputs' in job_data and job_data['udp_outputs']:
            unified['outputFormat'] = 'udp'
            unified['outputUrl'] = job_data['udp_outputs'][0].get('url') if job_data['udp_outputs'] else None

        # Handle RTMP output
        elif 'rtmp_outputs' in job_data and job_data['rtmp_outputs']:
            unified['outputFormat'] = 'rtmp'
            rtmp = job_data['rtmp_outputs'][0]
            # Use full_url if available (it's a property on the model, so might not be in dict if using .dict())
            # But job_data comes from request.dict(), so properties are NOT included by default unless computed_field is used.
            # So we need to reconstruct it or check if it's there.
            
            url = rtmp.get('url', '')
            stream_key = rtmp.get('stream_key') or rtmp.get('streamKey', '')
            
            if stream_key and stream_key not in url:
                if not url.endswith('/'):
                    url += '/'
                unified['outputUrl'] = f"{url}{stream_key}"
            else:
                unified['outputUrl'] = url
            
            # Preserve all RTMP outputs for multi-streaming
            unified['rtmpOutputs'] = [
                {
                    'url': r.get('url'),
                    'streamKey': r.get('stream_key') or r.get('streamKey')
                }
                for r in job_data['rtmp_outputs']
            ]

        # Default to file output if output_file is specified, otherwise HLS
        else:
            if 'output_file' in job_data and job_data['output_file']:
                # File output - detect format from file extension
                file_path = job_data['output_file']
                if file_path.endswith('.mp4'):
                    unified['outputFormat'] = 'mp4'
                elif file_path.endswith('.mkv'):
                    unified['outputFormat'] = 'mkv'
                elif file_path.endswith('.webm'):
                    unified['outputFormat'] = 'webm'
                elif file_path.endswith('.avi'):
                    unified['outputFormat'] = 'avi'
                elif file_path.endswith('.mov'):
                    unified['outputFormat'] = 'mov'
                else:
                    unified['outputFormat'] = 'mp4'  # Default to mp4 for file outputs
                unified['outputDir'] = file_path.rsplit('/', 1)[0]  # Extract directory
                unified['outputUrl'] = file_path  # Store full file path
            else:
                # Default to HLS
                unified['outputFormat'] = 'hls'
                unified['outputDir'] = '/output/hls'

        # Set required defaults if missing
        unified.setdefault('jobName', 'Unnamed Job')
        unified.setdefault('inputFile', job_data.get('input_file', ''))
        unified.setdefault('videoCodec', 'h264')
        unified.setdefault('audioCodec', 'aac')
        unified.setdefault('audioBitrate', '128k')

        logger.info(f"[_convert_to_unified_format] Final unified config: videoCodec={unified.get('videoCodec')}, outputFormat={unified.get('outputFormat')}, outputDir={unified.get('outputDir')}")

        return unified

    # Unified Configuration API (Feature: 001-edit-api-simplification)
    # ========================================================================

    async def get_job_unified(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job configuration as unified object (simplified edit API).

        This method implements a cache-first strategy:
        1. Try to load from full_config cache (fast path)
        2. If cache miss, build from normalized tables and cache it

        Args:
            job_id: Job identifier

        Returns:
            Unified configuration dictionary or None if job not found

        Feature: 001-edit-api-simplification
        """
        # Try cache first (fast path)
        row = await self.db.fetch_one(
            "SELECT full_config FROM encoding_jobs WHERE id = ?",
            (job_id,)
        )

        if row and row['full_config']:
            # Cache hit - return JSON directly
            logger.debug(f"Cache hit for job {job_id}")
            return json.loads(row['full_config'])

        # Cache miss - build from normalized tables
        logger.debug(f"Cache miss for job {job_id}, building from tables")
        job_data = await self.get_job_with_config(job_id)

        if not job_data:
            return None

        # Convert to unified format using config_mapper
        from services.config_mapper import config_mapper
        unified = config_mapper.to_unified_format(job_data)

        # Update cache for next time
        await self._update_config_cache(job_id, unified)

        return unified

    async def create_job_unified(self, config: Dict[str, Any]) -> str:
        """
        Create a new job using unified configuration (simplified create API).

        This method creates a job from a single unified configuration object,
        replacing the legacy three-object (job/input/output) pattern.

        Behavior:
        - Generates job ID automatically (UUID)
        - Converts unified config to legacy format for table inserts
        - Inserts into all 3 normalized tables (backward compatibility)
        - Generates FFmpeg command
        - Populates full_config cache immediately

        Args:
            config: Unified configuration dictionary

        Returns:
            str: Generated job ID

        Raises:
            ValueError: If validation fails

        Feature: 001-edit-api-simplification (Phase 7)
        """
        from uuid import uuid4
        from datetime import datetime

        # Generate job ID
        job_id = str(uuid4())
        config['id'] = job_id

        # Set defaults for fields not provided
        config.setdefault('status', 'pending')
        config.setdefault('createdAt', datetime.utcnow().isoformat())
        config.setdefault('updatedAt', datetime.utcnow().isoformat())

        # Validate configuration
        from services.validators.unified_config_validator import validator
        errors = validator.validate(config)

        if errors:
            error_messages = [f"{e.field}: {e.message}" for e in errors]
            raise ValueError(f"Validation failed: {', '.join(error_messages)}")

        # Generate FFmpeg command
        command = self._build_command_from_unified_config(config, job_id)
        config['ffmpegCommand'] = command

        # Convert unified to legacy format for table inserts
        legacy = config_mapper.to_legacy_format(config)
        job_fields = legacy['job']
        input_fields = legacy['input']
        output_fields = legacy['output']

        # Feature 008: Fix base_path to include job_id (matching FFmpeg command)
        # The command builder appends job_id, so normalized tables should match
        output_format = config.get('outputFormat', 'hls')
        if output_format == 'hls':
            base_output_dir = config.get('outputDir', '/output/hls')
            if job_id not in base_output_dir:
                output_fields['base_path'] = f'{base_output_dir.rstrip("/")}/{job_id}'
            else:
                output_fields['base_path'] = base_output_dir
        elif output_format in ['mp4', 'webm', 'mkv', 'avi', 'mov']:
            # File output - ensure job_id in path
            base_output_path = config.get('outputDir', f'/output/files/{job_id}/output.{output_format}')
            if job_id not in base_output_path:
                if base_output_path.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    dir_part = base_output_path.rsplit('/', 1)[0] if '/' in base_output_path else '/output/files'
                    file_part = base_output_path.rsplit('/', 1)[1] if '/' in base_output_path else base_output_path
                    output_fields['base_path'] = f'{dir_part}/{job_id}/{file_part}'
                else:
                    output_fields['base_path'] = f'{base_output_path.rstrip("/")}/{job_id}'
            else:
                output_fields['base_path'] = base_output_path

        # Prepare INSERT values
        async with self.db.get_connection() as conn:
            await conn.execute("BEGIN")

            try:
                # Insert into encoding_jobs table
                await conn.execute(
                    """
                    INSERT INTO encoding_jobs (
                        id, name, status, command, full_config, created_at,
                        video_codec, audio_codec, video_bitrate, audio_bitrate,
                        hardware_accel, audio_volume, custom_args
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        job_fields.get('name'),
                        job_fields.get('status', 'pending'),
                        command,
                        json.dumps(config, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)),
                        config.get('createdAt'),
                        job_fields.get('video_codec'),
                        job_fields.get('audio_codec'),
                        job_fields.get('video_bitrate'),
                        job_fields.get('audio_bitrate'),
                        job_fields.get('hardware_accel'),
                        job_fields.get('audio_volume'),
                        job_fields.get('custom_args')
                    )
                )

                # Insert into input_sources table
                await conn.execute(
                    """
                    INSERT INTO input_sources (
                        job_id, type, url, loop_enabled
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        input_fields.get('type', 'file'),
                        input_fields.get('url'),
                        input_fields.get('loop_enabled', False)
                    )
                )

                # Insert into output_configurations table
                await conn.execute(
                    """
                    INSERT INTO output_configurations (
                        job_id, output_type, base_path, output_url,
                        video_codec, video_bitrate, video_resolution, video_framerate,
                        encoding_preset, video_profile, profile, level,
                        audio_codec, audio_bitrate, audio_channels, audio_volume,
                        segment_duration, playlist_type, playlist_size,
                        segment_type, segment_pattern,
                        abr_enabled, renditions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        output_fields.get('output_type', 'hls'),
                        output_fields.get('base_path'),
                        output_fields.get('output_url'),
                        output_fields.get('video_codec'),
                        output_fields.get('video_bitrate'),
                        output_fields.get('video_resolution'),
                        output_fields.get('video_framerate'),
                        output_fields.get('encoding_preset'),
                        output_fields.get('video_profile'),
                        output_fields.get('profile'),
                        output_fields.get('level'),
                        output_fields.get('audio_codec'),
                        output_fields.get('audio_bitrate'),
                        output_fields.get('audio_channels'),
                        output_fields.get('audio_volume'),
                        output_fields.get('segment_duration', 6),
                        output_fields.get('playlist_type', 'vod'),
                        output_fields.get('playlist_size', 5),
                        output_fields.get('segment_type', 'mpegts'),
                        output_fields.get('segment_pattern', 'segment_%03d.ts'),
                        output_fields.get('abr_enabled', False),
                        output_fields.get('renditions')
                    )
                )

                await conn.commit()
                logger.info(f"Created job {job_id} using unified API")

            except Exception as e:
                await conn.rollback()
                logger.error(f"Failed to create job {job_id}: {e}", exc_info=True)
                raise

        return job_id

    async def update_job_unified(self, job_id: str, config: Dict[str, Any]) -> None:
        """
        Update job using unified configuration (simplified edit API).

        This method updates both the normalized tables (for backward compatibility)
        and the full_config cache in a single transaction.

        Args:
            job_id: Job identifier
            config: Unified configuration dictionary

        Raises:
            ValueError: If validation fails

        Feature: 001-edit-api-simplification
        """
        # Validate configuration
        from services.validators.unified_config_validator import validator
        errors = validator.validate(config)

        if errors:
            error_messages = [f"{e.field}: {e.message}" for e in errors]
            raise ValueError(
                f"Configuration validation failed:\n" + "\n".join(error_messages)
            )

        # Convert unified format to legacy format for database update
        from services.config_mapper import config_mapper
        legacy_format = config_mapper.to_legacy_format(config)

        # Feature 008: Fix base_path to include job_id (matching FFmpeg command)
        output_format = config.get('outputFormat', 'hls')
        if output_format == 'hls':
            base_output_dir = config.get('outputDir', '/output/hls')
            if job_id not in base_output_dir:
                legacy_format['output']['base_path'] = f'{base_output_dir.rstrip("/")}/{job_id}'
            else:
                legacy_format['output']['base_path'] = base_output_dir
        elif output_format in ['mp4', 'webm', 'mkv', 'avi', 'mov']:
            base_output_path = config.get('outputDir', f'/output/files/{job_id}/output.{output_format}')
            if job_id not in base_output_path:
                if base_output_path.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                    dir_part = base_output_path.rsplit('/', 1)[0] if '/' in base_output_path else '/output/files'
                    file_part = base_output_path.rsplit('/', 1)[1] if '/' in base_output_path else base_output_path
                    legacy_format['output']['base_path'] = f'{dir_part}/{job_id}/{file_part}'
                else:
                    legacy_format['output']['base_path'] = f'{base_output_path.rstrip("/")}/{job_id}'
            else:
                legacy_format['output']['base_path'] = base_output_path

        # Update all three tables + cache in a transaction
        async with self.db.get_connection() as conn:
            await conn.execute("BEGIN")

            try:
                # Update encoding_jobs table
                job_fields = legacy_format['job']
                job_fields.pop('id', None)  # Don't update ID
                job_fields.pop('updated_at', None)  # Column doesn't exist in current schema
                job_fields.pop('created_at', None)  # Don't update created_at

                if job_fields:
                    job_set_clause = ', '.join([f"{k} = ?" for k in job_fields.keys()])
                    job_values = list(job_fields.values()) + [job_id]
                    await conn.execute(
                        f"UPDATE encoding_jobs SET {job_set_clause} WHERE id = ?",
                        job_values
                    )

                # Update input_sources table
                input_fields = legacy_format['input']
                input_fields.pop('job_id', None)  # Don't update job_id

                if input_fields:
                    input_set_clause = ', '.join([f"{k} = ?" for k in input_fields.keys()])
                    input_values = list(input_fields.values()) + [job_id]
                    await conn.execute(
                        f"UPDATE input_sources SET {input_set_clause} WHERE job_id = ?",
                        input_values
                    )

                # Update output_configurations table
                output_fields = legacy_format['output']
                output_fields.pop('job_id', None)  # Don't update job_id

                if output_fields:
                    output_set_clause = ', '.join([f"{k} = ?" for k in output_fields.keys()])
                    output_values = list(output_fields.values()) + [job_id]
                    await conn.execute(
                        f"UPDATE output_configurations SET {output_set_clause} WHERE job_id = ?",
                        output_values
                    )

                # Regenerate FFmpeg command based on new configuration
                # Phase 7: Removed config merge that was overwriting updates with old cache
                new_command = self._build_command_from_unified_config(config, job_id)
                if new_command:
                    # Add command to config so it's included in cache
                    config['ffmpegCommand'] = new_command

                    await conn.execute(
                        "UPDATE encoding_jobs SET command = ? WHERE id = ?",
                        (new_command, job_id)
                    )
                    logger.info(f"Regenerated FFmpeg command for job {job_id}")

                # Update full_config cache (with datetime serialization and command included)
                def json_serializer(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    raise TypeError(f"Type {type(obj)} not serializable")

                await conn.execute(
                    "UPDATE encoding_jobs SET full_config = ? WHERE id = ?",
                    (json.dumps(config, default=json_serializer), job_id)
                )

                await conn.commit()
                logger.info(f"Updated job {job_id} using unified API (cache + normalized tables + command)")

            except Exception as e:
                await conn.rollback()
                logger.error(f"Failed to update job {job_id}: {e}", exc_info=True)
                raise

    def _build_command_from_unified_config(self, config: Dict[str, Any], job_id: str) -> str:
        """
        Build FFmpeg command from unified configuration.

        This is a simplified command builder that works directly with unified config.
        For ABR jobs, delegates to build_ffmpeg_command for proper multi-variant handling.

        Args:
            config: Unified configuration dictionary
            job_id: Job identifier (for output path generation)

        Returns:
            FFmpeg command string

        Feature: 001-edit-api-simplification
        """
        import shlex

        # If ABR is enabled, use proper ABR builder (handles filter_complex for multi-variant)
        if config.get('abrEnabled') and config.get('abrLadder'):
            from models.encoding_settings import CreateJobRequest, HLSOutput, UDPOutput
            from models.rendition import RenditionCreate
            from services.ffmpeg.command_builder import build_ffmpeg_command

            # Map camelCase to snake_case and create RenditionCreate objects
            # Use main job's codec/audio settings as defaults for renditions
            main_video_codec = config.get('videoCodec', 'h264')
            main_audio_codec = config.get('audioCodec', 'aac')
            main_audio_bitrate = config.get('audioBitrate', '128k')

            renditions_create = []
            for r in config.get('abrLadder', []):
                # Determine video codec for this rendition
                rendition_codec = r.get('videoCodec', main_video_codec)

                # Set default profile based on codec (AV1 doesn't support "main" profile)
                if rendition_codec in ['av1', 'libaom-av1']:
                    default_profile = None  # AV1 uses different profile system
                else:
                    default_profile = 'main'  # H.264/H.265 default

                # Get audio volume from rendition or fall back to main job config
                main_audio_volume = config.get('audioVolume')
                rendition_audio_volume = r.get('audioVolume', main_audio_volume)

                rendition_data = {
                    'name': r.get('name', ''),
                    'video_bitrate': r.get('videoBitrate', ''),
                    'video_resolution': r.get('videoResolution', '1920x1080'),
                    'video_framerate': r.get('videoFrameRate') or config.get('videoFrameRate'),  # Fall back to main job FPS
                    'video_codec': rendition_codec,  # Use main job codec if not specified
                    'video_profile': r.get('videoProfile', default_profile),
                    'audio_codec': r.get('audioCodec', main_audio_codec),  # Use main job audio codec
                    'audio_bitrate': r.get('audioBitrate', main_audio_bitrate),  # Use main job audio bitrate
                    'audio_channels': r.get('audioChannels') or config.get('audioChannels', 2),  # Fall back to main job channels
                    'audio_sample_rate': r.get('audioSampleRate', 48000),
                    'audio_volume': rendition_audio_volume,  # Audio volume percentage (0-100)
                    'preset': r.get('videoPreset') or config.get('videoPreset', 'medium'),  # Fall back to main job preset
                    'max_bitrate': r.get('maxBitrate'),
                    'buffer_size': r.get('bufferSize'),
                    'output_url': r.get('outputUrl'),  # For UDP ABR: each rendition can have its own output URL
                }
                renditions_create.append(RenditionCreate(**rendition_data))

            # Convert simplified codec names to FFmpeg format
            codec_map = {'h264': 'libx264', 'h265': 'libx265', 'vp9': 'libvpx-vp9', 'av1': 'libaom-av1'}
            video_codec = config.get('videoCodec', 'h264')
            video_codec = codec_map.get(video_codec, video_codec)  # Convert h264 -> libx264

            # Check output format to determine HLS or UDP
            output_format = config.get('outputFormat', 'hls')

            if output_format == 'udp':
                # ABR UDP: Create UDP outputs from first rendition's outputUrl or main outputUrl
                # Parse the base UDP URL from the main outputUrl or first rendition
                import re
                base_udp_url = config.get('outputUrl')
                if not base_udp_url and config.get('abrLadder'):
                    # Use first rendition's outputUrl as base
                    base_udp_url = config['abrLadder'][0].get('outputUrl')

                if not base_udp_url:
                    raise ValueError("UDP output format requires outputUrl")

                # Parse UDP URL to create UDPOutput object
                udp_match = re.match(r'udp://([^:]+):(\d+)(?:\?ttl=(\d+))?', base_udp_url)
                if not udp_match:
                    raise ValueError(f"Invalid UDP URL format: {base_udp_url}")

                address = udp_match.group(1)
                port = int(udp_match.group(2))
                ttl = int(udp_match.group(3)) if udp_match.group(3) else 64

                udp_output = UDPOutput(address=address, port=port, ttl=ttl)

                # Convert streamMaps format (camelCase dict) to StreamMap objects
                stream_maps = []
                if config.get('streamMaps'):
                    from models.encoding_settings import StreamMap
                    for sm in config.get('streamMaps', []):
                        stream_maps.append(StreamMap(
                            input_stream=sm.get('input_stream'),
                            output_label=sm.get('output_label')
                        ))

                request = CreateJobRequest(
                    input_file=config.get('inputFile', ''),
                    loop_input=config.get('loopInput', False),
                    input_format=config.get('inputFormat'),
                    input_args=config.get('inputArgs', []),
                    video_codec=video_codec,
                    audio_codec=config.get('audioCodec', 'aac'),
                    hardware_accel=config.get('hardwareAccel'),
                    udp_outputs=[udp_output],
                    abr_enabled=True,
                    abr_renditions=renditions_create,
                    stream_maps=stream_maps,
                )
            else:
                # ABR HLS: Create HLS output configuration
                # Feature 008: Ensure job_id is included in ABR HLS output path
                base_output_dir = config.get('outputDir', '/output/hls')
                if job_id not in base_output_dir:
                    abr_output_dir = f'{base_output_dir.rstrip("/")}/{job_id}'
                else:
                    abr_output_dir = base_output_dir

                hls_output = HLSOutput(
                    output_dir=abr_output_dir,
                    segment_duration=config.get('hlsSegmentDuration', 6),
                    playlist_type=config.get('hlsPlaylistType', 'event'),
                    segment_type=config.get('hlsSegmentType', 'mpegts'),
                    segment_pattern=config.get('hlsSegmentFilename', 'segment_%03d.ts'),
                    abr_enabled=True,
                    renditions=renditions_create,
                )

                # Convert streamMaps format (camelCase dict) to StreamMap objects
                stream_maps = []
                if config.get('streamMaps'):
                    from models.encoding_settings import StreamMap
                    for sm in config.get('streamMaps', []):
                        stream_maps.append(StreamMap(
                            input_stream=sm.get('input_stream'),
                            output_label=sm.get('output_label')
                        ))

                request = CreateJobRequest(
                    input_file=config.get('inputFile', ''),
                    loop_input=config.get('loopInput', False),
                    input_format=config.get('inputFormat'),
                    input_args=config.get('inputArgs', []),
                    video_codec=video_codec,
                    audio_codec=config.get('audioCodec', 'aac'),
                    hardware_accel=config.get('hardwareAccel'),
                    hls_output=hls_output,
                    abr_enabled=True,
                    abr_renditions=renditions_create,
                    stream_maps=stream_maps,
                )

            cmd_list = build_ffmpeg_command(request)
            cmd_list = build_ffmpeg_command(request)
            cmd_str = shlex.join(cmd_list)
            # Hack to quote 0:0 for avfoundation if requested (visual only, shlex.split removes it)
            if config.get('inputFormat') == 'avfoundation' and config.get('inputFile') == '0:0':
                 cmd_str = cmd_str.replace(' -i 0:0', ' -i "0:0"')
            return cmd_str

        # Simple single-bitrate builder for non-ABR jobs
        cmd = ['ffmpeg']

        # Hardware acceleration (must be BEFORE input)
        hw_accel = config.get('hardwareAccel', 'none')
        if hw_accel and hw_accel != 'none':
            if hw_accel == 'nvenc':
                cmd.extend(['-hwaccel', 'cuda'])
            elif hw_accel == 'vaapi':
                cmd.extend(['-hwaccel', 'vaapi'])
            elif hw_accel == 'videotoolbox':
                cmd.extend(['-hwaccel', 'videotoolbox'])

        # Input with loop (must be BEFORE input for continuous streaming)
        if config.get('loopInput'):
            cmd.extend(['-stream_loop', '-1'])
            cmd.append('-re')  # Read input at native framerate (real-time)

        # Input format
        if config.get('inputFormat'):
            cmd.extend(['-f', config['inputFormat']])

        # Input args
        if config.get('inputArgs'):
            cmd.extend(config['inputArgs'])

        # Input file
        cmd.extend(['-i', config.get('inputFile', '')])

        # Track mapping (use streamMaps if provided, otherwise default to first video/audio streams)
        stream_maps = config.get('streamMaps', [])
        has_audio_map = False
        if stream_maps:
            # Use explicit track selection from streamMaps
            for stream_map in stream_maps:
                cmd.extend(['-map', stream_map.get('input_stream')])
                if stream_map.get('output_label') == 'a':
                    has_audio_map = True
        else:
            # Default: map first video and first audio stream
            cmd.extend(['-map', '0:v:0', '-map', '0:a:0'])
            has_audio_map = True

        # Video codec and settings
        video_codec = config.get('videoCodec', 'h264')
        actual_codec = None

        # Hardware encoder codec mapping
        hw_codec_map = {
            'nvenc': {
                'h264': 'h264_nvenc', 'libx264': 'h264_nvenc',
                'h265': 'hevc_nvenc', 'hevc': 'hevc_nvenc', 'libx265': 'hevc_nvenc',
                'av1': 'av1_nvenc', 'libaom-av1': 'av1_nvenc',
            },
            'vaapi': {
                'h264': 'h264_vaapi', 'libx264': 'h264_vaapi',
                'h265': 'hevc_vaapi', 'hevc': 'hevc_vaapi', 'libx265': 'hevc_vaapi',
                'av1': 'av1_vaapi', 'libaom-av1': 'av1_vaapi',
            },
            'videotoolbox': {
                'h264': 'h264_videotoolbox', 'libx264': 'h264_videotoolbox',
                'h265': 'hevc_videotoolbox', 'hevc': 'hevc_videotoolbox', 'libx265': 'hevc_videotoolbox',
                # Note: AV1 is not supported by VideoToolbox
            },
        }

        if hw_accel and hw_accel != 'none' and hw_accel in hw_codec_map:
            actual_codec = hw_codec_map[hw_accel].get(video_codec, f'{video_codec}_{hw_accel}')
            cmd.extend(['-c:v', actual_codec])
        else:
            # Software codec: Map simplified codec to FFmpeg lib name
            codec_map = {'h264': 'libx264', 'h265': 'libx265', 'vp9': 'libvpx-vp9', 'av1': 'libaom-av1'}
            actual_codec = codec_map.get(video_codec, 'libx264')
            cmd.extend(['-c:v', actual_codec])

        # Add video codec tag for HEVC compatibility (hvc1 works better than hev1 on Apple devices)
        if 'hevc' in actual_codec.lower() or 'h265' in video_codec.lower() or '265' in video_codec.lower():
            cmd.extend(['-tag:v', 'hvc1'])

        # Video encoding settings
        if config.get('videoBitrate'):
            cmd.extend(['-b:v', config['videoBitrate']])

        if config.get('videoFrameRate'):
            cmd.extend(['-r', str(config['videoFrameRate'])])

        if config.get('videoPreset'):
            cmd.extend(['-preset', config['videoPreset']])

        if config.get('videoProfile'):
            cmd.extend(['-profile:v', config['videoProfile']])

        # Video filters (scale uses -vf for consistency with command_builder.py)
        filters = []
        if config.get('videoResolution'):
            filters.append(f"scale={config['videoResolution']}")
        if config.get('videoFilters'):
            filters.append(config['videoFilters'])
        if filters:
            cmd.extend(['-vf', ','.join(filters)])

        # GOP (Group of Pictures) size - keyframe interval
        if config.get('videoGOP'):
            cmd.extend(['-g', str(config['videoGOP'])])

        # Audio handling - check if audio stream map exists
        # If stream_maps is defined but has no audio map, it means audio is intentionally disabled
        if stream_maps and not has_audio_map:
            # Disable audio completely
            cmd.append('-an')
        else:
            # Audio codec
            audio_codec = config.get('audioCodec', 'aac')
            if audio_codec == 'copy':
                cmd.extend(['-c:a', 'copy'])
            else:
                cmd.extend(['-c:a', audio_codec])

                if config.get('audioBitrate'):
                    cmd.extend(['-b:a', config['audioBitrate']])

                if config.get('audioChannels'):
                    cmd.extend(['-ac', str(config['audioChannels'])])

                # Audio volume filter (0-100 percentage)
                audio_volume = config.get('audioVolume')
                if audio_volume is not None and audio_volume != 100:
                    # Convert percentage to volume factor (0-100 → 0.0-1.0)
                    volume_factor = audio_volume / 100.0
                    cmd.extend(['-af', f'volume={volume_factor}'])

        # Output based on format
        output_format = config.get('outputFormat', 'hls')

        if output_format == 'hls':
            # HLS output - ensure job_id is in path for segment isolation
            base_output_dir = config.get('outputDir', '/output/hls')

            # Feature 008: Ensure job_id is included in HLS output path
            # This prevents segment conflicts between jobs
            if job_id not in base_output_dir:
                output_dir = f'{base_output_dir.rstrip("/")}/{job_id}'
            else:
                output_dir = base_output_dir

            # FFmpeg only supports 'vod' and 'event' for hls_playlist_type
            # 'live' mode is achieved using 'event' + rolling playlist
            playlist_type = config.get('hlsPlaylistType', 'vod')

            cmd.extend([
                '-f', 'hls',
                '-hls_time', str(config.get('hlsSegmentDuration', 6)),
            ])

            # Set segment type: mpegts (universal) or fmp4 (required for HEVC/AV1)
            # FFmpeg automatically sets EXT-X-VERSION based on segment type and codec
            # - mpegts → Version 3 (H.264 compatible)
            # - fmp4 → Version 7 (HEVC/AV1 compatible)
            segment_type = config.get('hlsSegmentType', 'mpegts')
            cmd.extend(['-hls_segment_type', segment_type])

            # Set fmp4 init filename if using fragmented MP4
            if segment_type == 'fmp4':
                cmd.extend(['-hls_fmp4_init_filename', 'init.mp4'])

            if playlist_type == 'live':
                # For live rolling window: use list_size + delete_segments without playlist_type
                cmd.extend([
                    '-hls_list_size', str(config.get('hlsPlaylistSize', 10)),
                    '-hls_flags', 'delete_segments',
                ])
            else:
                # VOD or Event: set playlist_type
                cmd.extend(['-hls_playlist_type', playlist_type])

            cmd.extend([
                '-hls_segment_filename', f'{output_dir}/{config.get("hlsSegmentFilename", "segment_%03d.ts")}',
                f'{output_dir}/master.m3u8'
            ])
        elif output_format == 'udp':
            # UDP output
            if config.get('udpOutputs'):
                for udp in config['udpOutputs']:
                    udp_url = udp.get('url', '')
                    if udp_url:
                        cmd.extend(['-f', 'mpegts', udp_url])
            else:
                output_url = config.get('outputUrl', 'udp://239.1.1.1:5000')
                cmd.extend(['-f', 'mpegts', output_url])
        elif output_format == 'rtmp':
            # RTMP output
            if config.get('rtmpOutputs'):
                for rtmp in config['rtmpOutputs']:
                    url = rtmp.get('url', '')
                    key = rtmp.get('streamKey', '')
                    full_url = url
                    if key and key not in url:
                        if not full_url.endswith('/'):
                            full_url += '/'
                        full_url += key
                    
                    if full_url:
                        cmd.extend(['-f', 'flv', full_url])
            else:
                output_url = config.get('outputUrl', '')
                cmd.extend(['-f', 'flv', output_url])
        elif output_format in ['mp4', 'mkv', 'webm', 'avi', 'mov']:
            # File output (mp4, webm, etc.)
            # Use outputUrl if specified, otherwise use outputDir
            output_url = config.get('outputUrl')
            if output_url:
                # If outputUrl is provided, use it directly
                output_path = output_url
            else:
                # Feature 008: Ensure job_id is in path for file isolation
                base_output_path = config.get('outputDir', f'/output/files/{job_id}/output.mp4')

                # If path doesn't include job_id, add it
                if job_id not in base_output_path:
                    # Check if it's a directory or full file path
                    if base_output_path.endswith(('.mp4', '.webm', '.mkv', '.avi', '.mov')):
                        # It's a file path - insert job_id before filename
                        dir_part = base_output_path.rsplit('/', 1)[0] if '/' in base_output_path else '/output/files'
                        file_part = base_output_path.rsplit('/', 1)[1] if '/' in base_output_path else base_output_path
                        output_path = f'{dir_part}/{job_id}/{file_part}'
                    else:
                        # It's a directory - append job_id and filename
                        output_path = f'{base_output_path.rstrip("/")}/{job_id}/output.mp4'
                else:
                    output_path = base_output_path

            cmd.append(output_path)

        cmd_str = shlex.join(cmd)
        # Hack to quote 0:0 for avfoundation if requested (visual only, shlex.split removes it)
        if config.get('inputFormat') == 'avfoundation' and config.get('inputFile') == '0:0':
             cmd_str = cmd_str.replace(' -i 0:0', ' -i "0:0"')
        return cmd_str

    async def _update_config_cache(self, job_id: str, unified_config: Dict[str, Any]) -> None:
        """
        Update the full_config cache for a job.

        Args:
            job_id: Job identifier
            unified_config: Unified configuration dictionary

        Feature: 001-edit-api-simplification
        """
        try:
            # Handle datetime serialization
            def json_serializer(obj):
                """Custom JSON serializer for datetime objects"""
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            await self.db.execute(
                "UPDATE encoding_jobs SET full_config = ? WHERE id = ?",
                (json.dumps(unified_config, default=json_serializer), job_id)
            )
            logger.debug(f"Updated cache for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to update cache for job {job_id}: {e}")
            # Don't raise - cache update failure shouldn't break the operation

    async def update_job_command(self, job_id: str, command: str) -> None:
        """
        Update the FFmpeg command for a job directly.

        This allows manual editing of the FFmpeg command without regenerating
        it from the configuration. The custom command is stored and used
        when starting the job.

        Args:
            job_id: Job identifier
            command: New FFmpeg command string

        Raises:
            ValueError: If job not found or cannot be edited
        """
        job = await self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status == JobStatus.RUNNING:
            raise ValueError("Cannot edit command while job is running")

        async with self.db.get_connection() as conn:
            try:
                # Update the command in encoding_jobs table
                await conn.execute(
                    "UPDATE encoding_jobs SET command = ? WHERE id = ?",
                    (command, job_id)
                )

                # Also update the command in full_config cache
                row = await conn.execute(
                    "SELECT full_config FROM encoding_jobs WHERE id = ?",
                    (job_id,)
                )
                result = await row.fetchone()
                if result and result[0]:
                    config = json.loads(result[0])
                    config['ffmpegCommand'] = command
                    await conn.execute(
                        "UPDATE encoding_jobs SET full_config = ? WHERE id = ?",
                        (json.dumps(config), job_id)
                    )

                await conn.commit()
                logger.info(f"Updated custom FFmpeg command for job {job_id}")

            except Exception as e:
                await conn.rollback()
                logger.error(f"Failed to update command for job {job_id}: {e}", exc_info=True)
                raise


# Global instance
job_manager = JobManager()# $(date)
