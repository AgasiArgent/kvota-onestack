#!/bin/bash
# Migration helper script - can be run on VPS via SSH or locally

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Ensure psycopg2 is installed
if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo "📦 Installing psycopg2..."
    pip3 install psycopg2-binary
fi

# Run migration script
python3 scripts/migrate.py "$@"
