"""
Archives Management API Endpoints

Handles operations for archived (deleted) jobs including:
- Listing archived jobs
- Viewing archived job details
- Restoring archived jobs back to active jobs
- Permanently deleting archived jobs
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging
import json

from services.archives_storage import archives_storage
from services.job_manager import job_manager
from services.storage import db_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/archives", tags=["archives"])


@router.get("/", response_model=Dict[str, Any])
async def list_archived_jobs(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    order_by: str = Query("archived_at DESC", description="Sort order")
):
    """
    List all archived jobs.

    Returns paginated list of archived jobs with their full configuration.

    Args:
        limit: Maximum number of jobs to return (1-500)
        offset: Number of jobs to skip for pagination
        order_by: SQL ORDER BY clause (default: archived_at DESC)

    Returns:
        Dict containing:
            - jobs: List of archived jobs
            - total: Total count of archived jobs
            - limit: Requested limit
            - offset: Requested offset
    """
    try:
        # Validate order_by to prevent SQL injection
        allowed_order_fields = [
            "archived_at", "created_at", "name", "status", "id"
        ]
        allowed_order_dirs = ["ASC", "DESC"]

        order_parts = order_by.strip().split()
        if len(order_parts) != 2:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order_by format. Use: '<field> <ASC|DESC>'"
            )

        field, direction = order_parts
        if field not in allowed_order_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order field. Allowed: {allowed_order_fields}"
            )
        if direction.upper() not in allowed_order_dirs:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order direction. Allowed: {allowed_order_dirs}"
            )

        # Fetch archived jobs
        jobs = await archives_storage.list_archived_jobs(
            limit=limit,
            offset=offset,
            order_by=f"{field} {direction.upper()}"
        )

        # Get total count
        total = await archives_storage.count_archived_jobs()

        return {
            "jobs": jobs,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(jobs) < total
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing archived jobs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list archived jobs: {str(e)}"
        )


@router.get("/{job_id}", response_model=Dict[str, Any])
async def get_archived_job(job_id: str):
    """
    Get details of a specific archived job.

    Args:
        job_id: The job ID

    Returns:
        Dict containing full archived job details including input and output configuration

    Raises:
        404: If archived job not found
    """
    try:
        job = await archives_storage.get_archived_job(job_id)

        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Archived job not found: {job_id}"
            )

        return {
            "job": job,
            "message": "Archived job retrieved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting archived job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get archived job: {str(e)}"
        )


@router.post("/{job_id}/restore", response_model=Dict[str, Any])
async def restore_archived_job(job_id: str):
    """
    Restore an archived job back to active jobs.

    This operation:
    1. Retrieves the archived job data
    2. Creates a new job in the main jobs.db database
    3. Removes the job from archives.db

    Args:
        job_id: The job ID to restore

    Returns:
        Dict containing restored job details

    Raises:
        404: If archived job not found
        409: If job with same ID already exists in active jobs
        500: If restoration fails
    """
    try:
        # Get archived job parts (job, input, output)
        job_parts = await archives_storage.get_archived_job_parts(job_id)

        if not job_parts or not all(job_parts):
            raise HTTPException(
                status_code=404,
                detail=f"Archived job not found or incomplete: {job_id}"
            )

        job_data, input_data, output_data = job_parts

        # Check if job already exists in active jobs
        existing_job = await db_service.fetch_one(
            "SELECT id FROM encoding_jobs WHERE id = ?",
            (job_id,)
        )

        if existing_job:
            raise HTTPException(
                status_code=409,
                detail=f"Job already exists in active jobs: {job_id}"
            )

        # Clean up any orphaned records (input_sources, output_configurations)
        # This can happen if archival was interrupted
        async with db_service.get_connection() as cleanup_conn:
            await cleanup_conn.execute("DELETE FROM input_sources WHERE job_id = ?", (job_id,))
            await cleanup_conn.execute("DELETE FROM output_configurations WHERE job_id = ?", (job_id,))
            await cleanup_conn.commit()

        # Restore job to main database
        async with db_service.get_connection() as conn:
            try:
                # Insert job
                await conn.execute("""
                    INSERT INTO encoding_jobs (
                        id, name, profile_id, status, created_at, started_at,
                        stopped_at, pid, error_message, command, priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_data['id'],
                    job_data['name'],
                    job_data.get('profile_id'),
                    job_data['status'],
                    job_data.get('created_at'),
                    job_data.get('started_at'),
                    job_data.get('stopped_at'),
                    job_data.get('pid'),
                    job_data.get('error_message'),
                    job_data.get('command'),
                    job_data.get('priority', 5)
                ))

                # Insert input source
                # Deserialize hardware_accel if it's a JSON string
                hardware_accel = input_data.get('hardware_accel')
                if hardware_accel and isinstance(hardware_accel, str):
                    try:
                        hardware_accel = json.loads(hardware_accel)
                        hardware_accel = json.dumps(hardware_accel)  # Re-serialize for consistency
                    except (json.JSONDecodeError, TypeError):
                        pass  # Keep as-is if not valid JSON

                await conn.execute("""
                    INSERT INTO input_sources (
                        job_id, type, url, loop_enabled, hardware_accel
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    input_data['job_id'],
                    input_data['type'],
                    input_data['url'],
                    input_data.get('loop_enabled', False),
                    hardware_accel
                ))

                # Insert output configuration
                # Deserialize JSON fields if they're JSON strings
                variant_paths = output_data.get('variant_paths')
                if variant_paths and isinstance(variant_paths, str):
                    try:
                        variant_paths = json.loads(variant_paths)
                        variant_paths = json.dumps(variant_paths)  # Re-serialize for consistency
                    except (json.JSONDecodeError, TypeError):
                        pass

                renditions = output_data.get('renditions')
                if renditions and isinstance(renditions, str):
                    try:
                        renditions = json.loads(renditions)
                        renditions = json.dumps(renditions)  # Re-serialize for consistency
                    except (json.JSONDecodeError, TypeError):
                        pass

                await conn.execute("""
                    INSERT INTO output_configurations (
                        job_id, output_type, output_url, base_path, variant_paths,
                        nginx_served, manifest_url, segment_duration, playlist_size,
                        video_codec, video_bitrate, video_resolution, video_framerate,
                        audio_codec, audio_bitrate, audio_stream_index,
                        abr_enabled, renditions,
                        encoding_preset, crf, keyframe_interval, tune, two_pass, rate_control_mode,
                        profile, level, max_bitrate, buffer_size, look_ahead, pixel_format
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    output_data['job_id'],
                    output_data.get('output_type', 'hls'),
                    output_data.get('output_url'),
                    output_data.get('base_path'),
                    variant_paths,
                    output_data.get('nginx_served', True),
                    output_data.get('manifest_url'),
                    output_data.get('segment_duration', 6),
                    output_data.get('playlist_size', 10),
                    output_data.get('video_codec', 'libx264'),
                    output_data.get('video_bitrate'),
                    output_data.get('video_resolution'),
                    output_data.get('video_framerate'),
                    output_data.get('audio_codec', 'aac'),
                    output_data.get('audio_bitrate'),
                    output_data.get('audio_stream_index', 0),
                    output_data.get('abr_enabled', False),
                    renditions,
                    output_data.get('encoding_preset', 'medium'),
                    output_data.get('crf'),
                    output_data.get('keyframe_interval'),
                    output_data.get('tune'),
                    output_data.get('two_pass', False),
                    output_data.get('rate_control_mode'),
                    output_data.get('profile'),
                    output_data.get('level'),
                    output_data.get('max_bitrate'),
                    output_data.get('buffer_size'),
                    output_data.get('look_ahead'),
                    output_data.get('pixel_format')
                ))

                await conn.commit()

            except Exception as e:
                await conn.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to restore job to database: {str(e)}"
                )

        # Remove from archives
        deleted = await archives_storage.delete_archived_job(job_id)

        if not deleted:
            logger.warning(
                f"Job {job_id} restored but failed to remove from archives"
            )

        # Get restored job
        restored_job = await job_manager.get_job_with_config(job_id)

        return {
            "status": "restored",
            "job": restored_job,
            "message": f"Job {job_id} restored successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring archived job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restore archived job: {str(e)}"
        )


@router.delete("/{job_id}", response_model=Dict[str, Any])
async def delete_archived_job_permanently(job_id: str):
    """
    Permanently delete an archived job.

    WARNING: This operation is irreversible. The job data will be permanently
    removed from the archives database and cannot be recovered.

    Args:
        job_id: The job ID to permanently delete

    Returns:
        Dict with deletion status and message

    Raises:
        404: If archived job not found
        500: If deletion fails
    """
    try:
        # Check if job exists
        job = await archives_storage.get_archived_job(job_id)

        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Archived job not found: {job_id}"
            )

        # Permanently delete
        deleted = await archives_storage.delete_archived_job(job_id)

        if not deleted:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete archived job: {job_id}"
            )

        return {
            "status": "permanently_deleted",
            "job_id": job_id,
            "message": f"Job {job_id} permanently deleted from archives"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting archived job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to permanently delete archived job: {str(e)}"
        )


@router.get("/stats/summary", response_model=Dict[str, Any])
async def get_archives_stats():
    """
    Get summary statistics about archived jobs.

    Returns:
        Dict containing:
            - total_archived: Total number of archived jobs
            - oldest_archive: Date of oldest archived job
            - newest_archive: Date of newest archived job
    """
    try:
        total = await archives_storage.count_archived_jobs()

        # Get oldest and newest
        oldest = await archives_storage.fetch_one(
            "SELECT archived_at FROM archived_jobs ORDER BY archived_at ASC LIMIT 1"
        )

        newest = await archives_storage.fetch_one(
            "SELECT archived_at FROM archived_jobs ORDER BY archived_at DESC LIMIT 1"
        )

        return {
            "total_archived": total,
            "oldest_archive": oldest['archived_at'] if oldest else None,
            "newest_archive": newest['archived_at'] if newest else None
        }

    except Exception as e:
        logger.error(f"Error getting archives stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get archives stats: {str(e)}"
        )
