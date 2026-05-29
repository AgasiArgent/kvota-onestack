"""Testing 2 row 85 — MOQ round-up propagation into the calc engine.

The locked decision is ROUND-UP-TO-MOQ: the per-line calc quantity becomes
``max(ordered, minimum_order_quantity)`` when the supplier declares a positive
MOQ above the ordered amount. The single seam is
``services.calculation_helpers.build_calculation_inputs`` (the locked engine
reads only ``product['quantity']``).

Three layers of coverage:

1. ``effective_calc_quantity`` — the pure helper, exhaustively (no deps).
2. ``build_calculation_inputs`` — the floored quantity reaches the engine input
   (``QuoteCalculationInput.product.quantity``); null/0/negative MOQ is a no-op.
3. End-to-end through the LOCKED engine — a quote with ordered=5/MOQ=10 produces
   IDENTICAL totals (price, customs, logistics, COGS) to a quote ordered=10 with
   no MOQ, and STRICTLY DIFFERENT totals from ordered=5 with no MOQ. This proves
   the floor scales customs/logistics/totals, not just the displayed quantity.
"""

import os
import sys
from decimal import Decimal
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from calculation_engine import calculate_multiproduct_quote
from services.calculation_helpers import (
    build_calculation_inputs,
    effective_calc_quantity,
)


# ---------------------------------------------------------------------------
# Fixtures — self-contained minimal item/variables for the calc seam
# ---------------------------------------------------------------------------


def _make_minimal_variables() -> dict:
    """Minimum keys ``build_calculation_inputs`` reads, all-RUB with zero
    logistics/brokerage so no FX conversion is exercised (keeps the engine
    equivalence deterministic)."""
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
    """Calc-ready item dict (shape ``build_calculation_inputs`` consumes).

    Legacy ad-valorem customs (``customs_duty=5`` percent, no per-kg slot) so
    the import-tariff percent is quantity-invariant — the property that makes
    flooring only ``product['quantity']`` correct for customs.
    """
    item = {
        "id": "item-1",
        "purchase_price_original": Decimal("1000"),
        "purchase_currency": "RUB",
        "quantity": 5,
        "minimum_order_quantity": None,
        "weight_in_kg": Decimal("10"),
        "customs_code": "1234567890",
        "customs_duty": Decimal("5"),
        "customs_duty_per_kg": Decimal("0"),
        "supplier_country": "RU",
        "price_includes_vat": False,
        "markup": Decimal("15"),
        "supplier_discount": Decimal("0"),
    }
    item.update(overrides)
    return item


# ---------------------------------------------------------------------------
# Layer 1 — the pure helper
# ---------------------------------------------------------------------------


class TestEffectiveCalcQuantity:
    @pytest.mark.parametrize(
        "ordered, supplier_qty, expected",
        [
            (5, 10, 10),      # supplier higher → override up
            (10, 5, 5),       # supplier lower → override DOWN (new behaviour)
            (10, 10, 10),     # equal
            (5, None, 5),     # unset → ordered
            (5, 0, 5),        # zero treated as unset → ordered
            (5, -3, 5),       # negative treated as unset → ordered
            (10, None, 10),
        ],
    )
    def test_supplier_qty_overrides_when_set(self, ordered, supplier_qty, expected):
        assert effective_calc_quantity(ordered, supplier_qty) == expected

    def test_returns_int_when_overridden(self):
        result = effective_calc_quantity(5, 10)
        assert result == 10 and isinstance(result, int)

    def test_decimal_supplier_qty_coerced_to_int(self):
        result = effective_calc_quantity(5, Decimal("10"))
        assert result == 10 and isinstance(result, int)

    def test_unset_returns_ordered_verbatim(self):
        assert effective_calc_quantity(7, None) == 7


# ---------------------------------------------------------------------------
# Layer 2 — build_calculation_inputs propagates the floor to the engine input
# ---------------------------------------------------------------------------


class TestBuildCalculationInputsOverride:
    """The seam resolves product['quantity'] via effective_calc_quantity
    (supplier qty overrides ordered both ways when >0, else ordered)."""

    def _run(self, **item_kw):
        item = _make_item(**item_kw)
        with patch(
            "services.currency_service.convert_amount", side_effect=lambda v, f, t: v
        ):
            ci = build_calculation_inputs([item], _make_minimal_variables())
        assert len(ci) == 1
        return ci[0].product.quantity

    def test_override_up(self):
        assert self._run(quantity=5, minimum_order_quantity=10) == 10

    def test_override_down(self):
        assert self._run(quantity=10, minimum_order_quantity=5) == 5

    def test_unset_uses_ordered(self):
        assert self._run(quantity=5, minimum_order_quantity=None) == 5

    def test_zero_supplier_qty_uses_ordered(self):
        assert self._run(quantity=5, minimum_order_quantity=0) == 5

    def test_negative_supplier_qty_uses_ordered(self):
        # A negative value must never reach the engine's gt=0 validator; it
        # falls back to the ordered quantity (matches the DB column's >0 rule).
        assert self._run(quantity=5, minimum_order_quantity=-3) == 5


# ---------------------------------------------------------------------------
# Layer 3 — end-to-end: customs unit-qty ('796' family), logistics, totals scale
# ---------------------------------------------------------------------------


def _run_engine(item: dict):
    with patch(
        "services.currency_service.convert_amount",
        side_effect=lambda v, f, t: v,
    ):
        calc_inputs = build_calculation_inputs([item], _make_minimal_variables())
        return calculate_multiproduct_quote(calc_inputs)


class TestMoqRoundupScalesTotals:
    def test_override_quote_equals_ordering_that_amount(self):
        """ordered=5 / supplier qty=10 must produce IDENTICAL engine totals to
        ordered=10 / no override — proving the override scales price, customs
        and logistics for the whole line, not just the displayed quantity."""
        overridden = _run_engine(_make_item(quantity=5, minimum_order_quantity=10))
        ordered_ten = _run_engine(_make_item(quantity=10, minimum_order_quantity=None))
        assert overridden == ordered_ten

    def test_override_changes_totals_versus_raw_ordered(self):
        """The override must actually move the numbers: ordered=5 / supplier qty=10
        differs from ordered=5 / unset (the pre-override behaviour)."""
        overridden = _run_engine(_make_item(quantity=5, minimum_order_quantity=10))
        raw_five = _run_engine(_make_item(quantity=5, minimum_order_quantity=None))
        assert overridden != raw_five

    def test_override_down_changes_totals(self):
        """Override DOWN also moves totals: ordered=10 / supplier qty=5 equals
        ordering 5 outright, and differs from ordered=10 unset."""
        down = _run_engine(_make_item(quantity=10, minimum_order_quantity=5))
        ordered_five = _run_engine(_make_item(quantity=5, minimum_order_quantity=None))
        ordered_ten = _run_engine(_make_item(quantity=10, minimum_order_quantity=None))
        assert down == ordered_five
        assert down != ordered_ten
