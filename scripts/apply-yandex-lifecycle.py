#!/usr/bin/env python3
"""Apply S3 lifecycle policy to Yandex Object Storage backup bucket.

Reads credentials from /root/.config/rclone/rclone.conf [yandex] section.
Idempotent — running this overwrites the current policy with the same one.

Lifecycle = native Yandex retention; runs server-side daily without our cron.
Acts as a safety net if rclone-based pruning in backup-daily.sh breaks.

Usage:
    pip3 install --user boto3
    python3 scripts/apply-yandex-lifecycle.py

Rules:
    db/                  → expire current 30d, noncurrent 7d, abort multipart 7d
    configs/             → expire current 30d, noncurrent 7d
    storage/history/     → expire current 90d, noncurrent 7d
    storage/current/     → keep current forever, expire noncurrent (old versions) 30d

To modify: edit the LIFECYCLE_RULES dict below, rerun the script. Or use
Yandex Cloud console → Object Storage → bucket → Lifecycle for ad-hoc tweaks.
"""

import configparser
import json
import sys

try:
    import boto3
except ImportError:
    sys.exit("boto3 missing — run: pip3 install --user boto3")

RCLONE_CONF = "/root/.config/rclone/rclone.conf"
BUCKET = "kvota-backups"
ENDPOINT = "https://storage.yandexcloud.net"
REGION = "ru-central1"

LIFECYCLE_RULES = {
    "Rules": [
        {
            "ID": "expire-db-dumps-30d",
            "Status": "Enabled",
            "Filter": {"Prefix": "db/"},
            "Expiration": {"Days": 30},
            "NoncurrentVersionExpiration": {"NoncurrentDays": 7},
            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
        },
        {
            "ID": "expire-configs-30d",
            "Status": "Enabled",
            "Filter": {"Prefix": "configs/"},
            "Expiration": {"Days": 30},
            "NoncurrentVersionExpiration": {"NoncurrentDays": 7},
        },
        {
            "ID": "expire-storage-history-90d",
            "Status": "Enabled",
            "Filter": {"Prefix": "storage/history/"},
            "Expiration": {"Days": 90},
            "NoncurrentVersionExpiration": {"NoncurrentDays": 7},
        },
        {
            "ID": "expire-storage-current-old-versions",
            "Status": "Enabled",
            "Filter": {"Prefix": "storage/current/"},
            "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
        },
    ]
}


def main():
    conf = configparser.ConfigParser()
    conf.read(RCLONE_CONF)
    if "yandex" not in conf:
        sys.exit(f"[yandex] section missing in {RCLONE_CONF}")
    creds = conf["yandex"]

    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=creds["access_key_id"],
        aws_secret_access_key=creds["secret_access_key"],
    )

    print(f"Applying lifecycle policy to bucket: {BUCKET}")
    s3.put_bucket_lifecycle_configuration(
        Bucket=BUCKET, LifecycleConfiguration=LIFECYCLE_RULES
    )

    print("Verifying via read-back...")
    result = s3.get_bucket_lifecycle_configuration(Bucket=BUCKET)
    print(json.dumps(result.get("Rules", []), indent=2, default=str))


if __name__ == "__main__":
    main()
