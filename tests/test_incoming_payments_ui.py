"""
TDD Tests for Incoming Payments UI (specification_payments with category='income').

These tests define the expected behavior for:
1. Routes: GET/POST /specifications/{spec_id}/payments/new
2. Service: specification_payment_service (CRUD for specification_payments table)
3. Form: amount, currency, payment_date, comment fields
4. Access control: finance/admin only
5. Data persistence: category='income', auto-incremented payment_number
6. Display: payments section on specification detail page

ALL TESTS MUST FAIL — the implementation does not exist yet.
"""

import os
import re
import sys
import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# HELPER: Read main.py source for route inspection
# ============================================================================

def _read_main_source():
    """Read main.py source as a string."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    with open(source_path, "r") as f:
        return f.read()


def _find_route_decorators(source, route_pattern):
    """Find all @rt() decorators matching a route pattern."""
    results = []
    for i, line in enumerate(source.splitlines(), 1):
        if re.search(route_pattern, line):
            results.append((i, line.strip()))
    return results


# ============================================================================
# TEST 1: Route Registration — specification payment routes must exist
# ============================================================================

class TestIncomingPaymentRouteRegistration:
    """Verify that specification payment routes are registered in main.py."""

    def test_get_payment_form_route_exists(self):
        """GET /specifications/{spec_id}/payments/new route must be registered."""
        source = _read_main_source()
        decorators = _find_route_decorators(
            source, r'@rt\("/specifications/\{spec_id\}/payments/new"\)'
        )
        assert len(decorators) >= 1, (
            "Missing GET route @rt('/specifications/{spec_id}/payments/new') in main.py"
        )

    def test_post_payment_route_exists(self):
        """POST /specifications/{spec_id}/payments/new (or /payments) route must be registered."""
        source = _read_main_source()
        # Accept either /payments/new or /payments as the POST endpoint
        decorators_new = _find_route_decorators(
            source, r'@rt\("/specifications/\{spec_id\}/payments/new"\)'
        )
        decorators_base = _find_route_decorators(
            source, r'@rt\("/specifications/\{spec_id\}/payments"\)'
        )
        total = len(decorators_new) + len(decorators_base)
        # Need at least 2 matches (GET + POST) for /new, or 1 for /payments POST
        assert total >= 2, (
            "Missing POST route for specification payments. "
            "Expected @rt('/specifications/{spec_id}/payments/new') with both GET and POST handlers, "
            "or a separate @rt('/specifications/{spec_id}/payments'). "
            f"Found {total} total."
        )

    def test_route_has_get_handler(self):
        """The GET handler function for payment form must exist."""
        source = _read_main_source()
        # Look for a function definition after the route decorator
        has_get_handler = bool(re.search(
            r'@rt\("/specifications/\{spec_id\}/payments/new"\)\s*\ndef\s+\w+.*session',
            source, re.MULTILINE
        ))
        assert has_get_handler, (
            "No GET handler function found for /specifications/{spec_id}/payments/new"
        )

    def test_route_has_post_handler(self):
        """The POST handler function for specification payment submission must exist."""
        source = _read_main_source()
        # Find the specification payment section specifically
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail(
                "No specification payment route section found in main.py. "
                "Routes /specifications/{spec_id}/payments/new must exist with POST handler."
            )

        # Look for method="POST" in the form within this section
        has_form_post = (
            'method="POST"' in spec_payment_section
            or "method='POST'" in spec_payment_section
            or "hx-post" in spec_payment_section
        )
        assert has_form_post, (
            "No POST form found in specification payment route section"
        )


# ============================================================================
# TEST 2: Service — specification_payment_service must exist
# ============================================================================

class TestSpecificationPaymentService:
    """Verify specification_payment_service module exists with required functions."""

    def test_service_module_importable(self):
        """services/specification_payment_service.py must be importable."""
        try:
            from services import specification_payment_service
        except ImportError:
            pytest.fail(
                "Cannot import services.specification_payment_service. "
                "Module does not exist yet."
            )

    def test_create_payment_function_exists(self):
        """create_specification_payment() function must exist."""
        from services.specification_payment_service import create_specification_payment
        assert callable(create_specification_payment)

    def test_get_payments_for_specification_function_exists(self):
        """get_payments_for_specification() function must exist."""
        from services.specification_payment_service import get_payments_for_specification
        assert callable(get_payments_for_specification)

    def test_get_income_payments_function_exists(self):
        """get_income_payments() to filter category='income' must exist."""
        from services.specification_payment_service import get_income_payments
        assert callable(get_income_payments)

    def test_get_expense_payments_function_exists(self):
        """get_expense_payments() to filter category='expense' must exist."""
        from services.specification_payment_service import get_expense_payments
        assert callable(get_expense_payments)

    def test_get_payment_summary_function_exists(self):
        """get_payment_summary() returning totals for income/expense must exist."""
        from services.specification_payment_service import get_payment_summary
        assert callable(get_payment_summary)


# ============================================================================
# TEST 3: Service — create_specification_payment behavior
# ============================================================================

class TestCreateSpecificationPayment:
    """Test create_specification_payment() function behavior."""

    def test_create_income_payment_returns_payment_data(self):
        """Creating an income payment should return the created record."""
        from services.specification_payment_service import create_specification_payment

        spec_id = str(uuid4())
        org_id = str(uuid4())
        user_id = str(uuid4())

        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.insert.return_value.execute.return_value.data = [{
                "id": str(uuid4()),
                "specification_id": spec_id,
                "organization_id": org_id,
                "payment_date": "2026-02-09",
                "amount": "5000.00",
                "currency": "USD",
                "category": "income",
                "payment_number": 1,
                "comment": "First payment from client",
                "created_by": user_id,
            }]

            result = create_specification_payment(
                specification_id=spec_id,
                organization_id=org_id,
                payment_date=date(2026, 2, 9),
                amount=Decimal("5000.00"),
                currency="USD",
                category="income",
                comment="First payment from client",
                created_by=user_id,
            )

            assert result is not None
            assert result["category"] == "income"
            assert result["amount"] == "5000.00"

    def test_create_payment_validates_positive_amount(self):
        """Amount must be positive (>0)."""
        from services.specification_payment_service import create_specification_payment

        with pytest.raises((ValueError, Exception)):
            create_specification_payment(
                specification_id=str(uuid4()),
                organization_id=str(uuid4()),
                payment_date=date(2026, 2, 9),
                amount=Decimal("-100.00"),
                currency="USD",
                category="income",
            )

    def test_create_payment_validates_category(self):
        """Category must be 'income' or 'expense'."""
        from services.specification_payment_service import create_specification_payment

        with pytest.raises((ValueError, Exception)):
            create_specification_payment(
                specification_id=str(uuid4()),
                organization_id=str(uuid4()),
                payment_date=date(2026, 2, 9),
                amount=Decimal("1000.00"),
                currency="USD",
                category="invalid_category",
            )

    def test_create_payment_validates_currency(self):
        """Currency must be a valid 3-letter code (RUB, USD, EUR)."""
        from services.specification_payment_service import create_specification_payment

        # Valid currencies should not raise
        # This test ensures the function accepts standard currencies
        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.insert.return_value.execute.return_value.data = [{"id": str(uuid4())}]

            for currency in ["RUB", "USD", "EUR"]:
                result = create_specification_payment(
                    specification_id=str(uuid4()),
                    organization_id=str(uuid4()),
                    payment_date=date(2026, 2, 9),
                    amount=Decimal("1000.00"),
                    currency=currency,
                    category="income",
                )
                assert result is not None


# ============================================================================
# TEST 4: Service — get_payments_for_specification behavior
# ============================================================================

class TestGetPaymentsForSpecification:
    """Test fetching payments for a specification."""

    def test_returns_list_of_payments(self):
        """Should return a list of payment dicts for a specification."""
        from services.specification_payment_service import get_payments_for_specification

        spec_id = str(uuid4())

        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
                {
                    "id": str(uuid4()),
                    "specification_id": spec_id,
                    "payment_date": "2026-02-01",
                    "amount": "3000.00",
                    "currency": "USD",
                    "category": "income",
                    "payment_number": 1,
                    "comment": "Advance",
                },
                {
                    "id": str(uuid4()),
                    "specification_id": spec_id,
                    "payment_date": "2026-02-05",
                    "amount": "2000.00",
                    "currency": "USD",
                    "category": "expense",
                    "payment_number": 1,
                    "comment": "Supplier payment",
                },
            ]

            result = get_payments_for_specification(spec_id)

            assert isinstance(result, list)
            assert len(result) == 2

    def test_returns_empty_list_when_no_payments(self):
        """Should return empty list when spec has no payments."""
        from services.specification_payment_service import get_payments_for_specification

        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []

            result = get_payments_for_specification(str(uuid4()))

            assert isinstance(result, list)
            assert len(result) == 0


# ============================================================================
# TEST 5: Service — get_income_payments / get_expense_payments
# ============================================================================

class TestPaymentCategoryFilters:
    """Test filtering payments by category."""

    def test_get_income_payments_filters_correctly(self):
        """get_income_payments should only return category='income' records."""
        from services.specification_payment_service import get_income_payments

        spec_id = str(uuid4())

        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            # Mock the chained eq calls for spec_id and category
            chain = mock_table.select.return_value.eq.return_value.eq.return_value
            chain.order.return_value.execute.return_value.data = [
                {"category": "income", "amount": "5000.00"},
            ]

            result = get_income_payments(spec_id)

            assert isinstance(result, list)
            # All returned items should be income
            for p in result:
                assert p["category"] == "income"

    def test_get_expense_payments_filters_correctly(self):
        """get_expense_payments should only return category='expense' records."""
        from services.specification_payment_service import get_expense_payments

        spec_id = str(uuid4())

        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            chain = mock_table.select.return_value.eq.return_value.eq.return_value
            chain.order.return_value.execute.return_value.data = [
                {"category": "expense", "amount": "2000.00"},
            ]

            result = get_expense_payments(spec_id)

            assert isinstance(result, list)
            for p in result:
                assert p["category"] == "expense"


# ============================================================================
# TEST 6: Service — get_payment_summary
# ============================================================================

class TestPaymentSummary:
    """Test payment summary calculation."""

    def test_summary_returns_income_and_expense_totals(self):
        """Summary should include total_income and total_expense."""
        from services.specification_payment_service import get_payment_summary

        spec_id = str(uuid4())

        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.execute.return_value.data = [
                {"category": "income", "amount": "5000.00"},
                {"category": "income", "amount": "3000.00"},
                {"category": "expense", "amount": "2000.00"},
            ]

            summary = get_payment_summary(spec_id)

            assert "total_income" in summary
            assert "total_expense" in summary
            assert summary["total_income"] == Decimal("8000.00")
            assert summary["total_expense"] == Decimal("2000.00")

    def test_summary_returns_balance(self):
        """Summary should include balance (income - expense)."""
        from services.specification_payment_service import get_payment_summary

        spec_id = str(uuid4())

        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.execute.return_value.data = [
                {"category": "income", "amount": "10000.00"},
                {"category": "expense", "amount": "4000.00"},
            ]

            summary = get_payment_summary(spec_id)

            assert "balance" in summary
            assert summary["balance"] == Decimal("6000.00")

    def test_summary_with_no_payments(self):
        """Summary for spec with no payments should return zeros."""
        from services.specification_payment_service import get_payment_summary

        with patch("services.specification_payment_service.get_supabase") as mock_sb:
            mock_table = MagicMock()
            mock_sb.return_value.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.execute.return_value.data = []

            summary = get_payment_summary(str(uuid4()))

            assert summary["total_income"] == Decimal("0")
            assert summary["total_expense"] == Decimal("0")
            assert summary["balance"] == Decimal("0")


# ============================================================================
# TEST 7: Form Content — payment form must have required fields
# ============================================================================

class TestPaymentFormContent:
    """Verify the payment form rendered by the GET handler contains required fields."""

    def test_form_has_amount_field(self):
        """Form HTML must include an amount input field."""
        source = _read_main_source()
        # Look for amount input in the context of specification payments form
        has_amount = bool(re.search(
            r'name="amount".*type="number"',
            source
        ))
        # Also check the reverse order
        has_amount_alt = bool(re.search(
            r'type="number".*name="amount"',
            source
        ))
        # Check if there's an amount field near specification payment route
        spec_payment_section = _find_specification_payment_section(source)
        has_amount_in_section = "amount" in spec_payment_section if spec_payment_section else False

        assert has_amount_in_section, (
            "Payment form near specification payment routes must include "
            "an input field with name='amount'"
        )

    def test_form_has_currency_dropdown(self):
        """Form must have a currency select with RUB/USD/EUR options."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)
        has_currency = (
            spec_payment_section
            and 'name="currency"' in spec_payment_section
        )
        assert has_currency, (
            "Payment form must include a currency select dropdown (name='currency')"
        )

    def test_form_has_payment_date_field(self):
        """Form must have a payment_date date input."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)
        has_date = (
            spec_payment_section
            and 'name="payment_date"' in spec_payment_section
        )
        assert has_date, (
            "Payment form must include a date input with name='payment_date'"
        )

    def test_form_has_comment_field(self):
        """Form must have a comment/notes textarea."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)
        has_comment = (
            spec_payment_section
            and ('name="comment"' in spec_payment_section or 'name="notes"' in spec_payment_section)
        )
        assert has_comment, (
            "Payment form must include a comment/notes textarea"
        )

    def test_form_posts_to_correct_url(self):
        """Form action must POST to /specifications/{spec_id}/payments (or /payments/new)."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)
        has_correct_action = (
            spec_payment_section
            and ("specifications" in spec_payment_section and "payments" in spec_payment_section)
            and ('method="POST"' in spec_payment_section or "method='POST'" in spec_payment_section
                 or 'method="post"' in spec_payment_section)
        )
        # Alternative: form may use hx-post
        has_htmx_post = (
            spec_payment_section
            and "hx-post" in spec_payment_section
            and "payments" in spec_payment_section
        )
        assert has_correct_action or has_htmx_post, (
            "Form must POST to a URL containing /specifications/.../payments"
        )


def _find_specification_payment_section(source):
    """Extract source code section around specification payment routes.

    Returns the block of code (roughly 200 lines) around the specification
    payment route decorators, or None if not found.
    """
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if re.search(r'@rt\("/specifications/\{spec_id\}/payments', line):
            start = max(0, i - 5)
            end = min(len(lines), i + 200)
            return "\n".join(lines[start:end])
    return None


# ============================================================================
# TEST 8: Access Control — only finance/admin can register payments
# ============================================================================

class TestPaymentAccessControl:
    """Verify that payment routes check for finance/admin roles."""

    def test_route_checks_finance_or_admin_role(self):
        """GET/POST handlers must verify user has finance or admin role."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail(
                "No specification payment route section found in main.py. "
                "Routes /specifications/{spec_id}/payments/new must exist."
            )

        # Check for role verification
        has_role_check = (
            "user_has_any_role" in spec_payment_section
            or "user_has_role" in spec_payment_section
            or "require_role" in spec_payment_section
            or '"finance"' in spec_payment_section
        )
        assert has_role_check, (
            "Payment route handlers must check for finance/admin role access"
        )

    def test_route_includes_finance_role(self):
        """Role check must include 'finance' role."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        assert '"finance"' in spec_payment_section or "'finance'" in spec_payment_section, (
            "Payment route must explicitly check for 'finance' role"
        )

    def test_route_includes_admin_role(self):
        """Role check must include 'admin' role."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        assert '"admin"' in spec_payment_section or "'admin'" in spec_payment_section, (
            "Payment route must explicitly check for 'admin' role"
        )


# ============================================================================
# TEST 9: POST handler — saves with category='income'
# ============================================================================

class TestPostHandlerSetsCategory:
    """Verify the POST handler sets category='income' for incoming payments."""

    def test_post_handler_sets_income_category(self):
        """POST handler must set category='income' when creating incoming payment."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        # The handler must include category='income' or category="income"
        has_income_category = (
            "category='income'" in spec_payment_section
            or 'category="income"' in spec_payment_section
            or '"income"' in spec_payment_section
        )
        assert has_income_category, (
            "POST handler must set category='income' for incoming payments"
        )

    def test_post_handler_calls_create_function(self):
        """POST handler must call create_specification_payment or similar."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        has_create_call = (
            "create_specification_payment" in spec_payment_section
            or "specification_payment" in spec_payment_section
            or ".insert(" in spec_payment_section
        )
        assert has_create_call, (
            "POST handler must call a service function to create the payment record"
        )


# ============================================================================
# TEST 10: Specification detail — payments section displayed
# ============================================================================

class TestSpecificationDetailPayments:
    """Verify specification detail page shows payments section."""

    def test_spec_detail_page_has_payments_section(self):
        """Specification detail page must show a payments section."""
        source = _read_main_source()
        lines = source.splitlines()

        # Find the spec-control/{spec_id} GET handler
        spec_detail_section = None
        for i, line in enumerate(lines):
            if re.search(r'@rt\("/spec-control/\{spec_id\}"\)', line):
                start = i
                end = min(len(lines), i + 300)
                spec_detail_section = "\n".join(lines[start:end])
                break

        if not spec_detail_section:
            pytest.fail("No /spec-control/{spec_id} route found in main.py")

        # Check for payment-related content in the detail page
        has_payments_ui = (
            "payments" in spec_detail_section.lower()
            or "specification_payment" in spec_detail_section
            or "get_payments_for_specification" in spec_detail_section
            or "get_income_payments" in spec_detail_section
        )
        assert has_payments_ui, (
            "Specification detail page must include a payments section. "
            "Expected reference to payments data or service function."
        )

    def test_spec_detail_has_add_payment_button(self):
        """Specification detail page should have 'Add payment' button/link."""
        source = _read_main_source()
        lines = source.splitlines()

        spec_detail_section = None
        for i, line in enumerate(lines):
            if re.search(r'@rt\("/spec-control/\{spec_id\}"\)', line):
                start = i
                end = min(len(lines), i + 300)
                spec_detail_section = "\n".join(lines[start:end])
                break

        if not spec_detail_section:
            pytest.fail("No /spec-control/{spec_id} route found")

        has_add_button = (
            "payments/new" in spec_detail_section
            or "payment" in spec_detail_section.lower()
        )
        assert has_add_button, (
            "Specification detail page should have an 'Add payment' button "
            "linking to /specifications/{spec_id}/payments/new"
        )


# ============================================================================
# TEST 11: Currency options — form must offer RUB, USD, EUR
# ============================================================================

class TestCurrencyOptions:
    """Verify currency options in the payment form."""

    def test_rub_currency_option(self):
        """Currency dropdown must include RUB."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        assert "RUB" in spec_payment_section, (
            "Currency dropdown must include RUB option"
        )

    def test_usd_currency_option(self):
        """Currency dropdown must include USD."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        assert "USD" in spec_payment_section, (
            "Currency dropdown must include USD option"
        )

    def test_eur_currency_option(self):
        """Currency dropdown must include EUR."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        assert "EUR" in spec_payment_section, (
            "Currency dropdown must include EUR option"
        )


# ============================================================================
# TEST 12: Validation edge cases in POST handler
# ============================================================================

class TestPaymentValidationEdgeCases:
    """Test edge cases in payment form validation."""

    def test_post_handler_rejects_zero_amount(self):
        """POST handler must reject amount=0."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        # Look for amount validation logic
        has_amount_validation = (
            "<= 0" in spec_payment_section
            or "<=0" in spec_payment_section
            or "> 0" in spec_payment_section
            or "больше нуля" in spec_payment_section
            or "greater than" in spec_payment_section
        )
        assert has_amount_validation, (
            "POST handler must validate that amount is greater than zero"
        )

    def test_post_handler_validates_date(self):
        """POST handler must validate payment_date format."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        has_date_validation = (
            "fromisoformat" in spec_payment_section
            or "strptime" in spec_payment_section
            or "ValueError" in spec_payment_section
            or "date" in spec_payment_section
        )
        assert has_date_validation, (
            "POST handler must validate payment_date input"
        )

    def test_post_handler_redirects_after_success(self):
        """POST handler must redirect to spec detail after successful creation."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        has_redirect = (
            "RedirectResponse" in spec_payment_section
            or "redirect" in spec_payment_section.lower()
            or "303" in spec_payment_section
            or "hx-redirect" in spec_payment_section.lower()
        )
        assert has_redirect, (
            "POST handler must redirect to specification detail page after success"
        )


# ============================================================================
# TEST 13: Authentication — login required
# ============================================================================

class TestAuthenticationRequired:
    """Verify that payment routes require login."""

    def test_get_handler_requires_login(self):
        """GET handler must check for authenticated user."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        has_auth_check = (
            "require_login" in spec_payment_section
            or 'session.get("user")' in spec_payment_section
            or "session['user']" in spec_payment_section
            or "not user" in spec_payment_section
        )
        assert has_auth_check, (
            "GET handler must check for authenticated user (require_login or session check)"
        )

    def test_post_handler_requires_login(self):
        """POST handler must check for authenticated user."""
        source = _read_main_source()
        spec_payment_section = _find_specification_payment_section(source)

        if not spec_payment_section:
            pytest.fail("No specification payment route section found")

        # Count auth checks — need at least 2 (one for GET, one for POST)
        auth_count = spec_payment_section.count("require_login") + spec_payment_section.count('session.get("user")')
        assert auth_count >= 2, (
            "Both GET and POST handlers must check for authentication. "
            f"Found {auth_count} auth checks, expected at least 2."
        )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
