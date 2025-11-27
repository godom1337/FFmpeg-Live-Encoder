"""
Snapshot Generation API Endpoints
Generates preview thumbnails from input streams using FFmpeg
"""

from fastapi import APIRouter, HTTPException, Response
from typing import Optional
import logging
import asyncio
import tempfile
import os
from pathlib import Path

from models.job import JobStatus
from services.job_manager import job_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots"])


@router.get("/{job_id}/thumbnail.jpg")
async def get_job_thumbnail(job_id: str, quality: Optional[int] = 2):
    """Generate and return a thumbnail image from the job's input stream

    This endpoint uses FFmpeg to capture a single frame from the input stream
    and return it as a JPEG image. Works for all input types (UDP, HTTP, file, etc.)

    Args:
        job_id: Job ID to generate thumbnail for
        quality: JPEG quality (1-31, lower is better quality, default: 2)

    Returns:
        JPEG image bytes

    Raises:
        HTTPException: If job not found or thumbnail generation fails
    """
    try:
        # Get job details
        job_data = await job_manager.get_job_with_config(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check if job is running (can only capture from running jobs)
        job_status = job_data.get('job', {}).get('status')
        if job_status != JobStatus.RUNNING.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot generate thumbnail for job with status: {job_status}. Job must be running."
            )

        # Get input URL
        input_data = job_data.get('input', {})
        input_url = input_data.get('url')
        if not input_url:
            raise HTTPException(status_code=400, detail="Job has no input URL")

        # Create temporary file for snapshot
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Build FFmpeg command to capture a single frame
            # -ss 2: Skip first 2 seconds to avoid black frames at stream start
            # -i: input URL
            # -frames:v 1: capture only 1 frame
            # -q:v: JPEG quality (1-31, lower is better)
            # -f image2: force image format
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-hide_banner',
                '-loglevel', 'error',
                '-ss', '2',  # Seek 2 seconds into stream to skip initial black frames
                '-i', input_url,
                '-frames:v', '1',
                '-q:v', str(quality),
                '-f', 'image2',
                tmp_path
            ]

            logger.info(f"Generating thumbnail for job {job_id} from {input_url}")
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")

            # Execute FFmpeg with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=15.0  # 15 second timeout (increased for live streams with seek)
                )
            except asyncio.TimeoutError:
                process.kill()
                raise HTTPException(
                    status_code=504,
                    detail="Thumbnail generation timed out (15s). Input stream may not be accessible."
                )

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else 'Unknown error'
                logger.error(f"FFmpeg failed for job {job_id}: {error_msg}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate thumbnail: {error_msg[:200]}"
                )

            # Check if file was created and has content
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise HTTPException(
                    status_code=500,
                    detail="Thumbnail file was not created or is empty"
                )

            # Read the image file
            with open(tmp_path, 'rb') as f:
                image_data = f.read()

            logger.info(f"Successfully generated thumbnail for job {job_id} ({len(image_data)} bytes)")

            # Return image with appropriate headers
            return Response(
                content=image_data,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )

        finally:
            # Clean up temporary file
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {tmp_path}: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating thumbnail for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
