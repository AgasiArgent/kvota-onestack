"""
Tests for customer page bugs M1 and M7.

M1: Customer stats cards show 0 for all metrics when customers exist.
    - The /customers route handler calls get_customer_stats(organization_id=org_id)
      where org_id = session["user"].get("org_id").
    - Stats should return correct non-zero values and the route should render them.
    - If there's a mismatch in the org_id flow, stats silently return 0 via exception handler.

M7: Contact name duplicated/garbled (e.g., "Мамут Рахал Мамут Иванович Иванович").
    - get_full_name() should never produce duplicate tokens.
    - _render_contact_name_cell should not duplicate name parts.
    - Contact creation stores full name in 'name' field but not in 'last_name'/'patronymic',
      causing duplication when get_full_name() reassembles from all three parts.
"""

import pytest
from unittest.mock import MagicMock, patch
import re

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.customer_service import (
    CustomerContact,
    Customer,
    get_customer_stats,
    get_all_customers,
    get_contacts_for_customer,
    _parse_contact,
    _parse_customer,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def org_id():
    return "org-test-001"


@pytest.fixture
def sample_customers_data(org_id):
    """Three customers: two active, one inactive."""
    return [
        {
            "id": "cust-1",
            "organization_id": org_id,
            "name": "ООО Ромашка",
            "inn": "7712345678",
            "is_active": True,
        },
        {
            "id": "cust-2",
            "organization_id": org_id,
            "name": "ЗАО Лютик",
            "inn": None,
            "is_active": True,
        },
        {
            "id": "cust-3",
            "organization_id": org_id,
            "name": "ИП Сидоров",
            "inn": "771234567890",
            "is_active": False,
        },
    ]


@pytest.fixture
def sample_contacts_data():
    """Contacts for the customers above."""
    return [
        {"customer_id": "cust-1", "is_signatory": True},
        {"customer_id": "cust-1", "is_signatory": False},
        {"customer_id": "cust-2", "is_signatory": False},
    ]


def _has_duplicate_tokens(text: str) -> bool:
    """
    Check if a string has obviously duplicated consecutive tokens.

    Examples of duplicated text:
      "Мамут Рахал Мамут Иванович Иванович" -> True (Мамут and Иванович appear twice)
      "Мамут Рахал Иванович" -> False
    """
    tokens = text.split()
    # Check for any token appearing more than once
    from collections import Counter
    counts = Counter(tokens)
    return any(count > 1 for count in counts.values())


def _mock_supabase_for_stats(mock_get_supabase, customers_data, contacts_data):
    """Helper: configure mock supabase for get_customer_stats calls."""
    mock_client = MagicMock()
    mock_get_supabase.return_value = mock_client

    customers_response = MagicMock()
    customers_response.data = customers_data

    contacts_response = MagicMock()
    contacts_response.data = contacts_data

    def table_side_effect(name):
        mock_t = MagicMock()
        if name == "customers":
            mock_s = MagicMock()
            mock_t.select.return_value = mock_s
            mock_e = MagicMock()
            mock_s.eq.return_value = mock_e
            mock_e.execute.return_value = customers_response
        elif name == "customer_contacts":
            mock_s = MagicMock()
            mock_t.select.return_value = mock_s
            mock_i = MagicMock()
            mock_s.in_.return_value = mock_i
            mock_i.execute.return_value = contacts_response
        return mock_t

    mock_client.table.side_effect = table_side_effect
    return mock_client


# =============================================================================
# M1: Customer stats cards show 0 for all metrics
# =============================================================================

class TestM1CustomerStats:
    """
    M1: Stats cards on /customers page show "0 Всего, 0 Активных" even when
    customers exist in the organization.

    The route handler at main.py:32200 does:
        org_id = user.get("org_id")
        stats = get_customer_stats(organization_id=org_id)
    And then renders stats.get("total", 0), stats.get("active", 0) etc.

    If something goes wrong (org_id mismatch, query error), the exception
    handler at main.py:32238 silently sets stats = all zeros.
    """

    @patch('services.customer_service._get_supabase')
    def test_stats_total_matches_actual_customer_count(
        self, mock_get_supabase, org_id, sample_customers_data, sample_contacts_data
    ):
        """Stats 'total' should equal the number of customers in the organization."""
        _mock_supabase_for_stats(mock_get_supabase, sample_customers_data, sample_contacts_data)

        stats = get_customer_stats(organization_id=org_id)

        assert stats["total"] == 3, (
            f"Expected total=3 customers, got {stats['total']}. "
            "Stats cards show 0 when customers exist."
        )

    @patch('services.customer_service._get_supabase')
    def test_stats_active_count_matches_active_customers(
        self, mock_get_supabase, org_id, sample_customers_data, sample_contacts_data
    ):
        """Stats 'active' should equal number of active customers (2 out of 3)."""
        _mock_supabase_for_stats(mock_get_supabase, sample_customers_data, sample_contacts_data)

        stats = get_customer_stats(organization_id=org_id)

        assert stats["active"] == 2, (
            f"Expected active=2, got {stats['active']}. "
            "Active count should match customers where is_active=True."
        )

    @patch('services.customer_service._get_supabase')
    def test_stats_with_contacts_count(
        self, mock_get_supabase, org_id, sample_customers_data, sample_contacts_data
    ):
        """Stats 'with_contacts' should be 2 (cust-1 and cust-2 have contacts, cust-3 does not)."""
        _mock_supabase_for_stats(mock_get_supabase, sample_customers_data, sample_contacts_data)

        stats = get_customer_stats(organization_id=org_id)

        assert stats["with_contacts"] == 2, (
            f"Expected with_contacts=2, got {stats['with_contacts']}. "
            "Customers cust-1 and cust-2 have contacts."
        )

    @patch('services.customer_service._get_supabase')
    def test_stats_with_signatory_count(
        self, mock_get_supabase, org_id, sample_customers_data, sample_contacts_data
    ):
        """Stats 'with_signatory' should be 1 (only cust-1 has a signatory contact)."""
        _mock_supabase_for_stats(mock_get_supabase, sample_customers_data, sample_contacts_data)

        stats = get_customer_stats(organization_id=org_id)

        assert stats["with_signatory"] == 1, (
            f"Expected with_signatory=1, got {stats['with_signatory']}. "
            "Only cust-1 has a signatory contact."
        )

    def test_route_handler_stats_integration(self, org_id, sample_customers_data, sample_contacts_data):
        """
        Simulate the route handler flow at main.py:32200-32240.

        The route does:
          1. org_id = session["user"].get("org_id")
          2. stats = get_customer_stats(organization_id=org_id)
          3. renders stats.get("total", 0) etc.

        This test verifies the full flow: when customers exist, the stats dict
        returned by get_customer_stats AND rendered by stats.get() produce
        non-zero values. If the route exception handler catches an error,
        it resets stats to all zeros -- this test will catch that.
        """
        # Simulate session["user"] as it exists in the real app (main.py:4163-4168)
        session_user = {
            "id": "user-001",
            "email": "test@example.com",
            "org_id": org_id,
            "org_name": "Test Org",
            "roles": ["sales", "admin"],
        }

        # This is what the route handler does (main.py:32200-32201)
        route_org_id = session_user.get("org_id")

        # Simulate the try/except block from the route handler (main.py:32210-32242)
        try:
            with patch('services.customer_service._get_supabase') as mock_get_supabase:
                _mock_supabase_for_stats(mock_get_supabase, sample_customers_data, sample_contacts_data)
                stats = get_customer_stats(organization_id=route_org_id)
        except Exception:
            stats = {"total": 0, "active": 0, "inactive": 0, "with_contacts": 0, "with_signatory": 0}

        # These are the exact rendering calls from main.py:32320-32338
        total_display = str(stats.get("total", 0))
        active_display = str(stats.get("active", 0))
        with_contacts_display = str(stats.get("with_contacts", 0))
        with_signatory_display = str(stats.get("with_signatory", 0))

        # M1 BUG: all these show "0" on the page
        assert total_display != "0", (
            f"Stats card 'Всего' shows '{total_display}' but should show '3'. "
            "This is the M1 bug: stats cards show 0 for all metrics."
        )
        assert active_display != "0", (
            f"Stats card 'Активных' shows '{active_display}' but should show '2'."
        )

    def test_route_handler_stats_with_none_org_id(self):
        """
        When user.get("org_id") returns None, the route handler should
        not crash but stats will legitimately be 0.

        This tests the edge case where org_id is missing from the session.
        In production, this could happen if the user's organization_members
        record is missing or inactive.
        """
        session_user = {
            "id": "user-001",
            "email": "test@example.com",
            # org_id is missing from session
            "org_name": "No Organization",
            "roles": ["sales"],
        }

        route_org_id = session_user.get("org_id")  # Returns None

        # This should NOT crash
        with patch('services.customer_service._get_supabase') as mock_get_supabase:
            mock_client = MagicMock()
            mock_get_supabase.return_value = mock_client

            empty_response = MagicMock()
            empty_response.data = []

            def table_side_effect(name):
                mock_t = MagicMock()
                mock_s = MagicMock()
                mock_t.select.return_value = mock_s
                mock_e = MagicMock()
                mock_s.eq.return_value = mock_e
                mock_e.execute.return_value = empty_response
                return mock_t

            mock_client.table.side_effect = table_side_effect

            stats = get_customer_stats(organization_id=route_org_id)

        assert stats["total"] == 0
        assert isinstance(stats["total"], int)

    def test_stats_customers_exist_but_stats_not_all_zero(self, org_id, sample_customers_data, sample_contacts_data):
        """
        When get_all_customers returns customers for this org, get_customer_stats
        should NOT return total=0. This verifies the two functions are consistent
        -- if customers exist, stats must reflect that.

        This is the core M1 assertion: the page shows customers in the table
        but the stats cards above show "0 Всего, 0 Активных".
        """
        with patch('services.customer_service._get_supabase') as mock_get_supabase:
            # Setup mock that returns customers for both functions
            mock_client = MagicMock()
            mock_get_supabase.return_value = mock_client

            customers_response = MagicMock()
            customers_response.data = sample_customers_data

            contacts_response = MagicMock()
            contacts_response.data = sample_contacts_data

            def table_side_effect(name):
                mock_t = MagicMock()
                if name == "customers":
                    mock_s = MagicMock()
                    mock_t.select.return_value = mock_s
                    mock_e = MagicMock()
                    mock_s.eq.return_value = mock_e
                    # For get_all_customers: eq -> order -> range -> execute
                    mock_order = MagicMock()
                    mock_e.order.return_value = mock_order
                    mock_range = MagicMock()
                    mock_order.range.return_value = mock_range
                    mock_range.execute.return_value = customers_response
                    # For get_customer_stats: eq -> execute
                    mock_e.execute.return_value = customers_response
                elif name == "customer_contacts":
                    mock_s = MagicMock()
                    mock_t.select.return_value = mock_s
                    mock_i = MagicMock()
                    mock_s.in_.return_value = mock_i
                    mock_i.execute.return_value = contacts_response
                    # Also handle eq for get_contacts_for_customer
                    mock_eq = MagicMock()
                    mock_s.eq.return_value = mock_eq
                    mock_eq.order.return_value.order.return_value.execute.return_value = contacts_response
                return mock_t

            mock_client.table.side_effect = table_side_effect

            # The route handler does both of these
            customers = get_all_customers(organization_id=org_id)
            stats = get_customer_stats(organization_id=org_id)

        # If the table shows customers, stats must show non-zero
        assert len(customers) > 0, "Customers should exist"
        assert stats["total"] > 0, (
            f"M1 BUG: Table shows {len(customers)} customers but stats['total'] = {stats['total']}. "
            "Stats cards show 0 even though customers are visible in the table below."
        )
        assert stats["total"] == len(customers), (
            f"Stats total ({stats['total']}) doesn't match actual customer count ({len(customers)})"
        )

    def test_stats_rendered_values_are_not_all_zero_string(self, org_id, sample_customers_data, sample_contacts_data):
        """
        M1 BUG: The stats cards render "0" for all metrics.

        This test verifies that the rendered HTML stat values (from stats.get("total", 0) etc.)
        are not all "0" when customers exist. On the real page, lines 32320-32338 render:
          Div(str(stats.get("total", 0)), cls="stat-value")
          Div(str(stats.get("active", 0)), cls="stat-value")
          Div(str(stats.get("with_contacts", 0)), cls="stat-value")
          Div(str(stats.get("with_signatory", 0)), cls="stat-value")

        If the exception handler (main.py:32238) fires, all these become "0".
        This test ensures at least one stat is non-zero.
        """
        with patch('services.customer_service._get_supabase') as mock_get_supabase:
            _mock_supabase_for_stats(mock_get_supabase, sample_customers_data, sample_contacts_data)
            stats = get_customer_stats(organization_id=org_id)

        # Simulate what the template renders (main.py:32320-32338)
        rendered_values = {
            "Всего": str(stats.get("total", 0)),
            "Активных": str(stats.get("active", 0)),
            "С контактами": str(stats.get("with_contacts", 0)),
            "С подписантом": str(stats.get("with_signatory", 0)),
        }

        # At least total and active must be non-zero
        all_zeros = all(v == "0" for v in rendered_values.values())
        assert not all_zeros, (
            f"M1 BUG: All stat cards render '0': {rendered_values}. "
            "Expected non-zero values when 3 customers exist."
        )


# =============================================================================
# M7: Contact name duplicated/garbled
# =============================================================================

class TestM7ContactNameDuplication:
    """
    M7: Contact displays "Мамут Рахал Мамут Иванович Иванович" -- name duplicated.

    Root cause: Contact creation stores combined full name in 'name' field
    (e.g., "Мамут Рахал Иванович") but does not store 'last_name' and
    'patronymic' separately. When later edited or when get_full_name() is
    called with all three fields populated, name parts get duplicated.
    """

    def test_get_full_name_no_duplication_when_name_contains_full(self):
        """
        When 'name' contains the full combined name and last_name/patronymic
        are also set, get_full_name() should NOT produce duplicated tokens.

        This simulates the real scenario:
        - Contact created with name="Мамут Рахал Иванович" (full combined)
        - Later, last_name="Мамут" and patronymic="Иванович" are set via edit
        - get_full_name() should return "Мамут Рахал Иванович", not
          "Мамут Мамут Рахал Иванович Иванович"
        """
        contact = CustomerContact(
            id="contact-1",
            customer_id="cust-1",
            name="Мамут Рахал Иванович",  # Full name stored in 'name' field
            last_name="Мамут",             # Also set separately
            patronymic="Иванович",         # Also set separately
        )

        full_name = contact.get_full_name()

        # The full name should not contain any duplicated tokens
        assert not _has_duplicate_tokens(full_name), (
            f"get_full_name() produced duplicated tokens: '{full_name}'. "
            "Expected no duplication when name already contains the full name."
        )

    def test_get_full_name_all_parts_separate(self):
        """
        When last_name, name (first name only), and patronymic are all set
        correctly without overlap, get_full_name() should return clean result.
        """
        contact = CustomerContact(
            id="contact-2",
            customer_id="cust-1",
            name="Рахал",              # First name only
            last_name="Мамут",         # Last name only
            patronymic="Иванович",     # Patronymic only
        )

        full_name = contact.get_full_name()

        assert full_name == "Мамут Рахал Иванович", (
            f"Expected 'Мамут Рахал Иванович', got '{full_name}'"
        )
        assert not _has_duplicate_tokens(full_name)

    def test_get_full_name_only_name_field(self):
        """
        When only 'name' is set (as happens after contact creation),
        get_full_name() should return just that name without duplication.
        """
        contact = CustomerContact(
            id="contact-3",
            customer_id="cust-1",
            name="Мамут Рахал Иванович",
            last_name=None,
            patronymic=None,
        )

        full_name = contact.get_full_name()

        assert full_name == "Мамут Рахал Иванович"
        assert not _has_duplicate_tokens(full_name)

    def test_render_contact_name_cell_no_duplication(self):
        """
        _render_contact_name_cell builds name from last_name + name + patronymic.
        When name already contains the full string plus separate parts are set,
        the rendered name should not contain duplicated tokens.

        This tests the rendering function directly.
        """
        contact = CustomerContact(
            id="contact-4",
            customer_id="cust-1",
            name="Мамут Рахал Иванович",  # Full combined
            last_name="Мамут",             # Separately set
            patronymic="Иванович",         # Separately set
        )

        # Reproduce what _render_contact_name_cell does (lines 33582-33589)
        name_parts = []
        if contact.last_name:
            name_parts.append(contact.last_name)
        if contact.name:
            name_parts.append(contact.name)
        if contact.patronymic:
            name_parts.append(contact.patronymic)
        full_name = " ".join(name_parts) if name_parts else "—"

        # BUG: This produces "Мамут Мамут Рахал Иванович Иванович"
        assert not _has_duplicate_tokens(full_name), (
            f"_render_contact_name_cell produced duplicated name: '{full_name}'. "
            "When name field contains full combined name and last_name/patronymic "
            "are also set, tokens get duplicated."
        )

    def test_contact_creation_stores_separate_name_parts(self):
        """
        When a contact is created with last_name, name, and patronymic,
        the 'name' field should store only the first name (Имя),
        NOT the combined full name.

        Currently, the POST handler at main.py:34216-34223 stores:
          name = " ".join([last_name, name, patronymic])
        which means name="Мамут Рахал Иванович" instead of name="Рахал".

        This causes duplication when get_full_name() reassembles from all parts.
        """
        # Simulate what the POST handler does
        last_name = "Мамут"
        first_name = "Рахал"
        patronymic = "Иванович"

        # Current buggy behavior: name = combined full name
        full_name_parts = [last_name, first_name, patronymic]
        stored_name = " ".join(p.strip() for p in full_name_parts if p and p.strip())

        # The stored name should be just the first name, not the full combined name
        # BUG: stored_name = "Мамут Рахал Иванович" instead of "Рахал"
        assert stored_name == first_name, (
            f"Contact creation stores '{stored_name}' in name field instead of "
            f"'{first_name}'. The combined name should not be stored in the name "
            "field when last_name and patronymic are separate columns."
        )

    def test_contact_list_page_uses_name_directly(self):
        """
        On the customers list page (main.py:32229), contact.name is rendered
        directly via Span(contact.name). If name contains the full combined
        string "Мамут Рахал Иванович", that's fine. But on the detail page,
        get_full_name() is called which reassembles and duplicates.

        This tests that if name is the full combined, and get_full_name() is used,
        the result should be consistent with contact.name (no duplication).
        """
        contact = CustomerContact(
            id="contact-5",
            customer_id="cust-1",
            name="Мамут Рахал Иванович",  # Full combined
            last_name="Мамут",
            patronymic="Иванович",
        )

        # List page uses contact.name directly
        list_display = contact.name

        # Detail page uses get_full_name()
        detail_display = contact.get_full_name()

        # Both should produce the same clean result
        assert list_display == "Мамут Рахал Иванович"
        # BUG: detail_display = "Мамут Мамут Рахал Иванович Иванович"
        assert detail_display == list_display, (
            f"List page shows '{list_display}' but detail page shows "
            f"'{detail_display}'. These should be consistent."
        )

    def test_parse_contact_name_field_integrity(self):
        """
        When parsing a contact from DB row where 'name' contains full combined
        name and last_name/patronymic are also set, the parsed contact should
        produce a clean get_full_name() without duplication.
        """
        db_row = {
            "id": "contact-6",
            "customer_id": "cust-1",
            "name": "Мамут Рахал Иванович",  # Full combined
            "last_name": "Мамут",
            "patronymic": "Иванович",
            "position": "Директор",
            "email": None,
            "phone": None,
            "is_signatory": False,
            "is_primary": False,
            "is_lpr": False,
            "notes": None,
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T10:00:00Z",
        }

        contact = _parse_contact(db_row)
        full_name = contact.get_full_name()

        # BUG: produces "Мамут Мамут Рахал Иванович Иванович"
        assert not _has_duplicate_tokens(full_name), (
            f"Parsed contact produces duplicated name: '{full_name}'"
        )

    def test_get_full_name_with_only_last_and_first(self):
        """
        When only last_name and name (first) are set, no patronymic,
        get_full_name() should work correctly.
        """
        contact = CustomerContact(
            id="contact-7",
            customer_id="cust-1",
            name="Рахал",
            last_name="Мамут",
            patronymic=None,
        )

        full_name = contact.get_full_name()
        assert full_name == "Мамут Рахал"
        assert not _has_duplicate_tokens(full_name)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
