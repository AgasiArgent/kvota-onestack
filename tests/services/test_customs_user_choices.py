"""Tests for services/customs_user_choices.py — Phase A Req 10 history service."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from services.alta_client import Rate
from services.customs_user_choices import (
    HistoryMatch,
    find_recent,
    log_choice,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rate(
    *,
    payment_type: str = "IMP",
    category_code: str | None = None,
    value_1_number: float | None = 10.0,
    description: str | None = None,
    tnved_code: str = "8504408200",
    country_or_areal: str | None = "C:156",
) -> Rate:
    """Minimal Rate fixture that satisfies __post_init__ invariants."""
    return Rate(
        tnved_code=tnved_code,
        payment_type=payment_type,
        country_or_areal=country_or_areal,
        valid_from=date(2025, 1, 1),
        value_1_number=value_1_number,
        value_1_unit="percent",
        category_code=category_code,
        description=description,
    )


def _make_capture_sb():
    """Mock supabase whose .insert() captures the payload for assertions."""
    sb = MagicMock()
    captured: dict = {}

    def capture_insert(payload):
        captured["payload"] = payload
        execute = MagicMock()
        execute.execute.return_value = MagicMock(data=[])
        return execute

    sb.table.return_value.insert.side_effect = capture_insert
    return sb, captured


def _make_select_sb(rows: list[dict]):
    """Mock supabase whose SELECT chain returns ``rows``."""
    sb = MagicMock()
    chain = MagicMock()
    (chain.select.return_value
          .eq.return_value
          .eq.return_value
          .eq.return_value
          .order.return_value
          .limit.return_value
          .execute.return_value) = MagicMock(data=rows)
    sb.table.return_value = chain
    return sb


# ---------------------------------------------------------------------------
# log_choice
# ---------------------------------------------------------------------------


def test_log_choice_writes_full_payload():
    """All 6 chosen_*_variant JSONB fields + manual flags hit the INSERT."""
    sb, captured = _make_capture_sb()
    chosen = {
        "IMP": _rate(payment_type="IMP", category_code="imp_default", value_1_number=10.0),
        "IMPDEMP": _rate(payment_type="IMPDEMP", category_code="adp_brand_x", value_1_number=12.5),
        "IMPCOMP": _rate(payment_type="IMPCOMP", category_code="comp_default", value_1_number=5.0),
        "IMPDOP": _rate(payment_type="IMPDOP", category_code="dop_default", value_1_number=2.0),
        "IMPTMP": _rate(payment_type="IMPTMP", category_code="tmp_default", value_1_number=1.0),
        "NDS": _rate(payment_type="NDS", category_code="nds_med", value_1_number=10.0),
    }
    manual_payload = {"value_1_number": 7.5, "value_1_unit": "percent"}

    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ):
        log_choice(
            organization_id="org-1",
            user_id="user-1",
            tnved_code="8504408200",
            country_oksm=156,
            chosen_variants=chosen,
            manual_override=True,
            manual_rate_payload=manual_payload,
        )

    payload = captured["payload"]
    assert payload["organization_id"] == "org-1"
    assert payload["user_id"] == "user-1"
    assert payload["tnved_code"] == "8504408200"
    assert payload["country_oksm"] == 156
    assert payload["manual_override"] is True
    assert payload["manual_rate_payload"] == manual_payload
    # Each payment_type slot should serialise to its own JSONB column
    assert payload["chosen_imp_variant"]["category_code"] == "imp_default"
    assert payload["chosen_imp_variant"]["payment_type"] == "IMP"
    assert payload["chosen_impdemp_variant"]["category_code"] == "adp_brand_x"
    assert payload["chosen_impcomp_variant"]["value_1_number"] == 5.0
    assert payload["chosen_impdop_variant"]["category_code"] == "dop_default"
    assert payload["chosen_imptmp_variant"]["value_1_number"] == 1.0
    assert payload["chosen_nds_variant"]["category_code"] == "nds_med"


def test_log_choice_swallows_db_errors(caplog):
    """DB connection errors must NOT raise — fire-and-forget contract."""
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.side_effect = (
        ConnectionError("db down")
    )

    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ):
        # Must not raise
        with caplog.at_level("WARNING", logger="services.customs_user_choices"):
            log_choice(
                organization_id="org-1",
                user_id="user-1",
                tnved_code="8504408200",
                country_oksm=156,
                chosen_variants={"IMP": _rate()},
            )

    # logger.warning should have been emitted with org + code context
    assert any(
        "failed to log choice" in rec.message
        and "org=org-1" in rec.message
        and "code=8504408200" in rec.message
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# find_recent
# ---------------------------------------------------------------------------


def test_find_recent_returns_none_when_no_history():
    """Empty result set → None (UI shows no autofill suggestion)."""
    sb = _make_select_sb([])
    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ):
        match = find_recent(
            organization_id="org-1",
            tnved_code="8504408200",
            country_oksm=156,
        )
    assert match is None


def test_find_recent_returns_last_match():
    """Returns the row produced by the LIMIT 1 ORDER BY created_at DESC chain."""
    serialized_imp = {
        "tnved_code": "8504408200",
        "payment_type": "IMP",
        "country_or_areal": "C:156",
        "valid_from": "2025-01-01",
        "valid_to": None,
        "value_1_number": 10.0,
        "value_1_unit": "percent",
        "category_code": "imp_default",
        "is_default": True,
    }
    rows = [
        {
            "user_id": "user-recent",
            "chosen_imp_variant": serialized_imp,
            "chosen_impdemp_variant": None,
            "chosen_impcomp_variant": None,
            "chosen_impdop_variant": None,
            "chosen_imptmp_variant": None,
            "chosen_nds_variant": None,
            "manual_override": False,
            "manual_rate_payload": None,
            "created_at": "2026-04-22T10:30:00+00:00",
        }
    ]
    sb = _make_select_sb(rows)

    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ), patch(
        "services.customs_user_choices._fetch_user_email",
        return_value="customs@example.com",
    ):
        match = find_recent(
            organization_id="org-1",
            tnved_code="8504408200",
            country_oksm=156,
        )

    # Verify the SELECT chain was driven with the expected ordering
    chain = sb.table.return_value
    chain.select.assert_called_once()
    order_call = chain.select.return_value.eq.return_value.eq.return_value.eq.return_value.order
    order_call.assert_called_once_with("created_at", desc=True)
    limit_call = order_call.return_value.limit
    limit_call.assert_called_once_with(1)

    assert isinstance(match, HistoryMatch)
    assert match.user_id == "user-recent"
    assert match.user_email == "customs@example.com"
    assert match.manual_override is False
    assert match.manual_rate_payload is None
    assert match.is_actual is True  # no actual_variants → defaults True
    # Only IMP slot was populated; other payment_types stay absent
    assert set(match.chosen_variants.keys()) == {"IMP"}
    imp = match.chosen_variants["IMP"]
    assert imp.category_code == "imp_default"
    assert imp.value_1_number == 10.0


def test_find_recent_no_actual_variants_returns_is_actual_true():
    """When caller doesn't pass actual_variants, is_actual defaults to True."""
    rows = [
        {
            "user_id": "user-1",
            "chosen_imp_variant": {
                "tnved_code": "8504408200",
                "payment_type": "IMP",
                "country_or_areal": "C:156",
                "valid_from": "2025-01-01",
                "value_1_number": 10.0,
                "value_1_unit": "percent",
                "category_code": "imp_default",
            },
            "chosen_impdemp_variant": None,
            "chosen_impcomp_variant": None,
            "chosen_impdop_variant": None,
            "chosen_imptmp_variant": None,
            "chosen_nds_variant": None,
            "manual_override": False,
            "manual_rate_payload": None,
            "created_at": "2026-04-22T10:30:00+00:00",
        }
    ]
    sb = _make_select_sb(rows)
    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ), patch(
        "services.customs_user_choices._fetch_user_email", return_value=None
    ):
        match = find_recent(
            organization_id="org-1",
            tnved_code="8504408200",
            country_oksm=156,
            actual_variants=None,
        )
    assert match is not None
    assert match.is_actual is True


def test_find_recent_is_actual_loose_match():
    """LOOSE match — category_code AND value_1_number both must match.

    Description differences tolerated (Alta sometimes rephrases). Cases:
      A. exact (category_code + value_1_number match) → True
      B. description differs but category_code+value match → True
      C. category_code differs → False
      D. value_1_number differs (Alta изменил ставку) → False
    """
    chosen_serialized = {
        "tnved_code": "0123456789",
        "payment_type": "NDS",
        "country_or_areal": "C:156",
        "valid_from": "2025-01-01",
        "value_1_number": 22.0,
        "value_1_unit": "percent",
        "category_code": "nds_med",
        "description": "- Прочие",
    }
    rows = [
        {
            "user_id": "user-1",
            "chosen_imp_variant": None,
            "chosen_impdemp_variant": None,
            "chosen_impcomp_variant": None,
            "chosen_impdop_variant": None,
            "chosen_imptmp_variant": None,
            "chosen_nds_variant": chosen_serialized,
            "manual_override": False,
            "manual_rate_payload": None,
            "created_at": "2026-04-22T10:30:00+00:00",
        }
    ]
    sb = _make_select_sb(rows)

    # --- Case A: exact match (same category_code, same value_1_number)
    actual_a = {
        "NDS": [
            _rate(
                payment_type="NDS",
                category_code="nds_med",
                value_1_number=22.0,
                description="- Прочие",
            )
        ]
    }
    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ), patch(
        "services.customs_user_choices._fetch_user_email", return_value=None
    ):
        match_a = find_recent(
            organization_id="org-1",
            tnved_code="0123456789",
            country_oksm=156,
            actual_variants=actual_a,
        )
    assert match_a is not None
    assert match_a.is_actual is True

    # --- Case B: description differs but category_code+value match → True (LOOSE)
    actual_b = {
        "NDS": [
            _rate(
                payment_type="NDS",
                category_code="nds_med",
                value_1_number=22.0,
                description="- Иные товары",   # Alta rephrased
            )
        ]
    }
    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ), patch(
        "services.customs_user_choices._fetch_user_email", return_value=None
    ):
        match_b = find_recent(
            organization_id="org-1",
            tnved_code="0123456789",
            country_oksm=156,
            actual_variants=actual_b,
        )
    assert match_b is not None
    assert match_b.is_actual is True

    # --- Case C: category_code differs → False
    actual_c = {
        "NDS": [
            _rate(
                payment_type="NDS",
                category_code="nds_inv",     # different category
                value_1_number=22.0,
            )
        ]
    }
    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ), patch(
        "services.customs_user_choices._fetch_user_email", return_value=None
    ):
        match_c = find_recent(
            organization_id="org-1",
            tnved_code="0123456789",
            country_oksm=156,
            actual_variants=actual_c,
        )
    assert match_c is not None
    assert match_c.is_actual is False

    # --- Case D: value_1_number differs (Alta changed the rate) → False
    actual_d = {
        "NDS": [
            _rate(
                payment_type="NDS",
                category_code="nds_med",
                value_1_number=20.0,         # rate changed
            )
        ]
    }
    with patch(
        "services.customs_user_choices.get_supabase", return_value=sb
    ), patch(
        "services.customs_user_choices._fetch_user_email", return_value=None
    ):
        match_d = find_recent(
            organization_id="org-1",
            tnved_code="0123456789",
            country_oksm=156,
            actual_variants=actual_d,
        )
    assert match_d is not None
    assert match_d.is_actual is False
