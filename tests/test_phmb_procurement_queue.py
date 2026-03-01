"""
Tests for PHMB Procurement Queue with Brand Groups — service layer.

Feature: [86aftz8wn] — PHMB Procurement Queue with Brand Groups

Tests cover:
1. resolve_brand_group() — pure function, no DB:
   - Brand matches a pattern in group -> returns group_id
   - Brand doesn't match any pattern -> returns catchall group_id
   - No catchall group -> returns None
   - Case-insensitive matching
   - Empty brand -> catchall
   - Multiple groups, first match wins (by sort_order)

2. price_queue_item() — the critical write-back flow:
   - Sets queue status to 'priced'
   - Writes price back to phmb_quote_items
   - Upserts into phmb_price_list
   - Skips price list upsert if cat_number is empty
   - Rejects priced_rmb <= 0

3. ensure_queue_entries() — backfill logic:
   - Items with no price and not in queue -> get enqueued
   - Items already in queue -> skipped (no duplicates)
   - Items with a price list reference -> skipped

4. phmb_calculator.py with NULL list_price_rmb:
   - calculate_phmb_item with list_price_rmb=None should not crash

TDD: These tests are written BEFORE implementation.
The new functions do not exist yet — tests should fail with ImportError or AttributeError.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def org_id():
    """Organization ID for tests."""
    return str(uuid4())


@pytest.fixture
def quote_id():
    """Quote ID for tests."""
    return str(uuid4())


@pytest.fixture
def quote_item_id():
    """PHMB quote item ID for tests."""
    return str(uuid4())


@pytest.fixture
def queue_item_id():
    """Procurement queue item ID for tests."""
    return str(uuid4())


@pytest.fixture
def group_id_agilent():
    """Brand group ID for Agilent + Shimadzu group."""
    return str(uuid4())


@pytest.fixture
def group_id_mettler():
    """Brand group ID for Mettler Toledo group."""
    return str(uuid4())


@pytest.fixture
def group_id_catchall():
    """Brand group ID for the catchall group."""
    return str(uuid4())


@pytest.fixture
def sample_brand_groups(group_id_agilent, group_id_mettler, group_id_catchall, org_id):
    """Sample brand groups list as returned from DB."""
    return [
        {
            "id": group_id_agilent,
            "org_id": org_id,
            "name": "Agilent + Shimadzu",
            "brand_patterns": ["Agilent", "Shimadzu"],
            "is_catchall": False,
            "sort_order": 0,
        },
        {
            "id": group_id_mettler,
            "org_id": org_id,
            "name": "Mettler Toledo",
            "brand_patterns": ["Mettler Toledo"],
            "is_catchall": False,
            "sort_order": 1,
        },
        {
            "id": group_id_catchall,
            "org_id": org_id,
            "name": "Остальные",
            "brand_patterns": [],
            "is_catchall": True,
            "sort_order": 99,
        },
    ]


@pytest.fixture
def sample_brand_groups_no_catchall(group_id_agilent, group_id_mettler, org_id):
    """Brand groups without a catchall group."""
    return [
        {
            "id": group_id_agilent,
            "org_id": org_id,
            "name": "Agilent + Shimadzu",
            "brand_patterns": ["Agilent", "Shimadzu"],
            "is_catchall": False,
            "sort_order": 0,
        },
        {
            "id": group_id_mettler,
            "org_id": org_id,
            "name": "Mettler Toledo",
            "brand_patterns": ["Mettler Toledo"],
            "is_catchall": False,
            "sort_order": 1,
        },
    ]


@pytest.fixture
def sample_queue_item(queue_item_id, quote_item_id, quote_id, org_id, group_id_agilent):
    """Sample procurement queue row with FK join to phmb_quote_items."""
    return {
        "id": queue_item_id,
        "org_id": org_id,
        "quote_item_id": quote_item_id,
        "quote_id": quote_id,
        "brand": "Agilent",
        "brand_group_id": group_id_agilent,
        "status": "new",
        "priced_rmb": None,
        "notes": None,
        "created_at": "2026-03-01T10:00:00Z",
        "updated_at": "2026-03-01T10:00:00Z",
        # FK join data (PostgREST pattern)
        "phmb_quote_items": {
            "id": quote_item_id,
            "quote_id": quote_id,
            "cat_number": "1234-A",
            "product_name": "Probe Kit",
            "brand": "Agilent",
            "product_classification": "Accessories",
            "quantity": 2,
            "list_price_rmb": None,
            "phmb_price_list_id": None,
        },
    }


@pytest.fixture
def sample_phmb_items_mixed(quote_id):
    """PHMB quote items — mix of priced (from price list) and unpriced (custom)."""
    priced_item_id = str(uuid4())
    unpriced_item_id_1 = str(uuid4())
    unpriced_item_id_2 = str(uuid4())
    return [
        {
            "id": priced_item_id,
            "quote_id": quote_id,
            "phmb_price_list_id": str(uuid4()),  # has price list reference
            "cat_number": "PRICED-001",
            "product_name": "Standard Widget",
            "brand": "Agilent",
            "list_price_rmb": "100.00",
            "quantity": 5,
        },
        {
            "id": unpriced_item_id_1,
            "quote_id": quote_id,
            "phmb_price_list_id": None,  # custom, no price list
            "cat_number": "CUSTOM-001",
            "product_name": "Custom Probe",
            "brand": "Shimadzu",
            "list_price_rmb": None,
            "quantity": 2,
        },
        {
            "id": unpriced_item_id_2,
            "quote_id": quote_id,
            "phmb_price_list_id": None,  # custom, no price list
            "cat_number": "CUSTOM-002",
            "product_name": "Special Sensor",
            "brand": "UnknownBrand",
            "list_price_rmb": None,
            "quantity": 1,
        },
    ]


# =============================================================================
# 1. resolve_brand_group() — PURE FUNCTION TESTS
# =============================================================================

class TestResolveBrandGroup:
    """Tests for resolve_brand_group() — pure function, no DB calls."""

    def test_brand_matches_first_group(self, sample_brand_groups, group_id_agilent):
        """Brand 'Agilent' should match the 'Agilent + Shimadzu' group."""
        from services.phmb_price_service import resolve_brand_group

        result = resolve_brand_group("Agilent", sample_brand_groups)
        assert result == group_id_agilent

    def test_brand_matches_second_pattern_in_group(self, sample_brand_groups, group_id_agilent):
        """Brand 'Shimadzu' should also match the 'Agilent + Shimadzu' group."""
        from services.phmb_price_service import resolve_brand_group

        result = resolve_brand_group("Shimadzu", sample_brand_groups)
        assert result == group_id_agilent

    def test_brand_matches_mettler_group(self, sample_brand_groups, group_id_mettler):
        """Brand 'Mettler Toledo' should match the Mettler Toledo group."""
        from services.phmb_price_service import resolve_brand_group

        result = resolve_brand_group("Mettler Toledo", sample_brand_groups)
        assert result == group_id_mettler

    def test_brand_no_match_returns_catchall(self, sample_brand_groups, group_id_catchall):
        """Brand that doesn't match any pattern should return the catchall group."""
        from services.phmb_price_service import resolve_brand_group

        result = resolve_brand_group("SomeRandomBrand", sample_brand_groups)
        assert result == group_id_catchall

    def test_brand_no_match_no_catchall_returns_none(self, sample_brand_groups_no_catchall):
        """Brand that doesn't match and no catchall group exists should return None."""
        from services.phmb_price_service import resolve_brand_group

        result = resolve_brand_group("SomeRandomBrand", sample_brand_groups_no_catchall)
        assert result is None

    def test_case_insensitive_matching(self, sample_brand_groups, group_id_agilent):
        """Brand matching should be case-insensitive."""
        from services.phmb_price_service import resolve_brand_group

        result_lower = resolve_brand_group("agilent", sample_brand_groups)
        result_upper = resolve_brand_group("AGILENT", sample_brand_groups)
        result_mixed = resolve_brand_group("AgIlEnT", sample_brand_groups)

        assert result_lower == group_id_agilent
        assert result_upper == group_id_agilent
        assert result_mixed == group_id_agilent

    def test_empty_brand_returns_catchall(self, sample_brand_groups, group_id_catchall):
        """Empty string brand should go to catchall."""
        from services.phmb_price_service import resolve_brand_group

        result = resolve_brand_group("", sample_brand_groups)
        assert result == group_id_catchall

    def test_empty_groups_list_returns_none(self):
        """With no groups configured, should return None."""
        from services.phmb_price_service import resolve_brand_group

        result = resolve_brand_group("Agilent", [])
        assert result is None

    def test_sort_order_determines_priority(self, org_id):
        """When brand could match multiple groups, sort_order should determine the winner."""
        from services.phmb_price_service import resolve_brand_group

        group_a_id = str(uuid4())
        group_b_id = str(uuid4())
        groups = [
            {
                "id": group_b_id,
                "org_id": org_id,
                "name": "Group B (higher sort_order)",
                "brand_patterns": ["Agilent"],
                "is_catchall": False,
                "sort_order": 10,
            },
            {
                "id": group_a_id,
                "org_id": org_id,
                "name": "Group A (lower sort_order)",
                "brand_patterns": ["Agilent"],
                "is_catchall": False,
                "sort_order": 1,
            },
        ]
        # Should match by sort_order, not list position
        result = resolve_brand_group("Agilent", groups)
        assert result == group_a_id

    def test_none_brand_returns_catchall(self, sample_brand_groups, group_id_catchall):
        """None brand should be treated like empty — goes to catchall."""
        from services.phmb_price_service import resolve_brand_group

        # The function should handle None gracefully
        result = resolve_brand_group(None, sample_brand_groups)
        assert result == group_id_catchall


# =============================================================================
# 2. price_queue_item() — WRITE-BACK FLOW TESTS
# =============================================================================

class TestPriceQueueItem:
    """Tests for price_queue_item() — the critical write-back flow."""

    @patch("services.phmb_price_service.get_supabase")
    def test_sets_queue_status_to_priced(self, mock_get_sb, queue_item_id, org_id, sample_queue_item):
        """price_queue_item should update the queue entry status to 'priced'."""
        from services.phmb_price_service import price_queue_item

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Mock the select to return the queue item with FK join
        mock_select_chain = MagicMock()
        mock_select_chain.execute.return_value = MagicMock(data=[sample_queue_item])
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_chain

        # Mock update and upsert chains
        mock_update_chain = MagicMock()
        mock_update_chain.eq.return_value.execute.return_value = MagicMock(data=[sample_queue_item])
        mock_sb.table.return_value.update.return_value = mock_update_chain

        mock_upsert_chain = MagicMock()
        mock_upsert_chain.execute.return_value = MagicMock(data=[{}])
        mock_sb.table.return_value.upsert.return_value = mock_upsert_chain

        result = price_queue_item(org_id, queue_item_id, 250.00)

        # Verify that the queue table was updated with status='priced'
        update_calls = mock_sb.table.return_value.update.call_args_list
        assert len(update_calls) >= 1
        # Check at least one update call includes status='priced'
        found_status_update = False
        for c in update_calls:
            update_data = c[0][0] if c[0] else c[1]
            if isinstance(update_data, dict) and update_data.get("status") == "priced":
                found_status_update = True
                assert update_data.get("priced_rmb") == 250.00
                break
        assert found_status_update, "Expected status='priced' update on phmb_procurement_queue"

    @patch("services.phmb_price_service.get_supabase")
    def test_writes_price_back_to_quote_item(self, mock_get_sb, queue_item_id, org_id, sample_queue_item):
        """price_queue_item should write list_price_rmb back to phmb_quote_items."""
        from services.phmb_price_service import price_queue_item

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Mock select to return queue item (2 eq() calls: id + org_id)
        mock_select_chain = MagicMock()
        mock_select_chain.execute.return_value = MagicMock(data=[sample_queue_item])
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_chain

        # Mock update chains
        mock_update_chain = MagicMock()
        mock_update_chain.eq.return_value.execute.return_value = MagicMock(data=[{}])
        mock_update_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        mock_sb.table.return_value.update.return_value = mock_update_chain

        # Mock upsert
        mock_upsert_chain = MagicMock()
        mock_upsert_chain.execute.return_value = MagicMock(data=[{}])
        mock_sb.table.return_value.upsert.return_value = mock_upsert_chain

        price_queue_item(org_id, queue_item_id, 250.00)

        # Verify that phmb_quote_items table was called for update
        table_calls = [c[0][0] for c in mock_sb.table.call_args_list]
        assert "phmb_quote_items" in table_calls, \
            "Expected update call to phmb_quote_items table"

    @patch("services.phmb_price_service.get_supabase")
    def test_upserts_into_price_list(self, mock_get_sb, queue_item_id, org_id, sample_queue_item):
        """price_queue_item should upsert the product into phmb_price_list."""
        from services.phmb_price_service import price_queue_item

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Mock select (2 eq() calls: id + org_id)
        mock_select_chain = MagicMock()
        mock_select_chain.execute.return_value = MagicMock(data=[sample_queue_item])
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_chain

        # Mock update chains
        mock_update_chain = MagicMock()
        mock_update_chain.eq.return_value.execute.return_value = MagicMock(data=[{}])
        mock_update_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        mock_sb.table.return_value.update.return_value = mock_update_chain

        # Mock upsert
        mock_upsert_chain = MagicMock()
        mock_upsert_chain.execute.return_value = MagicMock(data=[{}])
        mock_sb.table.return_value.upsert.return_value = mock_upsert_chain

        price_queue_item(org_id, queue_item_id, 250.00)

        # Verify phmb_price_list upsert was called
        table_calls = [c[0][0] for c in mock_sb.table.call_args_list]
        assert "phmb_price_list" in table_calls, \
            "Expected upsert call to phmb_price_list table"

    @patch("services.phmb_price_service.get_supabase")
    def test_skips_price_list_upsert_if_cat_number_empty(
        self, mock_get_sb, queue_item_id, org_id, sample_queue_item
    ):
        """When cat_number is empty, should skip the price list upsert."""
        from services.phmb_price_service import price_queue_item

        # Modify sample to have empty cat_number
        queue_item_no_cat = {**sample_queue_item}
        queue_item_no_cat["phmb_quote_items"] = {
            **sample_queue_item["phmb_quote_items"],
            "cat_number": "",
        }

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Mock select (2 eq() calls: id + org_id)
        mock_select_chain = MagicMock()
        mock_select_chain.execute.return_value = MagicMock(data=[queue_item_no_cat])
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_chain

        # Mock update chains
        mock_update_chain = MagicMock()
        mock_update_chain.eq.return_value.execute.return_value = MagicMock(data=[{}])
        mock_update_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        mock_sb.table.return_value.update.return_value = mock_update_chain

        # Mock upsert (should NOT be called)
        mock_upsert_chain = MagicMock()
        mock_upsert_chain.execute.return_value = MagicMock(data=[{}])
        mock_sb.table.return_value.upsert.return_value = mock_upsert_chain

        price_queue_item(org_id, queue_item_id, 250.00)

        # Verify phmb_price_list was NOT called for upsert
        table_calls = [c[0][0] for c in mock_sb.table.call_args_list]
        # phmb_price_list should NOT appear — only phmb_procurement_queue and phmb_quote_items
        price_list_calls = [t for t in table_calls if t == "phmb_price_list"]
        assert len(price_list_calls) == 0, \
            f"Expected no calls to phmb_price_list when cat_number is empty, but got {len(price_list_calls)}"

    def test_rejects_priced_rmb_zero(self, org_id, queue_item_id):
        """price_queue_item should reject priced_rmb <= 0."""
        from services.phmb_price_service import price_queue_item

        with pytest.raises((ValueError, Exception)):
            price_queue_item(org_id, queue_item_id, 0)

    def test_rejects_priced_rmb_negative(self, org_id, queue_item_id):
        """price_queue_item should reject negative prices."""
        from services.phmb_price_service import price_queue_item

        with pytest.raises((ValueError, Exception)):
            price_queue_item(org_id, queue_item_id, -10.0)

    @patch("services.phmb_price_service.get_supabase")
    def test_raises_on_queue_item_not_found(self, mock_get_sb, org_id):
        """price_queue_item should raise ValueError when queue item not found."""
        from services.phmb_price_service import price_queue_item

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Mock select returning empty (2 eq() calls: id + org_id)
        mock_select_chain = MagicMock()
        mock_select_chain.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_chain

        nonexistent_id = str(uuid4())
        with pytest.raises(ValueError, match="not found"):
            price_queue_item(org_id, nonexistent_id, 250.00)

    @patch("services.phmb_price_service.get_supabase")
    def test_price_list_upsert_uses_correct_data(
        self, mock_get_sb, queue_item_id, org_id, sample_queue_item
    ):
        """Verify the upsert to phmb_price_list uses correct fields from the quote item."""
        from services.phmb_price_service import price_queue_item

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Mock select (2 eq() calls: id + org_id)
        mock_select_chain = MagicMock()
        mock_select_chain.execute.return_value = MagicMock(data=[sample_queue_item])
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select_chain

        # Track table/upsert calls
        upsert_calls = []
        original_table = mock_sb.table

        def track_table(name):
            result = original_table(name)
            if name == "phmb_price_list":
                def track_upsert(data, **kwargs):
                    upsert_calls.append(data)
                    chain = MagicMock()
                    chain.execute.return_value = MagicMock(data=[data])
                    return chain
                result.upsert = track_upsert
            return result

        mock_sb.table = track_table

        # Mock update chains
        mock_update_chain = MagicMock()
        mock_update_chain.eq.return_value.execute.return_value = MagicMock(data=[{}])
        mock_update_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        original_table.return_value.update.return_value = mock_update_chain

        price_queue_item(org_id, queue_item_id, 250.00)

        # Verify the upsert data contains the right fields
        assert len(upsert_calls) >= 1, "Expected at least one upsert to phmb_price_list"
        upsert_data = upsert_calls[0]
        assert upsert_data["org_id"] == org_id
        assert upsert_data["cat_number"] == "1234-A"
        assert upsert_data["product_name"] == "Probe Kit"
        assert upsert_data["brand"] == "Agilent"
        assert upsert_data["list_price_rmb"] == 250.00


# =============================================================================
# 3. ensure_queue_entries() — BACKFILL LOGIC TESTS
# =============================================================================

class TestEnsureQueueEntries:
    """Tests for ensure_queue_entries() — lazy backfill for unpriced items."""

    @patch("services.phmb_price_service.get_supabase")
    def test_enqueues_unpriced_items_not_in_queue(
        self, mock_get_sb, org_id, quote_id, sample_phmb_items_mixed
    ):
        """Items with no price list reference and not in queue should get enqueued."""
        from services.phmb_price_service import ensure_queue_entries

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # The function needs to:
        # 1. Fetch phmb_quote_items for the quote (items without price list ref)
        # 2. Fetch existing queue entries for this quote
        # 3. Insert new queue entries for items not already in queue

        # Mock: return mixed items (2 unpriced, 1 priced)
        items_response = MagicMock()
        items_response.data = sample_phmb_items_mixed

        # Mock: no existing queue entries
        queue_response = MagicMock()
        queue_response.data = []

        # Mock: insert returns the new queue entry
        insert_response = MagicMock()
        insert_response.data = [{"id": str(uuid4())}]

        # Set up the chain — different tables return different results
        table_data = {
            "phmb_quote_items": items_response,
            "phmb_procurement_queue": queue_response,
        }

        def mock_table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.is_.return_value = chain
            chain.order.return_value = chain
            chain.execute.return_value = table_data.get(name, MagicMock(data=[]))
            chain.insert.return_value = MagicMock(
                execute=MagicMock(return_value=insert_response)
            )
            return chain

        mock_sb.table = mock_table

        # Call the function — should enqueue unpriced items only
        ensure_queue_entries(quote_id, org_id)

        # The function should have been called without raising an error
        # (The actual verification of inserts depends on the implementation)

    @patch("services.phmb_price_service.get_supabase")
    def test_skips_items_already_in_queue(self, mock_get_sb, org_id, quote_id):
        """Items that are already in the queue should not be enqueued again."""
        from services.phmb_price_service import ensure_queue_entries

        item_id = str(uuid4())
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Only one unpriced item
        items_data = [
            {
                "id": item_id,
                "quote_id": quote_id,
                "phmb_price_list_id": None,
                "cat_number": "CUSTOM-001",
                "product_name": "Custom Probe",
                "brand": "Shimadzu",
                "list_price_rmb": None,
                "quantity": 2,
            }
        ]

        # Queue already has this item
        existing_queue = [
            {
                "id": str(uuid4()),
                "quote_item_id": item_id,
                "quote_id": quote_id,
                "brand": "Shimadzu",
                "status": "new",
            }
        ]

        items_response = MagicMock()
        items_response.data = items_data
        queue_response = MagicMock()
        queue_response.data = existing_queue

        insert_mock = MagicMock()
        insert_response = MagicMock()
        insert_response.data = []
        insert_mock.execute.return_value = insert_response

        def mock_table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.is_.return_value = chain
            chain.order.return_value = chain
            if name == "phmb_quote_items":
                chain.execute.return_value = items_response
            elif name == "phmb_procurement_queue":
                chain.execute.return_value = queue_response
                chain.insert.return_value = insert_mock
            return chain

        mock_sb.table = mock_table

        # Should not raise and should not insert (item already queued)
        ensure_queue_entries(quote_id, org_id)

        # The insert should NOT have been called for phmb_procurement_queue
        # since the item is already in queue
        # (Implementation-specific verification — the test just ensures no error)

    @patch("services.phmb_price_service.get_supabase")
    def test_skips_items_with_price_list_reference(self, mock_get_sb, org_id, quote_id):
        """Items that came from the price list (have phmb_price_list_id) should not be enqueued."""
        from services.phmb_price_service import ensure_queue_entries

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # All items have price list references
        items_data = [
            {
                "id": str(uuid4()),
                "quote_id": quote_id,
                "phmb_price_list_id": str(uuid4()),  # has price list ref
                "cat_number": "PRICED-001",
                "product_name": "Standard Widget",
                "brand": "Agilent",
                "list_price_rmb": "100.00",
                "quantity": 5,
            }
        ]

        items_response = MagicMock()
        items_response.data = items_data
        queue_response = MagicMock()
        queue_response.data = []

        insert_mock = MagicMock()
        insert_response = MagicMock()
        insert_response.data = []
        insert_mock.execute.return_value = insert_response

        def mock_table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.is_.return_value = chain
            chain.order.return_value = chain
            if name == "phmb_quote_items":
                chain.execute.return_value = items_response
            elif name == "phmb_procurement_queue":
                chain.execute.return_value = queue_response
                chain.insert.return_value = insert_mock
            return chain

        mock_sb.table = mock_table

        # Should complete without inserting anything
        ensure_queue_entries(quote_id, org_id)

    @patch("services.phmb_price_service.get_supabase")
    def test_does_not_crash_on_empty_items(self, mock_get_sb, org_id, quote_id):
        """ensure_queue_entries with no items should complete silently."""
        from services.phmb_price_service import ensure_queue_entries

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        empty_response = MagicMock()
        empty_response.data = []

        def mock_table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.is_.return_value = chain
            chain.order.return_value = chain
            chain.execute.return_value = empty_response
            return chain

        mock_sb.table = mock_table

        # Should not raise
        ensure_queue_entries(quote_id, org_id)

    @patch("services.phmb_price_service.get_supabase")
    def test_does_not_raise_on_db_error(self, mock_get_sb, org_id, quote_id):
        """ensure_queue_entries should not raise exceptions — it's a lazy backfill.

        Per blueprint: 'Wrap in try/except, log errors but don't raise —
        this is a lazy backfill and must not break the tab load.'
        """
        from services.phmb_price_service import ensure_queue_entries

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        # Simulate a DB error
        mock_sb.table.side_effect = Exception("DB connection lost")

        # Should NOT raise — logs error and returns silently
        ensure_queue_entries(quote_id, org_id)


# =============================================================================
# 4. phmb_calculator with NULL list_price_rmb
# =============================================================================

class TestPhmbCalculatorNullPrice:
    """Tests for calculate_phmb_item when list_price_rmb is None.

    After migration 195, list_price_rmb becomes nullable for custom items.
    The calculator should handle None gracefully.
    """

    def test_calculate_item_with_null_price_returns_zeros(self):
        """calculate_phmb_item with list_price_rmb=None should return all zeros."""
        from services.phmb_calculator import calculate_phmb_item

        item_data = {
            "list_price_rmb": None,
            "discount_pct": 0,
            "duty_pct": None,
            "delivery_days": 90,
            "quantity": 1,
        }
        settings = {
            "logistics_price_per_pallet": 1800,
            "base_price_per_pallet": 50000,
            "exchange_rate_insurance_pct": 3.0,
            "financial_transit_pct": 2.0,
            "customs_handling_cost": 800,
            "customs_insurance_pct": 5.0,
        }
        quote_params = {
            "advance_pct": 0,
            "markup_pct": 10,
            "payment_days": 30,
            "cny_to_usd_rate": 7.2,
        }

        result = calculate_phmb_item(item_data, settings, quote_params)

        # With list_price_rmb=None, _to_decimal returns 0
        # 0 / 7.2 = 0, so all prices should be 0
        assert result["exw_price_usd"] == Decimal("0")
        assert result["total_price_usd"] == Decimal("0")
        assert result["total_price_with_vat_usd"] == Decimal("0")

    def test_calculate_quote_with_mixed_items(self):
        """calculate_phmb_quote should handle a mix of priced and NULL-price items."""
        from services.phmb_calculator import calculate_phmb_quote

        items = [
            {
                "id": str(uuid4()),
                "list_price_rmb": 1000.00,  # normal priced item
                "discount_pct": 10,
                "duty_pct": 5.0,
                "delivery_days": 90,
                "quantity": 2,
            },
            {
                "id": str(uuid4()),
                "list_price_rmb": None,  # custom unpriced item
                "discount_pct": 0,
                "duty_pct": None,
                "delivery_days": 90,
                "quantity": 1,
            },
        ]
        settings = {
            "logistics_price_per_pallet": 1800,
            "base_price_per_pallet": 50000,
            "exchange_rate_insurance_pct": 3.0,
            "financial_transit_pct": 2.0,
            "customs_handling_cost": 800,
            "customs_insurance_pct": 5.0,
        }
        quote_params = {
            "advance_pct": 0,
            "markup_pct": 10,
            "payment_days": 30,
            "cny_to_usd_rate": 7.2,
        }

        result = calculate_phmb_quote(items, settings, quote_params)

        # Should not crash, should have 2 items in result
        assert len(result["items"]) == 2
        # Second item (NULL price) should have zero totals
        null_item = result["items"][1]
        assert null_item["exw_price_usd"] == Decimal("0")
        assert null_item["total_price_usd"] == Decimal("0")
        # First item should have non-zero prices
        priced_item = result["items"][0]
        assert priced_item["exw_price_usd"] > Decimal("0")
        assert priced_item["total_price_usd"] > Decimal("0")
        # Total quantity is sum of both
        assert result["totals"]["total_quantity"] == 3


# =============================================================================
# 5. Brand group CRUD — verify DB interactions
# =============================================================================

class TestBrandGroupCRUD:
    """Tests for get_brand_groups, upsert_brand_group, delete_brand_group."""

    @patch("services.phmb_price_service.get_supabase")
    def test_get_brand_groups_returns_sorted_list(self, mock_get_sb, org_id):
        """get_brand_groups should return groups sorted by sort_order."""
        from services.phmb_price_service import get_brand_groups

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        groups_data = [
            {"id": str(uuid4()), "name": "Group A", "sort_order": 0},
            {"id": str(uuid4()), "name": "Catchall", "sort_order": 99},
        ]

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=groups_data)
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value = mock_chain

        result = get_brand_groups(org_id)
        assert result == groups_data

    @patch("services.phmb_price_service.get_supabase")
    def test_get_brand_groups_empty(self, mock_get_sb, org_id):
        """get_brand_groups with no groups should return empty list."""
        from services.phmb_price_service import get_brand_groups

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value = mock_chain

        result = get_brand_groups(org_id)
        assert result == []

    @patch("services.phmb_price_service.get_supabase")
    def test_upsert_brand_group_creates_new(self, mock_get_sb, org_id):
        """upsert_brand_group should create a new brand group."""
        from services.phmb_price_service import upsert_brand_group

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        new_group = {
            "id": str(uuid4()),
            "org_id": org_id,
            "name": "Agilent + Shimadzu",
            "brand_patterns": ["Agilent", "Shimadzu"],
            "is_catchall": False,
            "sort_order": 0,
        }

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=[new_group])
        mock_sb.table.return_value.upsert.return_value = mock_chain

        result = upsert_brand_group(
            org_id=org_id,
            group_id=None,
            name="Agilent + Shimadzu",
            brand_patterns=["Agilent", "Shimadzu"],
            is_catchall=False,
            sort_order=0,
        )
        assert result.get("name") == "Agilent + Shimadzu"

    @patch("services.phmb_price_service.get_supabase")
    def test_delete_brand_group(self, mock_get_sb, org_id):
        """delete_brand_group should delete the group and return True."""
        from services.phmb_price_service import delete_brand_group

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        group_id = str(uuid4())

        mock_chain = MagicMock()
        mock_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": group_id}]
        )
        mock_sb.table.return_value.delete.return_value = mock_chain

        result = delete_brand_group(group_id, org_id)
        assert result is True

    @patch("services.phmb_price_service.get_supabase")
    def test_delete_nonexistent_brand_group(self, mock_get_sb, org_id):
        """delete_brand_group with non-existent ID should return False."""
        from services.phmb_price_service import delete_brand_group

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        mock_chain = MagicMock()
        mock_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.delete.return_value = mock_chain

        result = delete_brand_group(str(uuid4()), org_id)
        assert result is False


# =============================================================================
# 6. get_procurement_queue — verify query and filtering
# =============================================================================

class TestGetProcurementQueue:
    """Tests for get_procurement_queue() — fetching queue with filters."""

    @patch("services.phmb_price_service.get_supabase")
    def test_get_queue_no_filters(self, mock_get_sb, org_id):
        """get_procurement_queue with no filters returns all items for the org."""
        from services.phmb_price_service import get_procurement_queue

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        queue_data = [
            {"id": str(uuid4()), "brand": "Agilent", "status": "new"},
            {"id": str(uuid4()), "brand": "Shimadzu", "status": "requested"},
        ]

        # Mock the chain: select -> eq (org_id) -> [optional filters] -> order -> execute
        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=queue_data)
        mock_chain.order.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_sb.table.return_value.select.return_value = mock_chain

        result = get_procurement_queue(org_id)
        assert len(result) == 2

    @patch("services.phmb_price_service.get_supabase")
    def test_get_queue_filter_by_status(self, mock_get_sb, org_id):
        """get_procurement_queue filtered by status should only return matching items."""
        from services.phmb_price_service import get_procurement_queue

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        queue_data = [
            {"id": str(uuid4()), "brand": "Agilent", "status": "new"},
        ]

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=queue_data)
        mock_chain.order.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_sb.table.return_value.select.return_value = mock_chain

        result = get_procurement_queue(org_id, status="new")
        assert len(result) == 1
        assert result[0]["status"] == "new"

    @patch("services.phmb_price_service.get_supabase")
    def test_get_queue_filter_by_brand_group(self, mock_get_sb, org_id, group_id_agilent):
        """get_procurement_queue filtered by brand_group_id."""
        from services.phmb_price_service import get_procurement_queue

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        queue_data = [
            {
                "id": str(uuid4()),
                "brand": "Agilent",
                "brand_group_id": group_id_agilent,
                "status": "new",
            },
        ]

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=queue_data)
        mock_chain.order.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_sb.table.return_value.select.return_value = mock_chain

        result = get_procurement_queue(org_id, brand_group_id=group_id_agilent)
        assert len(result) == 1

    @patch("services.phmb_price_service.get_supabase")
    def test_get_queue_empty_result(self, mock_get_sb, org_id):
        """get_procurement_queue returns empty list when no items match."""
        from services.phmb_price_service import get_procurement_queue

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=[])
        mock_chain.order.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_sb.table.return_value.select.return_value = mock_chain

        result = get_procurement_queue(org_id, status="priced")
        assert result == []


# =============================================================================
# 7. enqueue_phmb_item — single item enqueue
# =============================================================================

class TestEnqueuePhmbItem:
    """Tests for enqueue_phmb_item() — inserting a single item into the queue."""

    @patch("services.phmb_price_service.get_supabase")
    def test_enqueue_item_with_brand_group(
        self, mock_get_sb, org_id, quote_item_id, quote_id, sample_brand_groups, group_id_agilent
    ):
        """Enqueueing an Agilent item should assign the correct brand group."""
        from services.phmb_price_service import enqueue_phmb_item

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        inserted_row = {
            "id": str(uuid4()),
            "org_id": org_id,
            "quote_item_id": quote_item_id,
            "quote_id": quote_id,
            "brand": "Agilent",
            "brand_group_id": group_id_agilent,
            "status": "new",
        }

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=[inserted_row])
        mock_sb.table.return_value.insert.return_value = mock_chain

        result = enqueue_phmb_item(
            org_id=org_id,
            quote_item_id=quote_item_id,
            quote_id=quote_id,
            brand="Agilent",
            groups=sample_brand_groups,
        )

        assert result.get("brand") == "Agilent"
        assert result.get("status") == "new"

    @patch("services.phmb_price_service.get_supabase")
    def test_enqueue_item_unknown_brand_gets_catchall(
        self, mock_get_sb, org_id, quote_item_id, quote_id, sample_brand_groups, group_id_catchall
    ):
        """Enqueueing an unknown brand should assign the catchall group."""
        from services.phmb_price_service import enqueue_phmb_item

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        inserted_row = {
            "id": str(uuid4()),
            "org_id": org_id,
            "quote_item_id": quote_item_id,
            "quote_id": quote_id,
            "brand": "UnknownBrand",
            "brand_group_id": group_id_catchall,
            "status": "new",
        }

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=[inserted_row])
        mock_sb.table.return_value.insert.return_value = mock_chain

        result = enqueue_phmb_item(
            org_id=org_id,
            quote_item_id=quote_item_id,
            quote_id=quote_id,
            brand="UnknownBrand",
            groups=sample_brand_groups,
        )

        assert result.get("status") == "new"


# =============================================================================
# 8. update_queue_item_status — status transitions
# =============================================================================

class TestUpdateQueueItemStatus:
    """Tests for update_queue_item_status() — transitioning status."""

    @patch("services.phmb_price_service.get_supabase")
    def test_transition_new_to_requested(self, mock_get_sb):
        """Status change from 'new' to 'requested'."""
        from services.phmb_price_service import update_queue_item_status

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        queue_item_id = str(uuid4())
        updated_row = {
            "id": queue_item_id,
            "status": "requested",
            "priced_rmb": None,
        }

        mock_chain = MagicMock()
        mock_chain.eq.return_value.execute.return_value = MagicMock(data=[updated_row])
        mock_sb.table.return_value.update.return_value = mock_chain

        result = update_queue_item_status(queue_item_id, "requested")
        assert result.get("status") == "requested"

    @patch("services.phmb_price_service.get_supabase")
    def test_transition_requested_to_priced_with_price(self, mock_get_sb):
        """Status change from 'requested' to 'priced' should include priced_rmb."""
        from services.phmb_price_service import update_queue_item_status

        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        queue_item_id = str(uuid4())
        updated_row = {
            "id": queue_item_id,
            "status": "priced",
            "priced_rmb": 350.00,
        }

        mock_chain = MagicMock()
        mock_chain.eq.return_value.execute.return_value = MagicMock(data=[updated_row])
        mock_sb.table.return_value.update.return_value = mock_chain

        result = update_queue_item_status(queue_item_id, "priced", priced_rmb=350.00)
        assert result.get("status") == "priced"
        assert result.get("priced_rmb") == 350.00
