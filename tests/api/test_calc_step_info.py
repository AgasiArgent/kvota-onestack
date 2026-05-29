"""Tests for ``GET /api/quotes/{quote_id}/calc-step-info`` — info card data.

Testing 2 rows 36 + 48: the calc-step page needs an info card above the items
table that surfaces per-invoice logistics cost, per-item customs duties +
ТН ВЭД codes, and the certifications attached to the quote. The data already
exists in DB; this endpoint just aggregates the three sections into a single
response so the FE doesn't have to fan out 3 queries.

Covers:
- 401 when no JWT and no session.
- 403 when JWT user has no organization_members row.
- 404 when the quote isn't visible to the caller's org.
- Happy path: returns the three sections in the documented shape, with
  per-invoice logistics GROUPED into ``segments[]`` (Row 48a). Each segment
  carries its main cost converted to the quote currency, a derived label
  (free-text or ``from → to``), transit_days and a missing_rate flag.
  is_filled is false when an invoice has no segment with a resolved cost > 0.
  Customs surfaces ТН ВЭД (``hs_code``) + duty % (``customs_duty``) per
  quote_item; certifications carry cost + currency + type.

Supabase is mocked at ``api.calc_step_info.get_supabase`` so we never hit a
real DB; the data shape mirrors the live schema (kvota.logistics_route_segments,
kvota.quote_items, kvota.quote_certificates).
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from api.calc_step_info import get_calc_step_info  # noqa: E402


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_request(api_user_id: str | None = "user-1", email: str = "u@x.com"):
    req = MagicMock()
    if api_user_id is None:
        req.state = SimpleNamespace(api_user=None)
    else:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(id=api_user_id, email=email)
        )
    req.headers = {}
    type(req).session = property(
        lambda _self: (_ for _ in ()).throw(AssertionError("no session"))
    )
    return req


class _FakeQueryChain:
    """Chainable mock returning a fixed `.data` payload at the end."""

    def __init__(self, data):
        self._data = data

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def is_(self, *_a, **_kw):
        return self

    def in_(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def execute(self):
        return SimpleNamespace(data=self._data)


def _build_supabase_mock(
    *,
    org_id: str | None = "org-1",
    quote: dict | None = None,
    invoices: list[dict] | None = None,
    items: list[dict] | None = None,
    segments: list[dict] | None = None,
    certificates: list[dict] | None = None,
    fx_rates: list[dict] | None = None,
):
    """Mock Supabase with per-table chainable queries."""

    sb = MagicMock()

    def table_side_effect(name: str):
        if name == "organization_members":
            data = [{"organization_id": org_id}] if org_id else []
            return _FakeQueryChain(data)
        if name == "quotes":
            return _FakeQueryChain([quote] if quote else [])
        if name == "invoices":
            return _FakeQueryChain(invoices or [])
        if name == "quote_items":
            return _FakeQueryChain(items or [])
        if name == "logistics_route_segments":
            return _FakeQueryChain(segments or [])
        if name == "quote_certificates":
            return _FakeQueryChain(certificates or [])
        if name == "exchange_rates":
            return _FakeQueryChain(fx_rates or [])
        return _FakeQueryChain([])

    sb.table.side_effect = table_side_effect
    return sb


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ----------------------------------------------------------------------------
# Auth edge cases
# ----------------------------------------------------------------------------


class TestCalcStepInfoAuth:
    def test_no_auth_returns_401(self):
        req = _make_request(api_user_id=None)
        resp = _run(get_calc_step_info(req, "q-1"))
        assert resp.status_code == 401

    @patch("api.calc_step_info.get_supabase")
    def test_jwt_without_org_returns_403(self, mock_get_sb):
        mock_get_sb.return_value = _build_supabase_mock(org_id=None)
        req = _make_request(api_user_id="u-no-org")
        resp = _run(get_calc_step_info(req, "q-1"))
        assert resp.status_code == 403

    @patch("api.calc_step_info.get_supabase")
    def test_missing_quote_returns_404(self, mock_get_sb):
        # Org membership OK, but quote row not visible
        mock_get_sb.return_value = _build_supabase_mock(quote=None)
        req = _make_request(api_user_id="u-1")
        resp = _run(get_calc_step_info(req, "q-missing"))
        assert resp.status_code == 404


# ----------------------------------------------------------------------------
# Response shape
# ----------------------------------------------------------------------------


class TestCalcStepInfoShape:
    @patch("api.calc_step_info.get_supabase")
    def test_happy_path_returns_three_sections(self, mock_get_sb):
        """Quote with 2 invoices, 2 items, segments + certs → all sections populated."""
        mock_get_sb.return_value = _build_supabase_mock(
            quote={
                "id": "q-1",
                "organization_id": "org-1",
                "currency": "RUB",
            },
            invoices=[
                {
                    "id": "inv-1",
                    "invoice_number": "INV-001",
                    "supplier_id": "sup-1",
                    "logistics_completed_at": None,
                },
                {
                    "id": "inv-2",
                    "invoice_number": "INV-002",
                    "supplier_id": None,
                    "logistics_completed_at": None,
                },
            ],
            items=[
                {
                    "id": "qi-1",
                    "brand": "Brand A",
                    "product_name": "Pump",
                    "hs_code": "8413701000",
                    "customs_duty": 5.0,
                },
                {
                    "id": "qi-2",
                    "brand": "Brand B",
                    "product_name": "Valve",
                    "hs_code": "8481801990",
                    "customs_duty": 7.5,
                },
            ],
            segments=[
                {
                    "id": "seg-1",
                    "invoice_id": "inv-1",
                    "sequence_order": 0,
                    "transit_days": 14,
                    "label": None,
                    "main_cost_rub": 12000,
                    "currency_code": "RUB",
                    "from_location": {
                        "id": "loc-1",
                        "country": "Китай",
                        "city": "Шанхай",
                        "location_type": "supplier",
                    },
                    "to_location": {
                        "id": "loc-2",
                        "country": "Россия",
                        "city": "Москва",
                        "location_type": "hub",
                    },
                },
                {
                    "id": "seg-2",
                    "invoice_id": "inv-1",
                    "sequence_order": 1,
                    "transit_days": None,
                    "label": "Доставка по РФ",
                    "main_cost_rub": 3000,
                    "currency_code": "RUB",
                    "from_location": None,
                    "to_location": None,
                },
                # inv-2 has no segments → not_filled
            ],
            certificates=[
                {
                    "id": "cert-1",
                    "type": "ds",
                    "display_name": "ДС",
                    "cost_original": 8000,
                    "cost_currency": "RUB",
                }
            ],
        )

        req = _make_request(api_user_id="u-1")
        resp = _run(get_calc_step_info(req, "q-1"))

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert body["success"] is True

        data = body["data"]
        # 1. logistics_per_invoice — both invoices included, grouped per-segment
        assert "logistics_per_invoice" in data
        assert len(data["logistics_per_invoice"]) == 2
        by_id = {row["invoice_id"]: row for row in data["logistics_per_invoice"]}

        # inv-1: two segments, both priced → is_filled, ordered by sequence_order
        inv1 = by_id["inv-1"]
        assert inv1["is_filled"] is True
        assert inv1["segment_count"] == 2
        assert inv1["missing_rates"] == []
        segs = inv1["segments"]
        assert len(segs) == 2
        # seg-1: no free-text label → derived "from → to" with city
        assert segs[0]["segment_id"] == "seg-1"
        assert segs[0]["label"] == "Китай · Шанхай → Россия · Москва"
        assert segs[0]["cost"] == 12000
        assert segs[0]["currency"] == "RUB"
        assert segs[0]["transit_days"] == 14
        assert segs[0]["missing_rate"] is False
        # seg-2: free-text label wins; null locations are irrelevant here;
        # transit_days null → carried through as None for the "дн" chip.
        assert segs[1]["segment_id"] == "seg-2"
        assert segs[1]["label"] == "Доставка по РФ"
        assert segs[1]["cost"] == 3000
        assert segs[1]["transit_days"] is None

        # inv-2: no segments → unfilled, empty group
        assert by_id["inv-2"]["is_filled"] is False
        assert by_id["inv-2"]["segment_count"] == 0
        assert by_id["inv-2"]["segments"] == []

        # 2. customs — list of items with hs_code + duty
        assert "customs" in data
        assert len(data["customs"]) == 2
        customs_by_item = {c["item_id"]: c for c in data["customs"]}
        assert customs_by_item["qi-1"]["hs_code"] == "8413701000"
        assert customs_by_item["qi-1"]["customs_duty"] == 5.0
        assert customs_by_item["qi-1"]["brand"] == "Brand A"
        assert customs_by_item["qi-1"]["product_name"] == "Pump"
        assert customs_by_item["qi-2"]["customs_duty"] == 7.5

        # 3. certifications
        assert "certifications" in data
        assert len(data["certifications"]) == 1
        cert = data["certifications"][0]
        assert cert["type"] == "ds"
        assert cert["display_name"] == "ДС"
        assert cert["cost"] == 8000
        assert cert["currency"] == "RUB"

    @patch("api.calc_step_info.get_supabase")
    def test_empty_quote_returns_empty_sections(self, mock_get_sb):
        """Quote with no invoices, no items, no certs → empty arrays (200)."""
        mock_get_sb.return_value = _build_supabase_mock(
            quote={"id": "q-1", "organization_id": "org-1", "currency": "RUB"},
        )
        req = _make_request(api_user_id="u-1")
        resp = _run(get_calc_step_info(req, "q-1"))

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        data = body["data"]
        assert data["logistics_per_invoice"] == []
        assert data["customs"] == []
        assert data["certifications"] == []

    @patch("api.calc_step_info.get_supabase")
    def test_invoice_with_zero_cost_segments_is_unfilled(self, mock_get_sb):
        """Segments exist but main_cost_rub = 0 → still not_filled (logistics
        defaults to 0 when the route hasn't been priced yet). The segment row
        is still emitted so the label/days remain visible."""
        mock_get_sb.return_value = _build_supabase_mock(
            quote={"id": "q-1", "organization_id": "org-1", "currency": "RUB"},
            invoices=[{"id": "inv-1", "invoice_number": "INV-001"}],
            segments=[
                {
                    "id": "seg-1",
                    "invoice_id": "inv-1",
                    "sequence_order": 0,
                    "transit_days": 3,
                    "label": None,
                    "main_cost_rub": 0,
                    "currency_code": "RUB",
                    "from_location": None,
                    "to_location": {
                        "id": "loc-9",
                        "country": "Россия",
                        "city": None,
                        "location_type": "client",
                    },
                }
            ],
        )
        req = _make_request(api_user_id="u-1")
        resp = _run(get_calc_step_info(req, "q-1"))

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        row = body["data"]["logistics_per_invoice"][0]
        assert row["is_filled"] is False
        assert row["segment_count"] == 1
        seg = row["segments"][0]
        assert seg["cost"] == 0
        # Null from_location → "Не выбрано"; to_location has no city → country only.
        assert seg["label"] == "Не выбрано → Россия"
        assert seg["transit_days"] == 3

    @patch("api.calc_step_info.get_supabase")
    def test_foreign_segment_converted_to_quote_currency(self, mock_get_sb):
        """A USD segment is converted foreign→RUB→quote currency. With a USD→RUB
        rate of 90 and a EUR (quote) →RUB rate of 100, a $200 segment becomes
        200·90/100 = 180 EUR. A segment whose currency has no rate is flagged
        missing_rate and contributes cost 0."""
        mock_get_sb.return_value = _build_supabase_mock(
            quote={"id": "q-1", "organization_id": "org-1", "currency": "EUR"},
            invoices=[{"id": "inv-1", "invoice_number": "INV-001"}],
            segments=[
                {
                    "id": "seg-usd",
                    "invoice_id": "inv-1",
                    "sequence_order": 0,
                    "transit_days": None,
                    "label": "Море",
                    "main_cost_rub": 200,
                    "currency_code": "USD",
                    "from_location": None,
                    "to_location": None,
                },
                {
                    "id": "seg-cny",
                    "invoice_id": "inv-1",
                    "sequence_order": 1,
                    "transit_days": None,
                    "label": "Авто",
                    "main_cost_rub": 500,
                    "currency_code": "CNY",  # no rate provided → missing
                    "from_location": None,
                    "to_location": None,
                },
            ],
            fx_rates=[
                {"from_currency": "USD", "rate": 90, "fetched_at": "2026-05-29"},
                {"from_currency": "EUR", "rate": 100, "fetched_at": "2026-05-29"},
            ],
        )
        req = _make_request(api_user_id="u-1")
        resp = _run(get_calc_step_info(req, "q-1"))

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        row = body["data"]["logistics_per_invoice"][0]
        segs = {s["segment_id"]: s for s in row["segments"]}
        # USD → quote (EUR): 200 * 90 / 100 = 180
        assert segs["seg-usd"]["cost"] == 180
        assert segs["seg-usd"]["currency"] == "EUR"
        assert segs["seg-usd"]["missing_rate"] is False
        # CNY has no rate → flagged, cost 0
        assert segs["seg-cny"]["missing_rate"] is True
        assert segs["seg-cny"]["cost"] == 0
        assert "CNY" in row["missing_rates"]
        # is_filled true because USD segment resolved to > 0
        assert row["is_filled"] is True

    @patch("api.calc_step_info.get_supabase")
    def test_items_without_hs_or_duty_still_returned(self, mock_get_sb):
        """Items missing hs_code / customs_duty appear with null fields."""
        mock_get_sb.return_value = _build_supabase_mock(
            quote={"id": "q-1", "organization_id": "org-1", "currency": "RUB"},
            items=[
                {
                    "id": "qi-1",
                    "brand": "B",
                    "product_name": "P",
                    "hs_code": None,
                    "customs_duty": None,
                }
            ],
        )
        req = _make_request(api_user_id="u-1")
        resp = _run(get_calc_step_info(req, "q-1"))

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        c = body["data"]["customs"][0]
        assert c["hs_code"] is None
        assert c["customs_duty"] is None
