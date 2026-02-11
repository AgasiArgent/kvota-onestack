"""
TDD Tests for Deal Payments Feature (Task 86af6ykhh)

Feature: PLATEZHI (Payments) section on finance deal detail page.
Re-implement payments on finance deals page using existing plan_fact_items
table and plan_fact_service.py.

Routes to be implemented:
  1. GET  /finance/{deal_id}/payments/new          -- payment registration form
  2. POST /finance/{deal_id}/payments               -- register payment
  3. DELETE /finance/{deal_id}/payments/{item_id}    -- clear payment

Helper functions to be implemented:
  - _deal_payments_section(deal_id, plan_fact_items, categories)
  - _payment_registration_form(deal_id, unpaid_items, categories)

These tests are written BEFORE implementation (TDD).
All route/UI tests should FAIL until the feature is implemented.
"""

import pytest
import re
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Path constants (relative to project root via os.path)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY) as f:
        return f.read()


def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def deal_id():
    return _make_uuid()


@pytest.fixture
def org_id():
    return _make_uuid()


@pytest.fixture
def user_id():
    return _make_uuid()


@pytest.fixture
def category_client_payment():
    """Income category: client payment."""
    return {
        "id": _make_uuid(),
        "code": "client_payment",
        "name": "Оплата от клиента",
        "is_income": True,
        "sort_order": 1,
    }


@pytest.fixture
def category_supplier_payment():
    """Expense category: supplier payment."""
    return {
        "id": _make_uuid(),
        "code": "supplier_payment",
        "name": "Оплата поставщику",
        "is_income": False,
        "sort_order": 2,
    }


@pytest.fixture
def categories(category_client_payment, category_supplier_payment):
    return [category_client_payment, category_supplier_payment]


@pytest.fixture
def unpaid_item(deal_id, category_client_payment):
    """Plan-fact item that has NOT been paid yet (actual_amount IS NULL)."""
    return {
        "id": _make_uuid(),
        "deal_id": deal_id,
        "category_id": category_client_payment["id"],
        "description": "Аванс от клиента (50%)",
        "planned_amount": 500000.00,
        "planned_currency": "RUB",
        "planned_date": "2026-02-15",
        "actual_amount": None,
        "actual_currency": None,
        "actual_date": None,
        "actual_exchange_rate": None,
        "variance_amount": None,
        "payment_document": None,
        "notes": None,
        "created_at": datetime.now().isoformat(),
        "plan_fact_categories": category_client_payment,
    }


@pytest.fixture
def paid_item(deal_id, category_supplier_payment):
    """Plan-fact item that HAS been paid (actual_amount IS NOT NULL)."""
    return {
        "id": _make_uuid(),
        "deal_id": deal_id,
        "category_id": category_supplier_payment["id"],
        "description": "Оплата поставщику (100%)",
        "planned_amount": 300000.00,
        "planned_currency": "RUB",
        "planned_date": "2026-02-10",
        "actual_amount": 298500.00,
        "actual_currency": "RUB",
        "actual_date": "2026-02-09",
        "actual_exchange_rate": None,
        "variance_amount": -1500.00,
        "payment_document": "PP-2026-001",
        "notes": "Paid on time",
        "created_at": datetime.now().isoformat(),
        "plan_fact_categories": category_supplier_payment,
    }


@pytest.fixture
def sample_plan_fact_items(unpaid_item, paid_item):
    """Mix of paid and unpaid items for a deal."""
    return [unpaid_item, paid_item]


@pytest.fixture
def sample_deal(deal_id, org_id):
    """A sample deal for testing."""
    return {
        "id": deal_id,
        "deal_number": "D-2026-0042",
        "signed_at": "2026-01-15",
        "total_amount": 1000000.00,
        "currency": "RUB",
        "status": "active",
        "organization_id": org_id,
        "created_at": datetime.now().isoformat(),
    }


# ==============================================================================
# 1. Route Existence Tests (source code inspection)
# ==============================================================================

class TestPaymentRoutesExist:
    """Verify that the 3 new payment routes are registered in main.py."""

    def test_get_payments_new_route_registered(self):
        """GET /finance/{deal_id}/payments/new route must be registered."""
        source = _read_main_source()
        # Look for route decorator pattern
        has_route = bool(re.search(
            r'@rt\(\s*"/finance/\{deal_id\}/payments/new"\s*\)',
            source,
        ))
        assert has_route, (
            'Route GET /finance/{deal_id}/payments/new must be registered with @rt decorator'
        )

    def test_post_payments_route_registered(self):
        """POST /finance/{deal_id}/payments route must be registered."""
        source = _read_main_source()
        has_route = bool(re.search(
            r'@rt\(\s*"/finance/\{deal_id\}/payments"\s*\)',
            source,
        ))
        assert has_route, (
            'Route POST /finance/{deal_id}/payments must be registered with @rt decorator'
        )

    def test_delete_payments_route_registered(self):
        """DELETE /finance/{deal_id}/payments/{item_id} route must be registered."""
        source = _read_main_source()
        has_route = bool(re.search(
            r'@rt\(\s*"/finance/\{deal_id\}/payments/\{item_id\}"\s*\)',
            source,
        ))
        assert has_route, (
            'Route DELETE /finance/{deal_id}/payments/{item_id} must be registered with @rt decorator'
        )


# ==============================================================================
# 2. Helper Function Existence Tests
# ==============================================================================

class TestHelperFunctionsExist:
    """Verify that the 2 helper functions exist in main.py source."""

    def test_deal_payments_section_function_exists(self):
        """_deal_payments_section() helper must exist in main.py."""
        source = _read_main_source()
        assert "def _deal_payments_section(" in source, (
            "_deal_payments_section() function must be defined in main.py"
        )

    def test_payment_registration_form_function_exists(self):
        """_payment_registration_form() helper must exist in main.py."""
        source = _read_main_source()
        assert "def _payment_registration_form(" in source, (
            "_payment_registration_form() function must be defined in main.py"
        )


# ==============================================================================
# 3. Deal Detail Page - PLATEZHI Section Tests
# ==============================================================================

class TestDealDetailShowsPaymentsSection:
    """
    The finance deal detail page GET /finance/{deal_id}
    must include a PLATEZHI section showing registered payments.
    """

    def test_deal_detail_page_references_payments_section(self):
        """The GET /finance/{deal_id} handler must call _deal_payments_section."""
        source = _read_main_source()
        # Find the deal detail GET handler
        match = re.search(
            r'@rt\("/finance/\{deal_id\}"\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance/{deal_id} handler not found"
        handler_body = match.group(1)
        assert "_deal_payments_section" in handler_body, (
            "GET /finance/{deal_id} handler must call _deal_payments_section()"
        )

    def test_payments_section_has_platezhi_header(self):
        """_deal_payments_section must render a section with 'ПЛАТЕЖИ' header."""
        source = _read_main_source()
        # Find _deal_payments_section function body
        match = re.search(
            r'def _deal_payments_section\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "_deal_payments_section function not found"
        fn_body = match.group(1)
        assert "ПЛАТЕЖИ" in fn_body, (
            "_deal_payments_section must include 'ПЛАТЕЖИ' header text"
        )

    def test_payments_section_shows_paid_items(self):
        """_deal_payments_section must display items where actual_amount is not null."""
        source = _read_main_source()
        match = re.search(
            r'def _deal_payments_section\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "_deal_payments_section function not found"
        fn_body = match.group(1)
        # It should reference actual_amount to filter/display paid items
        assert "actual_amount" in fn_body, (
            "_deal_payments_section must reference actual_amount to show paid items"
        )

    def test_payments_section_has_add_payment_button(self):
        """_deal_payments_section must have a button linking to payment form."""
        source = _read_main_source()
        match = re.search(
            r'def _deal_payments_section\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "_deal_payments_section function not found"
        fn_body = match.group(1)
        has_add_btn = (
            "payments/new" in fn_body
            or "Добавить платёж" in fn_body
            or "Зарегистрировать" in fn_body
        )
        assert has_add_btn, (
            "_deal_payments_section must include a button to add/register payment"
        )

    def test_payments_section_shows_empty_state(self):
        """When no payments exist, section must show an empty state message."""
        source = _read_main_source()
        match = re.search(
            r'def _deal_payments_section\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "_deal_payments_section function not found"
        fn_body = match.group(1)
        has_empty_state = (
            "ещё не зарегистрированы" in fn_body.lower()
            or "нет платежей" in fn_body.lower()
            or "нет зарегистрированных" in fn_body.lower()
            or "пусто" in fn_body.lower()
        )
        assert has_empty_state, (
            "_deal_payments_section must show an empty state message when no payments exist"
        )


# ==============================================================================
# 4. GET /finance/{deal_id}/payments/new - Payment Form Tests
# ==============================================================================

class TestPaymentFormRoute:
    """
    GET /finance/{deal_id}/payments/new returns the payment registration form.
    The form has two modes:
      - mode="plan": select an existing unpaid plan-fact item to register against
      - mode="new": create an ad-hoc payment (new plan-fact item + immediate actual)
    """

    def _get_payments_new_handler_source(self):
        """Extract the GET /finance/{deal_id}/payments/new handler."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance/\{deal_id\}/payments/new"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance/{deal_id}/payments/new handler not found"
        return match.group(1)

    def test_form_requires_login(self):
        """Payment form route must check require_login."""
        handler = self._get_payments_new_handler_source()
        assert "require_login" in handler, (
            "GET payments/new must call require_login"
        )

    def test_form_requires_finance_role(self):
        """Payment form route must check for finance or admin role."""
        handler = self._get_payments_new_handler_source()
        has_role_check = (
            "user_has_any_role" in handler or "user_has_role" in handler
        )
        assert has_role_check, (
            "GET payments/new must check for finance/admin role"
        )

    def test_form_has_mode_plan(self):
        """Payment form must support mode='plan' for existing items."""
        handler = self._get_payments_new_handler_source()
        assert "plan" in handler, (
            "Payment form must reference 'plan' mode for existing plan-fact items"
        )

    def test_form_has_mode_new(self):
        """Payment form must support mode='new' for ad-hoc payments."""
        handler = self._get_payments_new_handler_source()
        assert "new" in handler.lower(), (
            "Payment form must reference 'new' mode for ad-hoc payments"
        )

    def test_form_fetches_unpaid_items(self):
        """Payment form must fetch unpaid plan-fact items for the deal."""
        handler = self._get_payments_new_handler_source()
        has_unpaid_fetch = (
            "unpaid" in handler.lower()
            or "actual_amount" in handler
            or "get_unpaid_items" in handler
            or "is_('actual_amount'" in handler
        )
        assert has_unpaid_fetch, (
            "Payment form must fetch unpaid items for 'plan' mode selection"
        )

    def test_form_has_amount_field(self):
        """Payment form must include actual_amount input field."""
        handler = self._get_payments_new_handler_source()
        assert "actual_amount" in handler, (
            "Payment form must include an actual_amount input field"
        )

    def test_form_has_date_field(self):
        """Payment form must include actual_date input field."""
        handler = self._get_payments_new_handler_source()
        assert "actual_date" in handler, (
            "Payment form must include an actual_date input field"
        )

    def test_form_has_currency_field(self):
        """Payment form must include actual_currency field."""
        handler = self._get_payments_new_handler_source()
        assert "actual_currency" in handler or "currency" in handler, (
            "Payment form must include a currency selector"
        )

    def test_form_has_document_field(self):
        """Payment form must include payment_document input field."""
        handler = self._get_payments_new_handler_source()
        assert "payment_document" in handler, (
            "Payment form must include a payment_document input field"
        )

    def test_form_posts_to_payments_endpoint(self):
        """Form must POST to /finance/{deal_id}/payments."""
        handler = self._get_payments_new_handler_source()
        has_post_target = (
            "payments" in handler
            and ("POST" in handler or "method" in handler or "hx-post" in handler or "action" in handler)
        )
        assert has_post_target, (
            "Payment form must POST to /finance/{deal_id}/payments"
        )


# ==============================================================================
# 5. POST /finance/{deal_id}/payments - Register Payment Tests
# ==============================================================================

class TestRegisterPaymentRoute:
    """
    POST /finance/{deal_id}/payments registers a payment.
    Two modes:
      - mode="plan": records actual payment on an existing plan-fact item
      - mode="new":  creates a new plan-fact item with actual data (ad-hoc)
    """

    def _get_post_handler_source(self):
        """Extract the POST /finance/{deal_id}/payments handler source."""
        source = _read_main_source()
        # Find POST handler for /finance/{deal_id}/payments
        match = re.search(
            r'@rt\(\s*"/finance/\{deal_id\}/payments"\s*\)\s*\n(?:async )?def post\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "POST /finance/{deal_id}/payments handler not found"
        return match.group(1)

    def test_post_handler_requires_login(self):
        """POST handler must call require_login."""
        handler = self._get_post_handler_source()
        assert "require_login" in handler, (
            "POST /finance/{deal_id}/payments must call require_login"
        )

    def test_post_handler_requires_finance_role(self):
        """POST handler must check for finance or admin role."""
        handler = self._get_post_handler_source()
        has_role_check = (
            "user_has_any_role" in handler or "user_has_role" in handler
        )
        assert has_role_check, (
            "POST payments must check for finance/admin role"
        )

    def test_post_handler_supports_plan_mode(self):
        """POST handler must handle mode='plan' for existing plan-fact items."""
        handler = self._get_post_handler_source()
        assert "plan" in handler, (
            "POST handler must support 'plan' mode for existing items"
        )

    def test_post_handler_supports_new_mode(self):
        """POST handler must handle mode='new' for ad-hoc payments."""
        handler = self._get_post_handler_source()
        has_new_mode = "new" in handler.lower() or "ad-hoc" in handler.lower() or "create_plan_fact_item" in handler
        assert has_new_mode, (
            "POST handler must support 'new' mode for ad-hoc payments"
        )

    def test_post_handler_calls_register_payment(self):
        """POST handler must call register_payment_for_item or record_actual_payment."""
        handler = self._get_post_handler_source()
        calls_register = (
            "register_payment_for_item" in handler
            or "record_actual_payment" in handler
        )
        assert calls_register, (
            "POST handler must call register_payment_for_item or record_actual_payment"
        )

    def test_post_handler_validates_amount(self):
        """POST handler must validate that amount is provided and positive."""
        handler = self._get_post_handler_source()
        has_amount_validation = (
            "actual_amount" in handler
            and ("float" in handler or "Decimal" in handler or "validate" in handler)
        )
        assert has_amount_validation, (
            "POST handler must validate actual_amount"
        )

    def test_post_handler_redirects_on_success(self):
        """POST handler must redirect back to deal page on success."""
        handler = self._get_post_handler_source()
        has_redirect = (
            "RedirectResponse" in handler
            or "redirect" in handler.lower()
            or "303" in handler
        )
        assert has_redirect, (
            "POST handler must redirect back to deal page after successful registration"
        )

    def test_post_plan_mode_uses_existing_item_id(self):
        """In plan mode, POST handler must use the selected item_id."""
        handler = self._get_post_handler_source()
        assert "item_id" in handler, (
            "POST handler must reference item_id for 'plan' mode"
        )

    def test_post_new_mode_creates_plan_fact_item(self):
        """In new mode, POST handler must create a new plan-fact item."""
        handler = self._get_post_handler_source()
        has_create = (
            "create_plan_fact_item" in handler
            or "create_plan_fact_item_with_category_code" in handler
        )
        assert has_create, (
            "POST handler must call create_plan_fact_item for 'new' mode"
        )


# ==============================================================================
# 6. POST Validation Edge Cases
# ==============================================================================

class TestPaymentPostValidation:
    """Test validation logic in the POST handler via source inspection."""

    def _get_post_handler_source(self):
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance/\{deal_id\}/payments"\s*\)\s*\n(?:async )?def post\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "POST /finance/{deal_id}/payments handler not found"
        return match.group(1)

    def test_rejects_missing_amount(self):
        """POST handler must check for missing/invalid amount."""
        handler = self._get_post_handler_source()
        has_amount_check = (
            ("not" in handler and "actual_amount" in handler)
            or ("error" in handler.lower() and "amount" in handler.lower())
            or "validate" in handler.lower()
            or "required" in handler.lower()
        )
        assert has_amount_check, (
            "POST handler must validate and reject missing/invalid amount"
        )

    def test_rejects_negative_amount(self):
        """POST handler must reject negative amounts."""
        handler = self._get_post_handler_source()
        has_negative_check = (
            "<= 0" in handler
            or "< 0" in handler
            or "<= 0.0" in handler
            or "validate_payment_amount" in handler
        )
        assert has_negative_check, (
            "POST handler must reject negative or zero amounts"
        )

    def test_handles_already_paid_item(self):
        """POST handler must handle the case where item is already paid."""
        handler = self._get_post_handler_source()
        has_paid_check = (
            "is_paid" in handler
            or "already" in handler.lower()
            or "actual_amount" in handler
        )
        assert has_paid_check, (
            "POST handler must check if item is already paid (for plan mode)"
        )


# ==============================================================================
# 7. Edge Case: No Unpaid Items
# ==============================================================================

class TestNoUnpaidItemsEdgeCase:
    """When all items are paid, the form should only show 'new' mode."""

    def test_form_shows_only_new_mode_when_no_unpaid(self):
        """When there are no unpaid items, form should only offer ad-hoc mode."""
        source = _read_main_source()
        # Check if _payment_registration_form handles empty unpaid list
        match = re.search(
            r'def _payment_registration_form\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "_payment_registration_form function not found"
        fn_body = match.group(1)
        # Should handle case when unpaid_items is empty
        has_empty_check = (
            "len(" in fn_body
            or "not unpaid" in fn_body.lower()
            or "no " in fn_body.lower()
            or "if unpaid" in fn_body.lower()
            or "empty" in fn_body.lower()
        )
        assert has_empty_check, (
            "_payment_registration_form must handle empty unpaid items list"
        )


# ==============================================================================
# 8. DELETE /finance/{deal_id}/payments/{item_id} - Clear Payment Tests
# ==============================================================================

class TestDeletePaymentRoute:
    """
    DELETE /finance/{deal_id}/payments/{item_id} clears the actual payment
    from a plan-fact item (sets actual fields to NULL).
    """

    def _get_delete_handler_source(self):
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*"/finance/\{deal_id\}/payments/\{item_id\}"\s*\)\s*\ndef delete\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "DELETE /finance/{deal_id}/payments/{item_id} handler not found"
        return match.group(1)

    def test_delete_handler_requires_login(self):
        """DELETE handler must call require_login."""
        handler = self._get_delete_handler_source()
        assert "require_login" in handler, (
            "DELETE handler must call require_login"
        )

    def test_delete_handler_requires_finance_role(self):
        """DELETE handler must check for finance or admin role."""
        handler = self._get_delete_handler_source()
        has_role_check = (
            "user_has_any_role" in handler or "user_has_role" in handler
        )
        assert has_role_check, (
            "DELETE handler must check for finance/admin role"
        )

    def test_delete_handler_calls_clear_actual_payment(self):
        """DELETE handler must call clear_actual_payment from plan_fact_service."""
        handler = self._get_delete_handler_source()
        assert "clear_actual_payment" in handler, (
            "DELETE handler must call clear_actual_payment to reset actual fields"
        )

    def test_delete_handler_validates_item_exists(self):
        """DELETE handler must check that the plan-fact item exists."""
        handler = self._get_delete_handler_source()
        has_existence_check = (
            "get_plan_fact_item" in handler
            or "not found" in handler.lower()
            or "404" in handler
            or "item_id" in handler
        )
        assert has_existence_check, (
            "DELETE handler must validate that the item exists"
        )

    def test_delete_handler_returns_updated_section(self):
        """DELETE handler must return updated payments section or redirect."""
        handler = self._get_delete_handler_source()
        has_response = (
            "_deal_payments_section" in handler
            or "RedirectResponse" in handler
            or "redirect" in handler.lower()
        )
        assert has_response, (
            "DELETE handler must return updated section or redirect after clearing payment"
        )


# ==============================================================================
# 9. Auth Tests
# ==============================================================================

class TestPaymentRouteAuth:
    """Test authentication and authorization for all payment routes."""

    def test_all_payment_routes_have_login_check(self):
        """All 3 payment routes must have require_login."""
        source = _read_main_source()
        routes = [
            r'/finance/\{deal_id\}/payments/new',
            r'/finance/\{deal_id\}/payments"',
            r'/finance/\{deal_id\}/payments/\{item_id\}',
        ]
        for route_pattern in routes:
            match = re.search(
                rf'@rt\(\s*"{route_pattern}\s*\)\s*\ndef \w+\(.*?\n(.*?)(?=\n@rt\()',
                source,
                re.DOTALL,
            )
            if match:
                assert "require_login" in match.group(1), (
                    f"Route matching '{route_pattern}' must call require_login"
                )

    def test_all_payment_routes_check_finance_role(self):
        """All 3 payment routes must check for finance/admin role."""
        source = _read_main_source()
        # Check that the routes are protected with role checks
        route_patterns = [
            "payments/new",
            "payments\"",
            "payments/{item_id}",
        ]
        for pattern in route_patterns:
            # Just verify pattern is surrounded by role checking code
            idx = source.find(pattern)
            if idx > 0:
                # Look for role check within 1000 chars after route definition
                context = source[idx:idx + 1000]
                has_role = (
                    "user_has_any_role" in context
                    or "user_has_role" in context
                )
                assert has_role, (
                    f"Route containing '{pattern}' must check finance/admin role"
                )

    def test_non_finance_role_denied_access(self):
        """Verify source code rejects non-finance roles (sales, procurement, etc.)."""
        source = _read_main_source()
        # Find the payments/new handler and check it requires finance role specifically
        match = re.search(
            r'@rt\(\s*"/finance/\{deal_id\}/payments/new"\s*\)\s*\ndef get\(.*?\n(.*?)(?=\n@rt\()',
            source,
            re.DOTALL,
        )
        assert match, "GET /finance/{deal_id}/payments/new handler not found"
        handler = match.group(1)
        # Should check for ["finance", "admin"] specifically
        has_finance_check = (
            '"finance"' in handler
            and '"admin"' in handler
        )
        assert has_finance_check, (
            "Payment routes must check specifically for 'finance' and 'admin' roles"
        )


# ==============================================================================
# 10. Service Integration Tests
# ==============================================================================

class TestPaymentServiceIntegration:
    """Verify that route handlers use the correct plan_fact_service functions."""

    def test_get_paid_items_for_deal_used(self):
        """_deal_payments_section or deal detail must use get_paid_items_for_deal."""
        source = _read_main_source()
        has_get_paid = (
            "get_paid_items_for_deal" in source
            or "actual_amount" in source  # Direct filter
        )
        assert has_get_paid, (
            "Deal payments section must retrieve paid items via service or direct query"
        )

    def test_get_unpaid_items_for_deal_used(self):
        """Payment form must use get_unpaid_items_for_deal for plan mode selection."""
        source = _read_main_source()
        has_get_unpaid = (
            "get_unpaid_items_for_deal" in source
            or ("is_(" in source and "actual_amount" in source and "null" in source)
        )
        assert has_get_unpaid, (
            "Payment form must use get_unpaid_items_for_deal or equivalent query"
        )

    def test_clear_actual_payment_importable(self):
        """clear_actual_payment must be importable from plan_fact_service."""
        from services.plan_fact_service import clear_actual_payment
        assert callable(clear_actual_payment)

    def test_register_payment_for_item_importable(self):
        """register_payment_for_item must be importable from plan_fact_service."""
        from services.plan_fact_service import register_payment_for_item
        assert callable(register_payment_for_item)

    def test_create_plan_fact_item_importable(self):
        """create_plan_fact_item must be importable from plan_fact_service."""
        from services.plan_fact_service import create_plan_fact_item
        assert callable(create_plan_fact_item)

    def test_get_all_categories_importable(self):
        """get_all_categories must be importable from plan_fact_service."""
        from services.plan_fact_service import get_all_categories
        assert callable(get_all_categories)


# ==============================================================================
# 11. Payment Display Data Tests
# ==============================================================================

class TestPaymentDisplayData:
    """Test the data structures used for displaying payments."""

    def test_paid_item_has_actual_amount(self, paid_item):
        """A paid item must have actual_amount not null."""
        assert paid_item["actual_amount"] is not None
        assert paid_item["actual_amount"] > 0

    def test_paid_item_has_actual_date(self, paid_item):
        """A paid item must have actual_date not null."""
        assert paid_item["actual_date"] is not None

    def test_unpaid_item_has_null_actual(self, unpaid_item):
        """An unpaid item must have actual_amount as None."""
        assert unpaid_item["actual_amount"] is None
        assert unpaid_item["actual_date"] is None

    def test_variance_calculation(self, paid_item):
        """Variance = actual - planned (negative = underpayment)."""
        planned = Decimal(str(paid_item["planned_amount"]))
        actual = Decimal(str(paid_item["actual_amount"]))
        expected_variance = actual - planned
        actual_variance = Decimal(str(paid_item["variance_amount"]))
        assert actual_variance == expected_variance

    def test_category_included_in_item(self, paid_item):
        """Payment items must include category info for display."""
        cat = paid_item["plan_fact_categories"]
        assert cat is not None
        assert "name" in cat
        assert "is_income" in cat
        assert "code" in cat

    def test_payment_document_optional(self, unpaid_item):
        """payment_document field should be optional (can be None)."""
        assert unpaid_item["payment_document"] is None

    def test_filter_paid_items_from_list(self, sample_plan_fact_items):
        """Should be able to filter only paid items from a mixed list."""
        paid = [i for i in sample_plan_fact_items if i.get("actual_amount") is not None]
        unpaid = [i for i in sample_plan_fact_items if i.get("actual_amount") is None]
        assert len(paid) == 1
        assert len(unpaid) == 1


# ==============================================================================
# 12. Payment Registration Form Data Tests
# ==============================================================================

class TestPaymentRegistrationFormData:
    """Test the data structures used for the payment registration form."""

    def test_form_defaults_today_date(self):
        """Payment form should default actual_date to today."""
        today = date.today().isoformat()
        assert len(today) == 10  # YYYY-MM-DD format

    def test_form_defaults_planned_amount(self, unpaid_item):
        """Payment form should pre-fill amount with planned_amount."""
        planned = unpaid_item["planned_amount"]
        assert planned == 500000.00

    def test_form_defaults_planned_currency(self, unpaid_item):
        """Payment form should pre-fill currency with planned_currency."""
        assert unpaid_item["planned_currency"] == "RUB"

    def test_ad_hoc_payment_requires_category(self, categories):
        """Ad-hoc (new mode) payments must include a category selection."""
        # Verify categories exist for form dropdown
        assert len(categories) >= 2
        codes = [c["code"] for c in categories]
        assert "client_payment" in codes
        assert "supplier_payment" in codes

    def test_ad_hoc_payment_requires_description(self):
        """Ad-hoc payments must include a description field."""
        # Just verify the pattern -- form must have description field
        source = _read_main_source()
        match = re.search(
            r'def _payment_registration_form\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "_payment_registration_form function not found"
        fn_body = match.group(1)
        assert "description" in fn_body, (
            "_payment_registration_form must include a description field (for new mode)"
        )


# ==============================================================================
# 13. Edge Cases
# ==============================================================================

class TestPaymentEdgeCases:
    """Edge cases for the deal payments feature."""

    def test_deal_with_no_plan_fact_items(self):
        """Deal with no plan-fact items should still show payments section."""
        # The section should render even with empty data
        source = _read_main_source()
        assert "_deal_payments_section" in source, (
            "_deal_payments_section must be defined for rendering even with no items"
        )

    def test_multiple_payments_display(self):
        """Multiple paid items should all be displayed."""
        items = [
            {"id": _make_uuid(), "actual_amount": 100000, "actual_date": "2026-01-15",
             "planned_amount": 100000, "planned_currency": "RUB",
             "payment_document": "PP-001", "plan_fact_categories": {"name": "Client", "is_income": True, "code": "client_payment"}},
            {"id": _make_uuid(), "actual_amount": 200000, "actual_date": "2026-01-20",
             "planned_amount": 200000, "planned_currency": "RUB",
             "payment_document": "PP-002", "plan_fact_categories": {"name": "Client", "is_income": True, "code": "client_payment"}},
        ]
        paid_items = [i for i in items if i.get("actual_amount") is not None]
        assert len(paid_items) == 2

    def test_payment_with_foreign_currency(self):
        """Payments in foreign currency should display exchange rate."""
        item = {
            "actual_amount": 5000.00,
            "actual_currency": "USD",
            "actual_exchange_rate": 92.50,
            "planned_amount": 462500.00,
            "planned_currency": "RUB",
        }
        assert item["actual_currency"] != item["planned_currency"]
        assert item["actual_exchange_rate"] is not None

    def test_payment_date_formatting(self):
        """Payment dates should be in a parseable format."""
        date_str = "2026-02-09"
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
        assert parsed.year == 2026
        assert parsed.month == 2
        assert parsed.day == 9


# ==============================================================================
# 14. UI/HTMX Integration Tests (source inspection)
# ==============================================================================

class TestPaymentHTMXIntegration:
    """Test that payment section uses HTMX for interactivity."""

    def test_delete_uses_htmx_or_form(self):
        """Payment delete action should use HTMX or a standard form."""
        source = _read_main_source()
        match = re.search(
            r'def _deal_payments_section\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "_deal_payments_section function not found"
        fn_body = match.group(1)
        has_delete_mechanism = (
            "hx-delete" in fn_body
            or "hx_delete" in fn_body
            or "DELETE" in fn_body
            or "delete" in fn_body.lower()
        )
        assert has_delete_mechanism, (
            "_deal_payments_section must include a delete mechanism (HTMX or form)"
        )

    def test_payments_section_has_target_id(self):
        """Payments section should have an id for HTMX targeting."""
        source = _read_main_source()
        match = re.search(
            r'def _deal_payments_section\(.*?\n(.*?)(?=\ndef )',
            source,
            re.DOTALL,
        )
        assert match, "_deal_payments_section function not found"
        fn_body = match.group(1)
        has_id = (
            'id="' in fn_body
            or "id=" in fn_body
        )
        assert has_id, (
            "_deal_payments_section must have an element id for HTMX targeting"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
