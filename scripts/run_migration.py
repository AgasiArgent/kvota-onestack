#!/usr/bin/env python3
"""
Run database migrations against Supabase/PostgreSQL.

Usage:
    python scripts/run_migration.py
    python scripts/run_migration.py --dry-run  # Just print SQL without executing
"""

import os
import sys
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import psycopg2

load_dotenv()


def get_db_connection():
    """Get direct PostgreSQL connection."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set in .env")
    return psycopg2.connect(database_url)


def run_migration(dry_run=False):
    """Run the full schema migration."""
    migration_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "migrations",
        "full_schema.sql"
    )

    if not os.path.exists(migration_file):
        print(f"ERROR: Migration file not found: {migration_file}")
        sys.exit(1)

    with open(migration_file, 'r') as f:
        sql = f.read()

    print(f"Migration file: {migration_file}")
    print(f"SQL length: {len(sql)} characters")
    print()

    if dry_run:
        print("=== DRY RUN - SQL would be executed: ===")
        print(sql[:2000])
        print("... (truncated)")
        return

    print("Connecting to database...")
    conn = get_db_connection()
    conn.autocommit = True  # Required for CREATE INDEX CONCURRENTLY etc.

    cursor = conn.cursor()

    # Split SQL by semicolons and execute each statement
    # This is needed because psycopg2 doesn't handle multiple statements well
    statements = []
    current_stmt = []
    in_function = False
    in_dollar_quote = False

    for line in sql.split('\n'):
        stripped = line.strip()

        # Track $$ delimiters for functions
        if '$$' in line:
            in_dollar_quote = not in_dollar_quote

        current_stmt.append(line)

        # If we're not in a function body and line ends with ;
        if not in_dollar_quote and stripped.endswith(';') and not stripped.startswith('--'):
            stmt = '\n'.join(current_stmt).strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
            current_stmt = []

    # Add any remaining statement
    if current_stmt:
        stmt = '\n'.join(current_stmt).strip()
        if stmt and not stmt.startswith('--'):
            statements.append(stmt)

    print(f"Found {len(statements)} SQL statements")
    print()

    success = 0
    errors = 0

    for i, stmt in enumerate(statements):
        # Skip empty statements and comments
        stmt = stmt.strip()
        if not stmt or stmt.startswith('--'):
            continue

        # Get first line for logging
        first_line = stmt.split('\n')[0][:80]

        try:
            cursor.execute(stmt)
            success += 1
            if i % 10 == 0:
                print(f"  [{i+1}/{len(statements)}] OK: {first_line}...")
        except Exception as e:
            error_msg = str(e).split('\n')[0]
            # Ignore "already exists" errors
            if 'already exists' in error_msg.lower() or 'duplicate key' in error_msg.lower():
                print(f"  [{i+1}/{len(statements)}] SKIP (exists): {first_line}...")
                success += 1
            else:
                print(f"  [{i+1}/{len(statements)}] ERROR: {first_line}...")
                print(f"      {error_msg}")
                errors += 1

    cursor.close()
    conn.close()

    print()
    print("=" * 60)
    print(f"Migration complete: {success} succeeded, {errors} errors")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without executing")
    args = parser.parse_args()

    run_migration(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
