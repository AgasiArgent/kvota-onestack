"""
Tests for Currency Invoice Generation Service (TDD - tests first)

Tests for:
- calculate_segment_price: markup logic for EURTR and TRRU segments
- build_invoice_number: correct format CI-{idn}-{currency}-{segment}-{seq}
- group_items_by_buyer_company: merging items with same buyer company
- generate_currency_invoices: full generation flow for EU and TR buyers
"""

import pytest
from decimal import Decimal
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.currency_invoice_service import (
    generate_currency_invoices,
    calculate_segment_price,
    build_invoice_number,
    group_items_by_buyer_company,
)


# ============================================================================
# PRICE CALCULATION TESTS
# ============================================================================

class TestCalculateSegmentPrice:
    """Tests for calculate_segment_price function."""

    def test_eurtr_default_markup(self):
        """EURTR segment: base_price * (1 + markup/100), default 2%."""
        result = calculate_segment_price(
            base_price=Decimal("100.00"),
            segment="EURTR",
            markup_percent=Decimal("2.0"),
            prior_markup_percent=None,
        )
        assert result == Decimal("102.00")

    def test_trru_from_eu_chain_cumulative_markup(self):
        """TRRU from EU chain: base_price * (1 + eurtr_markup/100) * (1 + trru_markup/100)."""
        result = calculate_segment_price(
            base_price=Decimal("100.00"),
            segment="TRRU",
            markup_percent=Decimal("2.0"),
            prior_markup_percent=Decimal("2.0"),  # EURTR markup applied first
        )
        assert result == Decimal("104.04")

    def test_trru_from_tr_chain_single_markup(self):
        """TRRU from TR chain: base_price * (1 + markup/100), no prior segment."""
        result = calculate_segment_price(
            base_price=Decimal("100.00"),
            segment="TRRU",
            markup_percent=Decimal("2.0"),
            prior_markup_percent=None,
        )
        assert result == Decimal("102.00")

    def test_custom_markup_3_percent(self):
        """Custom 3% markup instead of default 2%."""
        result = calculate_segment_price(
            base_price=Decimal("100.00"),
            segment="EURTR",
            markup_percent=Decimal("3.0"),
            prior_markup_percent=None,
        )
        assert result == Decimal("103.00")

    def test_zero_base_price(self):
        """Edge case: zero base price returns zero."""
        result = calculate_segment_price(
            base_price=Decimal("0.00"),
            segment="EURTR",
            markup_percent=Decimal("2.0"),
            prior_markup_percent=None,
        )
        assert result == Decimal("0.00")

    def test_large_base_price(self):
        """Edge case: large base price with fractional markup."""
        result = calculate_segment_price(
            base_price=Decimal("999999.99"),
            segment="EURTR",
            markup_percent=Decimal("2.0"),
            prior_markup_percent=None,
        )
        expected = Decimal("999999.99") * Decimal("1.02")
        assert result == expected


# ============================================================================
# INVOICE NUMBERING TESTS
# ============================================================================

class TestBuildInvoiceNumber:
    """Tests for build_invoice_number function."""

    def test_eurtr_eur_format(self):
        """Standard EURTR invoice number format."""
        result = build_invoice_number(
            quote_idn="Q202601-0004",
            currency="EUR",
            segment="EURTR",
            sequence=1,
        )
        assert result == "CI-Q202601-0004-EUR-EURTR-1"

    def test_trru_usd_format(self):
        """TRRU invoice number with USD currency."""
        result = build_invoice_number(
            quote_idn="Q202601-0004",
            currency="USD",
            segment="TRRU",
            sequence=1,
        )
        assert result == "CI-Q202601-0004-USD-TRRU-1"

    def test_sequence_increments(self):
        """Multiple invoices get sequential numbers."""
        result_1 = build_invoice_number(
            quote_idn="Q202601-0004",
            currency="EUR",
            segment="EURTR",
            sequence=1,
        )
        result_2 = build_invoice_number(
            quote_idn="Q202601-0004",
            currency="EUR",
            segment="EURTR",
            sequence=2,
        )
        assert result_1 == "CI-Q202601-0004-EUR-EURTR-1"
        assert result_2 == "CI-Q202601-0004-EUR-EURTR-2"


# ============================================================================
# GROUPING TESTS
# ============================================================================

class TestGroupItemsByBuyerCompany:
    """Tests for group_items_by_buyer_company function."""

    def test_merges_same_company_items(self):
        """Multiple items with same buyer_company_id merge into one group."""
        items = [
            {"id": "item-1", "buyer_company_id": "bc-1", "product_name": "Item A"},
            {"id": "item-2", "buyer_company_id": "bc-1", "product_name": "Item B"},
            {"id": "item-3", "buyer_company_id": "bc-2", "product_name": "Item C"},
        ]
        groups = group_items_by_buyer_company(items)
        assert len(groups) == 2
        assert len(groups["bc-1"]) == 2
        assert len(groups["bc-2"]) == 1

    def test_single_item_per_company(self):
        """Each company has exactly one item."""
        items = [
            {"id": "item-1", "buyer_company_id": "bc-1", "product_name": "Item A"},
            {"id": "item-2", "buyer_company_id": "bc-2", "product_name": "Item B"},
        ]
        groups = group_items_by_buyer_company(items)
        assert len(groups) == 2
        assert len(groups["bc-1"]) == 1
        assert len(groups["bc-2"]) == 1

    def test_empty_items_list(self):
        """Empty input returns empty dict."""
        groups = group_items_by_buyer_company([])
        assert groups == {}


# ============================================================================
# GENERATION INTEGRATION TESTS
# ============================================================================

class TestGenerateCurrencyInvoices:
    """Tests for generate_currency_invoices function (pure logic, no DB)."""

    def _make_seller_company(self):
        return {"id": "sc-ru", "name": "MB Rus", "entity_type": "seller_company"}

    def test_eu_buyer_creates_two_invoices(self):
        """EU buyer_company -> 2 currency invoices (EURTR + TRRU)."""
        buyer_companies = {
            "bc-eu": {"id": "bc-eu", "name": "EuroInvest", "region": "EU"},
        }
        items = [
            {
                "id": "item-1", "buyer_company_id": "bc-eu",
                "product_name": "Bearing", "sku": "BRG-001", "idn_sku": "IDN-001",
                "brand": "SKF", "quantity": Decimal("100"), "unit": "pcs",
                "hs_code": "8482.10", "purchase_price_original": Decimal("50.00"),
                "purchase_currency": "EUR",
            },
        ]
        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=items,
            buyer_companies=buyer_companies,
            seller_company=self._make_seller_company(),
            organization_id="org-1",
        )
        assert len(result) == 2
        segments = {inv["segment"] for inv in result}
        assert segments == {"EURTR", "TRRU"}

    def test_tr_buyer_creates_one_invoice(self):
        """TR buyer_company -> 1 currency invoice (TRRU only)."""
        buyer_companies = {
            "bc-tr": {"id": "bc-tr", "name": "MB TR", "region": "TR"},
        }
        items = [
            {
                "id": "item-1", "buyer_company_id": "bc-tr",
                "product_name": "Seal", "sku": "SL-001", "idn_sku": "IDN-002",
                "brand": "NOK", "quantity": Decimal("200"), "unit": "pcs",
                "hs_code": "4016.93", "purchase_price_original": Decimal("10.00"),
                "purchase_currency": "USD",
            },
        ]
        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=items,
            buyer_companies=buyer_companies,
            seller_company=self._make_seller_company(),
            organization_id="org-1",
        )
        assert len(result) == 1
        assert result[0]["segment"] == "TRRU"

    def test_trru_contains_all_items_from_eu_and_tr(self):
        """TRRU invoice should contain ALL items (from both EU and TR chains)."""
        buyer_companies = {
            "bc-eu": {"id": "bc-eu", "name": "EuroInvest", "region": "EU"},
            "bc-tr": {"id": "bc-tr", "name": "MB TR", "region": "TR"},
        }
        items = [
            {
                "id": "item-1", "buyer_company_id": "bc-eu",
                "product_name": "EU Item", "sku": "EU-001", "idn_sku": "IDN-001",
                "brand": "SKF", "quantity": Decimal("10"), "unit": "pcs",
                "hs_code": "8482.10", "purchase_price_original": Decimal("100.00"),
                "purchase_currency": "EUR",
            },
            {
                "id": "item-2", "buyer_company_id": "bc-tr",
                "product_name": "TR Item", "sku": "TR-001", "idn_sku": "IDN-002",
                "brand": "NOK", "quantity": Decimal("20"), "unit": "pcs",
                "hs_code": "4016.93", "purchase_price_original": Decimal("50.00"),
                "purchase_currency": "USD",
            },
        ]
        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=items,
            buyer_companies=buyer_companies,
            seller_company=self._make_seller_company(),
            organization_id="org-1",
        )
        trru = [inv for inv in result if inv["segment"] == "TRRU"][0]
        assert len(trru["items"]) == 2  # both EU and TR items

    def test_items_snapshot_has_all_required_fields(self):
        """Currency invoice items contain all required snapshot fields."""
        buyer_companies = {
            "bc-tr": {"id": "bc-tr", "name": "MB TR", "region": "TR"},
        }
        items = [
            {
                "id": "item-1", "buyer_company_id": "bc-tr",
                "product_name": "Bearing XYZ", "sku": "BRG-XYZ", "idn_sku": "IDN-42",
                "brand": "Timken", "quantity": Decimal("500"), "unit": "kg",
                "hs_code": "8482.10.90", "purchase_price_original": Decimal("25.50"),
                "purchase_currency": "USD",
            },
        ]
        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=items,
            buyer_companies=buyer_companies,
            seller_company=self._make_seller_company(),
            organization_id="org-1",
        )
        item = result[0]["items"][0]
        assert item["product_name"] == "Bearing XYZ"
        assert item["sku"] == "BRG-XYZ"
        assert item["idn_sku"] == "IDN-42"
        assert item["manufacturer"] == "Timken"
        assert item["quantity"] == Decimal("500")
        assert item["unit"] == "kg"
        assert item["hs_code"] == "8482.10.90"
        assert item["base_price"] == Decimal("25.50")
        assert item["price"] == Decimal("26.01")  # 25.50 * 1.02
        assert item["total"] == Decimal("13005.00")  # 500 * 26.01

    def test_eu_buyer_eurtr_invoice_has_correct_segment_metadata(self):
        """EURTR invoice should have correct segment, currency, and entity types."""
        buyer_companies = {
            "bc-eu": {"id": "bc-eu", "name": "EuroInvest", "region": "EU"},
        }
        items = [
            {
                "id": "item-1", "buyer_company_id": "bc-eu",
                "product_name": "Bearing", "sku": "BRG-001", "idn_sku": "IDN-001",
                "brand": "SKF", "quantity": Decimal("100"), "unit": "pcs",
                "hs_code": "8482.10", "purchase_price_original": Decimal("50.00"),
                "purchase_currency": "EUR",
            },
        ]
        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=items,
            buyer_companies=buyer_companies,
            seller_company=self._make_seller_company(),
            organization_id="org-1",
        )
        eurtr = [inv for inv in result if inv["segment"] == "EURTR"][0]
        assert eurtr["deal_id"] == "deal-1"
        assert eurtr["organization_id"] == "org-1"
        assert eurtr["status"] == "draft"
        assert "invoice_number" in eurtr
        assert "items" in eurtr
        assert len(eurtr["items"]) > 0
