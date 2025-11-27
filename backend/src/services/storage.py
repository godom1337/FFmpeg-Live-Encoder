"""SQLite database connection and management"""

import os
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    """Manages SQLite database connections"""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database service

        Args:
            db_path: Path to SQLite database file
        """
        # Default to local data directory for development, /data for Docker
        default_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jobs.db")
        self.db_path = db_path or os.getenv("DB_PATH", default_db_path)
        self.wal_mode = os.getenv("DB_WAL_MODE", "true").lower() == "true"
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database and create tables if needed"""
        if self._initialized:
            return

        # Ensure directory exists with proper permissions
        db_dir = os.path.dirname(self.db_path)
        try:
            os.makedirs(db_dir, exist_ok=True)
            # Try to set permissions if possible (might fail if not owner)
            try:
                os.chmod(db_dir, 0o755)
            except (OSError, PermissionError):
                pass
        except Exception as e:
            logger.error(f"Failed to create database directory {db_dir}: {e}")
            raise

        try:
            async with self.get_connection() as db:
                # Try to enable WAL mode first (before testing write)
                # WAL mode can fail on network filesystems or cross-platform volumes
                if self.wal_mode:
                    try:
                        result = await db.execute("PRAGMA journal_mode = WAL")
                        journal_mode = await result.fetchone()
                        if journal_mode and journal_mode[0].lower() == 'wal':
                            logger.info("WAL mode enabled successfully")
                            await db.execute("PRAGMA busy_timeout = 5000")
                        else:
                            logger.warning(f"WAL mode not available, using {journal_mode[0] if journal_mode else 'default'} mode")
                    except Exception as e:
                        logger.warning(f"Could not enable WAL mode: {e}. Using DELETE mode instead.")
                        # Fall back to DELETE mode (default)
                        await db.execute("PRAGMA journal_mode = DELETE")

                # Test write access
                try:
                    await db.execute("CREATE TABLE IF NOT EXISTS _write_test (id INTEGER)")
                    await db.execute("DROP TABLE IF EXISTS _write_test")
                    await db.commit()
                except Exception as e:
                    logger.error(f"Database is read-only or not writable: {e}")
                    logger.error(f"Database path: {self.db_path}")
                    logger.error(f"Check permissions on {self.db_path} and {db_dir}")
                    raise Exception(f"Database is read-only: {e}")

                # Enable foreign keys
                await db.execute("PRAGMA foreign_keys = ON")

                # Create tables (will be defined in T013)
                # For now, create a simple version table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await db.commit()
                logger.info(f"Database initialized successfully at {self.db_path}")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

        self._initialized = True

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Get a database connection

        Yields:
            aiosqlite.Connection: Database connection
        """
        # Get timeout from env var or use 30 seconds default (increased from 5s)
        timeout_ms = int(os.getenv("DB_BUSY_TIMEOUT", "30000"))

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Set busy timeout for this connection to handle concurrent writes better
            await db.execute(f"PRAGMA busy_timeout = {timeout_ms}")
            yield db

    async def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a single query

        Args:
            query: SQL query to execute
            params: Query parameters
        """
        async with self.get_connection() as db:
            await db.execute(query, params)
            await db.commit()

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Optional[dict]: Row as dictionary or None
        """
        async with self.get_connection() as db:
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            list[dict]: List of rows as dictionaries
        """
        async with self.get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def health_check(self) -> dict:
        """Check database health

        Returns:
            dict: Health status
        """
        try:
            await self.execute("SELECT 1")
            return {"status": "healthy", "database": self.db_path}
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

# Global instance
db_service = DatabaseService()