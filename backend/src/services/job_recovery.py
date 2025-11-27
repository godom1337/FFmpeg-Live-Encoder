"""
Job Recovery Service
Handles automatic restart of jobs on container restart
"""

import logging
import asyncio
from typing import List

from services.job_state import job_state_manager
from services.job_manager import job_manager
from models.job import JobStatus

logger = logging.getLogger(__name__)


class JobRecoveryService:
    """Manages job recovery on application restart"""

    def __init__(self):
        """Initialize job recovery service"""
        self.state_manager = job_state_manager
        self.job_manager = job_manager

    async def recover_and_restart_jobs(self) -> int:
        """Recover jobs that were running before container restart and restart them

        This method:
        1. Finds jobs marked as RUNNING in the database
        2. Resets them to PENDING (since processes are dead)
        3. Optionally restarts them automatically

        Returns:
            int: Number of jobs recovered
        """
        try:
            logger.info("Starting job recovery process...")

            # Recover jobs marked as running (resets them to PENDING)
            recovered_job_ids = await self.state_manager.recover_running_jobs_on_restart()

            if not recovered_job_ids:
                logger.info("No jobs to recover")
                return 0

            logger.info(f"Found {len(recovered_job_ids)} jobs to recover")

            # Now restart each recovered job
            restarted_count = 0
            for job_id in recovered_job_ids:
                try:
                    # Get the job to verify it's in PENDING state
                    job = await self.job_manager.get_job(job_id)
                    if not job:
                        logger.warning(f"Job {job_id} not found, skipping restart")
                        continue

                    if job.status == JobStatus.PENDING:
                        logger.info(f"Job {job_id} ({job.name}) is ready to be restarted")
                        # Note: The actual restart will be triggered by the user or
                        # by calling the /start endpoint. We just reset the state here.
                        # If you want automatic restart, import and call the start logic here.
                        restarted_count += 1
                    else:
                        logger.warning(f"Job {job_id} is in state {job.status}, expected PENDING")

                except Exception as e:
                    logger.error(f"Failed to process recovered job {job_id}: {e}")
                    continue

            logger.info(f"Successfully recovered {restarted_count} jobs")
            return restarted_count

        except Exception as e:
            logger.error(f"Job recovery failed: {e}")
            return 0

    async def start_recovered_job(self, job_id: str) -> bool:
        """Start a specific recovered job

        This is a helper method that can be called to automatically restart
        a recovered job. For automatic restart on container startup, you would
        call this for each recovered job.

        Args:
            job_id: Job ID to start

        Returns:
            bool: True if job started successfully
        """
        try:
            from models.job import EncodingJob
            from models.input import InputSource
            from models.output import OutputConfiguration
            from services.simple_ffmpeg import simple_ffmpeg_launcher
            from services.output_manager import output_manager
            from typing import Dict, Any
            import shutil
            from pathlib import Path

            logger.info(f"Attempting to auto-restart job {job_id}")

            # STEP 1: STOP any orphaned FFmpeg processes for this job
            logger.info(f"STEP 1: Stopping any orphaned processes for job {job_id}")
            try:
                await simple_ffmpeg_launcher.stop_encoding(job_id, timeout=10)
                logger.info(f"Stopped orphaned processes for job {job_id}")
            except Exception as stop_error:
                logger.warning(f"Error stopping orphaned processes for job {job_id}: {stop_error}")
                # Continue anyway

            # STEP 2: Wait 30 seconds for processes to fully terminate and cleanup
            logger.info(f"STEP 2: Waiting 30 seconds for complete process cleanup for job {job_id}")
            await asyncio.sleep(30)
            logger.info(f"Cleanup wait completed for job {job_id}")

            # Get job with configuration
            job_data = await self.job_manager.get_job_with_config(job_id)
            if not job_data:
                logger.error(f"Job {job_id} not found")
                return False

            job = EncodingJob(**job_data['job'])

            # Check if job can be started
            if not job.can_start():
                logger.warning(f"Job {job_id} cannot be started from {job.status} state")
                return False

            # Get input and output configuration
            if not job_data['input'] or not job_data['output']:
                logger.error(f"Job {job_id} missing input or output configuration")
                return False

            input_source = InputSource(**job_data['input'])
            output_config = OutputConfiguration(**job_data['output'])

            # STEP 3: Directory setup for HLS outputs only
            # For UDP/RTMP/SRT/FILE outputs, base_path is None and no directories are needed
            from models.output import OutputType

            if output_config.output_type == OutputType.HLS:
                # Validate HLS jobs have a valid base path
                if not output_config.base_path or not output_config.base_path.strip():
                    logger.error(f"Job {job_id} is HLS type but has invalid or empty base_path")
                    await self.state_manager.mark_job_error(job, "Invalid HLS configuration: missing base_path")
                    return False

                # Clean up old output directory for fresh start
                try:
                    base_path = output_config.base_path
                    if Path(base_path).exists():
                        logger.info(f"STEP 3: Cleaning HLS output directory: {base_path}")
                        shutil.rmtree(base_path)
                        await asyncio.sleep(5)  # Wait longer for filesystem
                        logger.info(f"HLS output directory cleaned for job {job_id}")
                    else:
                        logger.info(f"No old HLS output directory for job {job_id}")

                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup HLS output directory for job {job_id}: {cleanup_error}")

                # STEP 3.5: Create fresh directory structure for HLS
                logger.info(f"STEP 3.5: Creating fresh HLS directory structure for job {job_id}")
                try:
                    base_path = output_config.base_path
                    Path(base_path).mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created HLS base directory: {base_path}")

                    # Check if ABR or single stream
                    output_dict = output_config.dict()
                    is_abr = output_dict.get("abr_enabled", False)

                    if is_abr:
                        renditions = output_dict.get("renditions", [])
                        for rendition in renditions:
                            rendition_name = rendition.get("name") if isinstance(rendition, dict) else rendition.name
                            rendition_path = f"{base_path}/{rendition_name}"
                            Path(rendition_path).mkdir(parents=True, exist_ok=True)
                            logger.info(f"Created rendition directory: {rendition_path}")
                    else:
                        # Create /stream subdirectory for single stream mode
                        stream_path = f"{base_path}/stream"
                        Path(stream_path).mkdir(parents=True, exist_ok=True)
                        logger.info(f"Created stream directory: {stream_path}")

                    await asyncio.sleep(2)  # Wait for filesystem to confirm
                    logger.info(f"HLS directory structure ready for job {job_id}")

                except Exception as dir_error:
                    logger.error(f"Failed to create HLS directories for job {job_id}: {dir_error}")
                    return False
            else:
                # Non-HLS output types (UDP, RTMP, SRT, FILE) don't need directory setup
                logger.info(f"Job {job_id} is {output_config.output_type} type - skipping directory setup")

            # Define callbacks for progress tracking
            async def on_progress(job_id: str, progress: Dict[str, Any]):
                logger.debug(f"Job {job_id} progress: {progress}")

            async def on_error(job_id: str, error: str):
                logger.error(f"Job {job_id} FFmpeg stderr: {error}")
                await self.state_manager.mark_job_error(job, error)

            async def on_complete(job_id: str, exit_code: int):
                if exit_code == 0:
                    logger.info(f"Job {job_id} completed successfully")
                    await self.state_manager.mark_job_completed(job)
                else:
                    error_msg = f"FFmpeg exited with code {exit_code}"
                    logger.error(f"Job {job_id} failed: {error_msg}")

                    # Read last few lines of log file for debugging
                    try:
                        log_file = Path(f"src/logs/{job_id}.log")
                        if log_file.exists():
                            with open(log_file, 'r') as f:
                                lines = f.readlines()
                                last_lines = ''.join(lines[-10:]) if len(lines) > 10 else ''.join(lines)
                                logger.error(f"Job {job_id} last log lines:\n{last_lines}")
                    except Exception as log_error:
                        logger.error(f"Could not read log file for job {job_id}: {log_error}")

                    await self.state_manager.mark_job_error(job, error_msg)

            # STEP 4: Start fresh FFmpeg process
            logger.info(f"STEP 4: Starting fresh FFmpeg process for job {job_id}")
            started = await simple_ffmpeg_launcher.start_encoding(
                job, input_source, output_config,
                on_progress, on_error, on_complete
            )

            if not started:
                error_msg = f"Failed to start FFmpeg process for job {job_id}"
                logger.error(error_msg)
                await self.state_manager.mark_job_error(job, "Failed to start FFmpeg process during recovery")
                return False

            # Get the actual PID from the process manager
            if job_id in simple_ffmpeg_launcher.active_processes:
                actual_pid = simple_ffmpeg_launcher.active_processes[job_id].pid
                logger.info(f"Job {job_id} FFmpeg process started with PID {actual_pid}")
            else:
                actual_pid = job.pid or 0
                logger.warning(f"Job {job_id} not found in active_processes, using job.pid: {actual_pid}")

            # Update job status to RUNNING with the correct PID
            logger.info(f"Marking job {job_id} as RUNNING with PID {actual_pid}")
            updated_job = await self.state_manager.mark_job_running(job, actual_pid)
            logger.info(f"Job {job_id} status after mark_job_running: {updated_job.status}, PID: {updated_job.pid}")

            # Verify the database was updated
            verify_job = await self.job_manager.get_job(job_id)
            if verify_job:
                logger.info(f"Database verification - Job {job_id} status: {verify_job.status}, PID: {verify_job.pid}")
                if verify_job.status != JobStatus.RUNNING:
                    logger.error(f"BUG: Job {job_id} not marked as RUNNING in database! Status is {verify_job.status}")
            else:
                logger.error(f"BUG: Could not verify job {job_id} in database after recovery!")

            logger.info(f"✓ Successfully restarted job {job_id} with PID {actual_pid}")
            return True

        except Exception as e:
            logger.error(f"Error auto-restarting job {job_id}: {e}", exc_info=True)
            # Try to mark job as error
            try:
                job_data = await self.job_manager.get_job_with_config(job_id)
                if job_data:
                    job = EncodingJob(**job_data['job'])
                    await self.state_manager.mark_job_error(job, f"Recovery failed: {str(e)}")
            except:
                pass
            return False

    async def recover_with_auto_restart(self) -> dict:
        """Recover jobs and automatically restart them

        Returns:
            dict: Recovery statistics
        """
        try:
            logger.info("Starting job recovery with auto-restart...")

            # Recover jobs (resets to PENDING)
            recovered_job_ids = await self.state_manager.recover_running_jobs_on_restart()

            if not recovered_job_ids:
                return {
                    'recovered': 0,
                    'restarted': 0,
                    'failed': 0
                }

            # Deduplicate job IDs in case of database issues
            unique_job_ids = list(set(recovered_job_ids))
            if len(unique_job_ids) < len(recovered_job_ids):
                logger.warning(
                    f"Found {len(recovered_job_ids) - len(unique_job_ids)} duplicate job IDs, "
                    f"deduplicating to {len(unique_job_ids)} unique jobs"
                )
                recovered_job_ids = unique_job_ids

            # Wait a moment for system to stabilize
            await asyncio.sleep(2)

            # Try to restart each job with staggered delays
            restarted = 0
            failed = 0

            for index, job_id in enumerate(recovered_job_ids, 1):
                try:
                    logger.info(f"Restarting job {index}/{len(recovered_job_ids)}: {job_id}")

                    if await self.start_recovered_job(job_id):
                        restarted += 1
                        logger.info(f"Successfully restarted job {index}/{len(recovered_job_ids)}")
                    else:
                        failed += 1
                        logger.warning(f"Failed to restart job {index}/{len(recovered_job_ids)}")
                except Exception as e:
                    logger.error(f"Exception restarting job {job_id}: {e}")
                    failed += 1

                # Increased delay between restarts to prevent resource conflicts
                # Allow time for FFmpeg process to fully initialize and claim resources
                if index < len(recovered_job_ids):  # Don't delay after last job
                    logger.info(f"Waiting 10 seconds before starting next job...")
                    await asyncio.sleep(10)

            stats = {
                'recovered': len(recovered_job_ids),
                'restarted': restarted,
                'failed': failed
            }

            logger.info(f"Job recovery complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Job recovery with auto-restart failed: {e}")
            return {
                'recovered': 0,
                'restarted': 0,
                'failed': 0,
                'error': str(e)
            }


# Global instance
job_recovery_service = JobRecoveryService()
