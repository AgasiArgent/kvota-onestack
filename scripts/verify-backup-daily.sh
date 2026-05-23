#!/bin/bash
# OneStack Layer 1 verification — daily existence check
#
# Catches:
#   - Cron didn't fire (backup file missing)
#   - Backup file age > 25h (yesterday's cron didn't complete)
#   - Backup file suspiciously small (0 bytes, partial upload)
#   - Storage volume not synced
#   - Configs not encrypted/uploaded
#
# Trade-offs vs full restore (Layer 2/3):
#   - Cheap (only S3 list/stat metadata, no downloads)
#   - Fast (~5 sec)
#   - Doesn't catch corruption — only existence/age/size
#
# Cron:
#   0 6 * * * /bin/bash -c 'source /etc/profile.d/backup.sh && /root/onestack/scripts/verify-backup-daily.sh' >> /var/log/verify-backup-daily.log 2>&1

set -uo pipefail

S3_REMOTE="${S3_REMOTE:-yandex:kvota-backups}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# Thresholds
MIN_DUMP_BYTES=10000000        # 10 MB — DB dump should be at least 10 MB
MIN_STORAGE_BYTES=10000000     # 10 MB — Storage current/ should be > 10 MB
MIN_CONFIGS_BYTES=1000         # 1 KB — encrypted configs tar.gz.gpg
MAX_AGE_HOURS=25               # Daily backup should be < 25h old

PROBLEMS=()

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

check_path() {
  local label=$1
  local path=$2
  local pattern=$3
  local min_bytes=$4

  local file_info
  file_info=$(rclone lsl "$path" --include "$pattern" 2>/dev/null | sort -k2,3 | tail -1)
  if [ -z "$file_info" ]; then
    PROBLEMS+=("$label: no files matching $pattern in $path")
    return 1
  fi

  # rclone lsl format: SIZE   DATE       TIME       FILENAME
  local size date time
  size=$(echo "$file_info" | awk '{print $1}')
  date=$(echo "$file_info" | awk '{print $2}')
  time=$(echo "$file_info" | awk '{print $3}')

  if [ "$size" -lt "$min_bytes" ]; then
    PROBLEMS+=("$label: latest file too small ($size bytes < $min_bytes)")
  fi

  local file_ts
  file_ts=$(date -d "$date $time" +%s 2>/dev/null || echo 0)
  local now_ts=$(date +%s)
  local age_hours=$(( (now_ts - file_ts) / 3600 ))

  if [ "$age_hours" -gt "$MAX_AGE_HOURS" ]; then
    PROBLEMS+=("$label: latest file is ${age_hours}h old (> ${MAX_AGE_HOURS}h)")
  fi

  log "$label OK: $size bytes, ${age_hours}h old"
}

check_storage() {
  local storage_size
  storage_size=$(rclone size "$S3_REMOTE/storage/current/" --json 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('bytes',0))" 2>/dev/null \
    || echo 0)

  if [ "$storage_size" -lt "$MIN_STORAGE_BYTES" ]; then
    PROBLEMS+=("storage: current/ too small ($storage_size bytes < $MIN_STORAGE_BYTES)")
  else
    log "storage OK: $storage_size bytes total"
  fi
}

log "=== Layer 1 verify starting ==="

check_path "db dump" "$S3_REMOTE/db/" "*.dump" "$MIN_DUMP_BYTES"
check_path "db roles" "$S3_REMOTE/db/" "*.roles.sql" "100"  # roles.sql is small
check_storage
check_path "configs" "$S3_REMOTE/configs/" "*.tar.gz.gpg" "$MIN_CONFIGS_BYTES"

if [ ${#PROBLEMS[@]} -eq 0 ]; then
  log "=== ALL CHECKS PASSED ==="
  # No notification on success — daily ✅ message would create alert fatigue
  # Only the daily backup success at 02:00 sends Telegram
else
  log "=== FAILED: ${#PROBLEMS[@]} problem(s) ==="
  for p in "${PROBLEMS[@]}"; do log "  - $p"; done

  msg="⚠️ <b>OneStack backup verification FAILED</b>

Layer 1 daily checks found ${#PROBLEMS[@]} problem(s):

"
  for p in "${PROBLEMS[@]}"; do
    msg+="• <code>$p</code>
"
  done
  msg+="
Check: <code>/var/log/verify-backup-daily.log</code>"

  tg_send "$msg"
  exit 1
fi
