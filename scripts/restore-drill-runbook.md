# Monthly Restore Drill — Runbook (Layer 3)

**Cadence:** Once per month (1st Sunday recommended).
**Time required:** 30-60 minutes.
**Where:** Local Docker on your laptop (default). Alternatives: Yandex Cloud temp VM, Beget temp VPS.

## Why we do this

Layers 1+2 are automated quick checks. They don't validate the **full restore procedure** under realistic conditions. A monthly drill catches:

- Actual RTO (vs theoretical)
- Procedure documentation drift
- Side effects (sequences, FKs, RLS policies)
- Application connection to restored DB
- Your own ability to execute under pressure

If a drill fails or takes 4x longer than expected, that's exactly what we want to discover **before** a real disaster.

## Pre-drill (one-time, ~5 min)

1. Install Docker Desktop / Docker Engine on your laptop
2. Install rclone locally: `brew install rclone` (Mac) / `apt-get install rclone` (Ubuntu)
3. Copy rclone config from VPS to your laptop (or configure separately):

   ```bash
   ssh beget-kvota "cat /root/.config/rclone/rclone.conf" > ~/.config/rclone/rclone.conf
   chmod 600 ~/.config/rclone/rclone.conf
   ```

4. Verify: `rclone ls yandex:kvota-backups/db/ | head` — should show dumps

## Drill procedure (~30-40 min)

### Step 1: Record start time

```bash
echo "Drill start: $(date)" | tee -a ~/drill-log.txt
```

### Step 2: Download latest dump + configs from S3

```bash
WORKDIR=$(mktemp -d)
cd "$WORKDIR"

# Download latest dump (find by sort)
LATEST_DUMP=$(rclone lsf yandex:kvota-backups/db/ --include "*.dump" | sort | tail -1)
rclone copy "yandex:kvota-backups/db/$LATEST_DUMP" .
rclone copy "yandex:kvota-backups/db/${LATEST_DUMP%.dump}.roles.sql" .

# Optional: download configs (for sanity-checking decryption)
LATEST_CFG=$(rclone lsf yandex:kvota-backups/configs/ --include "*.gpg" | sort | tail -1)
rclone copy "yandex:kvota-backups/configs/$LATEST_CFG" .

echo "Downloaded: $LATEST_DUMP ($(stat -c '%s' $LATEST_DUMP 2>/dev/null || stat -f '%z' $LATEST_DUMP) bytes)"
```

### Step 3: Spin up scratch PostgreSQL

```bash
docker run --rm -d \
  --name pg-drill \
  -e POSTGRES_PASSWORD=drill \
  -p 5433:5432 \
  postgres:15

# Wait for it to be ready
sleep 5
docker exec pg-drill pg_isready -U postgres
```

### Step 4: Create roles, then restore dump

```bash
# Roles first
docker cp ./${LATEST_DUMP%.dump}.roles.sql pg-drill:/tmp/
docker exec pg-drill psql -U postgres -f /tmp/${LATEST_DUMP%.dump}.roles.sql || true

# Then dump (single-transaction is safer)
docker cp ./$LATEST_DUMP pg-drill:/tmp/
docker exec pg-drill pg_restore \
  -U postgres -d postgres \
  --single-transaction --no-owner --no-acl \
  /tmp/$LATEST_DUMP

echo "Restore complete: $(date)"
```

If single-transaction fails on role errors:

```bash
docker exec pg-drill pg_restore \
  -U postgres -d postgres \
  --no-owner --no-acl \
  /tmp/$LATEST_DUMP || true
# Errors on roles are tolerable; data should land
```

### Step 5: Smoke queries

```bash
docker exec pg-drill psql -U postgres -d postgres <<'EOF'
-- Schema presence
\dn

-- Data sanity checks
SELECT COUNT(*) AS quotes FROM kvota.quotes;
SELECT COUNT(*) AS deals FROM kvota.deals;
SELECT COUNT(*) AS customers FROM kvota.customers;
SELECT COUNT(*) AS users FROM auth.users;
SELECT MAX(created_at) AS latest_quote_created FROM kvota.quotes;
SELECT MAX(created_at) AS latest_deal_created FROM kvota.deals;

-- FK integrity sample
SELECT COUNT(*) AS orphan_quote_items
FROM kvota.quote_items qi
WHERE NOT EXISTS (SELECT 1 FROM kvota.quotes q WHERE q.id = qi.quote_id);
EOF
```

### Step 6: Decrypt configs (optional sanity check)

```bash
# Replace passphrase with the one from your password manager
echo "YOUR_GPG_PASSPHRASE" > /tmp/.drill-pass
gpg --decrypt --batch --passphrase-file /tmp/.drill-pass "$LATEST_CFG" \
  | tar tzvf - | head -10
rm /tmp/.drill-pass

# Should list the .env files included in backup
```

### Step 7: Record RTO + observations

```bash
echo "Drill complete: $(date)" | tee -a ~/drill-log.txt
echo "Observed counts: <fill in>" | tee -a ~/drill-log.txt
echo "Issues found: <fill in>" | tee -a ~/drill-log.txt
```

Update `docs/runbooks/drill-log.md` in onestack repo with:

```markdown
## 2026-MM-DD drill

- **Latest dump:** YYYYMMDD-HHMMSS.dump (N MB)
- **Restore time (RTO):** N minutes
- **Smoke checks:** N quotes / N deals / N users restored
- **Issues:** <none|list>
- **Action items:** <if any>
```

### Step 8: Cleanup

```bash
docker stop pg-drill
rm -rf "$WORKDIR"
```

## Failure modes to investigate

| If you see... | Investigate |
|---------------|-------------|
| `pg_restore: error: could not find a file matching...` | Dump file corruption — escalate |
| Many `role "..." does not exist` errors | Roles dump issue — check `.roles.sql` is current |
| Schema kvota empty | Backup didn't include kvota schema — check `backup-daily.sh` |
| `kvota.quotes` count = 0 | Either DB is empty (unlikely) or restore truncated |
| `latest_quote_created` is old | Backup is stale — check cron |
| GPG decrypt fails | Wrong passphrase or configs corrupted |
| Restore took > 1 hour | Investigate slow point — bandwidth? Disk speed? |

## Calendar reminder

Set a recurring calendar event:
- **Title:** OneStack monthly backup drill
- **First occurrence:** 1st Sunday of next month, 10:00
- **Cadence:** Monthly
- **Reminder:** 24h before
- **Description:** Pull latest dump, spin pg-drill, restore, smoke check. Runbook: `~/workspace/.../scripts/restore-drill-runbook.md`. Log to `docs/runbooks/drill-log.md`.

## When to escalate

- 2 consecutive drills fail → Phase 1 backup pipeline broken, fix urgently
- Drill takes 2x expected time → optimize procedure or investigate VPS bandwidth
- Specific table consistently missing → review schema list in `backup-daily.sh`
- Smoke query counts drop significantly month-to-month → check for accidental data loss
