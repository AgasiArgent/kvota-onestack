# Phase 2 — WAL-G + Continuous WAL Archiving (PITR)

**Status:** PLAN — not yet activated.
**Requires:** ~30 second PG restart during quiet hours.
**Impact:** RPO drops from 24h (Phase 1) to ~5 min.
**Already installed:** WAL-G 3.0.5 in supabase-db container at `/usr/local/bin/wal-g`.

## Why this exists separately from Phase 1

Phase 1 (daily pg_dump) gives RPO 24h. If users update 50 quotes today and disaster hits at 19:00, the 02:00 backup loses everything from morning. For SaaS billing/contracts data, 24h loss is risky.

WAL-G continuously ships PostgreSQL Write-Ahead Log segments to S3 in near real-time. Combined with periodic base backups, this enables Point-in-Time Recovery (PITR) to any moment in the past 30 days.

## Architecture

```
PG writes data           PG writes WAL          WAL-G ships
  to data files    →     to pg_wal/      →     to S3 (every 60s
  (continuous)            (continuous)          or when WAL full)

Daily 03:00:
  WAL-G base-push      →  S3 (full snapshot)
```

S3 layout under existing bucket:
```
yandex:kvota-backups/
├── db/                      # Phase 1: daily pg_dump (already running)
├── storage/                 # Phase 1: rclone sync
├── configs/                 # Phase 1: encrypted .env
└── wal-g/                   # Phase 2: WAL-G data (NEW)
    ├── basebackups_005/     # base backups
    └── wal_005/             # WAL segments
```

## Activation procedure (PG restart required)

> ⚠️ Run during quiet hours (after 22:00 MSK or before 09:00 MSK).
> Takes ~30-60 seconds total, of which ~5-10 seconds is PG unavailable.

### Step 1: Create WAL-G env file inside container's data dir

```bash
ssh beget-kvota

# Env file location: in PG data dir (bind-mounted, accessible from container)
# Path on host: /root/lisa/supabase/docker/volumes/db/data/.walg-env.sh
# Path in container: /var/lib/postgresql/data/.walg-env.sh

cat > /root/lisa/supabase/docker/volumes/db/data/.walg-env.sh <<'EOF'
export AWS_ACCESS_KEY_ID=<from rclone.conf>
export AWS_SECRET_ACCESS_KEY=<from rclone.conf>
export AWS_ENDPOINT=https://storage.yandexcloud.net
export AWS_REGION=ru-central1
export AWS_S3_FORCE_PATH_STYLE=true
export WALG_S3_PREFIX=s3://kvota-backups/wal-g
export WALG_COMPRESSION_METHOD=lz4
export WALG_DELTA_MAX_STEPS=5
export WALG_UPLOAD_CONCURRENCY=4
export WALG_DOWNLOAD_CONCURRENCY=4
export WALG_PREVENT_WAL_OVERWRITE=true
EOF
chmod 600 /root/lisa/supabase/docker/volumes/db/data/.walg-env.sh
chown 999:999 /root/lisa/supabase/docker/volumes/db/data/.walg-env.sh  # postgres user UID in container
```

### Step 2: Create archive_command wrapper script

```bash
cat > /root/lisa/supabase/docker/volumes/db/data/.walg-push.sh <<'EOF'
#!/bin/bash
. /var/lib/postgresql/data/.walg-env.sh
exec /usr/local/bin/wal-g wal-push "$1"
EOF
chmod 755 /root/lisa/supabase/docker/volumes/db/data/.walg-push.sh
chown 999:999 /root/lisa/supabase/docker/volumes/db/data/.walg-push.sh
```

### Step 3: Take initial base backup (BEFORE enabling archive)

This ensures we have a starting point. Done while PG is still running normally.

```bash
docker exec supabase-db bash -c '
  source /var/lib/postgresql/data/.walg-env.sh
  wal-g backup-push /var/lib/postgresql/data
'
# Should take ~2-5 minutes; uploads to yandex:kvota-backups/wal-g/basebackups_005/
```

Verify in another terminal:
```bash
rclone ls yandex:kvota-backups/wal-g/basebackups_005/ | head
# Should see new base backup files
```

### Step 4: Modify postgresql.conf to enable archive

```bash
# Backup current config first
cp /root/lisa/supabase/docker/volumes/db/data/postgresql.conf{,.before-walg}

# Append archive settings to postgresql.auto.conf (Supabase usually uses this for overrides)
cat >> /root/lisa/supabase/docker/volumes/db/data/postgresql.auto.conf <<'EOF'

# WAL-G archive configuration (added 2026-XX-XX)
archive_mode = on
archive_command = '/var/lib/postgresql/data/.walg-push.sh %p'
archive_timeout = 60
EOF
```

### Step 5: Restart supabase-db container

> ⚠️ **5-10 second downtime here.** All other supabase services (auth, storage, etc.) depend on db, so they'll error too briefly.

```bash
docker restart supabase-db

# Wait for ready
sleep 5
docker exec supabase-db pg_isready -U postgres
# Should return "accepting connections"
```

### Step 6: Verify WAL archive is flowing

Wait 60 seconds (archive_timeout), then check:

```bash
# Force a WAL switch to test
docker exec supabase-db psql -U postgres -d postgres -c "SELECT pg_switch_wal();"

# Check S3 for new WAL files
sleep 30
rclone ls yandex:kvota-backups/wal-g/wal_005/ | tail -5
# Should see at least one WAL file appearing
```

### Step 7: Set up daily base backup cron

```bash
cat > /root/onestack/scripts/wal-g-base-backup.sh <<'EOF'
#!/bin/bash
set -euo pipefail
docker exec supabase-db bash -c '
  source /var/lib/postgresql/data/.walg-env.sh
  /usr/local/bin/wal-g backup-push /var/lib/postgresql/data
'
# Retention: keep 7 most recent base backups
docker exec supabase-db bash -c '
  source /var/lib/postgresql/data/.walg-env.sh
  /usr/local/bin/wal-g delete retain FULL 7 --confirm
'
EOF
chmod +x /root/onestack/scripts/wal-g-base-backup.sh

# Add to cron — 03:00 daily, 1h after Phase 1 pg_dump
(crontab -l 2>/dev/null
 echo '0 3 * * * /root/onestack/scripts/wal-g-base-backup.sh >> /var/log/wal-g-base-backup.log 2>&1'
) | crontab -
```

### Step 8: Update verify-restore-weekly.sh to also check WAL archive

(Phase 3 layer 2 update — verify WAL files are recent.)

This will be done in a separate commit.

## Rollback plan (if anything goes wrong)

If activation fails or causes issues:

```bash
# Remove archive settings from postgresql.auto.conf
sed -i '/^# WAL-G archive/,/^archive_timeout/d' \
  /root/lisa/supabase/docker/volumes/db/data/postgresql.auto.conf

# Restart to disable archive_mode
docker restart supabase-db
```

PG will resume normal operation without WAL archiving. Phase 1 backups still work independently.

## PITR Restore procedure (for runbook)

If we need to restore to a specific moment:

```bash
# 1. Stop PG
docker stop supabase-db

# 2. Backup current data (just in case)
mv /root/lisa/supabase/docker/volumes/db/data{,.before-pitr-$(date +%Y%m%d)}
mkdir /root/lisa/supabase/docker/volumes/db/data

# 3. Fetch base backup
docker run --rm \
  -v /root/lisa/supabase/docker/volumes/db/data:/var/lib/postgresql/data \
  --env-file /etc/walg-env.sh \
  supabase/postgres:15 \
  wal-g backup-fetch /var/lib/postgresql/data LATEST

# 4. Configure recovery target
cat > /root/lisa/supabase/docker/volumes/db/data/postgresql.auto.conf <<EOF
restore_command = '/var/lib/postgresql/data/.walg-fetch.sh %f %p'
recovery_target_time = '<YYYY-MM-DD HH:MM:SS MSK>'
recovery_target_action = 'promote'
EOF
touch /root/lisa/supabase/docker/volumes/db/data/recovery.signal

# 5. Restart PG → automatic recovery
docker start supabase-db

# 6. Verify recovery completed
docker exec supabase-db psql -U postgres -d postgres -c "SELECT pg_is_in_recovery();"
# Should return 'f' (false) after recovery completes
```

## Cost estimate after Phase 2

| Component | ~Monthly cost |
|-----------|--------------|
| Phase 1 already running | ~200 ₽ |
| WAL-G base backups (daily, retain 7) | ~70 ₽ |
| WAL archive (varies with write load, est. 100-500 MB/day) | ~30-100 ₽ |
| Egress for restore drills | ~10-30 ₽ |
| **Total Phase 1 + 2** | **~310-400 ₽/мес** |

Still well within "small-budget for solo SaaS" range.

## When to schedule activation

**Recommended timing:**
- After 22:00 MSK or before 09:00 MSK (low traffic hours)
- Not Monday/Friday (avoid bookend stress)
- Not during a deploy/release
- When you have 10-15 minutes available to monitor

**Pre-flight check:**
- Disk space ≥ 5 GB free (`df -h /`)
- supabase-db healthy (`docker ps | grep supabase-db`)
- No active migrations running

**Procedure time estimate:**
- Step 1-4 (prep): 5 minutes
- Step 5 (restart): 5-10 seconds downtime
- Step 6 (verify): 2-3 minutes monitoring
- Step 7-8 (cron): 1 minute
- **Total active work:** ~10 minutes
- **Total downtime:** ~5-10 seconds

## Communication template (if you want to notify users)

If OneStack has any active customer integration (webhooks, public API), consider posting:

> Maintenance window XX:YY MSK: brief database restart (~10 sec) for backup infrastructure upgrade. No data loss expected. Reply 'issues' if you see problems after.

Otherwise (B2B internal tool), no notification needed.

## Activation checklist

When you're ready:

- [ ] Pick a quiet hour
- [ ] Verify Phase 1 backups still working (Telegram should have ✅ this morning)
- [ ] Open `~/workspace/.../scripts/phase-2-walg-plan.md` (this file) in editor
- [ ] Run steps 1-8 sequentially
- [ ] If anything weird at step 5 (restart) — execute rollback immediately
- [ ] Update concept page in wiki with activation date
- [ ] Schedule first PITR drill (Layer 3 monthly drill can include PITR steps after Phase 2)
