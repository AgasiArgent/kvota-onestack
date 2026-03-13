#!/bin/bash
# Generate TypeScript types from the live Supabase database.
# Requires: SSH access to beget-kvota, pg npm package, SSH tunnel.
#
# Usage: npm run db:types
#   or:  ./scripts/gen-db-types.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT="$FRONTEND_DIR/src/shared/types/database.types.ts"
GEN_SCRIPT="$SCRIPT_DIR/gen-supabase-types.mjs"

DB_HOST="172.21.0.3"
DB_PORT="5432"
LOCAL_PORT="54322"
VPS_HOST="beget-kvota"
DB_SCHEMA="kvota"

# Read password from VPS
DB_PASS=$(ssh "$VPS_HOST" "grep POSTGRES_PASSWORD /root/lisa/supabase/docker/.env | cut -d= -f2")

# Start SSH tunnel (if not already running)
if ! lsof -i ":$LOCAL_PORT" &>/dev/null; then
  echo "Starting SSH tunnel on port $LOCAL_PORT..."
  ssh -f -N -L "$LOCAL_PORT:$DB_HOST:$DB_PORT" "$VPS_HOST"
  TUNNEL_STARTED=1
else
  echo "SSH tunnel already running on port $LOCAL_PORT"
  TUNNEL_STARTED=0
fi

# Ensure pg is available
if ! node -e "require('pg')" 2>/dev/null; then
  echo "Installing pg package..."
  npm install --no-save pg 2>/dev/null
fi

# Generate types
echo "Generating types from $DB_SCHEMA schema..."
node "$GEN_SCRIPT" "postgresql://postgres:${DB_PASS}@localhost:${LOCAL_PORT}/postgres" > "$OUTPUT"

# Kill tunnel if we started it
if [ "$TUNNEL_STARTED" = "1" ]; then
  echo "Stopping SSH tunnel..."
  lsof -ti ":$LOCAL_PORT" | xargs kill 2>/dev/null || true
fi

LINES=$(wc -l < "$OUTPUT")
echo "Done! Generated $LINES lines → $OUTPUT"
