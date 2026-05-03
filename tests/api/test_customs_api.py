"""Tests for new customs API endpoints — REQ-5 customs-phase-1.

Covers ``resolve_rates_handler``, ``non_tariff_measures_handler``, and the
extended ``autofill_handler`` (force_live → rate_resolver fallback).

Mocks both ``services.database.get_supabase`` and ``AltaClient`` (via the
``rate_resolver``/``alta_client`` modules) so the suite never hits a real
DB or the live Alta API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.alta_client import AltaApiError, Measure, Rate  # noqa: E402
from services.rate_resolver import ResolvedRate  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_request(
    *,
    api_user_id: str | None = "user-1",
    user_metadata: dict | None = None,
    session_user: dict | None = None,
    body: dict | None = None,
    raw_body_error: bool = False,
):
    """Build a minimal Starlette-style request with optional JWT/session + body."""
    req = MagicMock()
    if api_user_id is not None:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(
                id=api_user_id,
                email="u@x.com",
                user_metadata=user_metadata or {"org_id": "o-1"},
            )
        )
    else:
        req.state = SimpleNamespace(api_user=None)

    if session_user is not None:
        session = {"user": session_user}
        type(req).session = property(lambda self: session)
    else:
        type(req).session = property(
            lambda self: (_ for _ in ()).throw(AssertionError("no session"))
        )

    req.headers = {"content-type": "application/json"}

    async def _json():
        if raw_body_error:
            raise ValueError("bad json")
        return body or {}

    req.json = _json
    return req


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(response) -> dict:
    return json.loads(response.body)


def _make_resolved_rate(
    *,
    rate_id: str = "rate-1",
    payment_type: str = "IMP",
    value_1_number: float = 10.0,
    value_1_unit: str = "percent",
    value_1_currency: str | None = None,
    raw_value_string: str = "10%",
    source: str = "alta-live",
    fetched_at: datetime | None = None,
) -> ResolvedRate:
    rate = Rate(
        tnved_code="8409910008",
        payment_type=payment_type,
        country_or_areal="C:156",
        valid_from=date(2026, 1, 1),
        value_1_number=value_1_number,
        value_1_unit=value_1_unit,
        value_1_currency=value_1_currency,
        raw_value_string=raw_value_string,
        source=source,
    )
    fetched = fetched_at or datetime.now(timezone.utc)
    return ResolvedRate(
        id=rate_id,
        rate=rate,
        source=source,
        source_fetched_at=fetched,
        last_used_at=fetched,
    )


def _make_measure(
    *,
    measure_type: str = "certification",
    name: str = "Сертификация",
    description: str | None = "ТР ТС 010/2011",
    document_basis: str | None = "ТР ТС 010/2011",
    document_link: str | None = "https://pravo.gov.ru/example",
) -> Measure:
    return Measure(
        tnved_code="8409910008",
        country_or_areal="C:156",
        measure_type=measure_type,
        name=name,
        description=description,
        document_basis=document_basis,
        document_link=document_link,
    )


def _patch_country_lookup_ok():
    """Patch supabase to make countries.oksm_digital lookup return a row."""
    mock_sb = MagicMock()

    countries_exec = MagicMock()
    countries_exec.data = [{"oksm_digital": 156}]
    countries_chain = MagicMock()
    (
        countries_chain.select.return_value.eq.return_value.limit.return_value.execute.return_value
    ) = countries_exec

    item_update_exec = MagicMock()
    item_update_exec.data = []
    item_chain = MagicMock()
    (
        item_chain.update.return_value.eq.return_value.execute.return_value
    ) = item_update_exec

    def table(name: str):
        if name == "countries":
            return countries_chain
        if name == "quote_items":
            return item_chain
        return MagicMock()

    mock_sb.table.side_effect = table
    return mock_sb, item_chain


def _patch_country_lookup_missing():
    """Patch supabase so countries.oksm_digital lookup is empty (INVALID_OKSM)."""
    mock_sb = MagicMock()
    countries_exec = MagicMock()
    countries_exec.data = []
    countries_chain = MagicMock()
    (
        countries_chain.select.return_value.eq.return_value.limit.return_value.execute.return_value
    ) = countries_exec

    def table(name: str):
        if name == "countries":
            return countries_chain
        return MagicMock()

    mock_sb.table.side_effect = table
    return mock_sb


# ===========================================================================
# resolve_rates_handler
# ===========================================================================


class TestResolveRatesHandler:
    """POST /api/customs/resolve-rates — REQ-5 AC#1, #4-9."""

    def test_unauthenticated_returns_401(self):
        from api.customs import resolve_rates_handler

        req = _make_request(api_user_id=None)
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 401
        assert _body(resp)["success"] is False
        assert _body(resp)["error"]["code"] == "UNAUTHORIZED"

    @patch("api.customs.get_user_role_codes")
    def test_non_customs_role_returns_403(self, mock_roles):
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["sales"]
        req = _make_request(
            body={"tnved_code": "8409910008", "country_oksm": 156}
        )
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 403
        assert _body(resp)["error"]["code"] == "FORBIDDEN"

    @patch("api.customs.get_user_role_codes")
    def test_invalid_json_returns_400(self, mock_roles):
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(raw_body_error=True)
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "BAD_REQUEST"

    @patch("api.customs.get_user_role_codes")
    def test_invalid_tnved_code_returns_400(self, mock_roles):
        """tnved_code not 10 digits → 400 INVALID_TNVED_CODE."""
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(body={"tnved_code": "12345", "country_oksm": 156})
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "INVALID_TNVED_CODE"
        # Field-specific message
        assert "tnved_code" in _body(resp)["error"]["message"].lower()

    @patch("api.customs.get_user_role_codes")
    def test_missing_tnved_code_returns_400(self, mock_roles):
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(body={"country_oksm": 156})
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 400
        # Either INVALID_TNVED_CODE or BAD_REQUEST is acceptable for missing field
        assert _body(resp)["error"]["code"] in ("INVALID_TNVED_CODE", "BAD_REQUEST")

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_unknown_country_returns_400(self, mock_roles, mock_get_sb):
        """country_oksm not in kvota.countries → 400 INVALID_OKSM."""
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["customs"]
        mock_get_sb.return_value = _patch_country_lookup_missing()

        req = _make_request(
            body={"tnved_code": "8409910008", "country_oksm": 99999}
        )
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "INVALID_OKSM"

    @patch("api.customs.rate_resolver")
    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_happy_path_returns_rates(
        self, mock_roles, mock_get_sb, mock_rate_resolver
    ):
        """Resolver returns rates → 200 with rates + source + fetched_at."""
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["customs"]
        mock_sb, _ = _patch_country_lookup_ok()
        mock_get_sb.return_value = mock_sb

        # First call returns IMP rate, others return None
        async def _resolve(*args, **kwargs):
            payment_type = kwargs.get("payment_type")
            if payment_type == "IMP":
                return _make_resolved_rate(payment_type="IMP")
            if payment_type == "NDS":
                return _make_resolved_rate(
                    payment_type="NDS",
                    value_1_number=20.0,
                    raw_value_string="20%",
                )
            return None

        mock_rate_resolver.resolve_rate = AsyncMock(side_effect=_resolve)

        req = _make_request(
            body={"tnved_code": "8409910008", "country_oksm": 156}
        )
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 200
        body = _body(resp)
        assert body["success"] is True
        assert "rates" in body["data"]
        assert "source" in body["data"]
        assert "fetched_at" in body["data"]
        assert len(body["data"]["rates"]) >= 1
        # Resolver called for at least IMP and NDS
        assert mock_rate_resolver.resolve_rate.await_count >= 2

    @patch("api.customs.rate_resolver")
    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_503_when_alta_unavailable(
        self, mock_roles, mock_get_sb, mock_rate_resolver
    ):
        """Resolver returns None for ALL payment_types → 503 ALTA_UNAVAILABLE."""
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["customs"]
        mock_sb, _ = _patch_country_lookup_ok()
        mock_get_sb.return_value = mock_sb
        mock_rate_resolver.resolve_rate = AsyncMock(return_value=None)

        req = _make_request(
            body={"tnved_code": "8409910008", "country_oksm": 156}
        )
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 503
        assert _body(resp)["error"]["code"] == "ALTA_UNAVAILABLE"

    @patch("api.customs.rate_resolver")
    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_quote_item_id_triggers_update(
        self, mock_roles, mock_get_sb, mock_rate_resolver
    ):
        """quote_item_id provided → UPDATE quote_items issued."""
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["customs"]
        mock_sb, item_chain = _patch_country_lookup_ok()
        mock_get_sb.return_value = mock_sb
        mock_rate_resolver.resolve_rate = AsyncMock(
            return_value=_make_resolved_rate()
        )

        req = _make_request(
            body={
                "tnved_code": "8409910008",
                "country_oksm": 156,
                "quote_item_id": "qi-1",
            }
        )
        alta_client = MagicMock()
        resp = _run(resolve_rates_handler(req, alta_client))
        assert resp.status_code == 200

        # Verify quote_items.update was called
        assert item_chain.update.call_count >= 1
        update_payload = item_chain.update.call_args[0][0]
        assert update_payload.get("country_of_origin_oksm") == 156

    @patch("api.customs.rate_resolver")
    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_logs_structured_fields(
        self, mock_roles, mock_get_sb, mock_rate_resolver, caplog
    ):
        """REQ-5 AC#9: log user_id, tnved_code, country_oksm, source, cache_hit."""
        from api.customs import resolve_rates_handler

        mock_roles.return_value = ["customs"]
        mock_sb, _ = _patch_country_lookup_ok()
        mock_get_sb.return_value = mock_sb
        mock_rate_resolver.resolve_rate = AsyncMock(
            return_value=_make_resolved_rate()
        )

        req = _make_request(
            body={"tnved_code": "8409910008", "country_oksm": 156}
        )
        alta_client = MagicMock()
        with caplog.at_level(logging.INFO, logger="api.customs"):
            _run(resolve_rates_handler(req, alta_client))

        # At least one log record with structured info
        records = [
            r for r in caplog.records if "customs_resolve_rates" in r.getMessage()
        ]
        assert len(records) >= 1
        rec = records[0]
        # Structured fields attached via extra=
        assert getattr(rec, "user_id", None) == "user-1"
        assert getattr(rec, "tnved_code", None) == "8409910008"
        assert getattr(rec, "country_oksm", None) == 156
        assert hasattr(rec, "source")
        assert hasattr(rec, "cache_hit")


# ===========================================================================
# non_tariff_measures_handler
# ===========================================================================


class TestNonTariffMeasuresHandler:
    """POST /api/customs/non-tariff-measures — REQ-5 AC#2."""

    def test_unauthenticated_returns_401(self):
        from api.customs import non_tariff_measures_handler

        req = _make_request(api_user_id=None)
        alta_client = MagicMock()
        resp = _run(non_tariff_measures_handler(req, alta_client))
        assert resp.status_code == 401
        assert _body(resp)["error"]["code"] == "UNAUTHORIZED"

    @patch("api.customs.get_user_role_codes")
    def test_non_customs_role_returns_403(self, mock_roles):
        from api.customs import non_tariff_measures_handler

        mock_roles.return_value = ["sales"]
        req = _make_request(
            body={"tnved_code": "8409910008", "country_oksm": 156}
        )
        alta_client = MagicMock()
        resp = _run(non_tariff_measures_handler(req, alta_client))
        assert resp.status_code == 403
        assert _body(resp)["error"]["code"] == "FORBIDDEN"

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_happy_path_returns_measures(
        self, mock_roles, mock_get_sb
    ):
        from api.customs import non_tariff_measures_handler

        mock_roles.return_value = ["customs"]
        mock_sb, _ = _patch_country_lookup_ok()
        mock_get_sb.return_value = mock_sb

        alta_client = MagicMock()
        alta_client.get_non_tariff_measures = AsyncMock(
            return_value=[_make_measure()]
        )

        req = _make_request(
            body={"tnved_code": "8409910008", "country_oksm": 156}
        )
        resp = _run(non_tariff_measures_handler(req, alta_client))
        assert resp.status_code == 200
        body = _body(resp)
        assert body["success"] is True
        assert "measures" in body["data"]
        assert len(body["data"]["measures"]) == 1
        m = body["data"]["measures"][0]
        assert m["measure_type"] == "certification"
        assert m["name"] == "Сертификация"
        assert "fetched_at" in body["data"]
        assert "source" in body["data"]

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_503_on_alta_error(self, mock_roles, mock_get_sb):
        from api.customs import non_tariff_measures_handler

        mock_roles.return_value = ["customs"]
        mock_sb, _ = _patch_country_lookup_ok()
        mock_get_sb.return_value = mock_sb

        alta_client = MagicMock()
        alta_client.get_non_tariff_measures = AsyncMock(
            side_effect=AltaApiError(110, "limit reached")
        )

        req = _make_request(
            body={"tnved_code": "8409910008", "country_oksm": 156}
        )
        resp = _run(non_tariff_measures_handler(req, alta_client))
        assert resp.status_code == 503
        assert _body(resp)["error"]["code"] == "ALTA_UNAVAILABLE"

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_invalid_tnved_returns_400(self, mock_roles, mock_get_sb):
        from api.customs import non_tariff_measures_handler

        mock_roles.return_value = ["customs"]
        mock_sb, _ = _patch_country_lookup_ok()
        mock_get_sb.return_value = mock_sb

        alta_client = MagicMock()
        req = _make_request(body={"tnved_code": "1234", "country_oksm": 156})
        resp = _run(non_tariff_measures_handler(req, alta_client))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "INVALID_TNVED_CODE"


# ===========================================================================
# autofill_handler — backwards-compat + new force_live extension
# ===========================================================================


class TestAutofillBackwardsCompat:
    """Existing autofill response shape MUST NOT break — REQ-5 AC#3."""

    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_existing_fields_unchanged_without_force_live(
        self, mock_roles, mock_get_sb
    ):
        """Without force_live=True, response shape matches existing contract."""
        from api.customs import _AUTOFILL_FIELDS, autofill_handler

        # Verify _AUTOFILL_FIELDS still contains all original keys (additive only)
        legacy_required = {
            "hs_code",
            "customs_duty",
            "customs_duty_per_kg",
            "customs_util_fee",
            "customs_excise",
            "customs_eco_fee",
            "customs_honest_mark",
            "license_ds_required",
            "license_ss_required",
            "license_sgr_required",
            "license_ds_cost",
            "license_ss_cost",
            "license_sgr_cost",
        }
        assert legacy_required.issubset(set(_AUTOFILL_FIELDS)), (
            f"_AUTOFILL_FIELDS must remain strictly additive — "
            f"missing legacy keys: {legacy_required - set(_AUTOFILL_FIELDS)}"
        )

        # Run handler with no historical match — should still return success+empty
        mock_roles.return_value = ["customs"]
        mock_sb = MagicMock()
        empty_exec = MagicMock()
        empty_exec.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.not_.is_.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = empty_exec
        mock_get_sb.return_value = mock_sb

        req = _make_request(
            body={
                "items": [
                    {
                        "id": "i-1",
                        "brand": "SKF",
                        "product_code": "6203",
                    }
                ]
            }
        )
        resp = _run(autofill_handler(req))
        assert resp.status_code == 200
        body = _body(resp)
        assert body["success"] is True
        assert "data" in body
        assert "suggestions" in body["data"]


class TestAutofillForceLive:
    """force_live=True triggers rate_resolver fallback — REQ-5 AC#3."""

    @patch("api.customs.rate_resolver")
    @patch("api.customs.get_supabase")
    @patch("api.customs.get_user_role_codes")
    def test_force_live_falls_back_to_resolver_when_no_history(
        self, mock_roles, mock_get_sb, mock_rate_resolver
    ):
        """No historical match + force_live=True → resolver called + new fields appended."""
        from api.customs import autofill_handler

        mock_roles.return_value = ["customs"]

        # Empty historical lookup
        mock_sb = MagicMock()
        empty_exec = MagicMock()
        empty_exec.data = []

        # Build chain: select->eq->eq->not_.is_->eq->order->limit->execute
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.not_.is_.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = empty_exec
        mock_get_sb.return_value = mock_sb

        # Resolver yields a rate
        mock_rate_resolver.resolve_rate = AsyncMock(
            return_value=_make_resolved_rate()
        )

        req = _make_request(
            body={
                "items": [
                    {
                        "id": "i-1",
                        "brand": "SKF",
                        "product_code": "6203",
                        "tnved_code": "8409910008",
                        "country_oksm": 156,
                    }
                ],
                "force_live": True,
            }
        )
        # Pass an explicit (mock) Alta client so the handler doesn't need
        # ALTA_LOGIN/ALTA_PASSWORD env vars in test runs.
        alta_client = MagicMock()
        resp = _run(autofill_handler(req, alta_client))
        assert resp.status_code == 200
        body = _body(resp)
        assert body["success"] is True
        suggestions = body["data"]["suggestions"]
        # At least one suggestion produced via the resolver fallback
        assert len(suggestions) >= 1
        # Verify resolver was invoked (since force_live=True triggers fallback)
        assert mock_rate_resolver.resolve_rate.await_count >= 1
        # Suggestion includes the new optional fields
        s = suggestions[0]
        assert "customs_rates_source" in s
        assert "customs_rates_fetched_at" in s
