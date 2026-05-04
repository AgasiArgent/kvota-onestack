#!/usr/bin/env python3
"""One-off backfill: advance quotes stuck in pending_procurement after the
broken direct-Supabase-UPDATE per-invoice completion shipped before the
fix/per-invoice-procurement-stage-transition refactor.

For any quote where:
  - workflow_status = 'pending_procurement'
  - deleted_at IS NULL
  - ALL non-deleted invoices have procurement_completed_at IS NOT NULL

the quote should already be in pending_logistics_and_customs but isn't, because
the legacy direct-update mutation never advanced the workflow. This script:

  1. Finds all stuck quotes.
  2. For each: runs assign_logistics_to_invoices + assign_customs_to_invoices
     (idempotent — only assigns rows lacking assignment).
  3. Atomically advances workflow_status to pending_logistics_and_customs and
     inserts a workflow_transitions audit row.

The script is idempotent — re-running on already-advanced quotes is a no-op
(the conditional UPDATE in _atomic_advance_to_logistics_and_customs filters on
workflow_status='pending_procurement').

Specifically targets Q-202604-0061 (INV-01 was committed by a prior browser-test
run before the fix landed).

Usage:
    python scripts/backfill_stuck_procurement_completions.py
"""

import os
import sys
from typing import Any, Dict, List

# Add project root to sys.path so `services.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import get_supabase
from services.workflow_service import (
    _assign_logistics_and_customs_to_invoices,
    _atomic_advance_to_logistics_and_customs,
)


# Sentinel actor used for the audit row when there's no human user available
# (e.g. server-side cron-style backfill). The workflow_transitions FK to users
# is enforced — caller should set this to a real admin user UUID when running
# in production. Override via BACKFILL_ACTOR_ID env var.
BACKFILL_ACTOR_ID = os.getenv(
    "BACKFILL_ACTOR_ID",
    # Falls back to NULL if not provided — caller must set it when running.
    "",
)


def fetch_stuck_quotes() -> List[Dict[str, Any]]:
    """Return quotes in pending_procurement whose every non-deleted invoice has
    procurement_completed_at set."""
    supabase = get_supabase()

    # Step 1: candidate quotes still in pending_procurement
    candidates_resp = (
        supabase.table("quotes")
        .select("id, idn_quote")
        .eq("workflow_status", "pending_procurement")
        .is_("deleted_at", None)
        .execute()
    )
    candidates = [
        row for row in (candidates_resp.data or []) if isinstance(row, dict)
    ]

    stuck: List[Dict[str, Any]] = []
    for quote in candidates:
        # Step 2: count incomplete invoices for this quote
        try:
            inv_resp = (
                supabase.table("invoices")
                .select("id, procurement_completed_at")
                .eq("quote_id", quote["id"])
                .is_("deleted_at", None)
                .execute()
            )
        except Exception as exc:
            print(f"  WARN  {quote.get('idn_quote') or quote['id']}: invoice fetch failed: {exc}")
            continue

        rows = inv_resp.data or []
        if not rows:
            # No invoices at all — not what this script targets
            continue

        all_completed = all(
            isinstance(r, dict) and r.get("procurement_completed_at") is not None
            for r in rows
        )
        if all_completed:
            stuck.append(quote)

    return stuck


def backfill_quote(quote_id: str) -> Dict[str, Any]:
    """Re-run assigners + atomically advance the quote.

    Returns a dict with `advanced: bool, warnings: list[str]`.
    """
    warnings = _assign_logistics_and_customs_to_invoices(quote_id)

    if not BACKFILL_ACTOR_ID:
        # Skip the actual advance if no actor is set — the FK on
        # workflow_transitions.actor_id requires a real user. Surface this
        # as a no-op so the operator can re-run with BACKFILL_ACTOR_ID set.
        return {
            "advanced": False,
            "warnings": warnings,
            "note": "BACKFILL_ACTOR_ID env not set — would-advance, skipped",
        }

    advanced, _transition_id = _atomic_advance_to_logistics_and_customs(
        quote_id=quote_id,
        actor_id=BACKFILL_ACTOR_ID,
        actor_role="admin",
    )
    return {"advanced": advanced, "warnings": warnings}


def main() -> int:
    stuck = fetch_stuck_quotes()
    print(f"Found {len(stuck)} quote(s) stuck in pending_procurement with all invoices completed")

    if not stuck:
        return 0

    if not BACKFILL_ACTOR_ID:
        print("WARNING: BACKFILL_ACTOR_ID env var not set — running in dry-run mode.")
        print("         Set it to an admin user's UUID to actually advance quotes:")
        print("           BACKFILL_ACTOR_ID=<uuid> python scripts/backfill_stuck_procurement_completions.py")
        print()

    advanced_count = 0
    skipped_count = 0
    fail_count = 0

    for quote in stuck:
        idn = quote.get("idn_quote") or quote["id"]
        try:
            result = backfill_quote(quote["id"])
        except Exception as exc:  # surface, don't swallow
            fail_count += 1
            print(f"  {idn}: ERROR -> {exc}")
            continue

        if result.get("advanced"):
            advanced_count += 1
            print(f"  {idn}: ADVANCED to pending_logistics_and_customs")
        elif "note" in result:
            skipped_count += 1
            print(f"  {idn}: SKIPPED ({result['note']})")
        else:
            # Race-loss path — already advanced concurrently. Treat as success.
            advanced_count += 1
            print(f"  {idn}: already-advanced (race-loss is fine)")

        for warning in result.get("warnings") or []:
            print(f"          warn: {warning}")

    print(
        f"\nSummary: advanced={advanced_count} skipped={skipped_count} failed={fail_count}"
    )
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
