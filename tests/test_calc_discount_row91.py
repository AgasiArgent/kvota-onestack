"""Testing 2 row 91 — per-line КПП discount → calc input adaptation.

The procurement editor lets МОЗ set ``invoice_items.discount_pct`` (percent off
the line's unit purchase price). The discount is applied in the INPUT mapping
(``services.calculation_helpers``) BEFORE the value reaches the LOCKED
calculation engine — the engine itself is never touched.

    effective_price = purchase_price_original * (1 - discount_pct / 100)

A NULL / 0 / negative discount leaves the price unchanged, so the calc-engine
golden-master output stays byte-identical for all existing (discount-less)
data. These tests pin that contract on both the standalone helper and the
full ``build_calculation_inputs`` seam.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.calculation_helpers import (  # noqa: E402
    build_calculation_inputs,
    effective_purchase_price,
)


def _make_minimal_variables() -> dict:
    """Shape matches services.calculation_helpers.build_calculation_inputs."""
    return {
        "currency_of_quote": "RUB",
        "markup": Decimal("15"),
        "supplier_discount": Decimal("0"),
        "offer_incoterms": "DDP",
        "delivery_time": 30,
        "seller_company": "МАСТЕР БЭРИНГ ООО",
        "offer_sale_type": "поставка",
        "logistics_supplier_hub": Decimal("0"),
        "logistics_hub_customs": Decimal("0"),
        "logistics_customs_client": Decimal("0"),
        "brokerage_hub": Decimal("0"),
        "brokerage_hub_currency": "RUB",
        "brokerage_customs": Decimal("0"),
        "brokerage_customs_currency": "RUB",
        "warehousing_at_customs": Decimal("0"),
        "warehousing_at_customs_currency": "RUB",
        "customs_documentation": Decimal("0"),
        "customs_documentation_currency": "RUB",
        "brokerage_extra": Decimal("0"),
        "brokerage_extra_currency": "RUB",
        "advance_from_client": Decimal("100"),
        "advance_to_supplier": Decimal("100"),
        "time_to_advance": 0,
        "time_to_advance_on_receiving": 0,
        "dm_fee_type": "fixed",
        "dm_fee_value": Decimal("0"),
        "dm_fee_currency": "RUB",
        "exchange_rate": Decimal("1.0"),
    }


def _make_item(**overrides) -> dict:
    base = {
        "id": "ii-1",
        "purchase_price_original": Decimal("1000"),
        "purchase_currency": "RUB",
        "quantity": 1,
        "weight_in_kg": Decimal("10"),
        "customs_code": "1234567890",
        "customs_duty": Decimal("5"),
        "customs_duty_per_kg": Decimal("0"),
        "supplier_country": "RU",
        "price_includes_vat": False,
        "markup": Decimal("15"),
        "supplier_discount": Decimal("0"),
        "is_unavailable": False,
        "import_banned": False,
        "included_in_calc": True,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# effective_purchase_price — the standalone discount helper
# ---------------------------------------------------------------------------


class TestEffectivePurchasePrice:
    def test_discount_10_pct_yields_0_9x_original(self):
        item = _make_item(purchase_price_original=Decimal("1000"), discount_pct=Decimal("10"))
        assert effective_purchase_price(item) == Decimal("900")

    def test_discount_25_pct(self):
        item = _make_item(purchase_price_original=Decimal("200"), discount_pct=Decimal("25"))
        assert effective_purchase_price(item) == Decimal("150")

    def test_null_discount_returns_base_unchanged(self):
        item = _make_item(purchase_price_original=Decimal("1000"))
        item.pop("discount_pct", None)
        assert effective_purchase_price(item) == Decimal("1000")

    def test_zero_discount_returns_base_unchanged(self):
        item = _make_item(purchase_price_original=Decimal("1000"), discount_pct=Decimal("0"))
        assert effective_purchase_price(item) == Decimal("1000")

    def test_negative_discount_is_ignored(self):
        """A negative discount must NOT inflate the price — treated as no discount."""
        item = _make_item(purchase_price_original=Decimal("1000"), discount_pct=Decimal("-10"))
        assert effective_purchase_price(item) == Decimal("1000")

    def test_falls_back_to_base_price_vat(self):
        item = {
            "purchase_price_original": None,
            "base_price_vat": Decimal("500"),
            "discount_pct": Decimal("10"),
        }
        assert effective_purchase_price(item) == Decimal("450")


# ---------------------------------------------------------------------------
# build_calculation_inputs — the discount flows into the engine input
# ---------------------------------------------------------------------------


class TestBuildCalculationInputsDiscount:
    def test_discount_10_pct_applied_to_base_price(self):
        """A line with discount_pct=10 feeds effective_price = 0.9×original."""
        item = _make_item(purchase_price_original=Decimal("1000"), discount_pct=Decimal("10"))

        inputs = build_calculation_inputs([item], _make_minimal_variables())

        assert len(inputs) == 1
        # base_price_vat on the calc input carries the discounted unit price.
        assert Decimal(str(inputs[0].product.base_price_VAT)) == Decimal("900")

    def test_no_discount_produces_undiscounted_base_price(self):
        """No discount_pct → identical to the legacy (discount-less) input."""
        item = _make_item(purchase_price_original=Decimal("1000"))
        item.pop("discount_pct", None)

        inputs = build_calculation_inputs([item], _make_minimal_variables())

        assert len(inputs) == 1
        assert Decimal(str(inputs[0].product.base_price_VAT)) == Decimal("1000")

    def test_zero_discount_byte_identical_to_no_discount(self):
        """discount_pct=0 must produce the SAME calc input as no discount —
        the golden-master byte-identity guarantee at the unit level."""
        item_zero = _make_item(purchase_price_original=Decimal("1234.56"), discount_pct=Decimal("0"))
        item_none = _make_item(purchase_price_original=Decimal("1234.56"))
        item_none.pop("discount_pct", None)

        in_zero = build_calculation_inputs([item_zero], _make_minimal_variables())
        in_none = build_calculation_inputs([item_none], _make_minimal_variables())

        assert in_zero[0].product.base_price_VAT == in_none[0].product.base_price_VAT
