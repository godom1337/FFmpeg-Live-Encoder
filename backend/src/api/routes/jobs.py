"""
Job Management API Endpoints
Handles CRUD operations and control for encoding jobs
"""

from fastapi import APIRouter, HTTPException, Query, Body, Depends, Request, Response
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
import logging
import json
import asyncio
from pathlib import Path

from models.job import EncodingJob, EncodingJobCreate, EncodingJobUpdate, JobStatus
from models.input import InputSourceCreate
from models.output import OutputConfigurationCreate, OutputConfiguration
from services.job_manager import job_manager
from services.validators.job_validator import JobValidator
from services.validators.output_validator import OutputValidator
from services.ffmpeg import ffmpeg_launcher
from services.simple_ffmpeg import simple_ffmpeg_launcher
from services.output_manager import output_manager
from services.job_state import job_state_manager
from services.storage import db_service
from services.archives_storage import archives_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


# NOTE: Old POST /api/v1/jobs/ endpoint removed - use POST /api/v1/jobs/create instead
# The old endpoint used EncodingJobCreate/InputSourceCreate/OutputConfigurationCreate models
# New endpoint uses the simplified CreateJobRequest model (see line 1366)


# ============================================================================
# File Browser Endpoints
# IMPORTANT: These must come BEFORE /{job_id} to avoid path conflicts
# ============================================================================

@router.get("/browse/files", tags=["file-browser"])
async def browse_input_files(directory: str = None):
    """
    List files in any directory for file browsing in the UI.

    Args:
        directory: Directory to browse (default: /input if exists, otherwise home directory)

    Returns:
        List of files with metadata (name, size, type, modified time)
    """
    import os
    from pathlib import Path

    try:
        # Determine default directory if not specified
        if directory is None:
            # Try /input first (Docker environment), then fall back to home directory
            if os.path.exists("/input"):
                directory = "/input"
            else:
                directory = str(Path.home())

        # Check if directory exists
        if not os.path.exists(directory):
            raise HTTPException(
                status_code=404,
                detail={"message": f"Directory not found: {directory}"}
            )

        if not os.path.isdir(directory):
            raise HTTPException(
                status_code=400,
                detail={"message": f"Path is not a directory: {directory}"}
            )

        files = []

        # List items in directory
        try:
            dir_items = sorted(os.listdir(directory))
        except PermissionError:
            raise HTTPException(
                status_code=403,
                detail={"message": f"Permission denied: {directory}"}
            )

        for item in dir_items:
            item_path = os.path.join(directory, item)

            try:
                # Skip items we can't access
                if not os.path.exists(item_path):
                    continue

                if os.path.isdir(item_path):
                    # Include directories
                    try:
                        modified = os.path.getmtime(item_path)
                    except (OSError, PermissionError):
                        modified = 0
                    files.append({
                        "name": item,
                        "path": item_path,
                        "type": "directory",
                        "size": 0,
                        "modified": modified
                    })
                else:
                    # Include files only
                    try:
                        size = os.path.getsize(item_path)
                    except (OSError, PermissionError):
                        size = 0
                    try:
                        modified = os.path.getmtime(item_path)
                    except (OSError, PermissionError):
                        modified = 0
                    files.append({
                        "name": item,
                        "path": item_path,
                        "type": "file",
                        "size": size,
                        "modified": modified
                    })
            except (OSError, PermissionError) as e:
                # Skip files/directories we can't access
                logger.debug(f"Skipping inaccessible item {item_path}: {e}")
                continue

        return {
            "directory": directory,
            "files": files,
            "count": len(files)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to browse files in {directory}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to browse files", "error": str(e)}
        )


# ============================================================================
# Template Endpoints (User Story 4)
# IMPORTANT: These must come BEFORE /{job_id} to avoid path conflicts
# ============================================================================

@router.get("/templates")
async def get_all_templates():
    """
    Get all available encoding templates.

    Returns a list of template summaries (lightweight without full settings).
    Templates provide predefined configurations for common encoding scenarios.

    Returns:
        List of template summaries with id, name, description, tags, recommended_use
    """
    from services.ffmpeg.templates import get_all_templates

    try:
        templates = get_all_templates()
        return {"templates": templates}
    except Exception as e:
        logger.error(f"Failed to fetch templates: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to fetch templates", "error": str(e)}
        )


@router.get("/templates/{template_id}")
async def get_template_by_id(template_id: str):
    """
    Get a specific template by ID with full encoding settings.

    Available template IDs:
    - web_streaming: Standard Web Streaming (H.264, 2500k, balanced)
    - high_quality_archive: High-Quality Archive (H.265, 10000k, slow)
    - low_bandwidth_mobile: Low-Bandwidth Mobile (H.264, 800k, 480p)
    - 4k_hdr: 4K HDR (H.265, 25000k, 10-bit)
    - fast_preview: Fast Preview (H.264, 500k, ultrafast, 360p)

    Args:
        template_id: Template identifier

    Returns:
        Full template with all encoding settings
    """
    from services.ffmpeg.templates import get_template_by_id

    try:
        template = get_template_by_id(template_id)

        if template is None:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Template '{template_id}' not found"}
            )

        return template

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch template {template_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to fetch template", "error": str(e)}
        )


# ============================================================================
# JOB LOGS ENDPOINTS (Must come before /{job_id} to avoid route conflicts)
# ============================================================================

# Get job logs endpoint
@router.get("/{job_id}/logs", response_model=Dict[str, Any])
async def get_job_logs(job_id: str):
    """Get all logs for a job

    Returns the complete log content for a job.

    Args:
        job_id: Job ID

    Returns:
        Dict: Log information with full content

    Raises:
        HTTPException: If job not found or log file doesn't exist
    """
    try:
        # Verify job exists
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        # Check if log file exists
        log_file = Path(f"src/logs/{job_id}.log")
        if not log_file.exists():
            return {
                "job_id": job_id,
                "content": "",
                "lines": [],
                "total_lines": 0,
                "log_exists": False,
                "message": "Log file not created yet or job hasn't been started"
            }

        # Read all log content
        with open(log_file, 'r') as f:
            content = f.read()
            lines = content.splitlines()

        return {
            "job_id": job_id,
            "content": content,
            "lines": lines,
            "total_lines": len(lines),
            "log_exists": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get logs for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get logs", "error": str(e)}
        )


# Get job log tail endpoint
@router.get("/{job_id}/logs/tail", response_model=Dict[str, Any])
async def get_job_log_tail(
    job_id: str,
    lines: int = Query(20, ge=1, le=1000, description="Number of lines to return")
):
    """Get the last N lines of a job's log file

    Returns the tail of the job's log file for quick viewing of recent activity.

    Args:
        job_id: Job ID
        lines: Number of lines to return (default: 20, max: 1000)

    Returns:
        Dict: Log tail information

    Raises:
        HTTPException: If job not found or log file doesn't exist
    """
    try:
        # Verify job exists
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        # Check if log file exists
        log_file = Path(f"src/logs/{job_id}.log")
        if not log_file.exists():
            return {
                "job_id": job_id,
                "lines": [],
                "total_lines": 0,
                "log_exists": False,
                "message": "Log file not created yet or job hasn't been started"
            }

        # Read last N lines
        with open(log_file, 'r') as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {
            "job_id": job_id,
            "lines": [line.rstrip('\n') for line in tail_lines],
            "total_lines": len(all_lines),
            "returned_lines": len(tail_lines),
            "log_exists": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get log tail for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get log tail", "error": str(e)}
        )


# Download job log file endpoint
@router.get("/{job_id}/logs/download")
async def download_job_log(job_id: str):
    """Download the complete log file for a job

    Returns the full log file as a downloadable file.

    Args:
        job_id: Job ID

    Returns:
        FileResponse: Log file download

    Raises:
        HTTPException: If job not found or log file doesn't exist
    """
    try:
        # Verify job exists
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        # Check if log file exists
        log_file = Path(f"src/logs/{job_id}.log")
        if not log_file.exists():
            raise HTTPException(
                status_code=404,
                detail={"message": "Log file not found. Job may not have been started yet."}
            )

        # Get job name for filename
        job_name = job_data['job']['name'].replace(' ', '_').replace('/', '_')
        filename = f"{job_name}_{job_id}.log"

        return FileResponse(
            path=str(log_file),
            media_type='text/plain',
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download log for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to download log file", "error": str(e)}
        )


# T033: Create GET /api/v1/jobs/{id} endpoint
@router.get("/{job_id}", response_model=Dict[str, Any])
async def get_job(job_id: str):
    """Get job by ID with full configuration

    Returns complete job information including input and output configuration.

    Args:
        job_id: Job ID

    Returns:
        Dict: Job with input/output configuration

    Raises:
        HTTPException: If job not found
    """
    try:
        job_with_config = await job_manager.get_job_with_config(job_id)

        if not job_with_config:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        return job_with_config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get job", "error": str(e)}
        )


# ============================================================================
# Unified Configuration API (Feature: 001-edit-api-simplification)
# Simplified endpoints using single unified configuration object
# ============================================================================

@router.get("/{job_id}/unified", response_model=Dict[str, Any])
async def get_job_unified(job_id: str):
    """
    Get complete job configuration as unified object (Simplified Edit API).

    This endpoint returns the entire job configuration (job + input + output)
    as a single flat object that can be directly bound to frontend forms.

    Performance: <50ms typical response time (cache hit)

    Args:
        job_id: Job identifier

    Returns:
        Dict: Complete unified job configuration

    Raises:
        HTTPException: 404 if job not found, 500 on error

    Feature: 001-edit-api-simplification
    """
    try:
        config = await job_manager.get_job_unified(job_id)

        if not config:
            raise HTTPException(
                status_code=404,
                detail={"error": "Job not found", "jobId": job_id}
            )

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get unified config for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal server error", "message": str(e)}
        )


@router.put("/{job_id}/unified", response_model=Dict[str, Any])
async def update_job_unified(job_id: str, config: Dict[str, Any]):
    """
    Update complete job configuration using unified object (Simplified Edit API).

    This endpoint accepts the entire job configuration as a single flat object
    and updates all three underlying tables (job, input, output) plus the cache.

    Behavior:
    - Validates entire configuration
    - Updates all three normalized tables (backward compatibility)
    - Regenerates FFmpeg command
    - Updates cache for fast reads

    Constraints:
    - Job must not be in 'running' state
    - All required fields must be present
    - ABR ladder required if abrEnabled is true

    Performance: <50ms typical response time

    Args:
        job_id: Job identifier
        config: Complete unified configuration

    Returns:
        Dict: Status and updated job info

    Raises:
        HTTPException: 404 if job not found, 409 if job is running,
                      400 if validation fails, 500 on error

    Feature: 001-edit-api-simplification
    """
    try:
        # Check job exists
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail={"error": "Job not found", "jobId": job_id}
            )

        # Check job can be edited (not running)
        from services.validators.unified_config_validator import validator
        job_status = job.status.value if hasattr(job.status, 'value') else job.status
        can_edit, error_msg = validator.can_edit_job(job_status)

        if not can_edit:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Job cannot be edited",
                    "status": job_status,
                    "message": error_msg
                }
            )

        # Update job using unified API
        await job_manager.update_job_unified(job_id, config)

        # Get updated job to return command
        updated_job = await job_manager.get_job(job_id)

        return {
            "status": "updated",
            "jobId": job_id,
            "ffmpegCommand": updated_job.command
        }

    except HTTPException:
        raise
    except ValueError as e:
        # Validation errors
        raise HTTPException(
            status_code=400,
            detail={"error": "Validation failed", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to update unified config for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal server error", "message": str(e)}
        )


@router.put("/{job_id}/command", response_model=Dict[str, Any])
async def update_job_command(job_id: str, payload: Dict[str, Any]):
    """
    Update FFmpeg command directly for a job.

    This endpoint allows manual editing of the FFmpeg command without
    regenerating it from the configuration. Useful for advanced users
    who need to tweak specific FFmpeg parameters.

    Constraints:
    - Job must not be in 'running' state
    - Command must start with 'ffmpeg'

    Args:
        job_id: Job identifier
        payload: Dict containing 'command' key with the new FFmpeg command

    Returns:
        Dict: Status and updated command

    Raises:
        HTTPException: 404 if job not found, 409 if job is running,
                      400 if command is invalid
    """
    try:
        command = payload.get('command', '').strip()

        # Basic validation
        if not command:
            raise HTTPException(
                status_code=400,
                detail={"error": "Command is required"}
            )

        if not command.startswith('ffmpeg'):
            raise HTTPException(
                status_code=400,
                detail={"error": "Command must start with 'ffmpeg'"}
            )

        # Check job exists
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail={"error": "Job not found", "jobId": job_id}
            )

        # Check job can be edited (not running)
        job_status = job.status.value if hasattr(job.status, 'value') else job.status
        if job_status == 'running':
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "Job cannot be edited",
                    "status": job_status,
                    "message": "Stop the job before editing the command"
                }
            )

        # Update the command
        await job_manager.update_job_command(job_id, command)

        return {
            "status": "updated",
            "jobId": job_id,
            "command": command
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "Validation failed", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to update command for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal server error", "message": str(e)}
        )


@router.post("/create-unified", response_model=Dict[str, Any], status_code=201)
async def create_job_unified(config: Dict[str, Any]):
    """
    Create a new encoding job using unified configuration (Simplified Create API).

    This endpoint replaces the legacy three-object creation pattern with a single
    unified configuration object. The same format used for editing now works for creation.

    Behavior:
    - Accepts complete configuration as single flat object
    - Generates job ID automatically
    - Validates configuration
    - Checks for duplicate job names (409 Conflict)
    - Creates normalized table records (backward compatibility)
    - Populates cache immediately
    - Generates FFmpeg command

    Performance: <100ms typical response time

    Args:
        config: Complete unified configuration (same format as GET /unified returns)

    Returns:
        Dict: Created job info with jobId and ffmpegCommand

    Raises:
        HTTPException: 400 if validation fails, 409 if duplicate name, 500 on error

    Feature: 008-migrate-unified-db (completes feature 001)
    """
    try:
        # Validate configuration
        from services.validators.unified_config_validator import validator
        is_valid, errors = validator.validate_create_request(config)

        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail={"error": "Validation failed", "details": errors}
            )

        # Check for duplicate job name (Feature 008: FR-009 conflict handling)
        job_name = config.get('jobName')
        if job_name:
            existing_job = await job_manager.get_job_by_name(job_name)
            if existing_job:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "Conflict",
                        "message": f"Job with name '{job_name}' already exists"
                    }
                )

        # Create job using unified API
        job_id = await job_manager.create_job_unified(config)

        # Get created job to return full info
        created_job = await job_manager.get_job(job_id)

        return {
            "status": "created",
            "jobId": job_id,
            "ffmpegCommand": created_job.command
        }

    except HTTPException:
        raise
    except ValueError as e:
        # Validation errors
        raise HTTPException(
            status_code=400,
            detail={"error": "Validation failed", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to create job with unified config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal server error", "message": str(e)}
        )


# T034: Create POST /api/v1/jobs/{id}/start endpoint
@router.post("/{job_id}/start", response_model=Dict[str, Any])
async def start_job(job_id: str):
    """Start an encoding job

    Starts the FFmpeg process for a job that is in PENDING, STOPPED, ERROR,
    or COMPLETED state. Creates output directory structure and launches
    the encoding process.

    Args:
        job_id: Job ID

    Returns:
        Dict: Status response with job info

    Raises:
        HTTPException: If job cannot be started
    """
    try:
        # Get job with configuration
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        job = EncodingJob(**job_data['job'])

        # Check if job can be started
        if not job.can_start():
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Job cannot be started from {job.status} state",
                    "current_status": job.status
                }
            )

        # Get input and output configuration
        if not job_data['input']:
            raise HTTPException(
                status_code=400,
                detail={"message": "Job has no input configuration"}
            )

        if not job_data['output']:
            raise HTTPException(
                status_code=400,
                detail={"message": "Job has no output configuration"}
            )

        from models.input import InputSource
        from models.output import OutputConfiguration

        input_source = InputSource(**job_data['input'])
        output_config = OutputConfiguration(**job_data['output'])

        # Use simple FFmpeg launcher without profiles
        # Output directory will be created by the launcher itself

        # Define callbacks for progress tracking
        async def on_progress(job_id: str, progress: Dict[str, Any]):
            # This would be sent via WebSocket in Phase 4
            logger.debug(f"Job {job_id} progress: {progress}")

        async def on_error(job_id: str, error: str):
            logger.error(f"Job {job_id} error: {error}")
            # Update job status to ERROR
            await job_state_manager.mark_job_error(job, error)

        async def on_complete(job_id: str, exit_code: int):
            logger.info(f"Job {job_id} completed with code {exit_code}")
            # Update job status based on exit code
            if exit_code == 0:
                await job_state_manager.mark_job_completed(job)

                # Finalize HLS playlists with proper type tags (VOD/EVENT/LIVE)
                if output_config.output_type == 'hls':
                    try:
                        from pathlib import Path
                        from services.ffmpeg.playlist_generator import finalize_all_variant_playlists, PlaylistType
                        from models.rendition import Rendition

                        # HLS configuration is directly on OutputConfiguration (from HLSEncodingMixin)
                        # Map playlist_type string to enum
                        playlist_type_str = (output_config.playlist_type or 'vod').upper()
                        try:
                            playlist_type = PlaylistType[playlist_type_str]
                        except KeyError:
                            logger.warning(f"Invalid playlist_type '{playlist_type_str}', defaulting to VOD")
                            playlist_type = PlaylistType.VOD

                        # Get renditions if ABR is enabled
                        if output_config.abr_enabled and output_config.renditions:
                            renditions = [Rendition(**r) if isinstance(r, dict) else r for r in output_config.renditions]

                            # Finalize all variant playlists with proper tags
                            output_dir = Path(output_config.base_path)
                            finalize_all_variant_playlists(output_dir, renditions, playlist_type)
                            logger.info(f"Finalized {len(renditions)} variant playlists with type {playlist_type.value}")
                    except Exception as e:
                        logger.error(f"Failed to finalize HLS playlists: {e}", exc_info=True)
            else:
                await job_state_manager.mark_job_error(job, f"Process exited with code {exit_code}")

        # Use the pre-built FFmpeg command stored in the job
        # DO NOT regenerate the command - use the exact command that was previewed and approved
        logger.info(f"Starting job {job_id} with stored command: {job.command}")

        # Clean up existing output directory to avoid file overlap (same as delete job behavior)
        if output_config.base_path:
            try:
                await output_manager.cleanup_output(output_config)
                logger.info(f"Cleaned up existing output directory before starting job: {output_config.base_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup output directory before starting job (may not exist): {e}")

        # Create output directory structure before starting FFmpeg
        from pathlib import Path
        if output_config.base_path:
            try:
                output_dir = Path(output_config.base_path)
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created output directory: {output_config.base_path}")

                # For ABR jobs, create subdirectories for each rendition
                if output_config.abr_enabled and output_config.renditions:
                    logger.info(f"Creating ABR subdirectories for job {job_id}")
                    for rendition in output_config.renditions:
                        # Handle both dict and object access for rendition
                        rendition_name = rendition.get('name') if isinstance(rendition, dict) else rendition.name
                        if rendition_name:
                            rendition_dir = output_dir / rendition_name
                            rendition_dir.mkdir(parents=True, exist_ok=True)
                            logger.info(f"Created ABR subdirectory: {rendition_dir}")

                    # Generate master playlist immediately
                    try:
                        from services.ffmpeg.playlist_generator import generate_master_playlist
                        from models.rendition import Rendition
                        
                        # Convert dicts to Rendition objects if needed
                        rendition_objs = []
                        for r in output_config.renditions:
                            if isinstance(r, dict):
                                rendition_objs.append(Rendition(**r))
                            else:
                                rendition_objs.append(r)
                                
                        master_path = generate_master_playlist(rendition_objs, output_dir)
                        logger.info(f"Generated master playlist at {master_path}")
                    except Exception as e:
                        logger.error(f"Failed to generate master playlist: {e}")
                        # Don't fail the job start, but log error

            except Exception as e:
                logger.error(f"Failed to create output directory {output_config.base_path}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={"message": f"Failed to create output directory: {str(e)}"}
                )

        # Start FFmpeg process using simple launcher (no profile needed)
        started = await simple_ffmpeg_launcher.start_encoding(
            job, input_source, output_config,
            on_progress, on_error, on_complete
        )

        if not started:
            raise HTTPException(
                status_code=500,
                detail={"message": "Failed to start FFmpeg process"}
            )

        # Get the actual PID from the process manager
        if job_id in simple_ffmpeg_launcher.active_processes:
            actual_pid = simple_ffmpeg_launcher.active_processes[job_id].pid
            logger.info(f"Job {job_id} FFmpeg process started with PID {actual_pid}")
        else:
            actual_pid = job.pid or 0
            logger.warning(f"Job {job_id} not found in active_processes, using job.pid: {actual_pid}")

        # Update job status to RUNNING with the correct PID
        job = await job_state_manager.mark_job_running(job, actual_pid)

        # Simple preview URLs for single stream
        import os
        hls_base_url = os.getenv("HLS_BASE_URL", "http://localhost")
        preview_urls = {
            "master": f"{hls_base_url}/hls/{job_id}/master.m3u8",
            "stream": f"{hls_base_url}/hls/{job_id}/stream/master.m3u8"
        }

        return {
            "status": "started",
            "job": job.dict(),
            "pid": job.pid,
            "output_path": output_config.base_path,
            "preview_urls": preview_urls
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to start job", "error": str(e)}
        )


# Stop job endpoint
@router.post("/{job_id}/stop", response_model=Dict[str, Any])
async def stop_job(job_id: str):
    """Stop a running encoding job

    Stops the FFmpeg process for a running job and updates its status to STOPPED.

    Args:
        job_id: Job ID

    Returns:
        Dict: Status response with job info

    Raises:
        HTTPException: If job cannot be stopped
    """
    try:
        # Get job
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        job = EncodingJob(**job_data['job'])

        # Log current job state for debugging
        logger.info(f"Attempting to stop job {job_id}: current status={job.status}, pid={job.pid}")

        # Check if job is running
        if job.status != JobStatus.RUNNING:
            logger.warning(f"Cannot stop job {job_id} - current status is {job.status}, not RUNNING")
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Job cannot be stopped from {job.status} state",
                    "current_status": job.status,
                    "job_id": job_id
                }
            )

        # Check if process is actually in active_processes or running by PID
        is_in_active = simple_ffmpeg_launcher.is_job_running(job.id, job.pid)
        logger.info(f"Job {job_id} running status: {is_in_active} (checking active_processes and PID {job.pid})")

        # Stop FFmpeg process using simple launcher
        # Pass the PID from database so it can kill orphaned processes
        stopped = await simple_ffmpeg_launcher.stop_encoding(job.id, pid=job.pid)
        logger.info(f"Stop encoding result for job {job_id}: {stopped}")

        # Verify process is actually stopped (check both tracking and PID)
        if simple_ffmpeg_launcher.is_job_running(job.id, job.pid):
            logger.error(f"Job {job_id} still running after stop attempt")
            raise HTTPException(
                status_code=500,
                detail={"message": "Failed to stop FFmpeg process - process still running"}
            )

        # Update job status to STOPPED
        job = await job_state_manager.mark_job_stopped(job)

        logger.info(f"Stopped job {job_id}: {job.name}")

        return {
            "status": "stopped",
            "job": job.dict(),
            "message": f"Job {job.name} has been stopped"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to stop job", "error": str(e)}
        )


# Force kill job endpoint
@router.post("/{job_id}/force-kill", response_model=Dict[str, Any])
async def force_kill_job(job_id: str):
    """Force kill all FFmpeg processes for a job

    This endpoint forcefully terminates all FFmpeg processes associated with a job,
    regardless of the job's current status. Use this when normal stop doesn't work.

    Args:
        job_id: Job ID

    Returns:
        Dict: Status response with killed process count

    Raises:
        HTTPException: If force kill fails
    """
    try:
        # Get job
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        job = EncodingJob(**job_data['job'])

        logger.warning(f"Force killing all processes for job {job_id} (current status: {job.status}, PID: {job.pid})")

        # Use the improved force kill method with PID from database
        killed = await simple_ffmpeg_launcher._force_kill_by_job_id(job_id, job.pid)

        # Also ensure cleanup of tracking dictionaries
        simple_ffmpeg_launcher._cleanup_job(job_id)

        # Update job status to STOPPED if it was running
        if job.status == JobStatus.RUNNING:
            job = await job_state_manager.mark_job_stopped(job)
            logger.info(f"Marked force-killed job {job_id} as STOPPED")

        return {
            "status": "force_killed",
            "job": job.dict(),
            "killed": killed,
            "message": f"Force kill completed for job {job.name}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to force kill job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to force kill job", "error": str(e)}
        )


# Reset job status endpoint
@router.post("/{job_id}/reset-status", response_model=Dict[str, Any])
async def reset_job_status(job_id: str):
    """Reset job status from ERROR/STOPPED/COMPLETED to PENDING

    This allows restarting jobs that have finished or failed.
    Clears error messages and reset timestamps.

    Args:
        job_id: Job ID

    Returns:
        Dict: Job with reset status

    Raises:
        HTTPException: If reset fails or job is running
    """
    try:
        # Get job
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        job = EncodingJob(**job_data['job'])

        # Check if job can be reset
        if job.status == JobStatus.RUNNING:
            raise HTTPException(
                status_code=400,
                detail={"message": "Cannot reset status of a running job. Stop the job first."}
            )

        if job.status == JobStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail={"message": "Job is already in PENDING status."}
            )

        logger.info(f"Resetting job {job_id} status from {job.status} to PENDING")

        # Reset the job status
        reset_job = await job_manager.reset_job_status(job_id)

        return {
            "status": "success",
            "job": reset_job.dict(),
            "message": f"Job '{job.name}' status reset to PENDING"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset job status {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to reset job status", "error": str(e)}
        )


# Delete job endpoint
@router.delete("/{job_id}", response_model=Dict[str, Any])
async def delete_job(job_id: str):
    """Archive (delete) an encoding job

    Moves a job to the archives database instead of permanently deleting it.
    Archived jobs can be restored or permanently deleted later.
    Cannot delete running jobs.

    Args:
        job_id: Job ID

    Returns:
        Dict: Archive confirmation

    Raises:
        HTTPException: If job cannot be archived
    """
    try:
        # Get job with full configuration
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(
                status_code=404,
                detail={"message": f"Job {job_id} not found"}
            )

        job = EncodingJob(**job_data['job'])

        # Check if job is running
        if job.status == JobStatus.RUNNING:
            raise HTTPException(
                status_code=400,
                detail={"message": "Cannot delete a running job. Stop it first."}
            )

        # Archive the job (move to archives database)
        archived = await archives_storage.archive_job(
            job_data=job_data['job'],
            input_data=job_data['input'],
            output_data=job_data['output'],
            reason="manual_deletion"
        )

        if not archived:
            raise HTTPException(
                status_code=500,
                detail={"message": "Failed to archive job"}
            )

        # Now delete from main database
        deleted = await job_manager.delete_job(job_id)

        if not deleted:
            logger.warning(
                f"Job {job_id} was archived but failed to delete from main database"
            )

        # Clean up output directory if exists
        if job_data.get('output'):
            from models.output import OutputConfiguration
            output_config = OutputConfiguration(**job_data['output'])
            await output_manager.cleanup_output(output_config)

        logger.info(f"Archived job {job_id}: {job.name}")

        return {
            "status": "archived",
            "message": f"Job {job.name} has been archived. It can be restored from the Archives tab.",
            "job_id": job_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to archive job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to archive job", "error": str(e)}
        )


# Update job endpoint (DEPRECATED - Feature 008)
@router.patch("/{job_id}", response_model=Dict[str, Any], deprecated=True)
async def update_job(
    job_id: str,
    job_update: Optional[EncodingJobUpdate] = Body(None),
    input_update: Optional[InputSourceCreate] = Body(None),
    output_update: Optional[OutputConfigurationCreate] = Body(None)
):
    """Update an encoding job configuration (DEPRECATED - use PUT /jobs/{id}/unified)

    ⚠️ DEPRECATED: This endpoint uses the legacy three-object update pattern.
    Use PUT /api/v1/jobs/{id}/unified instead for the unified configuration format.

    This endpoint is maintained for backward compatibility but will be removed in a future version.

    Migration Guide:
    - Old: PATCH /jobs/{id} with separate job_update, input_update, output_update
    - New: PUT /jobs/{id}/unified with single unified configuration object

    Feature: 008-migrate-unified-db (deprecated as part of legacy format removal)

    Args:
        job_id: Job ID
        job_update: Job fields to update
        input_update: Input configuration to update
        output_update: Output configuration to update

    Returns:
        Dict: Error message directing to unified endpoint

    Raises:
        HTTPException: 410 Gone - endpoint deprecated
    """
    raise HTTPException(
        status_code=410,
        detail={
            "error": "Endpoint Deprecated",
            "message": "PATCH /api/v1/jobs/{id} is deprecated. Use PUT /api/v1/jobs/{id}/unified instead.",
            "migration": {
                "old_endpoint": f"PATCH /api/v1/jobs/{job_id}",
                "new_endpoint": f"PUT /api/v1/jobs/{job_id}/unified",
                "documentation": "See Feature 008 migration guide for unified configuration format"
            }
        }
    )

# NOTE: Old PATCH implementation removed (Feature 008 - ~480 lines using model_mapper)
# The implementation was deleted as it relied on deprecated model_mapper.py
# All job updates should now use PUT /jobs/{id}/unified endpoint

# Additional endpoint for listing jobs (part of T050 but useful now)
@router.get("/", response_model=List[EncodingJob])
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Skip results")
):
    """List encoding jobs

    Returns a paginated list of jobs, optionally filtered by status.

    Args:
        status: Filter by job status (optional)
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        List[EncodingJob]: List of jobs
    """
    try:
        jobs = await job_manager.list_jobs(status=status, limit=limit, offset=offset)
        return jobs

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to list jobs", "error": str(e)}
        )


# ============================================================================
# NEW MINIMAL JOB CREATION API (Rewrite)
# ============================================================================


@router.post("/validate", status_code=200)
async def validate_job_configuration(request_data: dict = Body(...)):
    """
    Validate job configuration without creating job (dry-run).

    This endpoint performs validation checks including:
    - FFmpeg command syntax validation
    - Hardware acceleration availability
    - Input file accessibility
    - Codec compatibility

    Returns warnings without creating the job.
    """
    from models.encoding_settings import ValidateJobRequest, ValidateJobResponse, ValidationWarning
    from services.ffmpeg.command_builder import build_ffmpeg_command, generate_output_path
    from services.ffmpeg.validator import dry_run_ffmpeg, check_hwaccel_available
    from utils.security import validate_input_path
    from uuid import uuid4

    try:
        # Parse request
        try:
            job_request = ValidateJobRequest(**request_data)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail={"message": "Request validation failed", "error": str(e)}
            )

        warnings = []

        # Validate input file exists
        try:
            validate_input_path(job_request.input_file)
        except ValueError as e:
            warnings.append(ValidationWarning(
                code="invalid_input_path",
                message=str(e),
                severity="error"
            ))

        # Generate a temporary job_id for preview paths (consistent with create endpoint)
        temp_job_id = str(uuid4())

        # Auto-generate HLS directory with job_id: /output/hls/job_id/
        if job_request.hls_output:
            if not job_request.hls_output.output_dir or job_request.hls_output.output_dir == '/output/hls':
                job_request.hls_output.output_dir = f"/output/hls/{temp_job_id}"

        # Generate file output path: /output/files/job_id/filename_encoded.mp4
        # Only generate output_file if not using HLS, UDP, or RTMP outputs
        if not job_request.output_file and not job_request.hls_output and not job_request.udp_outputs and not job_request.rtmp_outputs:
            input_basename = Path(job_request.input_file).stem
            input_ext = Path(job_request.input_file).suffix
            job_request.output_file = f"/output/files/{temp_job_id}/{input_basename}_encoded{input_ext}"

        # Build command
        cmd = build_ffmpeg_command(job_request)
        import shlex
        command_str = shlex.join(cmd)

        # Run hardware acceleration check and dry-run validation in parallel for better performance
        # This reduces latency from sequential execution (7-10s) to parallel execution (3-5s)
        tasks = [dry_run_ffmpeg(cmd)]

        # Only check hardware acceleration if it's explicitly requested
        if job_request.hardware_accel and job_request.hardware_accel != "none":
            tasks.append(check_hwaccel_available(job_request.hardware_accel))
        else:
            tasks.append(asyncio.sleep(0))  # Placeholder for parallel execution

        # Execute both operations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Extract results
        is_valid, error = results[0] if isinstance(results[0], tuple) else (results[0], "")
        hwaccel_result = results[1] if len(results) > 1 and isinstance(results[1], bool) else None

        # Handle hardware acceleration result
        if hwaccel_result is not None and not hwaccel_result:
            warnings.append(ValidationWarning(
                code="hwaccel_unavailable",
                message=f"Hardware acceleration '{job_request.hardware_accel}' is not available on this system. Job will fall back to software encoding.",
                severity="warning"
            ))

        if not is_valid:
            warnings.append(ValidationWarning(
                code="ffmpeg_validation_failed",
                message=error,
                severity="error"
            ))

        # Determine overall validity
        has_errors = any(w.severity == "error" for w in warnings)

        return {
            "valid": is_valid and not has_errors,
            "warnings": [w.dict() for w in warnings],
            "command": command_str,
            "estimated_duration": None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Validation error", "error": str(e)}
        )


@router.post("/metadata/probe", status_code=200)
async def probe_input_metadata(request_data: dict = Body(...)):
    """
    Extract metadata from input file using FFprobe.

    Returns information about:
    - Duration, format, bitrate
    - Video/audio/subtitle tracks with codecs, resolutions, etc.
    """
    from services.ffmpeg.probe import probe_input_file
    from utils.security import validate_input_path

    try:
        file_path = request_data.get("file_path")
        if not file_path:
            raise HTTPException(
                status_code=400,
                detail={"message": "file_path is required"}
            )

        # Validate path
        try:
            validated_path = validate_input_path(file_path)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={"message": str(e)}
            )

        # Probe file
        metadata = await probe_input_file(validated_path)

        return metadata

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"message": "File not found"}
        )
    except Exception as e:
        logger.error(f"Failed to probe file: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to probe file", "error": str(e)}
        )


# ============================================================================
# Job Creation Endpoints
# ============================================================================

@router.post("/create", status_code=201)
async def create_minimal_job(
    request_data: dict = Body(...),
    response: Response = None
):
    """
    Create a new encoding job with minimal configuration (DEPRECATED - use /create-unified).

    ⚠️ DEPRECATION NOTICE:
    This endpoint is deprecated as of Feature 008. Use POST /api/v1/jobs/create-unified instead,
    which provides a unified configuration format consistent with GET/PUT /unified endpoints.

    Migration Guide:
    - Old: POST /create with legacy three-object format
    - New: POST /create-unified with unified single-object format

    This endpoint uses the legacy approach with separate job/input/output objects.
    By default, jobs use H.264 video codec with audio copy.

    Request Body:
        {
            "input_file": "/input/video.mp4",  # Required
            "output_file": "/output/output.mp4",  # Optional (auto-generated if not provided)
            "video_codec": "libx264",  # Optional (default: libx264)
            "audio_codec": "copy"  # Optional (default: copy)
        }

    Returns:
        {
            "job_id": int,
            "status": "pending",
            "command": "ffmpeg -i ...",
            "created_at": "2025-10-20T..."
        }

    Raises:
        400: Invalid file paths or validation errors
        422: Request validation failed

    Feature: 008-migrate-unified-db (deprecation as part of unified migration)
    """
    from models.encoding_settings import CreateJobRequest, CreateJobResponse
    from services.ffmpeg.command_builder import build_ffmpeg_command, generate_output_path
    from utils.security import validate_input_path, validate_output_path
    from datetime import datetime
    from uuid import uuid4

    try:
        # Apply template if provided (User Story 4)
        if "template_id" in request_data and request_data["template_id"]:
            from services.ffmpeg.templates import get_template_by_id

            template_id = request_data.get("template_id")
            template = get_template_by_id(template_id)

            if template is None:
                raise HTTPException(
                    status_code=400,
                    detail={"message": f"Template '{template_id}' not found"}
                )

            # Apply template settings to request data (template values don't override user values)
            request_data = template.apply_to_job(request_data)
            logger.info(f"Applied template '{template_id}' to job request")

        # Parse and validate request
        try:
            # DEBUG: Log what we received
            logger.info(f"[DEBUG_AUDIO_VOLUME] Received request_data: audio_volume={request_data.get('audio_volume')}, audio_channels={request_data.get('audio_channels')}, audio_bitrate={request_data.get('audio_bitrate')}")

            job_request = CreateJobRequest(**request_data)

            # DEBUG: Log what's in the job_request object
            logger.info(f"[DEBUG_AUDIO_VOLUME] After parsing - job_request.audio_volume={job_request.audio_volume}, job_request.audio_channels={job_request.audio_channels}")

            # Additional ABR validation
            if job_request.hls_output and job_request.hls_output.abr_enabled:
                if not job_request.hls_output.renditions or len(job_request.hls_output.renditions) == 0:
                    raise HTTPException(
                        status_code=400,
                        detail={"message": "ABR enabled but no renditions provided. Please select a preset or configure custom variants."}
                    )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Request validation failed: {e}")
            raise HTTPException(
                status_code=422,
                detail={"message": "Request validation failed", "error": str(e)}
            )

        # Validate input file path
        try:
            validated_input = validate_input_path(job_request.input_file)
            job_request.input_file = validated_input
        except ValueError as e:
            logger.error(f"Input path validation failed: {e}")
            raise HTTPException(
                status_code=400,
                detail={"message": str(e)}
            )

        # Generate job ID early so we can use it for directory paths
        from uuid import uuid4
        job_id = str(uuid4())

        # Auto-generate HLS directory: /output/hls/job_id/
        if job_request.hls_output:
            if not job_request.hls_output.output_dir or job_request.hls_output.output_dir == '/output/hls':
                job_request.hls_output.output_dir = f"/output/hls/{job_id}"

        # Generate file output path: /output/files/job_id/filename.mp4
        # Only generate output_file if not using HLS, UDP, or RTMP outputs
        if not job_request.output_file and not job_request.hls_output and not job_request.udp_outputs and not job_request.rtmp_outputs:
            input_basename = Path(job_request.input_file).stem
            input_ext = Path(job_request.input_file).suffix
            job_request.output_file = f"/output/files/{job_id}/{input_basename}_encoded{input_ext}"

        # Validate output file path (only if not using HLS)
        if job_request.output_file:
            try:
                validated_output = validate_output_path(job_request.output_file)
                job_request.output_file = validated_output
            except ValueError as e:
                logger.error(f"Output path validation failed: {e}")
                raise HTTPException(
                    status_code=400,
                    detail={"message": str(e)}
                )

        # Build FFmpeg command
        ffmpeg_command = build_ffmpeg_command(job_request)

        # Use shlex.join() to properly quote arguments with spaces (e.g., filter_complex)
        import shlex
        command_str = shlex.join(ffmpeg_command)

        logger.info(f"Creating minimal job: {command_str}")

        # Note: Output directories will be created when the job is started (in start_job endpoint)
        # This prevents duplicate directory creation

        # Prepare data for unified save method
        # Convert CreateJobRequest to flat dictionary structure
        job_data = {
            'job_name': job_request.job_name or f"Encoding - {Path(job_request.input_file).stem}",
            'input_file': job_request.input_file,
            'output_file': job_request.output_file,
            'loop_input': job_request.loop_input,
            'video_codec': job_request.video_codec,
            'audio_codec': job_request.audio_codec,
            'video_bitrate': job_request.video_bitrate,
            'audio_bitrate': job_request.audio_bitrate,
            'hardware_accel': job_request.hardware_accel,
            'template_id': request_data.get("template_id"),
            'command': command_str,
            'video_framerate': job_request.video_framerate,
            'encoding_preset': job_request.encoding_preset,
            'video_resolution': job_request.video_resolution,
            'video_profile': job_request.video_profile,
            'audio_channels': job_request.audio_channels,
            'audio_volume': job_request.audio_volume,
            'hls_output': job_request.hls_output.dict() if job_request.hls_output else None,
            'udp_outputs': [udp.dict() for udp in job_request.udp_outputs] if job_request.udp_outputs else [],
            'stream_maps': [sm.dict() for sm in job_request.stream_maps] if job_request.stream_maps else [],
            # ABR settings (for UDP/File ABR - HLS ABR is in hls_output)
            'abr_enabled': job_request.abr_enabled,
            'abr_renditions': [r.dict() for r in job_request.abr_renditions] if job_request.abr_renditions else []
        }

        # Debug logging
        # Use the unified save method to create the job
        try:
            created_job = await job_manager.save_job_unified(job_data, job_id=job_id, is_update=False)
            logger.info(f"Job created successfully with unified method: {created_job.id}")

            # For ABR jobs, prepare output directory structure
            if job_request.hls_output and job_request.hls_output.abr_enabled and job_request.hls_output.renditions:
                from models.output import OutputConfiguration
                from models.rendition import Rendition
                from services.output_manager import output_manager
                from services.ffmpeg.playlist_generator import generate_master_playlist

                # Convert RenditionCreate to Rendition objects
                renditions = [Rendition(**r.dict()) for r in job_request.hls_output.renditions]

                # Create output configuration
                output_config = OutputConfiguration(
                    job_id=job_id,
                    abr_enabled=True,
                    renditions=renditions,
                    base_path=job_request.hls_output.output_dir,
                    output_type="hls"
                )

                # Create directory structure
                await output_manager.create_output_structure(output_config)

                # Generate master playlist (will be updated after FFmpeg runs)
                master_path = generate_master_playlist(renditions, Path(job_request.hls_output.output_dir))
                logger.info(f"Created ABR output structure and master playlist: {master_path}")

            # Add deprecation warning headers (Feature 008: FR-012)
            if response:
                response.headers["Deprecation"] = "true"
                response.headers["X-API-Warn"] = "DEPRECATED: Use POST /api/v1/jobs/create-unified instead"
                response.headers["Link"] = '</api/v1/jobs/create-unified>; rel="alternate"'

            # Return response (matching existing job structure)
            return {
                "job_id": created_job.id,  # UUID string (matches existing system)
                "status": created_job.status,
                "command": created_job.command or command_str,
                "created_at": created_job.created_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to create job using unified method: {e}")
            raise HTTPException(
                status_code=500,
                detail={"message": "Failed to save job", "error": str(e)}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create minimal job: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to create job", "error": str(e)}
        )
