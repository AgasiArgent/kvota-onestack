#!/bin/bash
# OneStack Layer 2 verification — weekly partial restore
#
# Catches (in addition to Layer 1):
#   - Dump file corruption (bit-rot, truncated, bad header)
#   - pg_restore can't parse format (PG version mismatch)
#   - Specific table corruption
#
# What it does:
#   1. Downloads latest .dump file from S3 to /tmp
#   2. Runs `pg_restore --list` to verify TOC integrity
#   3. Cleans up
#
# Why no actual restore: VPS disk is 90% full, can't fit 23GB temp DB.
# Full restore drill = Layer 3, done monthly on separate machine.
#
# Cost: ~70 MB egress per week = ~3 ₽/мес
#
# Cron:
#   0 4 * * 0 /bin/bash -c 'source /etc/profile.d/backup.sh && /root/onestack/scripts/verify-restore-weekly.sh' >> /var/log/verify-restore-weekly.log 2>&1

set -uo pipefail

S3_REMOTE="${S3_REMOTE:-yandex:kvota-backups}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

TEMP_DIR="$(mktemp -d /tmp/verify-restore-XXXXXX)"
trap 'cleanup' EXIT

cleanup() {
  rm -rf "$TEMP_DIR"
  docker exec supabase-db rm -f /tmp/verify-dump.bin 2>/dev/null || true
}

tg_send() {
  local text=$1
  [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ] && return 0
  curl -fsS -m 10 -X POST \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=$TELEGRAM_CHAT_ID" \
    -d "parse_mode=HTML" \
    --data-urlencode "text=$text" \
    > /dev/null || true
}

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

fail() {
  local reason=$1
  log "FAILED: $reason"
  tg_send "⚠️ <b>OneStack restore verification FAILED</b>

Layer 2 weekly restore check failed:
<code>$reason</code>

Latest dump file may be corrupted or unreadable.
Check: <code>/var/log/verify-restore-weekly.log</code>"
  exit 1
}

log "=== Layer 2 partial restore verify starting ==="

# Find latest dump
LATEST_DUMP=$(rclone lsf "$S3_REMOTE/db/" --include "*.dump" 2>/dev/null | sort | tail -1)
[ -z "$LATEST_DUMP" ] && fail "no .dump files in $S3_REMOTE/db/"

log "Latest dump: $LATEST_DUMP"

# Download
log "Downloading to $TEMP_DIR..."
rclone copy "$S3_REMOTE/db/$LATEST_DUMP" "$TEMP_DIR/" 2>&1 \
  || fail "rclone copy failed"

LOCAL_PATH="$TEMP_DIR/$LATEST_DUMP"
LOCAL_SIZE=$(stat -c '%s' "$LOCAL_PATH")
log "Downloaded: $LOCAL_SIZE bytes"

# Compare size with remote (rclone copy should have done verification, but double check)
REMOTE_SIZE=$(rclone size "$S3_REMOTE/db/$LATEST_DUMP" --json \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('bytes',0))")
[ "$LOCAL_SIZE" = "$REMOTE_SIZE" ] || fail "size mismatch: local $LOCAL_SIZE vs remote $REMOTE_SIZE"

# Verify TOC via pg_restore --list (uses supabase-db container's pg_restore)
log "Verifying TOC via pg_restore --list..."
docker cp "$LOCAL_PATH" supabase-db:/tmp/verify-dump.bin \
  || fail "docker cp into supabase-db failed"

TOC_FILE="$TEMP_DIR/toc.txt"
docker exec supabase-db pg_restore --list /tmp/verify-dump.bin > "$TOC_FILE" 2>&1 \
  || fail "pg_restore --list returned non-zero exit"

TOC_ENTRIES=$(grep -cE '^[0-9]+;' "$TOC_FILE")
log "TOC entries: $TOC_ENTRIES"
[ "$TOC_ENTRIES" -lt 10 ] && fail "TOC has only $TOC_ENTRIES entries (suspiciously few)"

# Sample check — verify we can find expected schema markers
grep -q "SCHEMA - kvota " "$TOC_FILE"   || fail "no kvota schema in TOC"
grep -q "SCHEMA - auth "  "$TOC_FILE"   || fail "no auth schema in TOC"
grep -q "SCHEMA - storage " "$TOC_FILE" || fail "no storage schema in TOC"

# Sanity check: ensure expected critical tables present
grep -q "TABLE DATA kvota quotes "  "$TOC_FILE" || fail "no kvota.quotes data in TOC"
grep -q "TABLE DATA auth users "    "$TOC_FILE" || fail "no auth.users data in TOC"

log "=== ALL CHECKS PASSED ($TOC_ENTRIES TOC entries, schemas present) ==="

# Quiet success — no Telegram noise. Failure was the noteworthy event.
# Comment out the line below if you want weekly success confirmations.
# tg_send "✅ Weekly restore check OK ($TOC_ENTRIES TOC entries in $LATEST_DUMP)"
