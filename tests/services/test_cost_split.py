"""Tests for services/cost_split.py — REQ-3 (Phase B customs-shared-certificates).

6 fixture-driven scenarios from `tests/fixtures/cost_split_fixtures.json`
exercise the proportional split, equal-split fallback, residual rule, and
multi-currency RUB-basis derivation. Additional unit tests cover edge
cases not in the fixtures (empty list, single item, all zeros).

The same JSON fixture is consumed by the TypeScript sister
implementation in `frontend/src/shared/lib/__tests__/cost-split.test.ts`
to guarantee kopek-identical output between Python and TS (REQ-3
AC#11/AC#12).
"""
from __future__ import annotations

import json
import os
from decimal import Decimal

import pytest

from services.cost_split import (
    customs_value_rub_for_item,
    split_cost,
    split_cost_batch,
)


# ---------------------------------------------------------------------------
# Fixture loader — relative path so tests work both locally and in CI.
# ---------------------------------------------------------------------------

_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "fixtures",
    "cost_split_fixtures.json",
)


def _load_fixtures() -> list[dict]:
    with open(_FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


_FIXTURES = _load_fixtures()


# ---------------------------------------------------------------------------
# Fixture-driven parameterized tests (REQ-3 AC#10) — 6 scenarios.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    _FIXTURES,
    ids=[fx["name"] for fx in _FIXTURES],
)
def test_fixture_split_cost_batch_matches_expected(fixture: dict) -> None:
    """For each fixture row, derive item_values from raw upstream fields,
    cross-check vs the pre-computed item_values, then run them through
    split_cost_batch and assert kopek-equality with expected_shares."""
    # 1) Derive RUB basis from raw upstream fields (parity formula).
    derived = [
        Decimal(it["purchase_price_original"])
        * Decimal(it["quantity"])
        * Decimal(it["currency_rate_to_rub"])
        for it in fixture["items"]
    ]

    # 2) Sanity-check: derived basis matches the pre-computed item_values
    #    in the fixture (so the JSON file is self-consistent — TS side
    #    will derive identically).
    declared = [Decimal(s) for s in fixture["item_values"]]
    assert [d for d in derived] == [d for d in declared], (
        f"derived RUB basis {derived} != declared item_values {declared}"
    )

    # 3) Run the batch split.
    cert_cost = Decimal(fixture["cert_cost"])
    actual = split_cost_batch(derived, cert_cost)
    expected = [Decimal(s) for s in fixture["expected_shares"]]

    assert len(actual) == len(expected), (
        f"length mismatch: got {len(actual)}, want {len(expected)}"
    )
    for i, (a, e) in enumerate(zip(actual, expected)):
        assert a == e, (
            f"share[{i}] mismatch in '{fixture['name']}': got {a}, want {e}"
        )

    # 4) Sum invariant: shares sum exactly to cert_cost (REQ-3 AC#7).
    assert sum(actual, Decimal("0")) == cert_cost


# ---------------------------------------------------------------------------
# Direct unit tests for split_cost (single-share).
# ---------------------------------------------------------------------------


def test_split_cost_basic_proportional() -> None:
    """item_value/total * cert_cost, quantized to kopeks."""
    # 100/400 * 12.50 = 3.125 → ROUND_HALF_UP to 0.01 → 3.13
    assert split_cost(
        Decimal("100"), Decimal("400"), Decimal("12.50")
    ) == Decimal("3.13")


def test_split_cost_zero_total_returns_zero() -> None:
    """REQ-3 AC#5: split_cost itself returns 0 when total is 0;
    the equal-split fallback is a batch-level concern."""
    assert split_cost(
        Decimal("0"), Decimal("0"), Decimal("100")
    ) == Decimal("0.00")


def test_split_cost_zero_cert_returns_zero() -> None:
    assert split_cost(
        Decimal("100"), Decimal("400"), Decimal("0")
    ) == Decimal("0.00")


def test_split_cost_quantizes_half_up() -> None:
    """0.005 must round UP, not banker's-round to even."""
    # 1/2 * 0.01 = 0.005 → ROUND_HALF_UP → 0.01
    assert split_cost(
        Decimal("1"), Decimal("2"), Decimal("0.01")
    ) == Decimal("0.01")


# ---------------------------------------------------------------------------
# Direct unit tests for split_cost_batch — edge cases not in fixtures.
# ---------------------------------------------------------------------------


def test_split_cost_batch_empty_list_returns_empty() -> None:
    assert split_cost_batch([], Decimal("100")) == []


def test_split_cost_batch_single_item_returns_full_cost() -> None:
    """REQ-3 AC#6: single item gets cert_cost without rounding."""
    result = split_cost_batch([Decimal("123.456789")], Decimal("999.99"))
    assert result == [Decimal("999.99")]


def test_split_cost_batch_all_zeros_equal_split() -> None:
    """REQ-3 AC#5: total basis == 0 → equal split with last absorbing residual."""
    result = split_cost_batch(
        [Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")],
        Decimal("100"),
    )
    # 100 / 4 = 25.00 exactly — no residual.
    assert result == [
        Decimal("25.00"),
        Decimal("25.00"),
        Decimal("25.00"),
        Decimal("25.00"),
    ]
    assert sum(result, Decimal("0")) == Decimal("100")


def test_split_cost_batch_all_zeros_with_residual() -> None:
    """Equal-split fallback also absorbs the rounding residual on the last item."""
    result = split_cost_batch(
        [Decimal("0"), Decimal("0"), Decimal("0")], Decimal("100")
    )
    # 100 / 3 = 33.333… → 33.33 first two, last = 100 - 66.66 = 33.34.
    assert result == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert sum(result, Decimal("0")) == Decimal("100")


def test_split_cost_batch_residual_absorbed_by_last() -> None:
    """REQ-3 AC#7: rounding residual lands on the last item, not split."""
    result = split_cost_batch(
        [Decimal("1"), Decimal("1"), Decimal("1")], Decimal("10")
    )
    assert result == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]
    # Specifically the last item is .34, not .33.
    assert result[-1] == Decimal("3.34")
    assert sum(result, Decimal("0")) == Decimal("10")


def test_split_cost_batch_proportional_normal() -> None:
    """Standard 50/50 split — last absorbs zero residual."""
    result = split_cost_batch(
        [Decimal("100"), Decimal("100")], Decimal("12500")
    )
    assert result == [Decimal("6250.00"), Decimal("6250.00")]


def test_split_cost_batch_sum_invariant_holds_for_irrational_ratios() -> None:
    """Across many invocations with awkward ratios, sum must always equal cert_cost."""
    cases = [
        ([Decimal("7"), Decimal("11"), Decimal("13")], Decimal("100")),
        ([Decimal("17"), Decimal("19"), Decimal("23")], Decimal("999.99")),
        ([Decimal("1"), Decimal("3"), Decimal("9"), Decimal("27")], Decimal("1234.56")),
    ]
    for item_values, cert_cost in cases:
        shares = split_cost_batch(item_values, cert_cost)
        assert sum(shares, Decimal("0")) == cert_cost, (
            f"sum invariant broken: {item_values} cert={cert_cost} → {shares}"
        )


# ---------------------------------------------------------------------------
# Re-export sanity check (LD-15) — calc-engine helper accessible via
# services.cost_split for backend consumers.
# ---------------------------------------------------------------------------


def test_customs_value_rub_for_item_is_reexported() -> None:
    """Phase B should expose `customs_value_rub_for_item` so callers do
    not need to reach into calculation_helpers directly."""
    assert callable(customs_value_rub_for_item)
    # Smoke call — RUB-priced item should return purchase_price * quantity.
    item = {
        "purchase_price_original": "100",
        "purchase_currency": "RUB",
        "quantity": "5",
    }
    result = customs_value_rub_for_item(item, "RUB", lambda amt, src, dst: amt)
    assert result == Decimal("500")
