#!/usr/bin/env python3
"""
Database migration tool for OneStack

Usage:
    python scripts/migrate.py        # Apply all pending migrations
    python scripts/migrate.py status # Show migration status
    python scripts/migrate.py list   # List all migrations
"""

import os
import sys
import glob
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path to import services
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


def get_db_connection():
    """Get direct PostgreSQL connection for migration operations"""
    import psycopg2

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL not found in environment")
        print("Please add DATABASE_URL to .env file:")
        print("  DATABASE_URL=postgresql://user:password@host:port/database")
        sys.exit(1)

    return psycopg2.connect(database_url)


def ensure_migrations_table(conn):
    """Create migrations tracking table if it doesn't exist"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kvota.migrations (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum VARCHAR(64)
            );

            COMMENT ON TABLE kvota.migrations IS 'Tracks applied database migrations';
        """)
        conn.commit()


def get_applied_migrations(conn):
    """Get list of already applied migrations"""
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM kvota.migrations ORDER BY filename")
        return {row[0] for row in cur.fetchall()}


def get_migration_files():
    """Get all migration files sorted by number"""
    migration_dir = Path(__file__).parent.parent / "migrations"
    files = glob.glob(str(migration_dir / "*.sql"))

    # Filter out special files
    filtered = []
    for f in files:
        filename = os.path.basename(f)
        # Skip files that don't start with a number
        if not re.match(r'^\d+_', filename):
            continue
        # Skip full schema dumps
        if filename in ['full_schema.sql', 'add_missing_tables.sql']:
            continue
        filtered.append(f)

    # Sort by number at start of filename
    def get_number(filepath):
        filename = os.path.basename(filepath)
        match = re.match(r'^(\d+)_', filename)
        return int(match.group(1)) if match else 0

    return sorted(filtered, key=get_number)


def apply_migration(conn, filepath):
    """Apply a single migration file"""
    filename = os.path.basename(filepath)

    print(f"  Applying: {filename}... ", end='', flush=True)

    try:
        with open(filepath, 'r') as f:
            sql = f.read()

        with conn.cursor() as cur:
            # Execute migration
            cur.execute(sql)

            # Record in migrations table
            cur.execute(
                "INSERT INTO kvota.migrations (filename) VALUES (%s)",
                (filename,)
            )

        conn.commit()
        print("✅ OK")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ FAILED")
        print(f"  Error: {e}")
        return False


def show_status(conn):
    """Show migration status"""
    applied = get_applied_migrations(conn)
    all_files = get_migration_files()

    print("\n" + "="*60)
    print("MIGRATION STATUS")
    print("="*60)

    pending_count = 0

    for filepath in all_files:
        filename = os.path.basename(filepath)
        if filename in applied:
            print(f"✅ {filename}")
        else:
            print(f"⏳ {filename} [PENDING]")
            pending_count += 1

    print("="*60)
    print(f"Total: {len(all_files)} migrations")
    print(f"Applied: {len(applied)}")
    print(f"Pending: {pending_count}")
    print("="*60 + "\n")


def list_migrations():
    """List all migration files"""
    all_files = get_migration_files()

    print("\n" + "="*60)
    print("ALL MIGRATIONS")
    print("="*60)

    for filepath in all_files:
        filename = os.path.basename(filepath)
        print(f"  {filename}")

    print("="*60)
    print(f"Total: {len(all_files)} migrations")
    print("="*60 + "\n")


def migrate():
    """Apply all pending migrations"""
    print("\n🔄 Starting migration process...\n")

    conn = get_db_connection()

    try:
        # Ensure migrations table exists
        ensure_migrations_table(conn)

        # Get applied and pending migrations
        applied = get_applied_migrations(conn)
        all_files = get_migration_files()

        pending = [f for f in all_files if os.path.basename(f) not in applied]

        if not pending:
            print("✅ No pending migrations. Database is up to date.\n")
            return

        print(f"Found {len(pending)} pending migration(s):\n")

        # Apply each pending migration
        success_count = 0
        for filepath in pending:
            if apply_migration(conn, filepath):
                success_count += 1
            else:
                print(f"\n❌ Migration failed. Stopping.\n")
                break

        print(f"\n✅ Applied {success_count}/{len(pending)} migration(s) successfully.\n")

    finally:
        conn.close()


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "migrate"

    if command == "status":
        conn = get_db_connection()
        try:
            ensure_migrations_table(conn)
            show_status(conn)
        finally:
            conn.close()

    elif command == "list":
        list_migrations()

    elif command == "migrate":
        migrate()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
