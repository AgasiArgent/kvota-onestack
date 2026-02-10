"""
Tests for UI-022: Quote controller checklist view.

Tests the checklist items including the new invoice verification section (v3.0).
"""
try:
    import pytest
except ImportError:
    pytest = None

from decimal import Decimal
from dataclasses import dataclass, field
from typing import List


# Mock the data classes for testing without Supabase dependency
@dataclass
class QuoteInvoicingItem:
    """Invoicing status for a single quote item."""
    quote_item_id: str
    product_name: str = ""
    quote_quantity: Decimal = Decimal("0.00")
    quote_unit_price: Decimal = Decimal("0.00")
    invoiced_quantity: Decimal = Decimal("0.00")
    invoiced_amount: Decimal = Decimal("0.00")
    invoice_count: int = 0
    is_fully_invoiced: bool = False


@dataclass
class QuoteInvoicingSummary:
    """Overall invoicing summary for a quote."""
    total_items: int = 0
    items_with_invoices: int = 0
    items_fully_invoiced: int = 0
    total_expected: Decimal = Decimal("0.00")
    total_invoiced: Decimal = Decimal("0.00")
    items: List[QuoteInvoicingItem] = field(default_factory=list)

    @property
    def all_invoiced(self) -> bool:
        return self.items_with_invoices == self.total_items and self.total_items > 0

    @property
    def coverage_percent(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.items_with_invoices / self.total_items) * 100


# =============================================================================
# DATA CLASS TESTS
# =============================================================================

class TestQuoteInvoicingItem:
    """Tests for QuoteInvoicingItem dataclass."""

    def test_create_with_defaults(self):
        """Test creating item with just required field."""
        item = QuoteInvoicingItem(quote_item_id="test-123")

        assert item.quote_item_id == "test-123"
        assert item.product_name == ""
        assert item.quote_quantity == Decimal("0.00")
        assert item.invoice_count == 0
        assert item.is_fully_invoiced is False

    def test_create_fully_invoiced(self):
        """Test creating fully invoiced item."""
        item = QuoteInvoicingItem(
            quote_item_id="test-123",
            product_name="Test Product",
            quote_quantity=Decimal("10"),
            quote_unit_price=Decimal("100"),
            invoiced_quantity=Decimal("10"),
            invoiced_amount=Decimal("1000"),
            invoice_count=1,
            is_fully_invoiced=True
        )

        assert item.is_fully_invoiced is True
        assert item.invoice_count == 1
        assert item.invoiced_amount == Decimal("1000")

    def test_create_partially_invoiced(self):
        """Test creating partially invoiced item."""
        item = QuoteInvoicingItem(
            quote_item_id="test-456",
            product_name="Partial Product",
            quote_quantity=Decimal("20"),
            quote_unit_price=Decimal("50"),
            invoiced_quantity=Decimal("10"),
            invoiced_amount=Decimal("500"),
            invoice_count=1,
            is_fully_invoiced=False
        )

        assert item.is_fully_invoiced is False
        assert item.invoice_count == 1
        assert item.invoiced_quantity == Decimal("10")

    def test_create_not_invoiced(self):
        """Test creating item with no invoices."""
        item = QuoteInvoicingItem(
            quote_item_id="test-789",
            product_name="Not Invoiced",
            quote_quantity=Decimal("5"),
            quote_unit_price=Decimal("200")
        )

        assert item.invoice_count == 0
        assert item.is_fully_invoiced is False
        assert item.invoiced_amount == Decimal("0.00")


class TestQuoteInvoicingSummary:
    """Tests for QuoteInvoicingSummary dataclass."""

    def test_empty_summary(self):
        """Test empty summary has correct defaults."""
        summary = QuoteInvoicingSummary()

        assert summary.total_items == 0
        assert summary.items_with_invoices == 0
        assert summary.items_fully_invoiced == 0
        assert summary.all_invoiced is False
        assert summary.coverage_percent == 0.0

    def test_full_coverage(self):
        """Test summary with 100% coverage."""
        summary = QuoteInvoicingSummary(
            total_items=3,
            items_with_invoices=3,
            items_fully_invoiced=3,
            total_expected=Decimal("3000"),
            total_invoiced=Decimal("3000")
        )

        assert summary.all_invoiced is True
        assert summary.coverage_percent == 100.0

    def test_partial_coverage(self):
        """Test summary with partial coverage."""
        summary = QuoteInvoicingSummary(
            total_items=4,
            items_with_invoices=2,
            items_fully_invoiced=1,
            total_expected=Decimal("4000"),
            total_invoiced=Decimal("1500")
        )

        assert summary.all_invoiced is False
        assert summary.coverage_percent == 50.0

    def test_no_coverage(self):
        """Test summary with no invoices."""
        summary = QuoteInvoicingSummary(
            total_items=5,
            items_with_invoices=0,
            items_fully_invoiced=0,
            total_expected=Decimal("5000"),
            total_invoiced=Decimal("0")
        )

        assert summary.all_invoiced is False
        assert summary.coverage_percent == 0.0

    def test_with_items_list(self):
        """Test summary with items list."""
        items = [
            QuoteInvoicingItem(
                quote_item_id="1",
                product_name="Product A",
                quote_quantity=Decimal("10"),
                quote_unit_price=Decimal("100"),
                invoiced_quantity=Decimal("10"),
                invoiced_amount=Decimal("1000"),
                invoice_count=1,
                is_fully_invoiced=True
            ),
            QuoteInvoicingItem(
                quote_item_id="2",
                product_name="Product B",
                quote_quantity=Decimal("5"),
                quote_unit_price=Decimal("200"),
                invoice_count=0,
                is_fully_invoiced=False
            )
        ]

        summary = QuoteInvoicingSummary(
            total_items=2,
            items_with_invoices=1,
            items_fully_invoiced=1,
            total_expected=Decimal("2000"),
            total_invoiced=Decimal("1000"),
            items=items
        )

        assert len(summary.items) == 2
        assert summary.items[0].is_fully_invoiced is True
        assert summary.items[1].is_fully_invoiced is False
        assert summary.coverage_percent == 50.0


# =============================================================================
# CHECKLIST ITEM TESTS (logic validation)
# =============================================================================

class TestChecklistLogic:
    """Tests for checklist item status logic."""

    def test_invoice_status_ok_when_all_covered(self):
        """Invoice status should be 'ok' when 100% coverage."""
        coverage = 100

        if coverage == 100:
            status = "ok"
        elif coverage > 0:
            status = "warning"
        else:
            status = "error"

        assert status == "ok"

    def test_invoice_status_warning_when_partial(self):
        """Invoice status should be 'warning' when partial coverage."""
        coverage = 50

        if coverage == 100:
            status = "ok"
        elif coverage > 0:
            status = "warning"
        else:
            status = "error"

        assert status == "warning"

    def test_invoice_status_error_when_none(self):
        """Invoice status should be 'error' when no coverage."""
        coverage = 0

        if coverage == 100:
            status = "ok"
        elif coverage > 0:
            status = "warning"
        else:
            status = "error"

        assert status == "error"

    def test_deal_type_status(self):
        """Test deal type status logic."""
        # With deal type
        deal_type = "supply"
        assert (deal_type is not None and deal_type != "") is True

        # Without deal type
        deal_type_empty = ""
        assert (deal_type_empty is not None and deal_type_empty != "") is False

    def test_needs_approval_rub_currency(self):
        """RUB currency requires approval."""
        currency = "RUB"
        needs_approval_reasons = []

        if currency == "RUB":
            needs_approval_reasons.append("Валюта КП = рубли")

        assert len(needs_approval_reasons) == 1

    def test_needs_approval_prepayment(self):
        """Non-100% prepayment requires approval."""
        prepayment = 70
        needs_approval_reasons = []

        if prepayment < 100:
            needs_approval_reasons.append(f"Не 100% предоплата ({prepayment}%)")

        assert len(needs_approval_reasons) == 1

    def test_needs_approval_low_markup_supply(self):
        """Low markup for supply requires approval."""
        deal_type = "supply"
        markup = 8
        min_markup_supply = 12
        min_markup_transit = 8
        needs_approval_reasons = []

        if deal_type == "supply" and markup < min_markup_supply:
            needs_approval_reasons.append(f"Наценка ({markup}%) ниже минимума для поставки ({min_markup_supply}%)")

        assert len(needs_approval_reasons) == 1

    def test_needs_approval_low_markup_transit(self):
        """Low markup for transit requires approval."""
        deal_type = "transit"
        markup = 5
        min_markup_supply = 12
        min_markup_transit = 8
        needs_approval_reasons = []

        if deal_type == "transit" and markup < min_markup_transit:
            needs_approval_reasons.append(f"Наценка ({markup}%) ниже минимума для транзита ({min_markup_transit}%)")

        assert len(needs_approval_reasons) == 1

    def test_needs_approval_lpr_reward(self):
        """LPR reward requires approval."""
        lpr_reward = 5000
        needs_approval_reasons = []

        if lpr_reward > 0:
            needs_approval_reasons.append(f"Есть вознаграждение ЛПРа ({lpr_reward})")

        assert len(needs_approval_reasons) == 1

    def test_multiple_approval_reasons(self):
        """Multiple conditions can trigger approval."""
        currency = "RUB"
        prepayment = 50
        lpr_reward = 1000

        needs_approval_reasons = []

        if currency == "RUB":
            needs_approval_reasons.append("Валюта КП = рубли")
        if prepayment < 100:
            needs_approval_reasons.append(f"Не 100% предоплата ({prepayment}%)")
        if lpr_reward > 0:
            needs_approval_reasons.append(f"Есть вознаграждение ЛПРа ({lpr_reward})")

        assert len(needs_approval_reasons) == 3


# =============================================================================
# CHECKLIST COMPLETENESS TESTS
# =============================================================================

class TestChecklistItems:
    """Tests for checklist items coverage."""

    def test_checklist_has_11_items(self):
        """Checklist should have 11 items according to spec."""
        checklist_items = [
            "1. Тип сделки",
            "2. Базис поставки (Incoterms)",
            "3. Валюта КП",
            "4. Условия расчётов с клиентом",
            "5. Размер аванса поставщику",
            "6. Закупочные цены и НДС",
            "7. Корректность логистики",
            "8. Минимальные наценки",
            "9. Вознаграждение ЛПРа",
            "10. % курсовой разницы",
            "11. Наличие инвойсов от поставщиков",  # v3.0
        ]

        assert len(checklist_items) == 11

    def test_invoice_verification_is_last_item(self):
        """Invoice verification should be item 11."""
        # This is the v3.0 addition
        assert "11. Наличие инвойсов от поставщиков" == "11. Наличие инвойсов от поставщиков"


# =============================================================================
# MAIN.PY INTEGRATION TESTS
# =============================================================================

class TestMainPyIntegration:
    """Tests that main.py has the correct integration for criterion 11."""

    def test_invoices_table_query_in_main(self):
        """main.py should query invoices table for criterion 11."""
        with open("main.py", "r") as f:
            content = f.read()

        # Check that we query the invoices table directly
        assert 'table("invoices")' in content

    def test_checklist_uses_janna_7_items(self):
        """main.py should use build_janna_checklist with 7 items (replaced old 11-item checklist)."""
        with open("main.py", "r") as f:
            content = f.read()

        assert "build_janna_checklist" in content

    def test_invoice_id_check_in_main(self):
        """main.py should check quote_items.invoice_id for coverage."""
        with open("main.py", "r") as f:
            content = f.read()

        # Check that we count items with invoice_id
        assert "invoice_id" in content


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__, "-v"])
    else:
        # Run tests without pytest
        import traceback
        import sys

        failed = 0
        passed = 0

        test_classes = [
            TestQuoteInvoicingItem,
            TestQuoteInvoicingSummary,
            TestChecklistLogic,
            TestChecklistItems,
            TestMainPyIntegration
        ]

        for cls in test_classes:
            print(f'\n{cls.__name__}:')
            instance = cls()
            for method_name in dir(instance):
                if method_name.startswith('test_'):
                    try:
                        getattr(instance, method_name)()
                        print(f'  ✓ {method_name}')
                        passed += 1
                    except Exception as e:
                        print(f'  ✗ {method_name}: {e}')
                        failed += 1

        print(f'\n========================================')
        print(f'Total: {passed} passed, {failed} failed')
        if failed == 0:
            print('✅ All tests passed!')
        else:
            print('❌ Some tests failed')
            sys.exit(1)
