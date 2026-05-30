"""Tests for contract_spec_export._effective_qty (supplier-override display qty).

The contract per-unit price is total / qty, so the displayed qty must be the
effective (supplier-override) quantity AND never 0 (no div-by-zero).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.contract_spec_export import _effective_qty  # noqa: E402


def test_uses_effective_quantity_when_present():
    assert _effective_qty({"effective_quantity": 738, "quantity": 32}) == 738


def test_falls_back_to_ordered_when_effective_missing():
    assert _effective_qty({"quantity": 7}) == 7


def test_falls_back_to_ordered_when_effective_none():
    assert _effective_qty({"effective_quantity": None, "quantity": 5}) == 5


def test_floors_zero_effective_to_one():
    # 0 would break the per-unit division (total / qty) — floor to 1
    assert _effective_qty({"effective_quantity": 0, "quantity": 0}) == 1


def test_floors_missing_everything_to_one():
    assert _effective_qty({}) == 1


def test_override_down_below_ordered():
    assert _effective_qty({"effective_quantity": 10, "quantity": 50}) == 10
