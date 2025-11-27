"""
Job State Manager
Implements job status transition logic
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from models.job import EncodingJob, JobStatus
from services.storage import db_service

logger = logging.getLogger(__name__)


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    pass


class JobStateManager:
    """Manages job state transitions and validation"""

    # Valid state transitions
    VALID_TRANSITIONS = {
        JobStatus.PENDING: [JobStatus.RUNNING, JobStatus.ERROR],
        JobStatus.RUNNING: [JobStatus.STOPPED, JobStatus.ERROR, JobStatus.COMPLETED],
        JobStatus.STOPPED: [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.ERROR],
        JobStatus.ERROR: [JobStatus.PENDING, JobStatus.RUNNING],
        JobStatus.COMPLETED: [JobStatus.PENDING, JobStatus.RUNNING]
    }

    def __init__(self):
        """Initialize job state manager"""
        self.db = db_service

    async def transition(
        self,
        job: EncodingJob,
        new_status: JobStatus,
        error_message: Optional[str] = None,
        pid: Optional[int] = None
    ) -> EncodingJob:
        """Transition job to a new state

        Args:
            job: Encoding job
            new_status: Target status
            error_message: Error message if transitioning to ERROR
            pid: Process ID if transitioning to RUNNING

        Returns:
            EncodingJob: Updated job

        Raises:
            TransitionError: If transition is not valid
        """
        # Validate transition
        if not self.is_valid_transition(job.status, new_status):
            raise TransitionError(
                f"Invalid transition from {job.status} to {new_status} for job {job.id}"
            )

        # Store old status for logging
        old_status = job.status

        # Update job fields based on transition
        job.status = new_status
        timestamp = datetime.utcnow()

        if new_status == JobStatus.RUNNING:
            job.started_at = timestamp
            job.stopped_at = None
            job.error_message = None
            if pid:
                job.pid = pid

        elif new_status == JobStatus.STOPPED:
            job.stopped_at = timestamp
            job.pid = None

        elif new_status == JobStatus.ERROR:
            job.stopped_at = timestamp
            job.pid = None
            job.error_message = error_message or "Unknown error"

        elif new_status == JobStatus.COMPLETED:
            job.stopped_at = timestamp
            job.pid = None
            job.error_message = None

        elif new_status == JobStatus.PENDING:
            # Reset for retry
            job.started_at = None
            job.stopped_at = None
            job.pid = None
            job.error_message = None

        # Persist to database
        await self._update_job_status(job)

        logger.info(
            f"Job {job.id} transitioned from {old_status} to {new_status}"
        )

        return job

    def is_valid_transition(
        self,
        current_status: JobStatus,
        target_status: JobStatus
    ) -> bool:
        """Check if a state transition is valid

        Args:
            current_status: Current job status
            target_status: Target status

        Returns:
            bool: True if transition is valid
        """
        if current_status == target_status:
            return True  # No-op transitions are valid

        valid_targets = self.VALID_TRANSITIONS.get(current_status, [])
        return target_status in valid_targets

    async def _update_job_status(self, job: EncodingJob) -> None:
        """Update job status in database

        Args:
            job: Encoding job
        """
        try:
            await self.db.execute("""
                UPDATE encoding_jobs
                SET status = ?, started_at = ?, stopped_at = ?,
                    pid = ?, error_message = ?, command = ?
                WHERE id = ?
            """, (
                job.status,
                job.started_at.isoformat() if job.started_at else None,
                job.stopped_at.isoformat() if job.stopped_at else None,
                job.pid,
                job.error_message,
                job.command,
                job.id
            ))
        except Exception as e:
            logger.error(f"Failed to update job status in database: {e}")
            raise

    async def get_job_history(
        self,
        job_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get status transition history for a job

        Args:
            job_id: Job ID
            limit: Maximum number of transitions to return

        Returns:
            List[Dict]: Status transition history
        """
        # Note: This would require an additional audit table to track transitions
        # For now, return current status as single entry
        job_row = await self.db.fetch_one(
            "SELECT * FROM encoding_jobs WHERE id = ?",
            (job_id,)
        )

        if not job_row:
            return []

        history = [{
            'timestamp': job_row['created_at'],
            'status': job_row['status'],
            'error_message': job_row['error_message']
        }]

        return history

    async def reset_job(self, job: EncodingJob) -> EncodingJob:
        """Reset job to pending state for retry

        Args:
            job: Encoding job

        Returns:
            EncodingJob: Reset job
        """
        return await self.transition(job, JobStatus.PENDING)

    async def mark_job_running(
        self,
        job: EncodingJob,
        pid: int
    ) -> EncodingJob:
        """Mark job as running with process ID

        Args:
            job: Encoding job
            pid: Process ID

        Returns:
            EncodingJob: Updated job
        """
        return await self.transition(job, JobStatus.RUNNING, pid=pid)

    async def mark_job_stopped(self, job: EncodingJob) -> EncodingJob:
        """Mark job as stopped

        Args:
            job: Encoding job

        Returns:
            EncodingJob: Updated job
        """
        return await self.transition(job, JobStatus.STOPPED)

    async def mark_job_error(
        self,
        job: EncodingJob,
        error_message: str
    ) -> EncodingJob:
        """Mark job as error with message

        Args:
            job: Encoding job
            error_message: Error description

        Returns:
            EncodingJob: Updated job
        """
        return await self.transition(job, JobStatus.ERROR, error_message=error_message)

    async def mark_job_completed(self, job: EncodingJob) -> EncodingJob:
        """Mark job as completed

        Args:
            job: Encoding job

        Returns:
            EncodingJob: Updated job
        """
        updated_job = await self.transition(job, JobStatus.COMPLETED)

        # Check if job should be auto-archived
        if job.archive_on_complete:
            logger.info(f"Job {job.id} marked for auto-archive on completion")
            # Import here to avoid circular dependency
            from services.archives_storage import archives_storage
            from services.job_manager import job_manager
            try:
                # Feature 008: Read from unified format (full_config) with lazy migration fallback
                unified_config = await job_manager.get_job_unified(job.id)

                if unified_config:
                    # Get full job data with full_config populated
                    job_row = await self.db.fetch_one(
                        "SELECT * FROM encoding_jobs WHERE id = ?", (job.id,)
                    )
                    input_row = await self.db.fetch_one(
                        "SELECT * FROM input_sources WHERE job_id = ?", (job.id,)
                    )
                    output_row = await self.db.fetch_one(
                        "SELECT * FROM output_configurations WHERE job_id = ?", (job.id,)
                    )

                    if job_row and input_row and output_row:
                        # Archive the job with full data (includes full_config)
                        archived = await archives_storage.archive_job(
                            job_data=dict(job_row),
                            input_data=dict(input_row),
                            output_data=dict(output_row),
                            reason="auto_archived_on_completion"
                        )
                        if archived:
                            logger.info(f"Job {job.id} ({job.name}) auto-archived successfully with full_config")
                            # Delete from main database
                            await self.db.execute("DELETE FROM encoding_jobs WHERE id = ?", (job.id,))
                        else:
                            logger.error(f"Failed to auto-archive job {job.id}")
                    else:
                        logger.error(f"Cannot auto-archive job {job.id}: missing job data (job={bool(job_row)}, input={bool(input_row)}, output={bool(output_row)})")
                else:
                    logger.error(f"Cannot auto-archive job {job.id}: failed to retrieve unified config")
            except Exception as e:
                logger.error(f"Error auto-archiving job {job.id}: {e}", exc_info=True)

        return updated_job

    async def cleanup_orphaned_jobs(self) -> int:
        """Clean up jobs marked as running but with no active process

        Returns:
            int: Number of jobs cleaned up
        """
        try:
            # Find jobs marked as running
            running_jobs = await self.db.fetch_all(
                "SELECT * FROM encoding_jobs WHERE status = ?",
                (JobStatus.RUNNING,)
            )

            cleaned = 0
            for job_row in running_jobs:
                pid = job_row.get('pid')

                if pid:
                    # Check if process is still running
                    import psutil
                    try:
                        process = psutil.Process(pid)
                        if not process.is_running():
                            # Process is dead, mark job as error
                            await self.db.execute("""
                                UPDATE encoding_jobs
                                SET status = ?, stopped_at = ?, pid = ?,
                                    error_message = ?
                                WHERE id = ?
                            """, (
                                JobStatus.ERROR,
                                datetime.utcnow().isoformat(),
                                None,
                                "Process died unexpectedly",
                                job_row['id']
                            ))
                            cleaned += 1
                            logger.warning(f"Cleaned up orphaned job {job_row['id']}")
                    except psutil.NoSuchProcess:
                        # Process doesn't exist
                        await self.db.execute("""
                            UPDATE encoding_jobs
                            SET status = ?, stopped_at = ?, pid = ?,
                                error_message = ?
                            WHERE id = ?
                        """, (
                            JobStatus.ERROR,
                            datetime.utcnow().isoformat(),
                            None,
                            "Process not found",
                            job_row['id']
                        ))
                        cleaned += 1
                        logger.warning(f"Cleaned up orphaned job {job_row['id']}")

            return cleaned

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned jobs: {e}")
            return 0

    async def recover_running_jobs_on_restart(self) -> List[str]:
        """Recover jobs marked as running on container restart

        When the container restarts, jobs marked as running no longer have
        active processes. This method resets them to PENDING so they can be
        restarted.

        Returns:
            List[str]: List of job IDs that were recovered
        """
        try:
            # Find all jobs marked as running
            running_jobs = await self.db.fetch_all(
                "SELECT id, name FROM encoding_jobs WHERE status = ?",
                (JobStatus.RUNNING,)
            )

            recovered_job_ids = []

            for job_row in running_jobs:
                job_id = job_row['id']
                job_name = job_row['name']

                # Reset job to PENDING state to allow restart
                await self.db.execute("""
                    UPDATE encoding_jobs
                    SET status = ?, started_at = NULL, pid = NULL,
                        error_message = NULL
                    WHERE id = ?
                """, (
                    JobStatus.PENDING,
                    job_id
                ))

                recovered_job_ids.append(job_id)
                logger.info(f"Recovered job {job_id} ({job_name}) - reset to PENDING for restart")

            if recovered_job_ids:
                logger.info(f"Recovered {len(recovered_job_ids)} jobs on restart")
            else:
                logger.info("No jobs needed recovery on restart")

            return recovered_job_ids

        except Exception as e:
            logger.error(f"Failed to recover running jobs on restart: {e}")
            return []

    def get_transition_diagram(self) -> str:
        """Get state transition diagram as text

        Returns:
            str: ASCII representation of state transitions
        """
        diagram = """
        Job State Transitions:
        =====================

        PENDING ──┬──> RUNNING ──┬──> STOPPED
                  │              ├──> ERROR
                  └──> ERROR    └──> COMPLETED
                        │              │
                        v              v
                     PENDING <──────────┘

        Valid Transitions:
        - PENDING -> RUNNING: Job starts
        - PENDING -> ERROR: Startup failure
        - RUNNING -> STOPPED: Manual stop
        - RUNNING -> ERROR: Process failure
        - RUNNING -> COMPLETED: File input ends
        - STOPPED/ERROR/COMPLETED -> PENDING: Reset for retry
        """
        return diagram


# Global instance
job_state_manager = JobStateManager()