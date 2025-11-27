#!/usr/bin/env python3
"""Initialize the database with schema and default data"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.storage import db_service
from services.archives_storage import archives_storage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """Initialize database with schema"""
    try:
        # Initialize main jobs database
        await db_service.initialize()

        # Initialize archives database
        await archives_storage.initialize()

        async with db_service.get_connection() as db:
            # Read and execute schema (will be created in T013)
            schema_path = Path(__file__).parent / "schema.sql"
            if schema_path.exists():
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()

                # Execute the entire schema as a script
                await db.executescript(schema_sql)
                logger.info("Executed schema.sql successfully")
            else:
                logger.warning("schema.sql not found, skipping schema creation")
                return

            # Insert default profiles matching the schema
            default_profiles = [
                # id, name, codec, encoder, audio_codec, segment_format, segment_duration, playlist_size, delete_segments, is_default
                ('default-hls-h264', 'Standard HLS (H.264)', 'h264', 'cpu', 'aac', 'ts', 6, 10, 1, 1),
                ('low-latency-hls', 'Low Latency HLS', 'h264', 'cpu', 'aac', 'ts', 2, 10, 1, 0),
                ('high-quality-h265', 'High Quality H.265', 'h265', 'cpu', 'aac', 'ts', 6, 10, 1, 0),
            ]

            for profile in default_profiles:
                await db.execute("""
                    INSERT OR IGNORE INTO encoding_profiles
                    (id, name, codec, encoder, audio_codec, segment_format, segment_duration, playlist_size, delete_segments, is_default)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, profile)

            # Insert default bitrate variants for the default profile
            default_variants = [
                # id, profile_id, label, width, height, video_bitrate, max_rate, buffer_size, order_index
                ('var-720p-default', 'default-hls-h264', '720p', 1280, 720, '5M', '5.5M', '10M', 0),
                ('var-480p-default', 'default-hls-h264', '480p', 854, 480, '2.5M', '3M', '5M', 1),
                ('var-360p-default', 'default-hls-h264', '360p', 640, 360, '1M', '1.5M', '2M', 2),
            ]

            for variant in default_variants:
                await db.execute("""
                    INSERT OR IGNORE INTO bitrate_variants
                    (id, profile_id, label, width, height, video_bitrate, max_rate, buffer_size, order_index)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, variant)

            await db.commit()
            logger.info("Database initialization completed successfully")

            # Verify tables
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            logger.info(f"Created tables: {[t[0] for t in tables]}")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def reset_database():
    """Reset database (for development)"""
    if os.path.exists(db_service.db_path):
        os.remove(db_service.db_path)
        logger.info(f"Removed existing database: {db_service.db_path}")

    await init_database()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Initialize database")
    parser.add_argument("--reset", action="store_true", help="Reset database (delete and recreate)")
    args = parser.parse_args()

    if args.reset:
        asyncio.run(reset_database())
    else:
        asyncio.run(init_database())