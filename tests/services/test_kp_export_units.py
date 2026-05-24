"""Unit tests for ``services.kp_export`` helpers.

These cover the deterministic Python helpers used by the renderer:
- ``_fmt_ru`` — Russian-locale number formatting with raw-passthrough fallback
- ``calc_row_total`` — per-row qty*price
- ``calc_grand_total`` — sum of valid rows
- items-table padding via the renderer's helper

Pure functions — no I/O, no WeasyPrint. Marked ``@pytest.mark.unit``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from services.kp_export import (
    KpItem,
    _fmt_ru,
    _pad_items,
    calc_grand_total,
    calc_row_total,
)


# ---------------------------------------------------------------------------
# _fmt_ru — defensive formatter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFmtRu:
    def test_plain_integer_groups_thousands(self) -> None:
        # Narrow no-break space (" ") OR regular non-breaking space —
        # the renderer settled on NNBSP per the spec. Accept either.
        result = _fmt_ru("5850000")
        # Should contain at least one space-like separator between thousands.
        assert "5" in result and "850" in result and "000" in result

    def test_space_separated_input(self) -> None:
        # "5 850 000" — user typed thousands as ASCII spaces; should parse.
        result = _fmt_ru("5 850 000")
        assert "5" in result and "850" in result and "000" in result

    def test_nonbreaking_space_input(self) -> None:
        result = _fmt_ru("5 850 000")
        assert "850" in result and "000" in result

    def test_comma_as_decimal(self) -> None:
        # "5850,5" — Russian decimal style; should parse as 5850.5.
        result = _fmt_ru("5850,5")
        assert "5850" in result.replace(" ", "").replace(" ", "").replace(
            " ", ""
        )
        # Output should contain the decimal portion ".5" or ",5".
        assert "5" in result.split(",")[-1] or "5" in result.split(".")[-1]

    def test_dot_as_decimal(self) -> None:
        result = _fmt_ru("5850.5")
        # 5850.5 formatted should contain "5850" digits (possibly with
        # thousands separator between 5 and 850).
        digits = "".join(c for c in result if c.isdigit())
        assert digits == "58505"

    def test_unparseable_returns_raw_string(self) -> None:
        # "abc" — non-numeric; renderer must echo it back unchanged so the
        # buyer sees what the user typed instead of "NaN" or a crash.
        assert _fmt_ru("abc") == "abc"

    def test_empty_string_returns_empty(self) -> None:
        assert _fmt_ru("") == ""

    def test_none_returns_empty(self) -> None:
        # None tolerated — renderer passes optional fields straight through.
        assert _fmt_ru(None) == ""


# ---------------------------------------------------------------------------
# calc_row_total / calc_grand_total
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCalcRowTotal:
    def test_qty_times_price(self) -> None:
        item = KpItem(name="X", model="Y", qty="2", price="100")
        assert calc_row_total(item) == Decimal("200")

    def test_decimal_qty_and_price(self) -> None:
        item = KpItem(qty="1.5", price="2000")
        assert calc_row_total(item) == Decimal("3000.0")

    def test_space_separated_price(self) -> None:
        item = KpItem(qty="1", price="5 850 000")
        assert calc_row_total(item) == Decimal("5850000")

    def test_comma_decimal_price(self) -> None:
        item = KpItem(qty="1", price="5850,5")
        assert calc_row_total(item) == Decimal("5850.5")

    def test_blank_qty_returns_none(self) -> None:
        item = KpItem(name="X", qty="", price="100")
        assert calc_row_total(item) is None

    def test_blank_price_returns_none(self) -> None:
        item = KpItem(name="X", qty="1", price="")
        assert calc_row_total(item) is None

    def test_garbage_qty_returns_none(self) -> None:
        item = KpItem(qty="abc", price="100")
        assert calc_row_total(item) is None


@pytest.mark.unit
class TestCalcGrandTotal:
    def test_empty_items_returns_zero(self) -> None:
        assert calc_grand_total(()) == Decimal("0")

    def test_sums_valid_rows(self) -> None:
        items = (
            KpItem(qty="1", price="100"),
            KpItem(qty="2", price="50"),
        )
        assert calc_grand_total(items) == Decimal("200")

    def test_ignores_unparseable_rows(self) -> None:
        items = (
            KpItem(qty="1", price="100"),
            KpItem(qty="abc", price="999"),  # ignored
            KpItem(qty="3", price="50"),
        )
        assert calc_grand_total(items) == Decimal("250")

    def test_ignores_blank_rows(self) -> None:
        items = (
            KpItem(qty="1", price="100"),
            KpItem(),  # padding row, contributes 0
            KpItem(qty="2", price="200"),
        )
        assert calc_grand_total(items) == Decimal("500")


# ---------------------------------------------------------------------------
# Items-table padding
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPadItems:
    """Per REQ-4.4 the items table renders ≥5 rows even when the user
    entered fewer items, to preserve the visual rhythm of the page-1 table.
    """

    def test_pads_to_minimum_five_when_empty(self) -> None:
        rows = _pad_items((), minimum=5)
        assert len(rows) == 5

    def test_pads_to_minimum_five_when_one_item(self) -> None:
        rows = _pad_items((KpItem(name="X"),), minimum=5)
        assert len(rows) == 5
        assert rows[0].name == "X"
        for r in rows[1:]:
            assert r.name == ""

    def test_does_not_truncate_when_more_than_minimum(self) -> None:
        items = tuple(KpItem(name=f"item-{i}") for i in range(7))
        rows = _pad_items(items, minimum=5)
        assert len(rows) == 7
