#!/usr/bin/env python3
"""
Apply database migration to support HTTP input type
"""

import sqlite3
import os
import sys
import shutil
from datetime import datetime

def backup_database(db_path):
    """Create a backup of the database before migration"""
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to backup database: {e}")
        return None

def apply_migration(db_path):
    """Apply the HTTP input type migration"""
    # Read the migration script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    migration_file = os.path.join(script_dir, 'migrate_http_input.sql')

    if not os.path.exists(migration_file):
        print(f"❌ Migration file not found: {migration_file}")
        return False

    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if migration is needed
        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type = 'table' AND name = 'input_sources'
        """)
        result = cursor.fetchone()

        if result and "'tcp'" in result[0]:
            print("📋 Migration needed: TCP -> HTTP")

            # Apply migration
            cursor.executescript(migration_sql)
            conn.commit()

            print("✅ Migration applied successfully!")

            # Show current input types
            cursor.execute("SELECT DISTINCT type FROM input_sources")
            types = cursor.fetchall()
            if types:
                print(f"📊 Current input types in database: {', '.join([t[0] for t in types])}")
            else:
                print("📊 No input sources in database yet")

        else:
            print("✅ Database already supports HTTP input type")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def main():
    # Default database path
    db_path = os.getenv("DB_PATH", "/data/jobs.db")

    # Allow override from command line
    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    print(f"🔄 Migrating database: {db_path}")

    # Check if database exists
    if not os.path.exists(db_path):
        print(f"⚠️  Database not found at {db_path}")
        print("   This is normal for fresh installations.")
        print("   The schema will be created with HTTP support on first run.")
        return 0

    # Backup database
    backup_path = backup_database(db_path)
    if not backup_path:
        print("⚠️  Continuing without backup...")

    # Apply migration
    if apply_migration(db_path):
        print("🎉 Migration completed successfully!")
        return 0
    else:
        print("❌ Migration failed!")
        if backup_path:
            print(f"   You can restore from backup: {backup_path}")
        return 1

if __name__ == "__main__":
    sys.exit(main())