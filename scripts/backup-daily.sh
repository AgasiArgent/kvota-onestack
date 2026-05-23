#!/bin/bash
# OneStack daily backup — Phase 1 (safety net before WAL-G PITR lands)
#
# What it does:
#   1. Streams pg_dump → Yandex Object Storage (no local staging; disk is 90% full)
#   2. Streams pg_dumpall --roles-only → S3
#   3. rclone sync Storage volume → S3 with history of changed/deleted files
#   4. GPG-encrypted snapshot of configs/.env → S3
#   5. Deletes dumps older than 30 days (configs/30d, storage history 90d)
#   6. Sends Telegram notification on success / failure
#
# Why Telegram, not Healthchecks.io: HC blocks Russian IPs (since Dec 2022).
# Trade-off: no dead-man-switch (silence = ??). Mitigation: Beget tier-3 auto-
# backups (2-5d cadence) as last-resort fallback + weekly visual check.
#
# Prerequisites (one-time setup):
#   1. rclone configured: ~/.config/rclone/rclone.conf with [yandex] section
#   2. /root/.backup-passphrase file (chmod 600) for GPG
#   3. /etc/profile.d/backup.sh sets: S3_REMOTE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
#
# Cron:
#   0 2 * * * /root/onestack/scripts/backup-daily.sh >> /var/log/backup-daily.log 2>&1
#
# Manual test:
#   source /etc/profile.d/backup.sh && /root/onestack/scripts/backup-daily.sh

set -euo pipefail

DATE=$(date +%Y%m%d-%H%M%S)
S3_REMOTE="${S3_REMOTE:-yandex:kvota-backups}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/root/.backup-passphrase}"
STORAGE_VOLUME="${STORAGE_VOLUME:-/root/lisa/supabase/docker/volumes/storage}"

START_TIME=$(date +%s)
CURRENT_STEP="initializing"

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

human_size() {
  local path=$1
  rclone size "$path" 2>/dev/null \
    | awk -F'[()]' '/Total size/ {print $1}' \
    | sed -E 's/.*Total size: //;s/ +$//' \
    || echo "?"
}

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

on_error() {
  local line=$1
  local duration=$(($(date +%s) - START_TIME))
  log "FAILED at line $line (step: $CURRENT_STEP, duration: ${duration}s)"
  tg_send "🔴 <b>OneStack backup FAILED</b>

Step: <code>$CURRENT_STEP</code>
Line: <code>$line</code>
Duration: ${duration}s
Time: $(date '+%Y-%m-%d %H:%M:%S')

Check: <code>/var/log/backup-daily.log</code>"
  exit 1
}
trap 'on_error $LINENO' ERR

log "=== OneStack daily backup starting (target: $S3_REMOTE) ==="

# Sanity checks
[ -f "$PASSPHRASE_FILE" ] || { log "ERROR: missing $PASSPHRASE_FILE"; exit 1; }
docker exec supabase-db true || { log "ERROR: supabase-db container not running"; exit 1; }

# === 1. Database dump — stream to S3 ===
CURRENT_STEP="db_dump"
log "DB dump: streaming to $S3_REMOTE/db/$DATE.dump"
docker exec -i supabase-db pg_dump \
  -U postgres -d postgres \
  --schema=kvota --schema=auth --schema=storage --schema=public --schema=realtime \
  --format=custom --compress=9 \
  | rclone rcat "$S3_REMOTE/db/$DATE.dump" --s3-no-check-bucket

# === 2. Roles ===
CURRENT_STEP="roles_dump"
log "Roles: streaming to $S3_REMOTE/db/$DATE.roles.sql"
docker exec -i supabase-db pg_dumpall -U postgres --roles-only \
  | rclone rcat "$S3_REMOTE/db/$DATE.roles.sql"

# === 3. Storage sync ===
CURRENT_STEP="storage_sync"
log "Storage sync: $STORAGE_VOLUME → $S3_REMOTE/storage/current/"
rclone sync "$STORAGE_VOLUME/" "$S3_REMOTE/storage/current/" \
  --backup-dir "$S3_REMOTE/storage/history/$DATE/" \
  --transfers 4

# === 4. Encrypted configs ===
CURRENT_STEP="configs_encrypt"
log "Configs: encrypting and uploading"
tar czf - \
  -C / \
  root/onestack/.env \
  root/onestack/docker-compose.prod.yml \
  root/lisa/supabase/docker/.env \
  2>/dev/null \
  | gpg --symmetric --batch --passphrase-file "$PASSPHRASE_FILE" \
        --cipher-algo AES256 --compress-algo none \
  | rclone rcat "$S3_REMOTE/configs/$DATE.tar.gz.gpg"

# === 5. Retention pruning ===
CURRENT_STEP="retention_prune"
log "Pruning: dumps >30d, configs >30d, storage history >90d"
rclone delete --min-age 30d "$S3_REMOTE/db/" --include "*.dump" --include "*.sql" || true
rclone delete --min-age 30d "$S3_REMOTE/configs/" --include "*.gpg" || true
rclone delete --min-age 90d "$S3_REMOTE/storage/history/" || true

# === 6. Success notification ===
CURRENT_STEP="done"
DURATION=$(($(date +%s) - START_TIME))
DB_SIZE=$(human_size "$S3_REMOTE/db/$DATE.dump")
STORAGE_SIZE=$(human_size "$S3_REMOTE/storage/current/")

log "=== Backup complete in ${DURATION}s ==="
tg_send "✅ <b>OneStack backup OK</b>

🗄 DB: $DB_SIZE
📁 Storage: $STORAGE_SIZE
⏱ Duration: ${DURATION}s
🪣 <code>$S3_REMOTE/</code>

$(date '+%Y-%m-%d %H:%M:%S')"
