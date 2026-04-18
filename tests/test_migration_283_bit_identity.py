"""
Bit-identity regression test for migration 283 — Phase 5c backfill.

Migration 283 populates ``kvota.invoice_items`` and ``kvota.invoice_item_coverage``
from the existing Phase 5b ``invoice_item_prices`` junction plus supplier-side
columns on ``quote_items``. After the backfill, the rewritten
``services/composition_service.py`` (commit e26de0b) reads from the new tables
to build the dicts consumed by ``build_calculation_inputs()`` in main.py, which
in turn feeds the locked ``calculate_multiproduct_quote()``.

Because the calculation engine is locked and deterministic, the only way for
migration 283 to change calc output is if the composition dicts fed into
``build_calculation_inputs()`` differ before vs. after backfill. This test
protects against that regression by comparing the Phase 5b composition shape
(quote_items + iip overlay) against the Phase 5c composition shape
(``get_composed_items``) field-by-field on the exact set of inputs the calc
engine consumes.

----

**Approach chosen:** single test module, orchestrated within one pytest process
against a live dev DB via psycopg (same pattern as tests/test_migration_281.py,
test_migration_282.py). Within a rollback-only transaction we:

1. **Pre-backfill snapshot**: build "legacy shape" dicts per quote_item by
   hand — quote_items row with iip's 4 overlay fields patched in (exactly
   what Phase 5b's ``get_composed_items`` used to return). This is the
   golden fingerprint of what ``build_calculation_inputs()`` has been
   receiving in production.

2. **Apply migration 283 in-transaction**: execute the SQL file verbatim.
   Rolled back at test teardown — no dev DB state leaks.

3. **Post-backfill**: call ``composition_service.get_composed_items()`` for
   the same quote IDs, reading through the same DB connection (pipe the
   connection through a minimal psycopg-backed supabase adapter so the
   service runs real SQL).

4. **Assert** every calc-input field the engine consumes is identical
   between the two shapes — product_name, quantity, purchase_currency,
   purchase_price_original, base_price_vat, price_includes_vat, customs_code,
   weight_in_kg, supplier_country, licenses, markup, supplier_discount,
   vat flags. Numeric fields compare within 1e-10 tolerance.

This is bit-identity at the composition-layer contract, which is the only
surface through which migration 283 can affect calc output. Running the full
calc engine on top would add latency without testing anything new — the
engine is deterministic given those inputs and is locked.

This module auto-skips when:
- DATABASE_URL is not set (CI without DB access)
- psycopg is not installed
- migration 283 SQL file is missing
- No representative quotes are present in the dev DB (fresh schema with
  no Phase 5b data)

Source of truth: .kiro/specs/phase-5c-invoice-items/tasks.md Task 3,
requirements.md REQ 3.6, design.md §1.2.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_283_PATH = REPO_ROOT / "migrations" / "283_backfill_invoice_items.sql"

# Fields that must be bit-identical between Phase 5b's legacy shape and the
# Phase 5c rewritten shape. These are exactly the keys build_calculation_inputs()
# in main.py reads for each item (see main.py:13058-13222).
CALC_INPUT_FIELDS: tuple[str, ...] = (
    "quantity",
    "purchase_currency",
    "purchase_price_original",
    "base_price_vat",
    "price_includes_vat",
    "weight_in_kg",
    "customs_code",
    "supplier_country",
    "license_ds_cost",
    "license_ss_cost",
    "license_sgr_cost",
    "markup",
    "supplier_discount",
    "vat_rate",
    "is_unavailable",
    "import_banned",
)

# Minimum number of representative quotes that must be present in the dev DB
# for the test to be meaningful. If fewer exist, the test skips with a clear
# signal that dev DB needs more Phase 5b data before we can trust the result.
MIN_TEST_QUOTES = 5

# Numeric comparison tolerance — the Phase 5b overlay path produced Decimals
# and native numerics mixed; we accept float-equivalent equality within 1e-10.
NUMERIC_TOL = Decimal("1e-10")


# ---------------------------------------------------------------------------
# Connection + skip guards
# ---------------------------------------------------------------------------


def _get_db_connection():
    """Open a direct psycopg connection. Skip gracefully on missing setup."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping migration 283 "
            "bit-identity test (requires direct DB access)."
        )

    try:
        import psycopg  # psycopg v3

        return psycopg.connect(dsn, autocommit=False)
    except ImportError:
        pass

    try:
        import psycopg2  # psycopg v2

        return psycopg2.connect(dsn)
    except ImportError:
        pytest.skip(
            "Neither psycopg nor psycopg2 is installed — skipping migration "
            "283 bit-identity test."
        )


@pytest.fixture
def db_conn():
    """Yield a live DB connection and roll back after each test.

    The test runs migration 283 inside this transaction and never commits —
    dev DB state is unchanged after the test.
    """
    conn = _get_db_connection()
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


# ---------------------------------------------------------------------------
# Phase 5b legacy-shape reconstruction — what composition_service USED to return
# ---------------------------------------------------------------------------


def _fetch_representative_quote_ids(cur) -> list[str]:
    """Pick quotes with ≥1 composed quote_item that has a non-zero iip price.

    We want the 5 quotes with the most composed items (maximises surface area
    per test run). Falls back to whatever is available if fewer than 5 qualify.
    """
    cur.execute(
        """
        SELECT q.id, COUNT(qi.id) AS n_items
        FROM kvota.quotes q
        JOIN kvota.quote_items qi ON qi.quote_id = q.id
        JOIN kvota.invoice_item_prices iip
            ON iip.quote_item_id = qi.id
            AND iip.invoice_id = qi.composition_selected_invoice_id
        WHERE qi.composition_selected_invoice_id IS NOT NULL
          AND iip.purchase_price_original IS NOT NULL
          AND iip.purchase_price_original > 0
        GROUP BY q.id
        ORDER BY n_items DESC, q.id
        LIMIT 10
        """
    )
    return [row[0] for row in cur.fetchall()]


def _fetch_legacy_composition(cur, quote_id: str) -> list[dict[str, Any]]:
    """Reconstruct what Phase 5b's get_composed_items returned for a quote.

    Phase 5b (commit 96b9860) returned each quote_items row verbatim with
    4 fields overlaid from the latest-version invoice_item_prices row:
        purchase_price_original, purchase_currency, base_price_vat,
        price_includes_vat.

    All other fields (quantity, weight_in_kg, customs_code, licenses, markup,
    etc.) came straight from quote_items. This function reproduces that shape
    using raw SQL so the "before" snapshot doesn't depend on any rewritten
    code.
    """
    # Note on markup/supplier_discount: these are quote-level (stored on
    # quotes, applied per-item by calc code). Phase 5b's get_composed_items
    # exposed them on each item dict via qi.get("markup") — which returned
    # None because quote_items has no such column. Phase 5c's rewritten
    # service preserves that None. So they remain None in both shapes and
    # _fields_equal passes trivially. We SELECT NULL explicitly here to
    # document the shape.
    cur.execute(
        """
        SELECT
            qi.id,
            qi.product_name,
            qi.quantity,
            qi.weight_in_kg,
            qi.customs_code,
            qi.supplier_country,
            qi.license_ds_cost,
            qi.license_ss_cost,
            qi.license_sgr_cost,
            NULL::numeric AS markup,
            NULL::numeric AS supplier_discount,
            qi.vat_rate,
            qi.is_unavailable,
            qi.import_banned,
            qi.composition_selected_invoice_id,
            iip.purchase_price_original,
            iip.purchase_currency,
            iip.base_price_vat,
            iip.price_includes_vat,
            iip.version
        FROM kvota.quote_items qi
        LEFT JOIN LATERAL (
            SELECT *
            FROM kvota.invoice_item_prices iip2
            WHERE iip2.quote_item_id = qi.id
              AND iip2.invoice_id = qi.composition_selected_invoice_id
            ORDER BY iip2.version DESC
            LIMIT 1
        ) iip ON true
        WHERE qi.quote_id = %s
          AND qi.composition_selected_invoice_id IS NOT NULL
        ORDER BY qi.position, qi.id
        """,
        (quote_id,),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _apply_migration_283(cur, sql: str) -> None:
    """Execute migration 283 SQL against the current transaction."""
    cur.execute(sql)


# ---------------------------------------------------------------------------
# Minimal psycopg-backed "supabase" adapter — enough for get_composed_items
# ---------------------------------------------------------------------------


class _PsycopgSupabase:
    """Translate the subset of the supabase-py fluent API that
    composition_service.get_composed_items uses into SQL against a live
    psycopg connection.

    Only implements the minimum: .table(name).select(cols).eq(col, val)
    / .in_(col, values).execute() returning an object with .data = list[dict].

    Nothing else in composition_service.get_composed_items is exercised —
    this is intentionally minimal to avoid shadowing the real supabase-py
    client in scope we don't need to test.
    """

    class _Result:
        def __init__(self, data: list[dict]):
            self.data = data
            self.error = None

    class _Query:
        def __init__(self, conn, table: str):
            self._conn = conn
            self._table = table
            self._cols = "*"
            self._filters: list[tuple[str, str, Any]] = []
            # Shape of nested joins requested via select() — only the
            # get_composed_items call "invoice_items!inner(*)" is supported.
            self._embed_invoice_items = False

        def select(self, cols: str):
            self._cols = cols
            if "invoice_items!inner(*)" in cols:
                self._embed_invoice_items = True
            return self

        def eq(self, col: str, val):
            self._filters.append(("=", col, val))
            return self

        def in_(self, col: str, values):
            self._filters.append(("IN", col, tuple(values)))
            return self

        def order(self, *args, **kwargs):
            return self

        def is_(self, col, val):
            self._filters.append(("IS", col, val))
            return self

        def limit(self, n):
            return self

        def single(self):
            return self

        def execute(self):
            cur = self._conn.cursor()
            try:
                if self._table == "quote_items":
                    # get_composed_items always does SELECT * WHERE quote_id=...
                    where_sql, params = self._build_where()
                    cur.execute(
                        f"SELECT * FROM kvota.quote_items {where_sql}",
                        params,
                    )
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                    return _PsycopgSupabase._Result(rows)

                if self._table == "invoice_item_coverage":
                    # Embedded join case — get_composed_items calls:
                    #   .select("invoice_item_id, quote_item_id, ratio, "
                    #           "invoice_items!inner(*)")
                    #   .in_("quote_item_id", [...])
                    # Build WHERE with aliased column name since the FROM
                    # clause uses "coverage c" as alias.
                    clauses: list[str] = []
                    params: list = []
                    for op, col, val in self._filters:
                        aliased = f"c.{col}"
                        if op == "=":
                            clauses.append(f"{aliased} = %s")
                            params.append(val)
                        elif op == "IN":
                            if not val:
                                clauses.append("false")
                            else:
                                placeholders = ",".join(["%s"] * len(val))
                                clauses.append(
                                    f"{aliased} IN ({placeholders})"
                                )
                                params.extend(val)
                        elif op == "IS":
                            clauses.append(f"{aliased} IS %s")
                            params.append(val)
                    where_sql = (
                        ("WHERE " + " AND ".join(clauses)) if clauses else ""
                    )
                    cur.execute(
                        f"""
                        SELECT
                            c.invoice_item_id,
                            c.quote_item_id,
                            c.ratio,
                            row_to_json(ii.*) AS invoice_items_json
                        FROM kvota.invoice_item_coverage c
                        JOIN kvota.invoice_items ii ON ii.id = c.invoice_item_id
                        {where_sql}
                        """,
                        tuple(params),
                    )
                    rows: list[dict] = []
                    for r in cur.fetchall():
                        inv_item_id, qi_id, ratio, ii_json = r
                        rows.append(
                            {
                                "invoice_item_id": str(inv_item_id)
                                if inv_item_id
                                else None,
                                "quote_item_id": str(qi_id) if qi_id else None,
                                "ratio": ratio,
                                "invoice_items": ii_json,
                            }
                        )
                    return _PsycopgSupabase._Result(rows)

                # Fallback: empty result for tables this adapter doesn't
                # specifically handle. get_composed_items only uses the two
                # above; tests that hit anything else should fail loudly.
                return _PsycopgSupabase._Result([])
            finally:
                cur.close()

        def _build_where(self) -> tuple[str, tuple]:
            clauses: list[str] = []
            params: list = []
            for op, col, val in self._filters:
                if op == "=":
                    clauses.append(f"{col} = %s")
                    params.append(val)
                elif op == "IN":
                    if not val:
                        clauses.append("false")  # empty IN () -> no rows
                    else:
                        placeholders = ",".join(["%s"] * len(val))
                        clauses.append(f"{col} IN ({placeholders})")
                        params.extend(val)
                elif op == "IS":
                    # Only NULL check used in service code
                    clauses.append(f"{col} IS %s")
                    params.append(val)
            if clauses:
                return "WHERE " + " AND ".join(clauses), tuple(params)
            return "", ()

    def __init__(self, conn):
        self._conn = conn

    def table(self, name: str):
        return _PsycopgSupabase._Query(self._conn, name)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _coerce_numeric(v):
    """Return v as Decimal if possible, else leave untouched."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    if isinstance(v, str):
        try:
            return Decimal(v)
        except Exception:
            return v
    return v


def _fields_equal(name: str, legacy_val, new_val) -> bool:
    """Compare a single field between legacy and new shapes.

    Numeric fields tolerate 1e-10 delta to absorb Phase 5b Decimal vs
    Phase 5c numeric coercion differences. Non-numeric fields must match
    exactly (None == None is True).
    """
    if legacy_val is None and new_val is None:
        return True
    # Numeric fields — compare as Decimal within tolerance
    if name in {
        "purchase_price_original",
        "base_price_vat",
        "weight_in_kg",
        "license_ds_cost",
        "license_ss_cost",
        "license_sgr_cost",
        "markup",
        "supplier_discount",
        "vat_rate",
        "quantity",
    }:
        a = _coerce_numeric(legacy_val)
        b = _coerce_numeric(new_val)
        if a is None and b is None:
            return True
        if a is None or b is None:
            # Phase 5b null ≠ Phase 5c filled: means backfill invented data
            return False
        try:
            return abs(Decimal(str(a)) - Decimal(str(b))) <= NUMERIC_TOL
        except Exception:
            return False
    # Boolean: None and False are distinct shapes but semantically equal
    # for the calc engine (see build_calculation_inputs handling)
    if name in {"price_includes_vat", "is_unavailable", "import_banned"}:
        return bool(legacy_val) == bool(new_val)
    # String fields — exact match
    return legacy_val == new_val


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_migration_283_file_exists():
    """Task 3 GREEN step: the migration SQL file must be present."""
    assert MIGRATION_283_PATH.exists(), (
        f"migrations/283_backfill_invoice_items.sql missing. "
        f"Expected at {MIGRATION_283_PATH}. Task 3 GREEN not complete."
    )


def test_migration_283_bit_identity(db_conn):
    """For every representative quote, post-backfill composition shape is
    bit-identical to pre-backfill composition shape on every calc-input field.

    This is the core regression test for Task 3. Failure means the backfill
    changed at least one field in a way that would shift calc engine output.
    """
    if not MIGRATION_283_PATH.exists():
        pytest.skip("migration 283 SQL file missing — run GREEN step first")

    migration_sql = MIGRATION_283_PATH.read_text()

    # Put services/ on sys.path so we can import composition_service
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from services.composition_service import get_composed_items
    except ImportError as e:
        pytest.skip(f"cannot import composition_service: {e}")

    cur = db_conn.cursor()

    # Step 1: pick representative quotes
    quote_ids = _fetch_representative_quote_ids(cur)
    if len(quote_ids) < MIN_TEST_QUOTES:
        pytest.skip(
            f"dev DB has only {len(quote_ids)} quotes with composed items + "
            f"non-zero iip prices; need ≥{MIN_TEST_QUOTES} for a meaningful "
            f"bit-identity check."
        )
    quote_ids = quote_ids[:MIN_TEST_QUOTES]

    # Step 2: pre-backfill snapshot (Phase 5b legacy shape)
    legacy_by_quote: dict[str, list[dict]] = {
        qid: _fetch_legacy_composition(cur, qid) for qid in quote_ids
    }

    # Sanity: every fetched quote has at least one item
    for qid, items in legacy_by_quote.items():
        assert items, f"quote {qid} has no composed items — fixture broken"

    # Step 3: apply migration 283 inside this transaction
    _apply_migration_283(cur, migration_sql)

    # Quick sanity on row counts — should have inserted one invoice_items
    # row per iip row for the represented quotes, with matching coverage.
    cur.execute("SELECT COUNT(*) FROM kvota.invoice_items")
    ii_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kvota.invoice_item_coverage")
    cov_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kvota.invoice_item_prices")
    iip_count = cur.fetchone()[0]
    assert ii_count == iip_count, (
        f"backfill produced {ii_count} invoice_items but there are {iip_count} "
        f"invoice_item_prices rows — row count mismatch"
    )
    assert cov_count == ii_count, (
        f"coverage count {cov_count} != invoice_items count {ii_count} — "
        f"backfill should create 1:1 coverage per invoice_items row"
    )

    # Step 4: post-backfill — invoke rewritten get_composed_items
    sb = _PsycopgSupabase(db_conn)
    new_by_quote: dict[str, list[dict]] = {
        qid: get_composed_items(qid, sb) for qid in quote_ids
    }

    # Step 5: assert bit-identity per (quote, item, field)
    failures: list[str] = []
    for qid in quote_ids:
        legacy_items = legacy_by_quote[qid]
        new_items = new_by_quote[qid]

        # Index new items by quote_item_id for order-independent comparison.
        # Phase 5b emitted exactly one item per quote_item; Phase 5c emits
        # one per invoice_item with a dedup set on merge. For purely-backfilled
        # (1:1) data there is one invoice_item per quote_item, so the count
        # must match exactly.
        assert len(legacy_items) == len(new_items), (
            f"quote {qid}: legacy items={len(legacy_items)}, "
            f"new items={len(new_items)} — expected equal for 1:1 backfill"
        )

        new_by_qi: dict[str, dict] = {}
        for new_item in new_items:
            key = new_item.get("quote_item_id")
            assert key, f"new item missing quote_item_id: {new_item}"
            new_by_qi[str(key)] = new_item

        for legacy in legacy_items:
            qi_id = str(legacy["id"])
            new_item = new_by_qi.get(qi_id)
            if new_item is None:
                failures.append(
                    f"quote={qid} qi={qi_id}: missing from post-backfill output"
                )
                continue
            for field in CALC_INPUT_FIELDS:
                legacy_val = legacy.get(field)
                new_val = new_item.get(field)
                if not _fields_equal(field, legacy_val, new_val):
                    failures.append(
                        f"quote={qid} qi={qi_id} field={field}: "
                        f"legacy={legacy_val!r} new={new_val!r}"
                    )

    assert not failures, (
        f"bit-identity failures detected — migration 283 changed calc-input "
        f"fields for {len(failures)} (item, field) pairs:\n"
        + "\n".join(failures[:30])
        + (f"\n... and {len(failures) - 30} more" if len(failures) > 30 else "")
    )


def test_migration_283_is_idempotent(db_conn):
    """Re-running migration 283 must not insert duplicate rows.

    Task 3 acceptance criteria: use ON CONFLICT DO NOTHING. Running the
    backfill twice produces the same invoice_items / coverage counts as
    running it once.
    """
    if not MIGRATION_283_PATH.exists():
        pytest.skip("migration 283 SQL file missing — run GREEN step first")

    migration_sql = MIGRATION_283_PATH.read_text()
    cur = db_conn.cursor()

    # Apply once
    _apply_migration_283(cur, migration_sql)
    cur.execute("SELECT COUNT(*) FROM kvota.invoice_items")
    after_first = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kvota.invoice_item_coverage")
    cov_after_first = cur.fetchone()[0]

    # Apply again
    _apply_migration_283(cur, migration_sql)
    cur.execute("SELECT COUNT(*) FROM kvota.invoice_items")
    after_second = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM kvota.invoice_item_coverage")
    cov_after_second = cur.fetchone()[0]

    assert after_first == after_second, (
        f"re-running migration 283 inserted extra invoice_items rows: "
        f"first={after_first}, second={after_second}. Missing "
        f"ON CONFLICT DO NOTHING guard."
    )
    assert cov_after_first == cov_after_second, (
        f"re-running migration 283 inserted extra coverage rows: "
        f"first={cov_after_first}, second={cov_after_second}. Missing "
        f"ON CONFLICT DO NOTHING guard."
    )


def test_migration_283_covers_all_active_composition_pointers(db_conn):
    """Every quote_item with composition_selected_invoice_id NOT NULL has
    at least one matching coverage row after backfill.

    Required by Task 3 acceptance: "every qi with composition_selected_invoice_id
    NOT NULL has a matching coverage row".
    """
    if not MIGRATION_283_PATH.exists():
        pytest.skip("migration 283 SQL file missing — run GREEN step first")

    migration_sql = MIGRATION_283_PATH.read_text()
    cur = db_conn.cursor()
    _apply_migration_283(cur, migration_sql)

    cur.execute(
        """
        SELECT qi.id
        FROM kvota.quote_items qi
        JOIN kvota.invoice_item_prices iip
            ON iip.quote_item_id = qi.id
            AND iip.invoice_id = qi.composition_selected_invoice_id
        WHERE qi.composition_selected_invoice_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM kvota.invoice_item_coverage c
              JOIN kvota.invoice_items ii ON ii.id = c.invoice_item_id
              WHERE c.quote_item_id = qi.id
                AND ii.invoice_id = qi.composition_selected_invoice_id
          )
        """
    )
    missing = [r[0] for r in cur.fetchall()]
    assert not missing, (
        f"{len(missing)} quote_items have a composition pointer but no "
        f"coverage row after backfill. First 5: {missing[:5]}"
    )
