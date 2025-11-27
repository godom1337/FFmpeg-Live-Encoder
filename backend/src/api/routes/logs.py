"""
Container Logs API Endpoints
Handles streaming of Docker container logs in real-time
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import logging
import asyncio
import subprocess
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_log_directory() -> str:
    """Get the logs directory path, works in both Docker and local mode.

    In Docker: /app/backend/src/logs exists
    In local: Job logs are written to src/logs relative to working directory (backend/src/)
              which results in backend/src/src/logs/
    """
    docker_path = "/app/backend/src/logs"
    if os.path.exists(docker_path):
        return docker_path

    # Local mode: job logs are written to "src/logs" from working dir (backend/src/)
    # So they end up in backend/src/src/logs/
    local_path = Path(__file__).parent.parent.parent / "src" / "logs"
    if os.path.exists(local_path):
        return str(local_path)

    # Fallback: try backend/src/logs
    fallback_path = Path(__file__).parent.parent.parent / "logs"
    return str(fallback_path)


def get_api_log_file() -> str:
    """Get the API log file path, works in both Docker and local mode.

    API logs are written by middleware to middleware/logs/api_requests.log
    """
    docker_path = "/app/backend/src/logs/api_requests.log"
    if os.path.exists(docker_path):
        return docker_path

    # Local mode: API logs are in middleware/logs/
    middleware_log = Path(__file__).parent.parent.parent / "middleware" / "logs" / "api_requests.log"
    return str(middleware_log)

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@router.get("/container/stream")
async def stream_container_logs(
    lines: Optional[int] = Query(100, description="Number of historical lines to fetch initially"),
    follow: Optional[bool] = Query(True, description="Follow log output (real-time streaming)")
):
    """Stream Docker container logs in real-time

    This endpoint streams logs from the current Docker container.
    It first returns the last N lines of logs, then continues streaming new logs.

    Args:
        lines: Number of historical lines to fetch (default: 100)
        follow: Whether to follow/stream new logs in real-time (default: True)

    Returns:
        StreamingResponse: Server-sent events stream of log lines

    Raises:
        HTTPException: If unable to access container logs
    """

    async def log_generator():
        """Generate log lines from Docker container"""
        try:
            # Get the container name from environment or use default
            container_name = os.getenv("HOSTNAME", "ffmpeg-encoder")

            # Build docker logs command
            # We're running inside the container, so we need to get logs from the host's Docker daemon
            # This requires the Docker socket to be mounted or use docker exec from outside

            # For now, we'll stream the application logs from the logs directory
            # This is more reliable when running inside the container
            log_dir = get_log_directory()

            # Try to get container logs if Docker is available and container is running
            container_running = False
            try:
                # Check if the specific container is running (not just exists)
                result = subprocess.run(
                    ["docker", "ps", "-q", "-f", f"name={container_name}"],
                    capture_output=True,
                    timeout=2
                )
                # Container is running if we get output (container ID)
                container_running = result.returncode == 0 and result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                container_running = False

            if container_running:
                # Use docker logs command - tail shows most recent logs first
                cmd = [
                    "docker", "logs",
                    "--tail", str(lines),
                    "--follow" if follow else ""
                ]

                # Remove empty strings from cmd
                cmd = [c for c in cmd if c]
                cmd.append(container_name)

                logger.info(f"Streaming Docker container logs: {' '.join(cmd)}")

                # Start the docker logs process
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )

                # Stream output line by line
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        # Process ended
                        break

                    # Decode and send the line
                    log_line = line.decode('utf-8', errors='replace').rstrip('\n')
                    yield f"data: {log_line}\n\n"

                    # Small delay to prevent overwhelming the client
                    await asyncio.sleep(0.01)

                # Wait for process to complete
                await process.wait()

            else:
                # Fallback: Stream application logs from the logs directory
                logger.info(f"Container '{container_name}' not running, streaming application logs from file system")

                # Find all log files in the logs directory
                import glob
                log_files = glob.glob(f"{log_dir}/*.log")

                if not log_files:
                    yield f"data: [INFO] No log files found in {log_dir}\n\n"
                    yield f"data: [INFO] Container logs may not be available from inside the container\n\n"
                    return

                # Sort by modification time (newest first)
                log_files.sort(key=os.path.getmtime, reverse=True)

                # For initial logs, show last N lines from the most recent log file
                main_log = log_files[0]

                try:
                    # Use tail command to get last N lines (tail shows most recent logs)
                    cmd = ["tail", "-n", str(lines)]
                    if follow:
                        cmd.append("-f")
                    cmd.append(main_log)

                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    # Stream output
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            break

                        log_line = line.decode('utf-8', errors='replace').rstrip('\n')
                        yield f"data: {log_line}\n\n"
                        await asyncio.sleep(0.01)

                except Exception as e:
                    logger.error(f"Error reading log file: {e}")
                    yield f"data: [ERROR] Failed to read log file: {e}\n\n"

        except Exception as e:
            logger.error(f"Error streaming container logs: {e}", exc_info=True)
            yield f"data: [ERROR] Failed to stream logs: {e}\n\n"

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/container/tail")
async def get_container_logs_tail(
    lines: Optional[int] = Query(100, description="Number of lines to fetch")
):
    """Get the last N lines of container logs (snapshot, not streaming)

    This endpoint returns a snapshot of the last N lines of container logs.
    Use the /stream endpoint for real-time streaming.

    Args:
        lines: Number of lines to fetch (default: 100)

    Returns:
        dict: Log lines and metadata

    Raises:
        HTTPException: If unable to access container logs
    """
    try:
        container_name = os.getenv("HOSTNAME", "ffmpeg-encoder")
        docker_success = False

        # Try to get Docker container logs
        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "logs",
                "--tail", str(lines),
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                log_lines = stdout.decode('utf-8', errors='replace').split('\n')
                return {
                    "success": True,
                    "source": "docker",
                    "container": container_name,
                    "lines": [line for line in log_lines if line.strip()],
                    "total_lines": len([line for line in log_lines if line.strip()])
                }
            else:
                # Docker command failed (container doesn't exist, etc.)
                logger.info(f"Docker logs failed for {container_name}, falling back to file logs")
        except Exception as e:
            logger.warning(f"Could not get Docker logs: {e}")

        # Fallback: Get application logs
        log_dir = get_log_directory()
        import glob

        log_files = glob.glob(f"{log_dir}/*.log")
        if not log_files:
            return {
                "success": False,
                "source": "none",
                "message": "No logs available",
                "lines": []
            }

        # Get the most recent log file
        log_files.sort(key=os.path.getmtime, reverse=True)
        main_log = log_files[0]

        # Read last N lines
        result = await asyncio.create_subprocess_exec(
            "tail",
            "-n", str(lines),
            main_log,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, _ = await result.communicate()
        log_lines = stdout.decode('utf-8', errors='replace').split('\n')

        return {
            "success": True,
            "source": "application_logs",
            "log_file": os.path.basename(main_log),
            "lines": [line for line in log_lines if line.strip()],
            "total_lines": len([line for line in log_lines if line.strip()])
        }

    except Exception as e:
        logger.error(f"Failed to get container logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get container logs", "error": str(e)}
        )


@router.get("/api/stream")
async def stream_api_logs(
    lines: Optional[int] = Query(100, description="Number of historical lines to fetch initially"),
    follow: Optional[bool] = Query(True, description="Follow log output (real-time streaming)")
):
    """Stream API request logs in real-time

    This endpoint streams API request/response logs for monitoring API usage.

    Args:
        lines: Number of historical lines to fetch (default: 100)
        follow: Whether to follow/stream new logs in real-time (default: True)

    Returns:
        StreamingResponse: Server-sent events stream of API log lines
    """

    async def api_log_generator():
        """Generate API log lines"""
        try:
            api_log_file = get_api_log_file()

            # Check if log file exists
            if not os.path.exists(api_log_file):
                yield f"data: [INFO] No API logs available yet\n\n"
                return

            # Build tail command - same as container logs
            cmd = ["tail", "-n", str(lines)]
            if follow:
                cmd.append("-f")
            cmd.append(api_log_file)

            logger.info(f"Streaming API logs: {' '.join(cmd)}")

            # Start the tail process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Stream output line by line
            while True:
                line = await process.stdout.readline()
                if not line:
                    # Process ended
                    break

                # Decode and send the line
                log_line = line.decode('utf-8', errors='replace').rstrip('\n')
                if log_line.strip():  # Skip empty lines
                    yield f"data: {log_line}\n\n"

                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)

            # Wait for process to complete
            await process.wait()

        except Exception as e:
            logger.error(f"Error streaming API logs: {e}")
            yield f"data: [ERROR] Failed to stream logs: {str(e)}\n\n"

    return StreamingResponse(
        api_log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/api/tail")
async def get_api_logs_tail(
    lines: Optional[int] = Query(100, description="Number of lines to return")
):
    """Get the last N lines of API logs (snapshot)

    Args:
        lines: Number of lines to return (default: 100)

    Returns:
        dict: Log lines and metadata
    """
    try:
        api_log_file = get_api_log_file()

        # Check if log file exists
        if not os.path.exists(api_log_file):
            return {
                "success": True,
                "source": "api_logs",
                "message": "No API logs available yet",
                "lines": []
            }

        # Read last N lines using tail
        result = await asyncio.create_subprocess_exec(
            "tail",
            "-n", str(lines),
            api_log_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, _ = await result.communicate()
        log_lines = stdout.decode('utf-8', errors='replace').split('\n')

        return {
            "success": True,
            "source": "api_logs",
            "log_file": "api_requests.log",
            "lines": [line for line in log_lines if line.strip()],
            "total_lines": len([line for line in log_lines if line.strip()])
        }

    except Exception as e:
        logger.error(f"Failed to get API logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"message": "Failed to get API logs", "error": str(e)}
        )
