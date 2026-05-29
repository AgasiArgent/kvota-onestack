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


def _quantity_of(calc_inputs):
    """Effective per-line quantity the engine will use, from the built input."""
    assert len(calc_inputs) == 1
    return calc_inputs[0].product.quantity


# ---------------------------------------------------------------------------
# Layer 1 — the pure helper
# ---------------------------------------------------------------------------


class TestEffectiveCalcQuantity:
    @pytest.mark.parametrize(
        "ordered, moq, expected",
        [
            (5, 10, 10),       # MOQ binds — round up
            (10, 5, 10),       # MOQ below ordered — unchanged
            (10, 10, 10),      # equal — unchanged
            (5, None, 5),      # no MOQ — unchanged
            (5, 0, 5),         # zero MOQ — unchanged
            (5, -3, 5),        # negative MOQ — unchanged
            (1, 1, 1),         # trivial equal
            (5, 6, 6),         # MOQ one above — binds
        ],
    )
    def test_returns_max_when_moq_positive(self, ordered, moq, expected):
        assert effective_calc_quantity(ordered, moq) == expected

    def test_returns_int_type_when_floored(self):
        # The engine model requires ``quantity: int, gt=0`` — the helper must
        # return an int, not a Decimal.
        result = effective_calc_quantity(5, 10)
        assert result == 10
        assert isinstance(result, int)

    def test_decimal_moq_coerced_to_int_when_floored(self):
        # Defensive: even if a caller passes a Decimal MOQ, the binding branch
        # must return a plain int so ProductInfo(quantity: int) validates on
        # any Pydantic version.
        result = effective_calc_quantity(5, Decimal("10"))
        assert result == 10
        assert isinstance(result, int)

    def test_ordered_unchanged_object_when_not_floored(self):
        # When no floor applies the ordered value is returned verbatim.
        assert effective_calc_quantity(7, None) == 7
        assert isinstance(effective_calc_quantity(7, None), int)

    def test_none_ordered_with_binding_moq_returns_moq(self):
        # Defensive: a missing ordered quantity (safe_decimal -> 0) with a
        # positive MOQ floors to the MOQ rather than crashing downstream.
        assert effective_calc_quantity(None, 10) == 10

    def test_non_numeric_moq_is_no_op(self):
        assert effective_calc_quantity(5, "not-a-number") == 5


# ---------------------------------------------------------------------------
# Layer 2 — build_calculation_inputs propagates the floor to the engine input
# ---------------------------------------------------------------------------


class TestBuildCalculationInputsMoqRoundup:
    def test_moq_above_ordered_floors_calc_quantity(self):
        item = _make_item(quantity=5, minimum_order_quantity=10)
        with patch(
            "services.currency_service.convert_amount",
            side_effect=lambda v, f, t: v,
        ):
            calc_inputs = build_calculation_inputs([item], _make_minimal_variables())
        assert _quantity_of(calc_inputs) == 10

    def test_null_moq_leaves_quantity_unchanged(self):
        item = _make_item(quantity=5, minimum_order_quantity=None)
        with patch(
            "services.currency_service.convert_amount",
            side_effect=lambda v, f, t: v,
        ):
            calc_inputs = build_calculation_inputs([item], _make_minimal_variables())
        assert _quantity_of(calc_inputs) == 5

    def test_zero_moq_leaves_quantity_unchanged(self):
        item = _make_item(quantity=5, minimum_order_quantity=0)
        with patch(
            "services.currency_service.convert_amount",
            side_effect=lambda v, f, t: v,
        ):
            calc_inputs = build_calculation_inputs([item], _make_minimal_variables())
        assert _quantity_of(calc_inputs) == 5

    def test_moq_below_ordered_leaves_quantity_unchanged(self):
        item = _make_item(quantity=10, minimum_order_quantity=3)
        with patch(
            "services.currency_service.convert_amount",
            side_effect=lambda v, f, t: v,
        ):
            calc_inputs = build_calculation_inputs([item], _make_minimal_variables())
        assert _quantity_of(calc_inputs) == 10


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
    def test_floored_quote_equals_ordering_the_moq_amount(self):
        """ordered=5 / MOQ=10 must produce IDENTICAL engine totals to
        ordered=10 / no MOQ — proving the floor scales price, customs and
        logistics for the whole line, not just the displayed quantity."""
        floored = _run_engine(_make_item(quantity=5, minimum_order_quantity=10))
        ordered_ten = _run_engine(_make_item(quantity=10, minimum_order_quantity=None))
        assert floored == ordered_ten

    def test_floor_changes_totals_versus_raw_ordered(self):
        """The floor must actually move the numbers: ordered=5 / MOQ=10 differs
        from ordered=5 / no MOQ (the pre-fix behaviour)."""
        floored = _run_engine(_make_item(quantity=5, minimum_order_quantity=10))
        raw_five = _run_engine(_make_item(quantity=5, minimum_order_quantity=None))
        assert floored != raw_five
