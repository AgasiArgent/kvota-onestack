#!/bin/bash
# Simple migration script using docker exec and psql
# Usage: bash scripts/apply-migrations.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🔄 OneStack Migration Tool"
echo "=========================="
echo ""

# Create migrations tracking table
echo "📋 Ensuring migrations table exists..."
docker exec supabase-db psql -U postgres -d postgres -c "
CREATE TABLE IF NOT EXISTS kvota.migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);

COMMENT ON TABLE kvota.migrations IS 'Tracks applied database migrations';
" > /dev/null 2>&1

echo "✅ Migrations table ready"
echo ""

# Get list of applied migrations
APPLIED=$(docker exec supabase-db psql -U postgres -d postgres -t -c "SELECT filename FROM kvota.migrations ORDER BY filename;" 2>/dev/null | xargs)

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
FAILED_COUNT=0

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

    # Apply migration with ON_ERROR_STOP=1 so any statement-level ERROR aborts
    # the file instead of continuing silently to the next statement. This
    # closes a silent-partial-success hole: previously, a file like
    #   ALTER TABLE foo DROP COLUMN a;  -- ERROR
    #   ALTER TABLE bar DROP COLUMN b;  -- SUCCESS
    # would report "✅ Success" because the last statement passed and the
    # grep-based filter below didn't recognise the first error. See
    # m318 incident 2026-05-21 and feedback_apply_migrations_silent_partial.md.
    #
    # search_path is set so old migrations without an explicit `kvota.`
    # prefix still resolve correctly.
    MIGRATION_OUTPUT=$(docker exec -i supabase-db psql -U postgres -d postgres \
        --set ON_ERROR_STOP=1 2>&1 << MIGRATION_EOF
SET search_path TO kvota, public;
$(cat "$file")
MIGRATION_EOF
)
    MIGRATION_STATUS=$?

    # psql exit codes (with ON_ERROR_STOP=1):
    #   0 = clean run
    #   3 = a statement-level ERROR aborted the file
    #   1/2 = client error (bad args, connection failure)
    # Any non-zero status means we must NOT mark the migration as applied —
    # the prior implementation marked it applied as long as the curated grep
    # didn't fire, which silently accepted half-applied migrations.
    if [ $MIGRATION_STATUS -ne 0 ]; then
        echo "  ❌ Failed (psql exit $MIGRATION_STATUS)"
        echo "$MIGRATION_OUTPUT" | grep -E "ERROR|FATAL|psql:" | head -10 | sed 's/^/      /'
        FAILED_COUNT=$((FAILED_COUNT + 1))
        continue
    fi

    # Record migration as applied
    docker exec supabase-db psql -U postgres -d postgres -c "
    INSERT INTO kvota.migrations (filename) VALUES ('$filename')
        ON CONFLICT (filename) DO NOTHING;
    " > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "  ✅ Success"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "  ⚠️  Applied but failed to record"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    fi
done

echo ""
if [ $FAILED_COUNT -gt 0 ]; then
    echo "⚠️  Applied $SUCCESS_COUNT/$PENDING_COUNT migration(s) ($FAILED_COUNT failed)"
else
    echo "✅ Applied $SUCCESS_COUNT/$PENDING_COUNT migration(s) successfully"
fi
echo ""

# Always exit 0 — failed migrations are non-blocking warnings
# (they're usually already-applied migrations not in the tracking table)
exit 0
