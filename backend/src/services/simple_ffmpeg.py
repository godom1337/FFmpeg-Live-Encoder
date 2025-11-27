"""
Simple FFmpeg Launcher - Compatibility Layer

This module provides a compatibility layer between the new minimal job creation
API and the existing job execution infrastructure.
"""

import asyncio
import logging
import shlex
import shutil
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SimpleFfmpegLauncher:
    """
    Simple FFmpeg launcher for executing jobs created via the new minimal API.

    This is a lightweight wrapper that executes the FFmpeg commands stored
    in the job's 'command' field.
    """

    def __init__(self):
        self.active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self.job_stats: Dict[str, dict] = {}

    async def start_encoding(
        self,
        job,
        input_source,
        output_config,
        on_progress=None,
        on_error=None,
        on_complete=None
    ) -> bool:
        """
        Start encoding job by executing the stored FFmpeg command.

        Args:
            job: EncodingJob object with 'id' and 'command' fields
            input_source: InputSource object (unused for minimal jobs)
            output_config: OutputConfiguration object (unused for minimal jobs)
            on_progress: Optional callback for progress updates
            on_error: Optional callback for errors
            on_complete: Optional callback for completion

        Returns:
            True if started successfully, False otherwise
        """
        try:
            job_id = job.id if hasattr(job, 'id') else str(job)
            command_str = job.command if hasattr(job, 'command') else None

            if not command_str:
                logger.error(f"Job {job_id} has no command field")
                return False

            # Parse command string into list (safe)
            cmd_list = shlex.split(command_str)

            # Use stdbuf to disable output buffering for real-time logs (Linux only)
            stdbuf_path = shutil.which('stdbuf')
            if stdbuf_path:
                cmd_list = [stdbuf_path, '-oL', '-eL'] + cmd_list
                logger.info(f"Using stdbuf for unbuffered output: {stdbuf_path}")

            logger.info(f"Starting job {job_id} with command: {command_str}")

            # Create log file
            log_dir = Path("src/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{job_id}.log"

            # Start the subprocess with stdin for graceful shutdown support
            process = await asyncio.create_subprocess_exec(
                *cmd_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,  # Enable stdin for 'q' command
            )

            # Store process reference
            self.active_processes[job_id] = process
            self.job_stats[job_id] = {
                'pid': process.pid,
                'command': command_str,
                'started_at': asyncio.get_event_loop().time(),
                'log_file': str(log_file)
            }

            logger.info(f"Job {job_id} started with PID {process.pid}")

            # Write initial log header
            with open(log_file, 'w') as f:
                f.write(f"=== Job {job_id} Started ===\n")
                f.write(f"PID: {process.pid}\n")
                f.write(f"Command: {command_str}\n")
                f.write("=" * 80 + "\n\n")

            # Set up async monitoring (basic - could be enhanced with callbacks later)
            asyncio.create_task(self._monitor_process(job_id, process, on_complete, on_error))

            return True

        except Exception as e:
            logger.error(f"Failed to start job {job_id}: {e}")
            if on_error:
                try:
                    await on_error(str(e))
                except:
                    pass
            return False

    async def _monitor_process(self, job_id, process, on_complete, on_error):
        """Monitor process completion and call callbacks, streaming logs in real-time"""
        log_file = None
        log_file_handle = None

        try:
            # Get log file path
            if job_id in self.job_stats and 'log_file' in self.job_stats[job_id]:
                log_file = self.job_stats[job_id]['log_file']
                log_file_handle = open(log_file, 'a', buffering=1)  # Line buffered

            # Create tasks to read stdout and stderr concurrently
            async def read_stream(stream, prefix):
                """Read from stream byte by byte to handle \\r progress updates"""
                try:
                    buffer = b''
                    while True:
                        chunk = await stream.read(1)
                        if not chunk:
                            # End of stream - flush remaining buffer
                            if buffer:
                                decoded_line = buffer.decode('utf-8', errors='replace')
                                if log_file_handle:
                                    log_file_handle.write(f"[{prefix}] {decoded_line}\n")
                                    log_file_handle.flush()
                            break

                        if chunk == b'\n':
                            # Newline - write complete line
                            decoded_line = buffer.decode('utf-8', errors='replace')
                            if log_file_handle:
                                log_file_handle.write(f"[{prefix}] {decoded_line}\n")
                                log_file_handle.flush()
                            buffer = b''
                        elif chunk == b'\r':
                            # Carriage return (FFmpeg progress) - write as new line
                            if buffer:
                                decoded_line = buffer.decode('utf-8', errors='replace')
                                if log_file_handle:
                                    log_file_handle.write(f"{decoded_line}\n")
                                    log_file_handle.flush()
                            buffer = b''
                        else:
                            buffer += chunk
                except Exception as e:
                    logger.error(f"Error reading {prefix} for job {job_id}: {e}")

            # Monitor both stdout and stderr concurrently
            stdout_task = asyncio.create_task(read_stream(process.stdout, 'STDOUT'))
            stderr_task = asyncio.create_task(read_stream(process.stderr, 'STDERR'))

            # Wait for process to complete
            await process.wait()

            # Wait for all output to be read
            await stdout_task
            await stderr_task

            # Write completion status to log
            if log_file_handle:
                log_file_handle.write("\n" + "=" * 80 + "\n")
                log_file_handle.write(f"Process exited with code: {process.returncode}\n")
                log_file_handle.write("=" * 80 + "\n")
                log_file_handle.flush()

            if process.returncode == 0:
                logger.info(f"Job {job_id} completed successfully")
                if on_complete:
                    try:
                        await on_complete(job_id, process.returncode)
                    except Exception as e:
                        logger.error(f"Error in on_complete callback: {e}")
            else:
                logger.error(f"Job {job_id} failed with code {process.returncode}")
                if on_error:
                    try:
                        await on_error(job_id, f"Process exited with code {process.returncode}")
                    except Exception as e:
                        logger.error(f"Error in on_error callback: {e}")
        except Exception as e:
            logger.error(f"Error monitoring job {job_id}: {e}")
            if log_file_handle:
                try:
                    log_file_handle.write(f"\n[ERROR] {str(e)}\n")
                    log_file_handle.flush()
                except:
                    pass
            if on_error:
                try:
                    await on_error(job_id, str(e))
                except:
                    pass
        finally:
            # Close log file handle
            if log_file_handle:
                try:
                    log_file_handle.close()
                except:
                    pass
            # Cleanup
            if job_id in self.active_processes:
                del self.active_processes[job_id]

    async def stop_encoding(self, job_id: str, timeout: int = 10, pid: int = None) -> bool:
        """
        Stop encoding job gracefully with comprehensive process cleanup.

        Strategy:
        1. Send 'q' command to FFmpeg stdin for graceful shutdown (2 seconds)
        2. If still running, use SIGTERM on entire process tree (timeout seconds)
        3. If still running, use SIGKILL on entire process tree

        Args:
            job_id: Job UUID
            timeout: Seconds to wait for graceful shutdown
            pid: Optional PID from database (used for orphaned process cleanup)

        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            if job_id not in self.active_processes:
                logger.warning(f"Job {job_id} not in active processes")
                # Even if not in our tracking, try to kill by PID from database or search processes
                return await self._force_kill_by_job_id(job_id, pid)

            process = self.active_processes[job_id]
            pid = process.pid

            logger.info(f"Stopping job {job_id} with PID {pid}")

            # Step 1: Try graceful FFmpeg shutdown via 'q' command
            if process.stdin and not process.stdin.is_closing():
                try:
                    logger.info(f"Sending 'q' command to FFmpeg stdin for job {job_id}")
                    process.stdin.write(b'q\n')
                    await process.stdin.drain()
                    process.stdin.close()

                    # Wait briefly for graceful shutdown
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                        logger.info(f"Job {job_id} stopped gracefully via 'q' command")
                        self._cleanup_job(job_id)
                        return True
                    except asyncio.TimeoutError:
                        logger.info(f"Job {job_id} didn't stop after 'q' command, escalating")
                except (BrokenPipeError, OSError) as e:
                    logger.warning(f"Could not send 'q' command to job {job_id}: {e}")

            # Step 2: Use psutil to terminate entire process tree
            try:
                import psutil

                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                    all_procs = [parent] + children

                    logger.info(f"Job {job_id}: Found {len(children)} child process(es), terminating tree")

                    # Send SIGTERM to all processes
                    for proc in all_procs:
                        try:
                            proc.terminate()
                            logger.debug(f"Sent SIGTERM to PID {proc.pid}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            logger.debug(f"Could not terminate PID {proc.pid}: {e}")

                    # Wait for graceful termination
                    gone, alive = psutil.wait_procs(all_procs, timeout=timeout)

                    logger.info(f"Job {job_id}: {len(gone)} process(es) terminated, {len(alive)} still alive")

                    # Step 3: Force kill any remaining processes
                    if alive:
                        logger.warning(f"Job {job_id}: Force killing {len(alive)} remaining process(es)")
                        for proc in alive:
                            try:
                                proc.kill()
                                logger.debug(f"Sent SIGKILL to PID {proc.pid}")
                            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                                logger.debug(f"Could not kill PID {proc.pid}: {e}")

                        # Final wait after SIGKILL
                        gone, still_alive = psutil.wait_procs(alive, timeout=3)

                        if still_alive:
                            logger.error(f"Job {job_id}: {len(still_alive)} process(es) could not be killed: {[p.pid for p in still_alive]}")
                            # CRITICAL FIX: Do NOT cleanup or return success if processes are still alive
                            return False
                        else:
                            logger.info(f"Job {job_id}: All processes successfully killed")

                except psutil.NoSuchProcess:
                    logger.info(f"Job {job_id}: Process {pid} already exited")

            except ImportError:
                # Fallback if psutil is not available (shouldn't happen)
                logger.warning(f"psutil not available, using basic process termination for job {job_id}")
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

            # Clean up tracking dictionaries ONLY after successful kill
            self._cleanup_job(job_id)
            logger.info(f"Job {job_id} stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to stop job {job_id}: {e}", exc_info=True)
            # CRITICAL FIX: Do NOT cleanup on error - process may still be running
            return False

    def _cleanup_job(self, job_id: str):
        """Remove job from tracking dictionaries"""
        if job_id in self.active_processes:
            del self.active_processes[job_id]
        if job_id in self.job_stats:
            del self.job_stats[job_id]
        logger.debug(f"Cleaned up tracking for job {job_id}")

    async def _force_kill_by_job_id(self, job_id: str, pid: int = None) -> bool:
        """
        Search for and kill any FFmpeg processes for this job.

        If PID is provided (from database), uses it directly.
        Otherwise, searches for FFmpeg processes containing job_id in command line.

        Args:
            job_id: Job UUID
            pid: Optional PID from database

        Returns:
            True if killed successfully, False otherwise
        """
        try:
            import psutil
            killed_count = 0

            # Strategy 1: If we have a PID from the database, try to kill it directly
            if pid:
                try:
                    logger.info(f"Attempting to kill job {job_id} using PID {pid} from database")
                    parent = psutil.Process(pid)

                    # Verify it's actually an ffmpeg process
                    if parent.name() and (parent.name() == 'ffmpeg' or parent.name().startswith('ffmpeg')):
                        # Get all children first
                        try:
                            children = parent.children(recursive=True)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            children = []

                        all_procs = [parent] + children
                        logger.info(f"Found {len(children)} child process(es) for PID {pid}")

                        # Kill all processes
                        for proc in all_procs:
                            try:
                                proc.kill()
                                logger.debug(f"Sent SIGKILL to PID {proc.pid}")
                                killed_count += 1
                            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                                logger.warning(f"Could not kill PID {proc.pid}: {e}")

                        # Wait for processes to die
                        gone, alive = psutil.wait_procs(all_procs, timeout=3)

                        if alive:
                            logger.error(f"Job {job_id}: {len(alive)} process(es) still alive after kill: {[p.pid for p in alive]}")
                            return False

                        logger.info(f"Successfully killed {killed_count} process(es) for job {job_id} using PID {pid}")
                        return True
                    else:
                        logger.warning(f"PID {pid} is not an FFmpeg process (name: {parent.name()})")
                except psutil.NoSuchProcess:
                    logger.info(f"PID {pid} for job {job_id} no longer exists")
                except Exception as e:
                    logger.error(f"Error killing job {job_id} by PID {pid}: {e}")

            # Strategy 2: Search for FFmpeg processes containing job_id in command line
            logger.info(f"Searching for orphaned FFmpeg processes for job {job_id}")
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and (proc.info['name'] == 'ffmpeg' or proc.info['name'].startswith('ffmpeg')):
                        cmdline = proc.info['cmdline']
                        if cmdline and job_id in ' '.join(cmdline):
                            logger.warning(f"Found orphaned FFmpeg process PID {proc.info['pid']} for job {job_id}, killing")

                            # Get children
                            try:
                                children = proc.children(recursive=True)
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                children = []

                            # Kill parent and children
                            try:
                                proc.kill()
                                for child in children:
                                    try:
                                        child.kill()
                                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                                        pass
                                killed_count += 1
                            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                                logger.error(f"Could not kill process {proc.info['pid']}: {e}")

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    logger.error(f"Error processing FFmpeg process: {e}")
                    continue

            if killed_count > 0:
                logger.info(f"Killed {killed_count} orphaned process(es) for job {job_id}")
                return True
            else:
                logger.info(f"No orphaned processes found for job {job_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to search for orphaned processes for job {job_id}: {e}")
            return False

    def is_job_running(self, job_id: str, pid: int = None) -> bool:
        """
        Check if job is currently running.

        This method checks both our tracking dictionary AND the actual system processes
        to detect orphaned FFmpeg processes.

        Args:
            job_id: Job UUID
            pid: Optional PID from database to check

        Returns:
            True if job is running, False otherwise
        """
        # First check our tracking dictionary
        if job_id in self.active_processes:
            process = self.active_processes[job_id]
            if process.returncode is None:
                return True

        # Strategy 1: Check if PID from database is still running
        if pid:
            try:
                import psutil
                try:
                    proc = psutil.Process(pid)
                    # Verify it's an ffmpeg process
                    if proc.name() and (proc.name() == 'ffmpeg' or proc.name().startswith('ffmpeg')):
                        logger.warning(f"Detected orphaned FFmpeg process for job {job_id}: PID {pid} (from database)")
                        return True
                except psutil.NoSuchProcess:
                    # PID doesn't exist, continue to strategy 2
                    pass
            except Exception as e:
                logger.error(f"Error checking PID {pid} for job {job_id}: {e}")

        # Strategy 2: Search for FFmpeg processes containing job_id in command line
        # This catches orphaned processes that failed to be killed
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and (proc.info['name'] == 'ffmpeg' or proc.info['name'].startswith('ffmpeg')):
                        cmdline = proc.info['cmdline']
                        if cmdline and job_id in ' '.join(cmdline):
                            logger.warning(f"Detected orphaned FFmpeg process for job {job_id}: PID {proc.info['pid']} (from cmdline search)")
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logger.error(f"Error checking for orphaned processes for job {job_id}: {e}")

        return False


# Global singleton instance
simple_ffmpeg_launcher = SimpleFfmpegLauncher()


__all__ = ['simple_ffmpeg_launcher']
