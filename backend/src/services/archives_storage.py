"""
Archives Storage Service

Manages the archives.db database for storing archived/deleted jobs.
Uses the same simple pattern as the main database (jobs.db).
"""

import os
import json
import aiosqlite
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

class ArchivesStorageService:
    """Service for managing archived jobs in a separate SQLite database."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the archives storage service.

        Args:
            db_path: Path to the archives SQLite database
        """
        # Default to local data directory for development, /data for Docker
        # Use same directory as DB_PATH (jobs.db) for consistency
        db_path_env = os.getenv("DB_PATH")
        if db_path_env:
            default_archives_path = os.path.join(os.path.dirname(db_path_env), "archives.db")
        else:
            default_archives_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "archives.db")
        self.db_path = db_path or os.getenv("ARCHIVES_DB_PATH", default_archives_path)
        self.wal_mode = True
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize archives database and create tables if needed"""
        if self._initialized:
            return

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        async with self.get_connection() as db:
            # Enable WAL mode for better concurrency
            if self.wal_mode:
                await db.execute("PRAGMA journal_mode = WAL")
                await db.execute("PRAGMA busy_timeout = 5000")

            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")

            # Create archived_jobs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS archived_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    profile_id TEXT,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    stopped_at TIMESTAMP,
                    pid INTEGER,
                    error_message TEXT,
                    command TEXT,
                    priority INTEGER DEFAULT 5,
                    archive_on_complete BOOLEAN DEFAULT 0,
                    video_codec TEXT,
                    audio_codec TEXT,
                    video_bitrate TEXT,
                    audio_bitrate TEXT,
                    audio_volume INTEGER CHECK(audio_volume >= 0 AND audio_volume <= 100),
                    hardware_accel TEXT,
                    template_id TEXT,
                    custom_args TEXT,
                    full_config TEXT,  -- JSON cache of complete unified job configuration (Feature: 001-edit-api-simplification)
                    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    archived_reason TEXT DEFAULT 'manual_deletion',
                    original_db_id TEXT NOT NULL
                )
            """)

            # Create archived_input_sources table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS archived_input_sources (
                    job_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    url TEXT NOT NULL,
                    loop_enabled BOOLEAN DEFAULT FALSE,
                    hardware_accel TEXT,
                    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES archived_jobs(id) ON DELETE CASCADE
                )
            """)

            # Create archived_output_configurations table (matches main schema output_configurations)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS archived_output_configurations (
                    job_id TEXT PRIMARY KEY,
                    output_type TEXT DEFAULT 'hls',
                    output_url TEXT,

                    -- Serialized Pydantic models (Option 2: Pydantic Serialization)
                    hls_config TEXT,
                    udp_config TEXT,
                    file_config TEXT,

                    -- Legacy flat columns (maintained for backward compatibility and simple queries)
                    base_path TEXT,
                    variant_paths TEXT NOT NULL DEFAULT '{}',
                    nginx_served BOOLEAN DEFAULT 1,
                    manifest_url TEXT,
                    segment_duration INTEGER DEFAULT 6,
                    playlist_size INTEGER DEFAULT 10,
                    playlist_type TEXT DEFAULT 'live' CHECK(playlist_type IN ('vod', 'event', 'live')),
                    segment_type TEXT DEFAULT 'mpegts' CHECK(segment_type IN ('mpegts', 'fmp4')),
                    segment_pattern TEXT DEFAULT 'segment_%03d.ts',
                    video_codec TEXT,
                    video_bitrate TEXT,
                    video_resolution TEXT,
                    video_framerate INTEGER,
                    audio_codec TEXT,
                    audio_bitrate TEXT,
                    audio_channels INTEGER,
                    audio_volume INTEGER CHECK(audio_volume >= 0 AND audio_volume <= 100),
                    audio_stream_index INTEGER,
                    abr_enabled BOOLEAN DEFAULT 0,
                    renditions TEXT,
                    encoding_preset TEXT,
                    crf INTEGER,
                    keyframe_interval INTEGER,
                    tune TEXT,
                    two_pass BOOLEAN DEFAULT 0,
                    rate_control_mode TEXT,
                    profile TEXT,
                    video_profile TEXT,
                    level TEXT,
                    max_bitrate TEXT,
                    buffer_size TEXT,
                    look_ahead INTEGER,
                    pixel_format TEXT,
                    stream_maps TEXT,
                    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES archived_jobs(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            await db.execute("CREATE INDEX IF NOT EXISTS idx_archived_jobs_archived_at ON archived_jobs(archived_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_archived_jobs_status ON archived_jobs(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_archived_jobs_name ON archived_jobs(name)")

            await db.commit()
            logger.info(f"Archives database initialized at {self.db_path}")

        self._initialized = True

    @asynccontextmanager
    async def get_connection(self):
        """Get an async database connection context manager."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    async def execute(self, query: str, params: Optional[tuple] = None) -> None:
        """Execute a query and commit."""
        async with self.get_connection() as conn:
            await conn.execute(query, params or ())
            await conn.commit()

    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params or ())
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params or ())
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def archive_job(
        self,
        job_data: Dict[str, Any],
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        reason: str = "manual_deletion"
    ) -> bool:
        """Archive a job by moving its data to the archives database."""
        async with self.get_connection() as conn:
            try:
                # Delete any existing archived data for this job (handles re-archiving restored jobs)
                # Must delete from child tables first, then parent (in case FK cascade isn't working)
                await conn.execute("DELETE FROM archived_input_sources WHERE job_id = ?", (job_data['id'],))
                await conn.execute("DELETE FROM archived_output_configurations WHERE job_id = ?", (job_data['id'],))
                await conn.execute("DELETE FROM archived_jobs WHERE id = ?", (job_data['id'],))

                # Serialize JSON fields
                hardware_accel = input_data.get('hardware_accel')
                if isinstance(hardware_accel, dict):
                    hardware_accel = json.dumps(hardware_accel)

                variant_paths = output_data.get('variant_paths')
                if isinstance(variant_paths, (dict, list)):
                    variant_paths = json.dumps(variant_paths)

                renditions = output_data.get('renditions')
                if isinstance(renditions, (dict, list)):
                    renditions = json.dumps(renditions)

                # Insert job
                await conn.execute("""
                    INSERT INTO archived_jobs (
                        id, name, profile_id, status, created_at, started_at,
                        stopped_at, pid, error_message, command, priority,
                        video_codec, audio_codec, video_bitrate, audio_bitrate,
                        audio_volume, hardware_accel, template_id, custom_args,
                        full_config, archived_reason, original_db_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_data['id'], job_data['name'], job_data.get('profile_id'),
                    job_data['status'], job_data.get('created_at'), job_data.get('started_at'),
                    job_data.get('stopped_at'), job_data.get('pid'), job_data.get('error_message'),
                    job_data.get('command'), job_data.get('priority', 5),
                    job_data.get('video_codec'), job_data.get('audio_codec'),
                    job_data.get('video_bitrate'), job_data.get('audio_bitrate'),
                    job_data.get('audio_volume'), job_data.get('hardware_accel'),
                    job_data.get('template_id'), job_data.get('custom_args'),
                    job_data.get('full_config'), reason, job_data['id']
                ))

                # Insert input source
                await conn.execute("""
                    INSERT INTO archived_input_sources (
                        job_id, type, url, loop_enabled, hardware_accel
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    input_data['job_id'], input_data['type'], input_data['url'],
                    input_data.get('loop_enabled', False), hardware_accel
                ))

                # Serialize additional JSON fields
                hls_config = output_data.get('hls_config')
                if isinstance(hls_config, dict):
                    hls_config = json.dumps(hls_config)
                udp_config = output_data.get('udp_config')
                if isinstance(udp_config, dict):
                    udp_config = json.dumps(udp_config)
                file_config = output_data.get('file_config')
                if isinstance(file_config, dict):
                    file_config = json.dumps(file_config)
                stream_maps = output_data.get('stream_maps')
                if isinstance(stream_maps, (dict, list)):
                    stream_maps = json.dumps(stream_maps)

                # Insert output configuration (all columns matching main schema)
                await conn.execute("""
                    INSERT INTO archived_output_configurations (
                        job_id, output_type, output_url,
                        hls_config, udp_config, file_config,
                        base_path, variant_paths, nginx_served, manifest_url,
                        segment_duration, playlist_size, playlist_type, segment_type, segment_pattern,
                        video_codec, video_bitrate, video_resolution, video_framerate,
                        audio_codec, audio_bitrate, audio_channels, audio_volume, audio_stream_index,
                        abr_enabled, renditions,
                        encoding_preset, crf, keyframe_interval, tune, two_pass,
                        rate_control_mode, profile, video_profile, level,
                        max_bitrate, buffer_size, look_ahead, pixel_format, stream_maps
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    output_data['job_id'], output_data.get('output_type', 'hls'),
                    output_data.get('output_url'),
                    hls_config, udp_config, file_config,
                    output_data.get('base_path'), variant_paths,
                    output_data.get('nginx_served', True), output_data.get('manifest_url'),
                    output_data.get('segment_duration'), output_data.get('playlist_size'),
                    output_data.get('playlist_type'), output_data.get('segment_type'),
                    output_data.get('segment_pattern'),
                    output_data.get('video_codec'), output_data.get('video_bitrate'),
                    output_data.get('video_resolution'), output_data.get('video_framerate'),
                    output_data.get('audio_codec'), output_data.get('audio_bitrate'),
                    output_data.get('audio_channels'), output_data.get('audio_volume'),
                    output_data.get('audio_stream_index'),
                    output_data.get('abr_enabled', False), renditions,
                    output_data.get('encoding_preset'), output_data.get('crf'),
                    output_data.get('keyframe_interval'), output_data.get('tune'),
                    output_data.get('two_pass', False),
                    output_data.get('rate_control_mode'), output_data.get('profile'),
                    output_data.get('video_profile'), output_data.get('level'),
                    output_data.get('max_bitrate'), output_data.get('buffer_size'),
                    output_data.get('look_ahead'), output_data.get('pixel_format'),
                    stream_maps
                ))

                await conn.commit()
                return True

            except Exception as e:
                await conn.rollback()
                logger.error(f"Error archiving job: {e}")
                return False

    async def list_archived_jobs(self, limit: int = 100, offset: int = 0, order_by: str = "archived_at DESC") -> List[Dict[str, Any]]:
        """List all archived jobs with their full configuration."""
        query = f"""
            SELECT
                aj.*,
                ais.type as input_type,
                ais.url as input_url,
                ais.loop_enabled as input_loop_enabled,
                ais.hardware_accel as input_hardware_accel,
                aoc.output_type,
                aoc.output_url,
                aoc.base_path,
                aoc.variant_paths,
                aoc.manifest_url
            FROM archived_jobs aj
            LEFT JOIN archived_input_sources ais ON aj.id = ais.job_id
            LEFT JOIN archived_output_configurations aoc ON aj.id = aoc.job_id
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """
        return await self.fetch_all(query, (limit, offset))

    async def get_archived_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific archived job with full configuration."""
        query = """
            SELECT
                aj.*,
                ais.type as input_type,
                ais.url as input_url,
                aoc.output_type
            FROM archived_jobs aj
            LEFT JOIN archived_input_sources ais ON aj.id = ais.job_id
            LEFT JOIN archived_output_configurations aoc ON aj.id = aoc.job_id
            WHERE aj.id = ?
        """
        return await self.fetch_one(query, (job_id,))

    async def get_archived_job_parts(self, job_id: str) -> Optional[tuple]:
        """Get archived job split into job, input, and output components."""
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM archived_jobs WHERE id = ?", (job_id,))
            job_row = await cursor.fetchone()
            if not job_row:
                return None

            cursor = await conn.execute("SELECT * FROM archived_input_sources WHERE job_id = ?", (job_id,))
            input_row = await cursor.fetchone()

            cursor = await conn.execute("SELECT * FROM archived_output_configurations WHERE job_id = ?", (job_id,))
            output_row = await cursor.fetchone()

            return (dict(job_row) if job_row else None, dict(input_row) if input_row else None, dict(output_row) if output_row else None)

    async def delete_archived_job(self, job_id: str) -> bool:
        """Permanently delete an archived job."""
        await self.execute("DELETE FROM archived_jobs WHERE id = ?", (job_id,))
        return True

    async def count_archived_jobs(self) -> int:
        """Count total number of archived jobs."""
        result = await self.fetch_one("SELECT COUNT(*) as count FROM archived_jobs")
        return result['count'] if result else 0


# Global instance
archives_storage = ArchivesStorageService()
