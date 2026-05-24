#!/bin/bash
# OneStack WAL-G daily base backup
# Cron: 0 3 * * * (1 hour after Phase 1 pg_dump)
# Retention: 7 most recent base backups (~7 days of full snapshots)
set -euo pipefail

TG_TOKEN=${TELEGRAM_BOT_TOKEN:-}
TG_CHAT=${TELEGRAM_CHAT_ID:-}

tg_send() {
  [ -z "$TG_TOKEN" ] || [ -z "$TG_CHAT" ] && return 0
  curl -fsS -m 10 -X POST "https://api.telegram.org/bot$TG_TOKEN/sendMessage"     -d "chat_id=$TG_CHAT" -d "parse_mode=HTML"     --data-urlencode "text=$1" > /dev/null || true
}

on_error() {
  tg_send "🔴 <b>WAL-G base backup FAILED</b>%0AStep: $1%0ATime: $(date)%0ALog: /var/log/wal-g-base-backup.log"
  exit 1
}
trap 'on_error $LINENO' ERR

START=$(date +%s)
echo "[$(date)] Starting wal-g backup-push"
docker exec supabase-db bash -c 'source /var/lib/postgresql/data/.walg-env.sh && /usr/local/bin/wal-g backup-push /var/lib/postgresql/data'

echo "[$(date)] Pruning to retain last 7 base backups"
docker exec supabase-db bash -c 'source /var/lib/postgresql/data/.walg-env.sh && /usr/local/bin/wal-g delete retain FULL 7 --confirm'

DUR=$(($(date +%s) - START))
echo "[$(date)] Complete in ${DUR}s"
tg_send "✅ <b>WAL-G base backup OK</b>%0ADuration: ${DUR}s%0A$(date)"
