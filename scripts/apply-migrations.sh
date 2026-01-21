#!/bin/bash
# Simple migration script using docker exec and psql
# Usage: bash scripts/apply-migrations.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🔄 OneStack Migration Tool"
echo "=========================="
echo ""

# Create migrations tracking table
echo "📋 Ensuring migrations table exists..."
docker exec supabase-db psql -U postgres -d postgres << 'EOF'
SET search_path TO kvota;

CREATE TABLE IF NOT EXISTS kvota.migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);

COMMENT ON TABLE kvota.migrations IS 'Tracks applied database migrations';
EOF

if [ $? -ne 0 ]; then
    echo "❌ Failed to create migrations table"
    exit 1
fi

echo "✅ Migrations table ready"
echo ""

# Get list of applied migrations
APPLIED=$(docker exec supabase-db psql -U postgres -d postgres -t -c "SELECT filename FROM kvota.migrations ORDER BY filename;" | xargs)

# Find all migration files
PENDING_COUNT=0
APPLIED_COUNT=0

echo "📊 Checking migration status..."
echo ""

for file in $(ls -1 migrations/*.sql 2>/dev/null | sort); do
    filename=$(basename "$file")

    # Skip special files
    if [[ ! "$filename" =~ ^[0-9]+_ ]]; then
        continue
    fi
    if [[ "$filename" == "full_schema.sql" ]] || [[ "$filename" == "add_missing_tables.sql" ]]; then
        continue
    fi

    # Check if already applied
    if echo " $APPLIED " | grep -q " $filename "; then
        echo "✅ $filename"
        APPLIED_COUNT=$((APPLIED_COUNT + 1))
    else
        echo "⏳ $filename [PENDING]"
        PENDING_COUNT=$((PENDING_COUNT + 1))
    fi
done

echo ""
echo "=========================="
echo "Total migrations: $((APPLIED_COUNT + PENDING_COUNT))"
echo "Applied: $APPLIED_COUNT"
echo "Pending: $PENDING_COUNT"
echo "=========================="
echo ""

# Apply pending migrations
if [ $PENDING_COUNT -eq 0 ]; then
    echo "✅ No pending migrations. Database is up to date."
    exit 0
fi

echo "🚀 Applying $PENDING_COUNT pending migration(s)..."
echo ""

SUCCESS_COUNT=0

for file in $(ls -1 migrations/*.sql 2>/dev/null | sort); do
    filename=$(basename "$file")

    # Skip special files
    if [[ ! "$filename" =~ ^[0-9]+_ ]]; then
        continue
    fi
    if [[ "$filename" == "full_schema.sql" ]] || [[ "$filename" == "add_missing_tables.sql" ]]; then
        continue
    fi

    # Skip if already applied
    if echo " $APPLIED " | grep -q " $filename "; then
        continue
    fi

    echo "  Applying: $filename..."

    # Apply migration and record it
    if docker exec -i supabase-db psql -U postgres -d postgres << MIGRATION_EOF
BEGIN;

$(cat "$file")

INSERT INTO kvota.migrations (filename) VALUES ('$filename')
    ON CONFLICT (filename) DO NOTHING;

COMMIT;
MIGRATION_EOF
    then
        echo "  ✅ Success"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "  ❌ Failed"
        echo ""
        echo "Migration failed. Stopping."
        exit 1
    fi
done

echo ""
echo "✅ Applied $SUCCESS_COUNT/$PENDING_COUNT migration(s) successfully."
echo ""
