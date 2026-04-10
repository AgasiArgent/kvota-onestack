#!/usr/bin/env python3
"""One-off: re-run assign_logistics_to_invoices for quotes stuck after migration 260.

After migration 260 populates invoices.pickup_country for quotes stuck in
`pending_logistics_and_customs`, this script triggers the Python routing logic
that SQL alone cannot perform: for each such quote it calls
`services.workflow_service.assign_logistics_to_invoices(quote_id)`, which
routes invoices to logistics users via the RPC
`get_logistics_manager_for_locations` and updates
`quotes.assigned_logistics_user`.

The script is idempotent — `assign_logistics_to_invoices` overwrites any prior
assignment, so re-running it is safe.

Related bugs: FB-260410-110450-4b85, FB-260410-123751-4b94
ClickUp: 86agtxp84

Usage:
    python scripts/backfill_logistics_assignment.py
"""

import os
import sys
from typing import Any, Dict, List

# Add project root to sys.path so `services.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database import get_supabase
from services.workflow_service import assign_logistics_to_invoices


def fetch_stuck_quotes() -> List[Dict[str, Any]]:
    """Return quotes in pending_logistics_and_customs with no logistics user yet."""
    supabase = get_supabase()
    response = (
        supabase.table("quotes")
        .select("id, idn_quote")
        .eq("workflow_status", "pending_logistics_and_customs")
        .is_("deleted_at", None)
        .is_("assigned_logistics_user", None)
        .execute()
    )
    # Narrow supabase-py's List[JSON] | list[Dict[str, Any]] union via isinstance
    # so Pyright can resolve the return type without any-casts.
    return [row for row in (response.data or []) if isinstance(row, dict)]


def backfill_quote(quote: Dict[str, Any]) -> Dict[str, Any]:
    """Run assign_logistics_to_invoices for a single quote and return its result."""
    return assign_logistics_to_invoices(quote["id"])


def main() -> int:
    stuck = fetch_stuck_quotes()
    print(f"Found {len(stuck)} quote(s) needing logistics assignment")

    if not stuck:
        return 0

    ok_count = 0
    fail_count = 0

    for quote in stuck:
        idn = quote.get("idn_quote") or quote["id"]
        try:
            result = backfill_quote(quote)
        except Exception as exc:  # surface, don't swallow
            fail_count += 1
            print(f"  {idn}: ERROR -> {exc}")
            continue

        status = "OK" if result.get("success") else "FAIL"
        user = result.get("quote_level_user_id") or "unmatched"
        unmatched = len(result.get("unmatched_invoice_ids") or [])
        error = result.get("error_message")

        if result.get("success"):
            ok_count += 1
        else:
            fail_count += 1

        extras = f"unmatched_invoices={unmatched}"
        if error:
            extras += f", error={error!r}"
        print(f"  {idn}: {status} -> user={user} ({extras})")

    print(f"\nSummary: {ok_count} OK, {fail_count} FAIL (of {len(stuck)} total)")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
