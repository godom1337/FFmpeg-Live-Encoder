"""Main FastAPI application"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
import logging
import uuid
import asyncio
import os
from pathlib import Path

# Import middleware and services
from middleware.cors import setup_cors
from middleware.error_handler import create_error_handlers
from middleware.api_logger import setup_api_logging
from services.storage import db_service
from services.archives_storage import archives_storage
from ws_manager.manager import connection_manager
from utils.logger import setup_logger

# Import API routes
from api.routes import jobs, analysis, presets, archives, logs, snapshots

# Setup logging
logger = setup_logger("ffmpeg_encoder")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting FFmpeg Live Encoder API")
    await db_service.initialize()
    logger.info("Database initialized")

    # Initialize archives database
    try:
        await archives_storage.initialize()
        logger.info(f"Archives database initialized at {archives_storage.db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize archives database: {e}", exc_info=True)
        # Don't crash the application - archives is optional feature

    # Recover jobs that were running before container restart
    # Run in background to not block application startup
    async def run_recovery():
        try:
            import os
            from services.job_recovery import job_recovery_service

            # Check if auto-restart is enabled
            auto_restart = os.getenv("AUTO_RESTART_JOBS_ON_BOOT", "true").lower() == "true"

            logger.info("Checking for jobs to recover after restart...")

            if auto_restart:
                # Automatically restart recovered jobs
                logger.info("Auto-restart enabled - will automatically restart recovered jobs")
                recovery_stats = await job_recovery_service.recover_with_auto_restart()
                if recovery_stats.get('recovered', 0) > 0:
                    logger.info(
                        f"Job recovery complete: {recovery_stats['recovered']} recovered, "
                        f"{recovery_stats['restarted']} restarted, {recovery_stats['failed']} failed"
                    )
                else:
                    logger.info("No jobs needed recovery")
            else:
                # Just reset to PENDING (manual restart required)
                logger.info("Auto-restart disabled - jobs will be reset to PENDING for manual restart")
                recovered_count = await job_recovery_service.recover_and_restart_jobs()
                if recovered_count > 0:
                    logger.info(f"Recovered {recovered_count} jobs - they are now in PENDING state and ready to restart")
                else:
                    logger.info("No jobs needed recovery")
        except Exception as e:
            logger.error(f"Job recovery failed during startup: {e}", exc_info=True)
            # Don't crash the application - continue running

    # Run recovery in background task
    try:
        asyncio.create_task(run_recovery())
        logger.info("Job recovery started in background")
    except Exception as e:
        logger.error(f"Failed to start job recovery: {e}", exc_info=True)

    yield
    # Shutdown
    logger.info("Shutting down FFmpeg Live Encoder API")

app = FastAPI(
    title="FFmpeg Live Encoder API",
    version="1.0.0",
    description="API for managing FFmpeg live encoding jobs",
    lifespan=lifespan
)

# Setup CORS
setup_cors(app)

# Setup error handlers
create_error_handlers(app)

# Setup API logging middleware
setup_api_logging(app)

# Register API routes
app.include_router(jobs.router)
app.include_router(analysis.router)
app.include_router(presets.router)
app.include_router(archives.router)
app.include_router(logs.router)
app.include_router(snapshots.router)

# System endpoints - MUST be defined BEFORE the catch-all frontend route
# These are defined directly on app (not in a router) so order matters
@app.get("/api/v1/system/health")
async def health_check():
    """Health check endpoint"""
    # Check database
    db_status = await db_service.health_check()

    return {
        "status": "healthy",
        "components": {
            "api": {"status": "healthy"},
            "database": db_status,
            "ffmpeg": {"status": "pending"},  # Will be implemented with job manager
            "websocket": {
                "status": "healthy",
                "connections": connection_manager.get_connection_count()
            }
        }
    }

@app.get("/api/v1/system/config")
async def system_config():
    """Get system configuration"""
    import os
    return {
        "hls_base_url": os.getenv("HLS_URL", "http://localhost/hls")
    }

@app.get("/api/v1/system/info")
async def system_info():
    """Get system information"""
    import platform
    import psutil

    return {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_total_mb": psutil.virtual_memory().total // (1024 * 1024),
        "memory_available_mb": psutil.virtual_memory().available // (1024 * 1024),
        "disk_usage": {
            "total_gb": psutil.disk_usage("/").total // (1024 * 1024 * 1024),
            "free_gb": psutil.disk_usage("/").free // (1024 * 1024 * 1024)
        },
        "websocket_stats": connection_manager.get_subscription_info()
    }

async def get_apple_silicon_gpu_stats():
    """Get Apple Silicon GPU statistics using system tools"""
    import subprocess
    import re
    import plistlib

    gpu_info = {
        "index": 0,
        "name": None,
        "temperature": None,
        "utilization": {
            "gpu": None,
            "memory": None,
            "decoder": None,
            "encoder": None
        },
        "memory": {
            "used_mb": None,
            "total_mb": None,
            "percent": None
        },
        "power": {
            "draw_watts": None,
            "limit_watts": None
        },
        "encoder": {
            "active_sessions": 0,
            "average_fps": None,
            "average_latency": None
        },
        "type": "apple_silicon",
        "video_toolbox_available": False
    }

    # Get GPU name and core count from system_profiler
    try:
        result = subprocess.run(
            ['system_profiler', 'SPDisplaysDataType', '-xml'],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            plist_data = plistlib.loads(result.stdout)
            if plist_data and len(plist_data) > 0:
                displays = plist_data[0].get('_items', [])
                for display in displays:
                    chip_type = display.get('sppci_model', '')
                    if chip_type:
                        gpu_info["name"] = chip_type
                        # Extract GPU cores if available
                        cores = display.get('sppci_cores', '')
                        if cores:
                            gpu_info["name"] = f"{chip_type} ({cores} cores)"
                        break
    except Exception as e:
        logger.debug(f"Could not get Apple GPU info from system_profiler: {e}")

    # Fallback: get chip name from sysctl
    if not gpu_info["name"]:
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'machdep.cpu.brand_string'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                brand = result.stdout.strip()
                # Extract M-series chip name
                match = re.search(r'Apple M\d+\s*(Pro|Max|Ultra)?', brand)
                if match:
                    gpu_info["name"] = f"{match.group(0)} GPU"
                else:
                    gpu_info["name"] = "Apple Silicon GPU"
        except Exception:
            gpu_info["name"] = "Apple Silicon GPU"

    # Check if VideoToolbox hardware encoder is available
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            if 'h264_videotoolbox' in result.stdout or 'hevc_videotoolbox' in result.stdout:
                gpu_info["video_toolbox_available"] = True
    except Exception as e:
        logger.debug(f"Could not check VideoToolbox availability: {e}")

    # Get GPU utilization using powermetrics (requires sudo, so may not work)
    # We'll try ioreg as a fallback which doesn't need elevated privileges
    try:
        # Try to get GPU utilization from ioreg (limited info but no sudo needed)
        result = subprocess.run(
            ['ioreg', '-r', '-c', 'AGXAccelerator', '-d', '1'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and 'AGXAccelerator' in result.stdout:
            # GPU is available and active
            # Unfortunately ioreg doesn't give us utilization directly
            # We can at least confirm the GPU is present
            pass
    except Exception as e:
        logger.debug(f"Could not query AGXAccelerator: {e}")

    # Get memory pressure as a proxy for unified memory usage
    # On Apple Silicon, GPU shares memory with CPU
    try:
        import psutil
        mem = psutil.virtual_memory()
        # Calculate unified memory stats
        # Apple Silicon uses unified memory, so GPU memory = system memory
        gpu_info["memory"]["total_mb"] = mem.total // (1024 * 1024)
        gpu_info["memory"]["used_mb"] = (mem.total - mem.available) // (1024 * 1024)
        gpu_info["memory"]["percent"] = round(mem.percent, 1)
    except Exception as e:
        logger.debug(f"Could not get memory stats for Apple GPU: {e}")

    # Only return if we have at least a name
    if gpu_info["name"]:
        return gpu_info
    return None


@app.get("/api/v1/system/metrics")
async def system_metrics():
    """Get real-time system metrics for monitoring"""
    import psutil
    import subprocess
    import json

    # Get CPU usage (percentage)
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # Get per-CPU usage
    cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)

    # Get memory usage
    memory = psutil.virtual_memory()
    memory_used_mb = (memory.total - memory.available) // (1024 * 1024)
    memory_total_mb = memory.total // (1024 * 1024)
    memory_percent = memory.percent

    # Get disk usage
    disk = psutil.disk_usage("/")
    disk_used_gb = (disk.total - disk.free) // (1024 * 1024 * 1024)
    disk_total_gb = disk.total // (1024 * 1024 * 1024)
    disk_percent = disk.percent

    # Get GPU stats (NVIDIA or Apple Silicon)
    gpu_stats = []

    # Try NVIDIA GPU first
    try:
        # Use nvidia-smi to get GPU information in JSON format
        result = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=index,name,temperature.gpu,utilization.gpu,utilization.memory,utilization.decoder,utilization.encoder,memory.used,memory.total,power.draw,power.limit,encoder.stats.sessionCount,encoder.stats.averageFps,encoder.stats.averageLatency',
                '--format=csv,noheader,nounits'
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 9:
                        gpu_stats.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "temperature": float(parts[2]) if parts[2] != '[N/A]' else None,
                            "utilization": {
                                "gpu": float(parts[3]) if parts[3] != '[N/A]' else None,
                                "memory": float(parts[4]) if parts[4] != '[N/A]' else None,
                                "decoder": float(parts[5]) if parts[5] != '[N/A]' else None,
                                "encoder": float(parts[6]) if parts[6] != '[N/A]' else None
                            },
                            "memory": {
                                "used_mb": int(parts[7]) if parts[7] != '[N/A]' else None,
                                "total_mb": int(parts[8]) if parts[8] != '[N/A]' else None,
                                "percent": round((int(parts[7]) / int(parts[8]) * 100), 1) if parts[7] != '[N/A]' and parts[8] != '[N/A]' and int(parts[8]) > 0 else None
                            },
                            "power": {
                                "draw_watts": float(parts[9]) if parts[9] != '[N/A]' else None,
                                "limit_watts": float(parts[10]) if parts[10] != '[N/A]' else None
                            },
                            "encoder": {
                                "active_sessions": int(parts[11]) if len(parts) > 11 and parts[11] != '[N/A]' else 0,
                                "average_fps": float(parts[12]) if len(parts) > 12 and parts[12] != '[N/A]' else None,
                                "average_latency": float(parts[13]) if len(parts) > 13 and parts[13] != '[N/A]' else None
                            }
                        })
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        logger.debug(f"Could not get NVIDIA GPU stats: {e}")
        # NVIDIA GPU not available or nvidia-smi not found

    # If no NVIDIA GPU found, try Apple Silicon GPU
    if not gpu_stats:
        try:
            import platform
            if platform.system() == "Darwin" and platform.machine() == "arm64":
                apple_gpu = await get_apple_silicon_gpu_stats()
                if apple_gpu:
                    gpu_stats.append(apple_gpu)
        except Exception as e:
            logger.debug(f"Could not get Apple Silicon GPU stats: {e}")

    response = {
        "cpu": {
            "percent": round(cpu_percent, 1),
            "count": psutil.cpu_count(),
            "per_core": [round(p, 1) for p in cpu_per_core] if cpu_per_core else []
        },
        "memory": {
            "used_mb": memory_used_mb,
            "total_mb": memory_total_mb,
            "percent": round(memory_percent, 1),
            "available_mb": memory.available // (1024 * 1024)
        },
        "disk": {
            "used_gb": disk_used_gb,
            "total_gb": disk_total_gb,
            "percent": round(disk_percent, 1)
        }
    }

    # Add GPU stats if available
    if gpu_stats:
        response["gpu"] = gpu_stats

    return response

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    connection_id = str(uuid.uuid4())

    await connection_manager.connect(websocket, connection_id)

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            await connection_manager.handle_message(connection_id, data)

    except WebSocketDisconnect:
        await connection_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
        await connection_manager.disconnect(connection_id)

# Serve frontend static files
# Look for frontend dist directory relative to this file
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    # Mount static assets (CSS, JS, etc.)
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    # Serve index.html for all non-API routes (SPA fallback)
    # NOTE: This MUST be the last route defined, as it's a catch-all
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend SPA - catch-all route for client-side routing"""
        # Don't serve frontend for API routes - let them 404 properly
        if full_path.startswith("api/") or full_path.startswith("ws"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API endpoint not found")

        # Serve index.html for all other routes
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))

        return {"status": "healthy", "service": "FFmpeg Live Encoder API"}
else:
    logger.warning(f"Frontend dist directory not found at {frontend_dist}")

    @app.get("/")
    async def root():
        """Root endpoint"""
        return {"status": "healthy", "service": "FFmpeg Live Encoder API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)