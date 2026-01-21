#!/bin/bash
# Migration script that runs inside Docker container
# Usage: bash scripts/migrate-docker.sh [command]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default command
COMMAND="${1:-migrate}"

cd "$PROJECT_ROOT"

# Check if running inside Docker or on VPS
if [ -f "/.dockerenv" ]; then
    # Inside Docker container - use local psql
    export PGHOST="supabase-db"
    export PGPORT="5432"
    export PGUSER="postgres"
    export PGDATABASE="postgres"
    export PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
else
    # On VPS - use docker exec
    echo "Running migrations via docker exec..."
    docker exec -i supabase-db bash -c "
        cd /tmp &&
        export PGHOST=localhost &&
        export PGPORT=5432 &&
        export PGUSER=postgres &&
        export PGDATABASE=postgres &&
        bash
    " << 'DOCKER_EOF'

# Create migrations table if not exists
psql -c "
CREATE SCHEMA IF NOT EXISTS kvota;

CREATE TABLE IF NOT EXISTS kvota.migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"

# Get list of applied migrations
APPLIED=$(psql -t -c "SELECT filename FROM kvota.migrations ORDER BY filename;" | xargs)

echo "📊 Migration Status:"
echo "===================="

# Check each migration file
for file in $(ls /root/onestack/migrations/*.sql 2>/dev/null | sort); do
    filename=$(basename "$file")

    # Skip special files
    if [[ ! "$filename" =~ ^[0-9]+_ ]]; then
        continue
    fi
    if [[ "$filename" == "full_schema.sql" ]] || [[ "$filename" == "add_missing_tables.sql" ]]; then
        continue
    fi

    # Check if already applied
    if echo "$APPLIED" | grep -q "$filename"; then
        echo "✅ $filename"
    else
        echo "⏳ $filename [PENDING]"
    fi
done

echo "===================="
echo ""

DOCKER_EOF
    exit 0
fi

# If we got here, something went wrong
echo "Error: Could not determine execution environment"
exit 1
