#!/bin/bash
# Check Supabase Realtime health via Kong
# Run as cron: */5 * * * * /root/onestack/scripts/check-realtime-health.sh >> /var/log/realtime-health.log 2>&1

LOGFILE="/var/log/realtime-health.log"
MAX_LOG_SIZE=1048576  # 1MB

# Rotate log if too large
if [ -f "$LOGFILE" ] && [ $(stat -f%z "$LOGFILE" 2>/dev/null || stat -c%s "$LOGFILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]; then
  tail -100 "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi

# Check if realtime endpoint responds (via Kong → Caddy)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://db.kvotaflow.ru/realtime/v1/" 2>/dev/null)

if [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "200" ]; then
  # 401 = endpoint works (needs auth), 200 = also fine
  exit 0
fi

echo "$(date -Iseconds) WARN: Realtime unhealthy (HTTP $HTTP_CODE). Restarting..."

# Restart realtime container
cd /root/lisa/supabase/docker
docker compose restart realtime 2>&1 | tail -2

# Wait for it to come up
sleep 10

# Restart Kong to refresh DNS cache
docker restart supabase-kong 2>&1

# Wait and verify
sleep 5
HTTP_CODE_AFTER=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "https://db.kvotaflow.ru/realtime/v1/" 2>/dev/null)

if [ "$HTTP_CODE_AFTER" = "401" ] || [ "$HTTP_CODE_AFTER" = "200" ]; then
  echo "$(date -Iseconds) OK: Realtime recovered (HTTP $HTTP_CODE_AFTER)"
else
  echo "$(date -Iseconds) ERROR: Realtime still unhealthy after restart (HTTP $HTTP_CODE_AFTER)"
fi
