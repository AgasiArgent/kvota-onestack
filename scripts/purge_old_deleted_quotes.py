#!/usr/bin/env python3
"""Hard-purge of quotes whose soft-delete is older than the retention window.

Part of the soft-delete / entity-lifecycle initiative (spec:
`.kiro/specs/soft-delete-entity-lifecycle/`). Implements REQ-008: daily
permanent deletion of rows whose `deleted_at` is older than 365 days.

How it works
------------
A quote is the top of the `quote -> specification -> deal` chain. FK wiring:

- `specifications.quote_id` -> CASCADE (spec goes when quote goes)
- `deals.specification_id` -> RESTRICT  (deal blocks spec deletion)
- `deals.quote_id`         -> RESTRICT  (deal blocks quote deletion)

Therefore the per-quote delete order MUST be:
  1) delete `deals` whose `specification_id` belongs to this quote's specs,
  2) delete `specifications` for this quote,
  3) delete the `quote` row itself.

Everything downstream of `deals` (plan_fact_items, logistics_stages,
currency_invoices, deal_logistics_expenses, ...) and downstream of `quotes`
(quote_items, quote_comments, quote_timeline_events, quote_workflow_transitions,
phmb_*, quote_calculation_*, status_history, approvals, ...) is wired as
CASCADE, so those rows disappear automatically.

Scheduling
----------
Not configured here (out of scope for this change). To enable on beget-kvota,
add to the existing host cron or a systemd timer something like:

    5 3 * * *  cd /root/onestack && /usr/bin/python scripts/purge_old_deleted_quotes.py >> /var/log/kvota-purge.log 2>&1

Do NOT bake scheduling into docker-compose in this PR.

Usage
-----
    python scripts/purge_old_deleted_quotes.py                  # real run, 365d
    python scripts/purge_old_deleted_quotes.py --dry-run        # plan only
    python scripts/purge_old_deleted_quotes.py --days 400       # stricter retention
    python scripts/purge_old_deleted_quotes.py --limit 100      # smaller batch

Exit codes: 0 on success (including dry-run), 1 on unexpected error.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

# Ensure project root on sys.path so `services.database` resolves when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import get_supabase  # noqa: E402

DEFAULT_RETENTION_DAYS = 365
DEFAULT_BATCH_LIMIT = 500
MIN_RETENTION_DAYS = 30  # guardrail: refuse dangerously short retention windows

logger = logging.getLogger("purge_old_deleted_quotes")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hard-delete quotes soft-deleted longer than the retention window.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be deleted but make no changes.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Retention window in days (default: {DEFAULT_RETENTION_DAYS}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_BATCH_LIMIT,
        help=f"Max quotes to process in this run (default: {DEFAULT_BATCH_LIMIT}).",
    )
    return parser.parse_args(argv)


def _fetch_expired_quotes(supabase: Any, cutoff_iso: str, limit: int) -> list[dict[str, Any]]:
    """Return soft-deleted quotes older than the cutoff, oldest first."""
    response = (
        supabase.table("quotes")
        .select("id, idn_quote, customer_id, deleted_at")
        .lt("deleted_at", cutoff_iso)
        .order("deleted_at", desc=False)
        .limit(limit)
        .execute()
    )
    return list(response.data or [])


def _delete_rows(supabase: Any, table: str, column: str, values: list[str] | str) -> int:
    """Delete rows matching column in/eq values. Returns affected row count."""
    query = supabase.table(table).delete()
    if isinstance(values, list):
        if not values:
            return 0
        query = query.in_(column, values)
    else:
        query = query.eq(column, values)
    response = query.execute()
    return len(response.data or [])


def _purge_one_quote(
    supabase: Any, quote: dict[str, Any], dry_run: bool
) -> dict[str, int]:
    """Delete one quote and its spec/deal subtree. Returns counts per table.

    Delete order: deals -> specs -> quote. Keys on quote_id for deals AND specs
    (not on specification_id for deals) because BOTH deals.quote_id AND
    deals.specification_id are RESTRICT FKs — keying the delete on quote_id
    alone covers every deal that belongs to this quote, regardless of whether
    a spec intermediates it. Using specification_id would miss the degenerate
    (deal-without-spec) case and leave a RESTRICT violation when the quote
    delete fires.
    """
    quote_id = quote["id"]
    idn = quote.get("idn_quote") or quote_id
    counts = {"deals": 0, "specifications": 0, "quotes": 0}

    if dry_run:
        # Count what WOULD be touched without mutating. All three counts use
        # quote_id so dry-run matches the real-run key.
        deals_resp = (
            supabase.table("deals")
            .select("id")
            .eq("quote_id", quote_id)
            .execute()
        )
        counts["deals"] = len(deals_resp.data or [])
        specs_resp = (
            supabase.table("specifications")
            .select("id")
            .eq("quote_id", quote_id)
            .execute()
        )
        counts["specifications"] = len(specs_resp.data or [])
        counts["quotes"] = 1
        logger.info(
            "[DRY-RUN] would purge %s (id=%s, deleted_at=%s) -> %d deal(s), "
            "%d spec(s), 1 quote (CASCADE covers children)",
            idn,
            quote_id,
            quote.get("deleted_at"),
            counts["deals"],
            counts["specifications"],
        )
        return counts

    # Real run. Order matters: deals -> specs -> quote (FK RESTRICT forces it).
    counts["deals"] = _delete_rows(supabase, "deals", "quote_id", quote_id)
    counts["specifications"] = _delete_rows(
        supabase, "specifications", "quote_id", quote_id
    )
    counts["quotes"] = _delete_rows(supabase, "quotes", "id", quote_id)

    if counts["quotes"] == 0:
        # Row vanished between fetch and delete (parallel cron / manual cleanup).
        logger.info(
            "[SKIP] %s (id=%s) already gone; nothing to purge",
            idn,
            quote_id,
        )
        return counts

    logger.info(
        "purging %s (id=%s, deleted_at=%s) -> removed: %d deal(s), %d spec(s), "
        "1 quote (CASCADE covers children)",
        idn,
        quote_id,
        quote.get("deleted_at"),
        counts["deals"],
        counts["specifications"],
    )
    return counts


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.days < MIN_RETENTION_DAYS:
        logger.error(
            "refusing to run with retention=%d day(s): minimum allowed is %d. "
            "If this is intentional, raise MIN_RETENTION_DAYS deliberately.",
            args.days,
            MIN_RETENTION_DAYS,
        )
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    cutoff_iso = cutoff.isoformat()

    mode = "[DRY-RUN] " if args.dry_run else ""
    logger.info(
        "%sstarting purge: retention=%d day(s), cutoff=%s, limit=%d",
        mode,
        args.days,
        cutoff_iso,
        args.limit,
    )

    started = time.monotonic()
    supabase = get_supabase()
    expired = _fetch_expired_quotes(supabase, cutoff_iso, args.limit)

    if not expired:
        logger.info("%sno quotes eligible for purge", mode)
        elapsed = time.monotonic() - started
        logger.info(
            "%spurge complete: 0 quotes purged, %.2f seconds, 0 rows in total",
            mode,
            elapsed,
        )
        return 0

    totals = {"deals": 0, "specifications": 0, "quotes": 0}
    purged_quotes = 0
    for quote in expired:
        counts = _purge_one_quote(supabase, quote, args.dry_run)
        for k, v in counts.items():
            totals[k] += v
        if counts["quotes"] > 0 or args.dry_run:
            purged_quotes += 1

    elapsed = time.monotonic() - started
    total_rows = sum(totals.values())
    logger.info(
        "%spurge complete: %d quote(s) purged, %.2f seconds, %d row(s) in total "
        "(deals=%d, specs=%d, quotes=%d; CASCADE-deleted children not counted)",
        mode,
        purged_quotes,
        elapsed,
        total_rows,
        totals["deals"],
        totals["specifications"],
        totals["quotes"],
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return run(argv)
    except Exception:
        logger.exception("unexpected error during purge")
        return 1


if __name__ == "__main__":
    sys.exit(main())
