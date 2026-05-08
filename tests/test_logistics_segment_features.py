"""Unit tests for Combo-3 segment editor features.

Covers helper functions added in api/logistics.py for РОЛ Тест 07
#3.5 (hybrid templates) and #3.7 (per-segment currency). Pure unit
tests — no DB, no Supabase mocks. Integration coverage of the
endpoints lives in the integration smoke suite (skipped without
DATABASE_URL).
"""

from __future__ import annotations

import pytest

from api.logistics import (
    _SEGMENT_CURRENCIES,
    _build_template_segment_row,
    _validate_currency,
)


class TestValidateCurrency:
    """`_validate_currency` accepts the four supported codes (3.7)."""

    @pytest.mark.parametrize("code", sorted(_SEGMENT_CURRENCIES))
    def test_returns_canonical_code_for_supported(self, code: str) -> None:
        assert _validate_currency(code) == code

    def test_uppercases_and_trims(self) -> None:
        assert _validate_currency("  rub ") == "RUB"
        assert _validate_currency("usd") == "USD"

    @pytest.mark.parametrize(
        "value",
        ["", "JPY", "BTC", "rubles", "ru", None, 42, {"code": "RUB"}],
    )
    def test_rejects_unsupported(self, value: object) -> None:
        assert _validate_currency(value) is None


class TestBuildTemplateSegmentRow:
    """`_build_template_segment_row` carries optional concrete FKs (3.5)."""

    def test_minimal_payload_has_null_fks(self) -> None:
        row = _build_template_segment_row(
            template_id="tpl-1",
            idx=1,
            seg={
                "from_location_type": "supplier",
                "to_location_type": "hub",
            },
        )
        assert row["template_id"] == "tpl-1"
        assert row["sequence_order"] == 1
        assert row["from_location_type"] == "supplier"
        assert row["to_location_type"] == "hub"
        assert row["from_location_id"] is None
        assert row["to_location_id"] is None
        assert row["default_label"] is None
        assert row["default_days"] is None

    def test_concrete_location_ids_pass_through(self) -> None:
        row = _build_template_segment_row(
            template_id="tpl-1",
            idx=2,
            seg={
                "from_location_type": "supplier",
                "to_location_type": "customs",
                "from_location_id": "loc-from",
                "to_location_id": "loc-to",
                "default_label": "Sea freight",
                "default_days": 14,
            },
        )
        assert row["from_location_id"] == "loc-from"
        assert row["to_location_id"] == "loc-to"
        assert row["default_label"] == "Sea freight"
        assert row["default_days"] == 14

    def test_partial_concrete_locations(self) -> None:
        """One side concrete, the other type-only — both surfaces supported."""
        row = _build_template_segment_row(
            template_id="tpl-1",
            idx=3,
            seg={
                "from_location_type": "customs",
                "to_location_type": "client",
                "from_location_id": "loc-customs",
            },
        )
        assert row["from_location_id"] == "loc-customs"
        assert row["to_location_id"] is None
