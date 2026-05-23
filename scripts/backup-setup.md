# Backup Setup — Phase 1 (Daily pg_dump + Storage + Configs → Yandex Object Storage)

One-time setup steps for `scripts/backup-daily.sh`. See concept page in wiki for the full strategy:
`~/workspace/wiki/wiki/concepts/onestack-backup-disaster-recovery.md`

## 1. Yandex Cloud account + S3 bucket

**Manual steps (one-time, ~30 min):**

1. Create Yandex ID at https://passport.yandex.ru if you don't have one
2. Activate Yandex Cloud at https://console.cloud.yandex.ru — link your Yandex ID
3. Create a billing account (нужна банковская карта; есть free trial кредит на старте)
4. Create a **folder** (logical container): e.g., `onestack`
5. Create a **service account** with role `storage.editor`:
   - Console → IAM → Service Accounts → Create
   - Name: `onestack-backup`
   - Role: `storage.editor`
6. Create **static access keys** for that service account:
   - Service account detail page → Create new key → Static access key
   - **SAVE** the `Access Key ID` (visible) and `Secret` (shown once!)
7. Create **bucket**:
   - Console → Object Storage → Create Bucket
   - Name: `onestack-backups` (globally unique — may need suffix like `onestack-backups-kvotaflow`)
   - Storage class: `Standard` (or `Cold` for cheaper, slower retrieval)
   - Access: **Private**
   - Versioning: **On** (extra safety vs accidental overwrite)
   - Encryption: **Enabled** (server-side AES-256, free)

**Output you need to capture:**
- `BUCKET_NAME` (e.g., `onestack-backups-kvotaflow`)
- `ACCESS_KEY_ID`
- `SECRET_ACCESS_KEY`

## 2. Configure rclone on VPS

```bash
ssh beget-kvota

# Create rclone config dir
mkdir -p /root/.config/rclone

# Write rclone.conf
cat > /root/.config/rclone/rclone.conf <<'EOF'
[yandex]
type = s3
provider = Other
env_auth = false
access_key_id = <PASTE-ACCESS-KEY-ID>
secret_access_key = <PASTE-SECRET-KEY>
endpoint = https://storage.yandexcloud.net
region = ru-central1
acl = private
force_path_style = true
EOF
chmod 600 /root/.config/rclone/rclone.conf

# Verify connection
rclone lsd yandex:
# Should list your bucket

# Update S3_REMOTE in /etc/profile.d/backup.sh if bucket name differs:
# Default: yandex:kvota-backups
# If your bucket is different: yandex:<your-bucket-name>
```

## 3. Set up GPG passphrase for configs encryption

```bash
# Generate a strong random passphrase
openssl rand -base64 48 > /root/.backup-passphrase
chmod 600 /root/.backup-passphrase

# CRITICAL: copy this passphrase to a password manager!
# If you lose it, encrypted configs become unrecoverable.
cat /root/.backup-passphrase
# Save to: 1Password / Bitwarden / your password manager
```

## 4. Telegram bot notifications

> ⚠️ **Why not Healthchecks.io:** their service blocks Russian IPs since Dec 2022
> ([blog.healthchecks.io/2022/12/ru-ip-block](https://blog.healthchecks.io/2022/12/ru-ip-block/)).
> First production backup run from beget-kvota returned HTTP 403 on the success
> ping despite successful data upload. Switched to direct Telegram Bot API.

OneStack already runs a Telegram bot for app errors (`@kvota_error_bot`).
We reuse the same bot for backup alerts.

Get the token and chat ID from the running container:

```bash
ssh beget-kvota "docker exec kvota-onestack env | grep -E 'TELEGRAM_BOT_TOKEN|ADMIN_TELEGRAM_CHAT_ID'"
# Outputs: TELEGRAM_BOT_TOKEN=...  ADMIN_TELEGRAM_CHAT_ID=...
```

Set the env file (chmod 600 because it contains the bot token):

```bash
cat > /etc/profile.d/backup.sh <<'EOF'
export S3_REMOTE=yandex:kvota-backups
export TELEGRAM_BOT_TOKEN=<bot-token-from-container>
export TELEGRAM_CHAT_ID=<your-admin-chat-id>
EOF
chmod 600 /etc/profile.d/backup.sh
```

**Trade-off:** No dead-man-switch monitoring — if cron never fires at all,
you won't be notified. Mitigations:
- Beget tier-3 auto-backups (every 2-5 days, ~10d retention) as last-resort fallback
- Weekly visual check on `@kvota_error_bot` chat history
- Future enhancement: add cron-job.org as external HTTP monitor pointing at
  `/api/health` if dead-man becomes a priority

## 5. Deploy backup script + cron

```bash
ssh beget-kvota

# Pull latest onestack code (assumes you've pushed scripts/backup-daily.sh)
cd /root/onestack && git pull

# Make script executable
chmod +x /root/onestack/scripts/backup-daily.sh

# First-time dry-run test (with empty HEALTHCHECK_URL to skip ping)
HEALTHCHECK_URL="" /root/onestack/scripts/backup-daily.sh

# If success — install cron
(crontab -l 2>/dev/null; \
 echo "0 2 * * * /root/onestack/scripts/backup-daily.sh >> /var/log/backup-daily.log 2>&1" \
) | crontab -

# Verify
crontab -l | grep backup
```

## 6. Verify in Yandex Cloud

After first manual run, check Yandex Object Storage console:
- `onestack-backups/db/YYYYMMDD-HHMMSS.dump` — should be ~3-8 GB (compressed PG)
- `onestack-backups/db/YYYYMMDD-HHMMSS.roles.sql` — small, ~5-50 KB
- `onestack-backups/storage/current/...` — mirror of Storage volume
- `onestack-backups/configs/YYYYMMDD-HHMMSS.tar.gz.gpg` — small, ~5-50 KB

## Restore (for reference — full procedure in concept page Phase 1 section)

### Restore DB
```bash
# Download dump
rclone copy yandex:onestack-backups/db/<DATE>.dump /tmp/

# Restore via pg_restore (single-transaction is safer)
docker cp /tmp/<DATE>.dump supabase-db:/tmp/
docker exec supabase-db pg_restore \
  -U postgres -d postgres \
  --single-transaction \
  --no-owner --no-acl \
  /tmp/<DATE>.dump
```

### Restore Storage
```bash
rclone sync yandex:onestack-backups/storage/current/ \
  /root/lisa/supabase/docker/volumes/storage/
```

### Decrypt configs (if needed)
```bash
rclone copy yandex:onestack-backups/configs/<DATE>.tar.gz.gpg /tmp/
gpg --decrypt --batch \
  --passphrase-file /root/.backup-passphrase \
  /tmp/<DATE>.tar.gz.gpg | tar xzvf - -C /restore/path/
```

## Costs (estimated)

| Item | Monthly |
|------|---------|
| Storage ~10 GB (30 days of dumps + configs) | ~30 ₽ |
| Storage Standard egress (occasional drills) | ~30 ₽ |
| API requests (PUT/GET) | ~20 ₽ |
| **Total** | **~80 ₽** |

(Yandex pricing: ~1.96 ₽/GB-month for Standard storage)
