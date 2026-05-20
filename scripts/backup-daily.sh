#!/bin/bash
# OneStack daily backup — Phase 1 (safety net before WAL-G PITR lands)
#
# What it does:
#   1. Streams pg_dump → Yandex Object Storage (no local staging; disk is 90% full)
#   2. Streams pg_dumpall --roles-only → S3
#   3. rclone sync Storage volume → S3 with history of changed/deleted files
#   4. GPG-encrypted snapshot of configs/.env → S3
#   5. Deletes dumps older than 30 days (configs/30d, storage history 90d)
#   6. Pings Healthchecks.io on success (or /fail on error)
#
# Prerequisites (one-time setup):
#   1. Install rclone: apt-get install -y rclone (✅ done 2026-05-20)
#   2. Configure rclone: ~/.config/rclone/rclone.conf with [yandex] section
#      (see scripts/backup-setup-rclone.md)
#   3. Create GPG passphrase file: echo "<random-passphrase>" > /root/.backup-passphrase && chmod 600 $_
#      Store the passphrase in a password manager — needed for restore!
#   4. (optional) Set HEALTHCHECK_URL in /etc/profile.d/backup.sh
#
# Cron (add via `crontab -e`):
#   0 2 * * * /root/onestack/scripts/backup-daily.sh >> /var/log/backup-daily.log 2>&1
#
# Manual test run:
#   HEALTHCHECK_URL="" /root/onestack/scripts/backup-daily.sh

set -euo pipefail

DATE=$(date +%Y%m%d-%H%M%S)
S3_REMOTE="${S3_REMOTE:-yandex:onestack-backups}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/root/.backup-passphrase}"
STORAGE_VOLUME="${STORAGE_VOLUME:-/root/lisa/supabase/docker/volumes/storage}"

on_error() {
  local line=$1
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] FAILED at line $line"
  if [ -n "$HEALTHCHECK_URL" ]; then
    curl -fsS -m 10 "$HEALTHCHECK_URL/fail" > /dev/null || true
  fi
  exit 1
}
trap 'on_error $LINENO' ERR

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "=== OneStack daily backup starting (target: $S3_REMOTE) ==="

# Sanity checks
[ -f "$PASSPHRASE_FILE" ] || { log "ERROR: missing $PASSPHRASE_FILE"; exit 1; }
docker exec supabase-db true || { log "ERROR: supabase-db container not running"; exit 1; }

# === 1. Database custom-format dump — streaming to S3 ===
log "DB dump: streaming to $S3_REMOTE/db/$DATE.dump"
docker exec -i supabase-db pg_dump \
  -U postgres -d postgres \
  --schema=kvota --schema=auth --schema=storage --schema=public --schema=realtime \
  --format=custom --compress=9 \
  | rclone rcat "$S3_REMOTE/db/$DATE.dump" --s3-no-check-bucket

# === 2. Roles (small, needed for restore) ===
log "Roles: streaming to $S3_REMOTE/db/$DATE.roles.sql"
docker exec -i supabase-db pg_dumpall -U postgres --roles-only \
  | rclone rcat "$S3_REMOTE/db/$DATE.roles.sql"

# === 3. Storage volume (Supabase Storage API files) ===
log "Storage sync: $STORAGE_VOLUME → $S3_REMOTE/storage/current/"
rclone sync "$STORAGE_VOLUME/" "$S3_REMOTE/storage/current/" \
  --backup-dir "$S3_REMOTE/storage/history/$DATE/" \
  --transfers 4 \
  --stats 1m

# === 4. Encrypted snapshot of configs/.env ===
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
log "Pruning: dumps >30d, configs >30d, storage history >90d"
rclone delete --min-age 30d "$S3_REMOTE/db/" --include "*.dump" --include "*.sql" || true
rclone delete --min-age 30d "$S3_REMOTE/configs/" --include "*.gpg" || true
rclone delete --min-age 90d "$S3_REMOTE/storage/history/" || true

# === 6. Healthcheck success ===
if [ -n "$HEALTHCHECK_URL" ]; then
  curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" > /dev/null
fi

log "=== Backup complete ==="
