#!/usr/bin/env python3
"""
Set up local PostgreSQL for OneStack development.

Creates the kvota schema, prerequisite tables (organizations, quotes, etc.),
and applies all numbered migrations. Then seeds dev data.

Usage:
    # Start local PG first:
    docker compose -f docker-compose.dev.yml up -d

    # Then run this script:
    python scripts/setup_local_db.py

    # To reset everything:
    python scripts/setup_local_db.py --reset
"""

import os
import sys
import argparse
import glob
import re
from pathlib import Path

from dotenv import load_dotenv

# Load .env.dev if it exists, otherwise .env
env_dev = Path(__file__).parent.parent / ".env.dev"
if env_dev.exists():
    load_dotenv(env_dev)
else:
    load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


def get_connection():
    """Get direct PostgreSQL connection."""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set.")
        print("Copy .env.dev.example to .env.dev and configure it.")
        sys.exit(1)

    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"ERROR: Cannot connect to database: {e}")
        print("Is PostgreSQL running? Try: docker compose -f docker-compose.dev.yml up -d")
        sys.exit(1)


def reset_database(conn):
    """Drop and recreate the kvota schema."""
    print("Resetting database...")
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS kvota CASCADE")
        cur.execute("DROP TABLE IF EXISTS public.organizations CASCADE")
        cur.execute("DROP TABLE IF EXISTS public.organization_members CASCADE")
        cur.execute("DROP TABLE IF EXISTS public.quotes CASCADE")
        cur.execute("DROP TABLE IF EXISTS public.quote_items CASCADE")
        cur.execute("DROP TABLE IF EXISTS public.quote_versions CASCADE")
        cur.execute("DROP TABLE IF EXISTS public.customers CASCADE")
    conn.commit()
    print("  Database reset complete.")


def create_prerequisite_tables(conn):
    """Create tables that Supabase normally provides (organizations, quotes, etc.)."""
    print("Creating prerequisite tables...")

    sql = """
    -- Extension for UUID generation
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    -- Organizations (normally from Supabase)
    CREATE TABLE IF NOT EXISTS public.organizations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Organization members (normally from Supabase)
    CREATE TABLE IF NOT EXISTS public.organization_members (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL,
        organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
        status VARCHAR(20) DEFAULT 'active',
        is_owner BOOLEAN DEFAULT false,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        UNIQUE(user_id, organization_id)
    );

    -- Customers
    CREATE TABLE IF NOT EXISTS public.customers (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
        email VARCHAR(255),
        phone VARCHAR(50),
        inn VARCHAR(20),
        address TEXT,
        postal_address TEXT,
        notes TEXT,
        order_source VARCHAR(100),
        manager_id UUID,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Quotes (core table)
    CREATE TABLE IF NOT EXISTS public.quotes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        idn_quote VARCHAR(50),
        title VARCHAR(255),
        customer_id UUID REFERENCES public.customers(id) ON DELETE SET NULL,
        organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
        currency VARCHAR(10) DEFAULT 'RUB',
        delivery_terms VARCHAR(50) DEFAULT 'DDP',
        delivery_city VARCHAR(255),
        delivery_country VARCHAR(100),
        delivery_method VARCHAR(100),
        status VARCHAR(20) DEFAULT 'draft',
        workflow_status VARCHAR(50) DEFAULT 'draft',
        deal_type VARCHAR(20),
        seller_company_id UUID,
        contact_person_id UUID,
        is_phmb BOOLEAN DEFAULT false,
        variables JSONB DEFAULT '{}',
        notes TEXT,
        created_by UUID,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Quote items (core table)
    CREATE TABLE IF NOT EXISTS public.quote_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        quote_id UUID NOT NULL REFERENCES public.quotes(id) ON DELETE CASCADE,
        sku VARCHAR(100),
        description TEXT,
        brand VARCHAR(100),
        quantity INTEGER DEFAULT 1,
        base_price DECIMAL(15, 4),
        base_price_vat DECIMAL(15, 4),
        currency VARCHAR(10) DEFAULT 'RUB',
        purchase_currency VARCHAR(10),
        weight_kg DECIMAL(15, 4),
        volume_m3 DECIMAL(15, 6),
        supplier_sku VARCHAR(100),
        assigned_procurement_user UUID,
        procurement_status VARCHAR(20) DEFAULT 'pending',
        hs_code VARCHAR(20),
        customs_duty DECIMAL(15, 4) DEFAULT 0,
        supplier_city VARCHAR(255),
        production_time_days INTEGER DEFAULT 0,
        procurement_notes TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Quote versions (core table)
    CREATE TABLE IF NOT EXISTS public.quote_versions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        quote_id UUID NOT NULL REFERENCES public.quotes(id) ON DELETE CASCADE,
        version_number INTEGER DEFAULT 1,
        snapshot JSONB,
        created_by UUID,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_customers_org ON public.customers(organization_id);
    CREATE INDEX IF NOT EXISTS idx_quotes_org ON public.quotes(organization_id);
    CREATE INDEX IF NOT EXISTS idx_quotes_customer ON public.quotes(customer_id);
    CREATE INDEX IF NOT EXISTS idx_quote_items_quote ON public.quote_items(quote_id);
    CREATE INDEX IF NOT EXISTS idx_quote_versions_quote ON public.quote_versions(quote_id);
    """

    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("  Prerequisite tables created.")


def create_kvota_schema(conn):
    """Create the kvota schema and move tables into it."""
    print("Creating kvota schema...")

    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS kvota")

        # Move prerequisite tables to kvota schema
        tables_to_move = [
            "organizations", "organization_members", "customers",
            "quotes", "quote_items", "quote_versions",
        ]
        for table in tables_to_move:
            cur.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = '{table}'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'kvota' AND table_name = '{table}'
                    ) THEN
                        ALTER TABLE public.{table} SET SCHEMA kvota;
                    END IF;
                END $$;
            """)

        # Set default search path for convenience
        cur.execute("SET search_path TO kvota, public")

    conn.commit()
    print("  kvota schema created, tables moved.")


def create_migrations_table(conn):
    """Create the migrations tracking table."""
    with conn.cursor() as cur:
        cur.execute("SET search_path TO kvota, public")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kvota.migrations (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum VARCHAR(64)
            )
        """)
    conn.commit()


def get_migration_files():
    """Get numbered migration files, excluding schema-level ones already handled."""
    migration_dir = PROJECT_ROOT / "migrations"
    files = glob.glob(str(migration_dir / "*.sql"))

    # Skip non-numbered files and schema migrations we handle separately
    skip_files = {
        "full_schema.sql",
        "add_missing_tables.sql",
        "100_create_kvota_schema.sql",
        "101_move_tables_to_kvota_schema.sql",
    }

    filtered = []
    for f in files:
        filename = os.path.basename(f)
        if filename in skip_files:
            continue
        if not re.match(r"^\d+_", filename):
            continue
        # Skip migrations below 102 (old pre-schema migrations)
        match = re.match(r"^(\d+)_", filename)
        if match and int(match.group(1)) < 102:
            continue
        filtered.append(f)

    def get_number(filepath):
        match = re.match(r"^(\d+)_", os.path.basename(filepath))
        return int(match.group(1)) if match else 0

    return sorted(filtered, key=get_number)


def apply_migrations(conn):
    """Apply all pending migrations."""
    print("Applying migrations...")

    create_migrations_table(conn)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO kvota, public")
        cur.execute("SELECT filename FROM kvota.migrations ORDER BY filename")
        applied = {row[0] for row in cur.fetchall()}

    all_files = get_migration_files()
    pending = [f for f in all_files if os.path.basename(f) not in applied]

    if not pending:
        print("  No pending migrations.")
        return

    print(f"  {len(pending)} pending migration(s)...")

    success = 0
    for filepath in pending:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r") as f:
                sql = f.read()

            with conn.cursor() as cur:
                cur.execute("SET search_path TO kvota, public")

                # Strip Supabase-specific constructs that don't exist in plain PG
                cleaned_sql = sql
                # Remove references to auth.users, auth.uid()
                cleaned_sql = _strip_supabase_auth(cleaned_sql)

                cur.execute(cleaned_sql)
                cur.execute(
                    "INSERT INTO kvota.migrations (filename) VALUES (%s)",
                    (filename,),
                )

            conn.commit()
            success += 1

        except Exception as e:
            conn.rollback()
            # Non-critical errors: continue with remaining migrations
            error_str = str(e)
            if "already exists" in error_str or "duplicate" in error_str.lower():
                print(f"  SKIP (already exists): {filename}")
                # Mark as applied so we don't retry
                try:
                    with conn.cursor() as cur:
                        cur.execute("SET search_path TO kvota, public")
                        cur.execute(
                            "INSERT INTO kvota.migrations (filename) VALUES (%s) ON CONFLICT DO NOTHING",
                            (filename,),
                        )
                    conn.commit()
                except Exception:
                    conn.rollback()
                continue
            else:
                print(f"  WARN: {filename} - {error_str[:120]}")
                continue

    print(f"  Applied {success} migration(s).")


def _strip_supabase_auth(sql):
    """Remove Supabase-specific auth references from SQL for local PG.

    Local PostgreSQL doesn't have auth.users or auth.uid().
    We strip RLS policies and auth references, keeping table/column DDL.
    """
    lines = sql.split("\n")
    result = []
    skip_block = False
    paren_depth = 0

    for line in lines:
        stripped = line.strip().upper()

        # Skip RLS-related statements
        if "ENABLE ROW LEVEL SECURITY" in stripped:
            continue

        if "CREATE POLICY" in stripped or "DROP POLICY" in stripped:
            skip_block = True
            paren_depth = line.count("(") - line.count(")")
            if paren_depth <= 0 and line.rstrip().endswith(";"):
                skip_block = False
            continue

        if skip_block:
            paren_depth += line.count("(") - line.count(")")
            if line.rstrip().endswith(";") and paren_depth <= 0:
                skip_block = False
            continue

        # Skip references to auth.users in FK constraints
        if "REFERENCES AUTH.USERS" in stripped:
            # Replace with plain UUID (drop the FK)
            line = re.sub(
                r"REFERENCES\s+auth\.users\s*\([^)]*\)\s*(ON\s+DELETE\s+\w+)?",
                "",
                line,
                flags=re.IGNORECASE,
            )

        # Skip auth.uid() calls (should be in policies only, already removed)
        if "AUTH.UID()" in stripped:
            continue

        # Skip GRANT statements (no roles in local PG)
        if stripped.startswith("GRANT ") or stripped.startswith("REVOKE "):
            continue

        # Skip ALTER DEFAULT PRIVILEGES
        if "ALTER DEFAULT PRIVILEGES" in stripped:
            continue

        result.append(line)

    return "\n".join(result)


def main():
    parser = argparse.ArgumentParser(description="Set up local PostgreSQL for OneStack dev")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate everything")
    parser.add_argument("--skip-seed", action="store_true", help="Skip seed data")
    args = parser.parse_args()

    print("=" * 60)
    print("OneStack Local Database Setup")
    print("=" * 60)

    conn = get_connection()

    try:
        if args.reset:
            reset_database(conn)

        create_prerequisite_tables(conn)
        create_kvota_schema(conn)
        apply_migrations(conn)

        if not args.skip_seed:
            print("\nRunning seed script...")
            # Import and run seed inline to share the connection
            sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
            from seed_dev_data import seed_all
            seed_all(conn)

        print("\n" + "=" * 60)
        print("Local database setup complete!")
        print("=" * 60)
        print("\nConnection: postgresql://kvota:devpassword@localhost:5434/kvota_dev")
        print("Schema: kvota")
        print("\nTo connect: psql postgresql://kvota:devpassword@localhost:5434/kvota_dev")
        print("Then run: SET search_path TO kvota;")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
