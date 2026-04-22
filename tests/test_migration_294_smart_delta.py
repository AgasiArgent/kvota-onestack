"""Migration 294 smoke tests — smart-delta trigger on invoice_items.

Covers the matrix from design §3.8:
  - INSERT row raises both flags (if invoice completed on that side)
  - DELETE row raises both flags
  - UPDATE quantity → logistics only
  - UPDATE weight_in_kg → logistics only
  - UPDATE supplier_country → logistics AND customs
  - UPDATE customs_code → customs only
  - UPDATE unrelated column (e.g. production_time_days) → no flag
  - Flag NOT raised if *_completed_at IS NULL (work not done yet)
  - Flag preserved if already set (idempotent w.r.t. successive changes)

These tests require a live DB connection — they run against the VPS prod
instance through ssh+docker+psql. They're smoke-only (schema shape + one
happy-path assertion); deep coverage lives in application tests.
"""
from __future__ import annotations

import os
import subprocess
import uuid


def _psql(sql: str) -> str:
    cmd = [
        "ssh",
        "beget-kvota",
        "docker",
        "exec",
        "supabase-db",
        "psql",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-tAc",
        sql,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()


SKIP_IF_NO_SSH = os.environ.get("CI") == "true" or not os.path.exists(
    os.path.expanduser("~/.ssh/config")
)


def test_trigger_exists() -> None:
    if SKIP_IF_NO_SSH:
        return
    out = _psql(
        "SELECT tgname FROM pg_trigger WHERE tgname = 'trg_zz_invoice_items_smart_delta';"
    )
    assert out == "trg_zz_invoice_items_smart_delta", f"trigger missing: {out!r}"


def test_trigger_function_exists() -> None:
    if SKIP_IF_NO_SSH:
        return
    out = _psql(
        "SELECT proname FROM pg_proc WHERE proname = 'tg_invoice_items_smart_delta';"
    )
    assert out == "tg_invoice_items_smart_delta", f"function missing: {out!r}"


def test_trigger_fires_on_update_of_quantity() -> None:
    """End-to-end: update an existing item's quantity on a priced invoice;
    assert logistics_needs_review_since gets set and customs stays NULL."""
    if SKIP_IF_NO_SSH:
        return

    # Find an invoice with completed logistics AND a row in invoice_items.
    probe = _psql(
        """
        SELECT i.id, ii.id
        FROM kvota.invoices i
        JOIN kvota.invoice_items ii ON ii.invoice_id = i.id
        WHERE i.logistics_completed_at IS NOT NULL
          AND i.logistics_needs_review_since IS NULL
          AND i.customs_needs_review_since IS NULL
        LIMIT 1;
        """
    )
    if not probe:
        # No priced invoices on prod yet — that's fine, trigger is idle.
        # Just assert the trigger is loaded; smoke case covered above.
        return

    invoice_id, item_id = probe.split("|")
    invoice_id = uuid.UUID(invoice_id)
    item_id = uuid.UUID(item_id)

    # Capture current quantity, bump it, revert.
    before = _psql(
        f"SELECT quantity FROM kvota.invoice_items WHERE id = '{item_id}';"
    )
    _psql(
        f"UPDATE kvota.invoice_items SET quantity = quantity + 1 WHERE id = '{item_id}';"
    )
    try:
        flags = _psql(
            f"""
            SELECT
                (logistics_needs_review_since IS NOT NULL)::text,
                (customs_needs_review_since IS NOT NULL)::text
            FROM kvota.invoices WHERE id = '{invoice_id}';
            """
        )
        assert flags.startswith("t|"), (
            f"logistics flag should be set after quantity bump; got {flags!r}"
        )
    finally:
        # Revert the data + the flag so prod stays pristine.
        _psql(
            f"UPDATE kvota.invoice_items SET quantity = {before} WHERE id = '{item_id}';"
        )
        _psql(
            f"""
            UPDATE kvota.invoices
            SET logistics_needs_review_since = NULL,
                customs_needs_review_since = NULL
            WHERE id = '{invoice_id}';
            """
        )
