"""
Tests for Invoice-Level Logistics Auto-Assignment (TDD)

Tests for the assign_logistics_to_invoices() function that automatically assigns
logistics managers to each procurement invoice based on pickup_country,
using route_logistics_assignments routing rules.

The function:
- Fetches quote (organization_id, delivery_city) and all invoices (id, pickup_country)
- For each invoice with pickup_country, calls get_logistics_manager_for_locations()
- Updates each invoice's assigned_logistics_user column
- Uses Counter for majority vote across invoices -> sets quotes.assigned_logistics_user
- Returns dict: {success, assigned_invoices, unmatched_invoice_ids, quote_level_user_id, error_message}
- Wired into complete_procurement() as best-effort try/except
"""

import os
import sys
from typing import Any, Callable, Optional
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# TDD import guard: function doesn't exist yet
_IMPORT_ERROR = None
try:
    from services.workflow_service import assign_logistics_to_invoices
except ImportError as e:
    _IMPORT_ERROR = str(e)
    assign_logistics_to_invoices = None

from services.workflow_service import WorkflowStatus, complete_procurement


def _require_function():
    """Fail with a clear message if assign_logistics_to_invoices is not yet implemented."""
    if assign_logistics_to_invoices is None:
        pytest.fail(
            f"assign_logistics_to_invoices not yet implemented (ImportError: {_IMPORT_ERROR}). "
            "This is expected for TDD — implement the function to make this test pass."
        )


# =============================================================================
# HELPERS
# =============================================================================

def _make_uuid(suffix=""):
    """Generate a deterministic UUID-like string for test readability."""
    import uuid
    if suffix:
        return f"00000000-0000-0000-0000-{suffix.zfill(12)}"
    return str(uuid.uuid4())


QUOTE_ID = _make_uuid("quote001")
ORG_ID = _make_uuid("org00001")
MANAGER_A = _make_uuid("managera")
MANAGER_B = _make_uuid("managerb")
INVOICE_1 = _make_uuid("invoice1")
INVOICE_2 = _make_uuid("invoice2")
INVOICE_3 = _make_uuid("invoice3")


# =============================================================================
# IN-MEMORY FAKE SUPABASE CLIENT
#
# Purpose: replace unittest.mock.MagicMock chains with a deterministic
# fluent-API stub. MagicMock's chain resolution changed between Python
# 3.12 and 3.14 — when a caller walks a sub-set of a pre-configured chain,
# 3.12 returns a fresh Mock instead of the configured .data, which was
# silently masked by MagicMock's permissive attribute access and caused
# 14/16 tests to fail on CI only. This fake implements exactly the fluent
# subset workflow_service.assign_logistics_to_invoices() + complete_procurement()
# exercise, stores call data, and is completely Python-version-agnostic.
# =============================================================================


class _Response:
    """Mimic the ``.data``/``.error`` shape returned by supabase-py."""

    def __init__(self, data: Any):
        self.data = data
        self.error = None


class _Query:
    """Chainable query builder translating fluent calls into filtered reads
    or tracked writes against the parent FakeSupabase's in-memory state."""

    def __init__(self, client: "FakeSupabase", table: str):
        self._client = client
        self._table = table
        self._mode: Optional[str] = None  # "select" | "update" | "insert"
        self._update_payload: Any = None
        self._insert_payload: Any = None
        self._filters: list[tuple[str, str, Any]] = []
        self._single = False

    # --- query builders ---
    def select(self, cols: str = "*") -> "_Query":
        self._mode = "select"
        return self

    def update(self, payload: dict) -> "_Query":
        self._mode = "update"
        self._update_payload = payload
        return self

    def insert(self, payload: Any) -> "_Query":
        self._mode = "insert"
        self._insert_payload = payload
        return self

    def eq(self, col: str, val: Any) -> "_Query":
        self._filters.append(("=", col, val))
        return self

    def in_(self, col: str, values: list) -> "_Query":
        self._filters.append(("IN", col, tuple(values)))
        return self

    def is_(self, col: str, val: Any) -> "_Query":
        self._filters.append(("IS", col, val))
        return self

    def order(self, *args, **kwargs) -> "_Query":
        return self

    def limit(self, n: int) -> "_Query":
        return self

    def single(self) -> "_Query":
        self._single = True
        return self

    # --- terminal ---
    def execute(self) -> _Response:
        if self._mode == "select":
            return self._execute_select()
        if self._mode == "update":
            return self._execute_update()
        if self._mode == "insert":
            return self._execute_insert()
        raise RuntimeError(f"Query on {self._table} terminated without a mode")

    # --- internal ---
    def _matches(self, row: dict) -> bool:
        for op, col, val in self._filters:
            cell = row.get(col)
            if op == "=" and cell != val:
                return False
            if op == "IN" and cell not in val:
                return False
            if op == "IS" and cell is not val:
                return False
        return True

    def _execute_select(self) -> _Response:
        rows = [r for r in self._client._rows(self._table) if self._matches(r)]

        # Allow tests to override the reader entirely for a given table (used
        # for embedded joins like invoice_item_coverage → invoice_items!inner).
        override = self._client._select_overrides.get(self._table)
        if override is not None:
            rows = override(self._filters)

        if self._single:
            if not rows:
                # supabase-py raises on single() with zero rows; mirror that
                # so the tested code path hits its except branch.
                raise RuntimeError(f"No rows found in {self._table} for .single()")
            return _Response(rows[0])
        return _Response(rows)

    def _execute_update(self) -> _Response:
        rows = self._client._rows(self._table)
        updated = []
        for row in rows:
            if self._matches(row):
                row.update(self._update_payload)
                updated.append(row)
        self._client._updates.append(
            (self._table, dict(self._update_payload), list(self._filters))
        )
        return _Response([{"id": r.get("id")} for r in updated] or [{"id": "updated"}])

    def _execute_insert(self) -> _Response:
        payload = self._insert_payload
        if isinstance(payload, dict):
            payload = [payload]
        inserted = []
        for record in payload:
            record = dict(record)
            record.setdefault("id", _make_uuid())
            self._client._rows(self._table).append(record)
            inserted.append(record)
        self._client._inserts.append((self._table, [dict(r) for r in inserted]))
        return _Response(inserted)


class FakeSupabase:
    """Minimal in-memory Supabase client supporting the fluent subset used
    by workflow_service.assign_logistics_to_invoices() and complete_procurement()."""

    def __init__(self):
        self._tables: dict[str, list[dict]] = {}
        self._select_overrides: dict[str, Callable[[list], list[dict]]] = {}
        self._updates: list[tuple[str, dict, list]] = []
        self._inserts: list[tuple[str, list[dict]]] = []

    # --- data seeding ---
    def seed(self, table: str, rows: list[dict]) -> None:
        """Replace ``table``'s rows with ``rows`` (deep-copied)."""
        self._tables[table] = [dict(r) for r in rows]

    def set_select_override(
        self, table: str, handler: Callable[[list], list[dict]]
    ) -> None:
        """Override SELECT results for ``table`` with a custom handler.

        Useful for tables whose query includes an embedded join (e.g.
        ``invoice_item_coverage`` selecting ``invoice_items!inner(...)``)
        where the row shape differs from the raw seeded rows.
        """
        self._select_overrides[table] = handler

    def _rows(self, table: str) -> list[dict]:
        return self._tables.setdefault(table, [])

    # --- fluent entry point ---
    def table(self, name: str) -> _Query:
        return _Query(self, name)

    # --- test introspection ---
    def updates_for(self, table: str) -> list[tuple[dict, list]]:
        """Return (payload, filters) tuples for every UPDATE on ``table``."""
        return [(p, f) for (t, p, f) in self._updates if t == table]

    def inserts_for(self, table: str) -> list[list[dict]]:
        """Return one list of inserted records per INSERT call on ``table``."""
        return [records for (t, records) in self._inserts if t == table]


def _make_fake(
    quote_data: Optional[dict] = None,
    invoices_data: Optional[list[dict]] = None,
) -> FakeSupabase:
    """Seed a FakeSupabase with the rows assign_logistics_to_invoices reads.

    Preserves the public contract of the original helper (quote_data and
    invoices_data parameters) so call sites don't change.
    """
    sb = FakeSupabase()
    if quote_data is not None:
        sb.seed("quotes", [quote_data])
    if invoices_data is not None:
        # Each invoice row needs a quote_id link for the .eq("quote_id", ...) filter.
        sb.seed(
            "invoices",
            [{**inv, "quote_id": (quote_data or {}).get("id", QUOTE_ID)} for inv in invoices_data],
        )
    return sb


# Keep the old name exported for any out-of-tree callers still importing it.
# The signature matches; only the return type changes from MagicMock to FakeSupabase.
_mock_supabase_for_assignment = _make_fake


# =============================================================================
# UNIT TESTS: assign_logistics_to_invoices()
# =============================================================================

class TestAssignLogisticsToInvoices:
    """Unit tests for the assign_logistics_to_invoices function."""

    def setup_method(self):
        """Each test requires the function to exist; fail clearly if not."""
        _require_function()

    # -------------------------------------------------------------------------
    # Test 1: Happy path — single country
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.route_logistics_assignment_service.get_logistics_manager_for_locations"
    )
    def test_single_country_both_invoices_assigned(
        self, mock_get_logistics, mock_get_sb
    ):
        """Two invoices both with pickup_country='Китай' → both get same manager, quote gets that manager."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": "Китай"},
                {"id": INVOICE_2, "pickup_country": "Китай"},
            ],
        )
        mock_get_sb.return_value = sb
        mock_get_logistics.return_value = MANAGER_A

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True
        assert result["error_message"] is None
        assert len(result["assigned_invoices"]) == 2
        assert all(
            inv["user_id"] == MANAGER_A for inv in result["assigned_invoices"]
        )
        assert result["quote_level_user_id"] == MANAGER_A
        assert result["unmatched_invoice_ids"] == []

    # -------------------------------------------------------------------------
    # Test 2: Happy path — multi-country (majority vote)
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.route_logistics_assignment_service.get_logistics_manager_for_locations"
    )
    def test_multi_country_majority_vote(self, mock_get_logistics, mock_get_sb):
        """2 invoices 'Китай' (→A) + 1 invoice 'Турция' (→B) → quote gets A (majority)."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": "Китай"},
                {"id": INVOICE_2, "pickup_country": "Китай"},
                {"id": INVOICE_3, "pickup_country": "Турция"},
            ],
        )
        mock_get_sb.return_value = sb

        def side_effect(org_id, origin, dest):
            if origin == "Китай":
                return MANAGER_A
            elif origin == "Турция":
                return MANAGER_B
            return None

        mock_get_logistics.side_effect = side_effect

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True
        assert len(result["assigned_invoices"]) == 3

        # Each invoice got its correct manager
        china_invoices = [
            inv for inv in result["assigned_invoices"] if inv["pickup_country"] == "Китай"
        ]
        turkey_invoices = [
            inv for inv in result["assigned_invoices"] if inv["pickup_country"] == "Турция"
        ]
        assert len(china_invoices) == 2
        assert all(inv["user_id"] == MANAGER_A for inv in china_invoices)
        assert len(turkey_invoices) == 1
        assert turkey_invoices[0]["user_id"] == MANAGER_B

        # Quote gets majority winner (A has 2 vs B has 1)
        assert result["quote_level_user_id"] == MANAGER_A

    # -------------------------------------------------------------------------
    # Test 3: No invoices
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    def test_no_invoices(self, mock_get_sb):
        """Quote has zero invoices → success=True, empty lists, no assignment."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[],
        )
        mock_get_sb.return_value = sb

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_invoices"] == []
        assert result["unmatched_invoice_ids"] == []
        assert result["quote_level_user_id"] is None

    # -------------------------------------------------------------------------
    # Test 4: Invoices with no pickup_country
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    def test_invoices_no_pickup_country(self, mock_get_sb):
        """All invoices have NULL pickup_country → all in unmatched_invoice_ids."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": None},
                {"id": INVOICE_2, "pickup_country": None},
            ],
        )
        mock_get_sb.return_value = sb

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_invoices"] == []
        assert set(result["unmatched_invoice_ids"]) == {INVOICE_1, INVOICE_2}
        assert result["quote_level_user_id"] is None

    # -------------------------------------------------------------------------
    # Test 5: No matching route pattern
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.route_logistics_assignment_service.get_logistics_manager_for_locations"
    )
    def test_no_matching_route_pattern(self, mock_get_logistics, mock_get_sb):
        """pickup_country='Австралия' with no route → unmatched."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": "Австралия"},
            ],
        )
        mock_get_sb.return_value = sb
        mock_get_logistics.return_value = None  # No match

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_invoices"] == []
        assert INVOICE_1 in result["unmatched_invoice_ids"]
        assert result["quote_level_user_id"] is None

    # -------------------------------------------------------------------------
    # Test 6: No delivery_city on quote
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.route_logistics_assignment_service.get_logistics_manager_for_locations"
    )
    def test_no_delivery_city_on_quote(self, mock_get_logistics, mock_get_sb):
        """delivery_city=None → routing still works (wildcard patterns match)."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": None,
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": "Китай"},
            ],
        )
        mock_get_sb.return_value = sb
        mock_get_logistics.return_value = MANAGER_A

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True
        assert len(result["assigned_invoices"]) == 1
        assert result["assigned_invoices"][0]["user_id"] == MANAGER_A

        # Verify get_logistics_manager_for_locations was called with None delivery_city
        mock_get_logistics.assert_called_once_with(ORG_ID, "Китай", None)

    # -------------------------------------------------------------------------
    # Test 7: Routing service raises exception
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.route_logistics_assignment_service.get_logistics_manager_for_locations"
    )
    def test_routing_service_exception(self, mock_get_logistics, mock_get_sb):
        """get_logistics_manager_for_locations throws → success=False, error_message set."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": "Китай"},
            ],
        )
        mock_get_sb.return_value = sb
        mock_get_logistics.side_effect = Exception("DB connection failed")

        result = assign_logistics_to_invoices(QUOTE_ID)

        # The outer try/except in the function should catch this
        assert result["success"] is False
        assert result["error_message"] is not None
        assert "DB connection failed" in result["error_message"]

    # -------------------------------------------------------------------------
    # Test 8: Quote not found
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    def test_quote_not_found(self, mock_get_sb):
        """Bad quote_id → success=False."""
        sb = _make_fake(quote_data=None, invoices_data=None)
        mock_get_sb.return_value = sb

        result = assign_logistics_to_invoices("nonexistent-id")

        assert result["success"] is False
        assert "not found" in result["error_message"].lower()

    # -------------------------------------------------------------------------
    # Test 9: Quote missing organization_id
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.route_logistics_assignment_service.get_logistics_manager_for_locations"
    )
    def test_quote_missing_organization_id(self, mock_get_logistics, mock_get_sb):
        """Quote with organization_id=None → routing receives None org_id, may not match."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": None,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": "Китай"},
            ],
        )
        mock_get_sb.return_value = sb
        # With None org_id, routing returns None
        mock_get_logistics.return_value = None

        result = assign_logistics_to_invoices(QUOTE_ID)

        # Should still succeed, but invoice is unmatched
        assert result["success"] is True
        assert INVOICE_1 in result["unmatched_invoice_ids"]
        assert result["quote_level_user_id"] is None

    # -------------------------------------------------------------------------
    # Test 10: DB update verification
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.route_logistics_assignment_service.get_logistics_manager_for_locations"
    )
    def test_db_update_calls(self, mock_get_logistics, mock_get_sb):
        """Verify supabase.table('invoices').update() called with correct user_id for each invoice."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": "Китай"},
                {"id": INVOICE_2, "pickup_country": "Турция"},
            ],
        )
        mock_get_sb.return_value = sb

        def logistics_lookup(org_id, origin, dest):
            if origin == "Китай":
                return MANAGER_A
            elif origin == "Турция":
                return MANAGER_B
            return None

        mock_get_logistics.side_effect = logistics_lookup

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True

        # Verify invoice updates — one update per distinct user_id (batch by .in_())
        invoice_updates = sb.updates_for("invoices")
        assert len(invoice_updates) == 2

        update_user_ids = {p["assigned_logistics_user"] for (p, _f) in invoice_updates}
        assert MANAGER_A in update_user_ids
        assert MANAGER_B in update_user_ids

        # Verify quote-level update (majority = MANAGER_A if tied, or whichever is more common)
        quote_updates = sb.updates_for("quotes")
        assert len(quote_updates) >= 1

    # -------------------------------------------------------------------------
    # Test 11: Return dict shape
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    def test_return_dict_shape(self, mock_get_sb):
        """Verify all keys present and correct types in return dict."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[],
        )
        mock_get_sb.return_value = sb

        result = assign_logistics_to_invoices(QUOTE_ID)

        # Verify all required keys exist
        assert "success" in result
        assert "assigned_invoices" in result
        assert "unmatched_invoice_ids" in result
        assert "quote_level_user_id" in result
        assert "error_message" in result

        # Verify types
        assert isinstance(result["success"], bool)
        assert isinstance(result["assigned_invoices"], list)
        assert isinstance(result["unmatched_invoice_ids"], list)
        # quote_level_user_id can be str or None
        assert result["quote_level_user_id"] is None or isinstance(
            result["quote_level_user_id"], str
        )
        # error_message can be str or None
        assert result["error_message"] is None or isinstance(
            result["error_message"], str
        )

    # -------------------------------------------------------------------------
    # Test 12: Mixed — some invoices have pickup_country, some don't
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.route_logistics_assignment_service.get_logistics_manager_for_locations"
    )
    def test_mixed_invoices(self, mock_get_logistics, mock_get_sb):
        """Some invoices have pickup_country, some don't → only those with country get assigned."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": "Китай"},
                {"id": INVOICE_2, "pickup_country": None},
                {"id": INVOICE_3, "pickup_country": "Китай"},
            ],
        )
        mock_get_sb.return_value = sb
        mock_get_logistics.return_value = MANAGER_A

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True
        assert len(result["assigned_invoices"]) == 2
        assert INVOICE_2 in result["unmatched_invoice_ids"]
        assert result["quote_level_user_id"] == MANAGER_A

    # -------------------------------------------------------------------------
    # Test 12b: Empty string pickup_country treated as None
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    def test_empty_string_pickup_country(self, mock_get_sb):
        """Invoice with pickup_country='' (empty string) should be treated as unmatched."""
        sb = _make_fake(
            quote_data={
                "id": QUOTE_ID,
                "organization_id": ORG_ID,
                "delivery_city": "Москва",
            },
            invoices_data=[
                {"id": INVOICE_1, "pickup_country": ""},
                {"id": INVOICE_2, "pickup_country": "  "},
            ],
        )
        mock_get_sb.return_value = sb

        result = assign_logistics_to_invoices(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_invoices"] == []
        assert set(result["unmatched_invoice_ids"]) == {INVOICE_1, INVOICE_2}


# =============================================================================
# INTEGRATION TESTS: complete_procurement() wiring
# =============================================================================

class TestCompleteProcurementLogisticsWiring:
    """Integration tests: complete_procurement calls assign_logistics_to_invoices."""

    def _setup_successful_procurement_mocks(self, sb: FakeSupabase):
        """Seed FakeSupabase for a successful complete_procurement call.

        Covers the full Phase 5d readiness flow:
          1. quotes.select(...).eq("id", quote_id).single().execute() — status check
          2. composition_service.is_procurement_complete:
               a) quote_items.select(id, is_unavailable,
                  composition_selected_invoice_id).eq().execute()
               b) invoice_item_coverage.select(..., invoice_items!inner(...))
                  .in_().execute() — coverage row must reference invoice_items
                  with the selected invoice_id and non-null
                  purchase_price_original so readiness returns True.
          3. quotes.update().eq().execute() — transition write
          4. workflow_transitions.insert().execute() — audit log
        """
        qi_id = "qi-1"
        selected_invoice_id = INVOICE_1

        sb.seed(
            "quotes",
            [
                {
                    "id": QUOTE_ID,
                    "workflow_status": WorkflowStatus.PENDING_PROCUREMENT.value,
                    "procurement_completed_at": None,
                }
            ],
        )
        sb.seed(
            "quote_items",
            [
                {
                    "id": qi_id,
                    "quote_id": QUOTE_ID,
                    "is_unavailable": False,
                    "composition_selected_invoice_id": selected_invoice_id,
                }
            ],
        )
        # The invoice_item_coverage query has an embedded join
        # "invoice_items!inner(invoice_id, purchase_price_original)" that our
        # generic select handler can't resolve by itself. Override it to
        # return the join-shaped row readiness expects.
        def coverage_select(_filters):
            return [
                {
                    "quote_item_id": qi_id,
                    "invoice_items": {
                        "invoice_id": selected_invoice_id,
                        "purchase_price_original": 100.0,
                    },
                }
            ]

        sb.set_select_override("invoice_item_coverage", coverage_select)

    # -------------------------------------------------------------------------
    # Test 13: complete_procurement calls assign_logistics_to_invoices
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.workflow_service.assign_logistics_to_invoices",
        create=True,
    )
    def test_complete_procurement_calls_assign_logistics(
        self, mock_assign_logistics, mock_get_sb
    ):
        """complete_procurement calls assign_logistics_to_invoices after status transition."""
        sb = FakeSupabase()
        mock_get_sb.return_value = sb
        self._setup_successful_procurement_mocks(sb)

        mock_assign_logistics.return_value = {
            "success": True,
            "assigned_invoices": [],
            "unmatched_invoice_ids": [],
            "quote_level_user_id": None,
            "error_message": None,
        }

        result = complete_procurement(
            quote_id=QUOTE_ID,
            actor_id=_make_uuid("actor001"),
            actor_roles=["procurement"],
        )

        # Procurement should succeed
        assert result.success is True
        assert result.to_status == WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value

        # assign_logistics_to_invoices should have been called
        mock_assign_logistics.assert_called_once_with(QUOTE_ID)

    # -------------------------------------------------------------------------
    # Test 14: complete_procurement succeeds even if assign_logistics raises
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.workflow_service.assign_logistics_to_invoices",
        create=True,
    )
    def test_complete_procurement_survives_assignment_exception(
        self, mock_assign_logistics, mock_get_sb
    ):
        """complete_procurement succeeds even if assign_logistics_to_invoices raises."""
        sb = FakeSupabase()
        mock_get_sb.return_value = sb
        self._setup_successful_procurement_mocks(sb)

        mock_assign_logistics.side_effect = Exception("Logistics routing DB down")

        result = complete_procurement(
            quote_id=QUOTE_ID,
            actor_id=_make_uuid("actor001"),
            actor_roles=["procurement"],
        )

        # Procurement should still succeed (logistics assignment is best-effort)
        assert result.success is True
        assert result.to_status == WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value

        # The function must have been called (wiring exists) even though it raised
        mock_assign_logistics.assert_called_once_with(QUOTE_ID)

    # -------------------------------------------------------------------------
    # Test 15: complete_procurement succeeds when assignment returns failure
    # -------------------------------------------------------------------------
    @patch("services.workflow_service.get_supabase")
    @patch(
        "services.workflow_service.assign_logistics_to_invoices",
        create=True,
    )
    def test_complete_procurement_ok_when_assignment_fails(
        self, mock_assign_logistics, mock_get_sb
    ):
        """complete_procurement succeeds when assignment returns success=False."""
        sb = FakeSupabase()
        mock_get_sb.return_value = sb
        self._setup_successful_procurement_mocks(sb)

        mock_assign_logistics.return_value = {
            "success": False,
            "assigned_invoices": [],
            "unmatched_invoice_ids": [INVOICE_1],
            "quote_level_user_id": None,
            "error_message": "No routes configured",
        }

        result = complete_procurement(
            quote_id=QUOTE_ID,
            actor_id=_make_uuid("actor001"),
            actor_roles=["procurement"],
        )

        # Procurement should still succeed
        assert result.success is True
        assert result.to_status == WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value

        # The function must have been called (wiring exists)
        mock_assign_logistics.assert_called_once_with(QUOTE_ID)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
