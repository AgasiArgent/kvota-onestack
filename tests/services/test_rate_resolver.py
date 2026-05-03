"""Unit tests for services.rate_resolver — REQ-3 acceptance criteria.

Mocks both ``services.database.get_supabase`` and ``AltaClient`` so the
suite never hits a real DB or the live Alta API. The Supabase mock
emulates the chained query API enough to cover the resolver's calls.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.alta_client import AltaApiError, Rate
from services.rate_resolver import (
    CACHE_TTL,
    FROZEN_STATUSES,
    ResolvedRate,
    ResolveOutcome,
    ResolveResult,
    resolve_rate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _row(
    *,
    id: str = "rate-1",
    tnved_code: str = "8409910008",
    payment_type: str = "IMP",
    country_or_areal: str | None = "C:156",
    valid_from: str = "2026-01-01",
    valid_to: str | None = None,
    value_1_number: float = 10.0,
    value_1_unit: str = "percent",
    value_1_currency: str | None = None,
    source: str = "alta-live",
    source_fetched_at: str | None = None,
    last_used_at: str | None = None,
    certificate_required: bool = False,
    sp_certificate_required: bool = False,
    raw_value_string: str = "10%",
) -> dict:
    """Build a minimal kvota.tnved_rates row dict matching what the
    Supabase client would return."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": id,
        "tnved_code": tnved_code,
        "payment_type": payment_type,
        "country_or_areal": country_or_areal,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "value_1_number": value_1_number,
        "value_1_unit": value_1_unit,
        "value_1_currency": value_1_currency,
        "value_2_number": None,
        "value_2_unit": None,
        "value_2_currency": None,
        "sign_1": None,
        "value_3_number": None,
        "value_3_unit": None,
        "value_3_currency": None,
        "sign_2": None,
        "raw_value_string": raw_value_string,
        "certificate_required": certificate_required,
        "sp_certificate_required": sp_certificate_required,
        "source": source,
        "source_fetched_at": source_fetched_at or now,
        "last_used_at": last_used_at or now,
    }


def _make_rate(
    *,
    tnved_code: str = "8409910008",
    payment_type: str = "IMP",
    country_or_areal: str | None = "C:156",
    valid_from: date = date(2026, 1, 1),
    value_1_number: float = 10.0,
    value_1_unit: str = "percent",
    value_1_currency: str | None = None,
) -> Rate:
    return Rate(
        tnved_code=tnved_code,
        payment_type=payment_type,
        country_or_areal=country_or_areal,
        valid_from=valid_from,
        value_1_number=value_1_number,
        value_1_unit=value_1_unit,
        value_1_currency=value_1_currency,
        raw_value_string=f"{value_1_number}{value_1_unit}",
    )


class _MockTable:
    """Minimal builder that mimics supabase-py's chained query API.

    Configure with ``set_select(rows)`` to make ``.execute()`` return
    those rows for any chain that ends in ``.execute()``. Tracks every
    chain method call so tests can assert on them.
    """

    def __init__(self, name: str, recorder: list[tuple]) -> None:
        self._name = name
        self._recorder = recorder
        self._select_rows: list[dict] = []
        self._upsert_rows: list[list[dict]] = []
        self._update_payloads: list[dict] = []
        self._is_filters: list[tuple[str, str]] = []
        self._eq_filters: list[tuple[str, object]] = []
        self._single_pending = False  # set by .single(), cleared by .execute()

    def set_select(self, rows: list[dict]) -> None:
        self._select_rows = rows

    @property
    def upserts(self) -> list[list[dict]]: return self._upsert_rows

    @property
    def updates(self) -> list[dict]: return self._update_payloads

    @property
    def is_filters(self) -> list[tuple[str, str]]: return self._is_filters

    @property
    def eq_filters(self) -> list[tuple[str, object]]: return self._eq_filters

    def select(self, *_a, **_kw) -> "_MockTable":
        self._recorder.append(("select", self._name))
        return self

    def eq(self, col: str, val: object) -> "_MockTable":
        self._eq_filters.append((col, val))
        return self

    def lte(self, *_a, **_kw) -> "_MockTable": return self
    def gte(self, *_a, **_kw) -> "_MockTable": return self

    def is_(self, col: str, val: str) -> "_MockTable":
        self._is_filters.append((col, val))
        return self

    def order(self, *_a, **_kw) -> "_MockTable": return self
    def limit(self, *_a, **_kw) -> "_MockTable": return self

    def single(self) -> "_MockTable":
        self._single_pending = True
        return self

    def upsert(self, payload, **_kw) -> "_MockTable":
        self._upsert_rows.append(payload)
        return self

    def update(self, payload: dict) -> "_MockTable":
        self._update_payloads.append(payload)
        return self

    def execute(self) -> MagicMock:
        resp = MagicMock()
        if self._single_pending and self._select_rows:
            # supabase-py .single().execute() returns the dict directly
            resp.data = self._select_rows[0]
        else:
            resp.data = list(self._select_rows)
        self._single_pending = False  # reset for next chain
        return resp


class _MockSupabase:
    """Routes table() to per-name _MockTable instances. Tests inspect
    via ``mock_sb.tables['tnved_rates'].upserts`` etc.
    """

    def __init__(self) -> None:
        self.tables: dict[str, _MockTable] = {}
        self.recorder: list[tuple] = []

    def table(self, name: str) -> _MockTable:
        self.recorder.append(("table", name))
        if name not in self.tables:
            self.tables[name] = _MockTable(name, self.recorder)
        return self.tables[name]


@pytest.fixture
def mock_sb() -> _MockSupabase:
    return _MockSupabase()


@pytest.fixture
def alta_client_mock() -> MagicMock:
    client = MagicMock()
    client.get_rates = AsyncMock(return_value=[])
    return client


def _patch_get_supabase(sb: _MockSupabase):
    return patch("services.rate_resolver.get_supabase", return_value=sb)


# ---------------------------------------------------------------------------
# Tier 1 — exact country
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier_1_exact_country_match_returns_rate(mock_sb, alta_client_mock):
    """Cache hit on exact country (C:156) → no Alta call, no fallthrough."""
    mock_sb.tables.setdefault("tnved_rates", _MockTable("tnved_rates", mock_sb.recorder))
    mock_sb.tables["tnved_rates"].set_select([_row(country_or_areal="C:156")])

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert result.outcome == ResolveOutcome.FOUND
    assert result.rate is not None
    assert result.rate.country_or_areal == "C:156"
    assert result.rate.source == "alta-live"
    alta_client_mock.get_rates.assert_not_called()


@pytest.mark.asyncio
async def test_tier_1_uses_country_filter_with_C_prefix(mock_sb, alta_client_mock):
    """Verify the resolver writes 'C:{oksm}' as the lookup key."""
    mock_sb.tables.setdefault("tnved_rates", _MockTable("tnved_rates", mock_sb.recorder))
    mock_sb.tables["tnved_rates"].set_select([_row(country_or_areal="C:643")])

    with _patch_get_supabase(mock_sb):
        await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=643,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    eq_filters = mock_sb.tables["tnved_rates"].eq_filters
    assert ("country_or_areal", "C:643") in eq_filters


# ---------------------------------------------------------------------------
# Tier 2 — areal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier_2_areal_match_when_no_country_row(mock_sb, alta_client_mock):
    """No exact-country row → check country_areals → match A:EAEU."""
    # tnved_rates returns empty for C:643, then a row for A:EAEU, then nothing
    # for base. Same table is hit 3 times so we need a side_effect script.
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    mock_sb.tables["tnved_rates"] = rates_table

    countries_table = _MockTable("country_areals", mock_sb.recorder)
    countries_table.set_select([{"areal_code": "EAEU"}, {"areal_code": "CIS"}])
    mock_sb.tables["country_areals"] = countries_table

    # Drive scripted answers per call to .execute()
    call_seq = iter([
        [],                                  # Tier 1 — C:643 miss
        [{"areal_code": "EAEU"}, {"areal_code": "CIS"}],  # country_areals
        [_row(country_or_areal="A:EAEU")],  # Tier 2 — A:EAEU hit
    ])

    def execute_side_effect():
        try:
            rows = next(call_seq)
        except StopIteration:
            rows = []
        resp = MagicMock()
        resp.data = rows
        return resp

    rates_table.execute = execute_side_effect
    countries_table.execute = execute_side_effect

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=643,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert result.outcome == ResolveOutcome.FOUND
    assert result.rate is not None
    assert result.rate.country_or_areal == "A:EAEU"
    alta_client_mock.get_rates.assert_not_called()


# ---------------------------------------------------------------------------
# Tier 3 — base rate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier_3_base_rate_when_no_country_no_areal(mock_sb, alta_client_mock):
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    countries_table = _MockTable("country_areals", mock_sb.recorder)
    mock_sb.tables["tnved_rates"] = rates_table
    mock_sb.tables["country_areals"] = countries_table

    call_seq = iter([
        [],                                          # Tier 1 — C:643 miss
        [],                                          # country_areals empty
        [_row(country_or_areal="__base__")],         # Tier 3 — base hit
    ])

    def execute_side_effect():
        try:
            rows = next(call_seq)
        except StopIteration:
            rows = []
        resp = MagicMock()
        resp.data = rows
        return resp

    rates_table.execute = execute_side_effect
    countries_table.execute = execute_side_effect

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=643,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert result.outcome == ResolveOutcome.FOUND
    assert result.rate is not None
    # Migration 302: '__base__' replaced NULL — uq_tnved_rates_v2 now actually
    # enforces uniqueness for all-country rates.
    assert result.rate.country_or_areal == "__base__"
    assert ("country_or_areal", "__base__") in rates_table.eq_filters


# ---------------------------------------------------------------------------
# REQ-3 AC#10 — is_unfriendly NOT in lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_unfriendly_not_in_lookup_path(mock_sb, alta_client_mock):
    """Alta encodes elevated tariffs in response automatically — resolver
    must not query countries.is_unfriendly itself.
    """
    mock_sb.tables.setdefault("tnved_rates", _MockTable("tnved_rates", mock_sb.recorder))
    mock_sb.tables["tnved_rates"].set_select([_row()])

    with _patch_get_supabase(mock_sb):
        await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    # countries table was never queried for is_unfriendly
    table_names = [t[1] for t in mock_sb.recorder if t[0] == "table"]
    for name in table_names:
        # only allowed table reads in the happy-path: tnved_rates and last_used_at touch
        assert name in {"tnved_rates"}


# ---------------------------------------------------------------------------
# Lazy-fetch fallback on full miss + bulk upsert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_miss_calls_alta_and_upserts_then_re_lookup(
    mock_sb, alta_client_mock,
):
    """All 3 tiers dry → Alta call → upsert all returned rates → re-lookup."""
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    countries_table = _MockTable("country_areals", mock_sb.recorder)
    mock_sb.tables["tnved_rates"] = rates_table
    mock_sb.tables["country_areals"] = countries_table

    # Note: upsert.execute() and the last_used_at update.execute() each
    # consume an iterator slot, so we budget extra []s for don't-care calls.
    call_seq = iter([
        [],                                  # Tier 1 miss
        [],                                  # country_areals empty
        [],                                  # Tier 3 miss
        [],                                  # upsert.execute() — don't care
        [_row(country_or_areal="C:156")],   # Re-lookup Tier 1 — hit
        [],                                  # last_used_at update — don't care
    ])

    def execute_side_effect():
        try:
            rows = next(call_seq)
        except StopIteration:
            rows = []
        resp = MagicMock()
        resp.data = rows
        return resp

    rates_table.execute = execute_side_effect
    countries_table.execute = execute_side_effect

    fetched = [
        _make_rate(payment_type="IMP", country_or_areal="C:156"),
        _make_rate(payment_type="NDS", country_or_areal=None),
        _make_rate(payment_type="AKC", country_or_areal=None, value_1_number=0),
    ]
    alta_client_mock.get_rates.return_value = fetched

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert result.outcome == ResolveOutcome.FOUND
    assert result.rate is not None
    assert result.rate.country_or_areal == "C:156"
    alta_client_mock.get_rates.assert_called_once()
    # Bulk upsert with all 3 returned rates in one shot (REQ-3 AC#4)
    assert len(rates_table.upserts) == 1
    assert len(rates_table.upserts[0]) == 3


@pytest.mark.asyncio
async def test_resolve_rate_alta_empty_response_returns_not_found(mock_sb, alta_client_mock):
    """REVIEW M4: Alta call SUCCEEDED with empty list → outcome=NOT_FOUND
    (the rate genuinely doesn't exist for this code+country). Distinct from
    ALTA_ERROR — retrying won't help; the user must enter the rate manually.
    """
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    countries_table = _MockTable("country_areals", mock_sb.recorder)
    mock_sb.tables["tnved_rates"] = rates_table
    mock_sb.tables["country_areals"] = countries_table

    rates_table.execute = lambda: MagicMock(data=[])
    countries_table.execute = lambda: MagicMock(data=[])
    alta_client_mock.get_rates.return_value = []

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert result.outcome == ResolveOutcome.NOT_FOUND
    assert result.rate is None
    # No upsert when nothing came back
    assert rates_table.upserts == []


# ---------------------------------------------------------------------------
# REQ-3 AC#6 — Alta failure returns ALTA_ERROR (retry-worthy), never raises.
# REVIEW M4: distinct from NOT_FOUND (terminal — rate doesn't exist).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_rate_alta_api_error_returns_alta_error(mock_sb, alta_client_mock, caplog):
    """REVIEW M4: AltaApiError → outcome=ALTA_ERROR (Alta is genuinely
    down). Caller (handler) should respond 503 — retrying may succeed.
    """
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    countries_table = _MockTable("country_areals", mock_sb.recorder)
    mock_sb.tables["tnved_rates"] = rates_table
    mock_sb.tables["country_areals"] = countries_table
    rates_table.execute = lambda: MagicMock(data=[])
    countries_table.execute = lambda: MagicMock(data=[])

    alta_client_mock.get_rates.side_effect = AltaApiError(140, "insufficient funds")

    with _patch_get_supabase(mock_sb), caplog.at_level("ERROR"):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert result.outcome == ResolveOutcome.ALTA_ERROR
    assert result.rate is None
    assert any("Alta error 140" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_resolve_rate_network_error_returns_alta_error(mock_sb, alta_client_mock):
    """REVIEW M4: network failure → outcome=ALTA_ERROR (transient infra
    issue). Distinct from NOT_FOUND — retry path is appropriate.
    """
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    countries_table = _MockTable("country_areals", mock_sb.recorder)
    mock_sb.tables["tnved_rates"] = rates_table
    mock_sb.tables["country_areals"] = countries_table
    rates_table.execute = lambda: MagicMock(data=[])
    countries_table.execute = lambda: MagicMock(data=[])

    alta_client_mock.get_rates.side_effect = ConnectionError("network down")

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert result.outcome == ResolveOutcome.ALTA_ERROR
    assert result.rate is None


# ---------------------------------------------------------------------------
# REQ-3 AC#7 — last_used_at update on success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_used_at_updated_on_cache_hit(mock_sb, alta_client_mock):
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    rates_table.set_select([_row(id="rate-uuid-42")])
    mock_sb.tables["tnved_rates"] = rates_table

    with _patch_get_supabase(mock_sb):
        await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert len(rates_table.updates) == 1
    assert "last_used_at" in rates_table.updates[0]
    # eq("id", "rate-uuid-42") was issued for the update path
    assert ("id", "rate-uuid-42") in rates_table.eq_filters


@pytest.mark.asyncio
async def test_last_used_at_failure_does_not_break_resolve(mock_sb, alta_client_mock, caplog):
    """A failing UPDATE should be logged but not propagate — the cron
    will eventually re-touch the row.
    """
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    rates_table.set_select([_row()])
    mock_sb.tables["tnved_rates"] = rates_table

    original_update = rates_table.update

    def boom(payload):  # noqa: ARG001
        # Mimic a failure during the chained call
        raise RuntimeError("update failed")

    rates_table.update = boom  # type: ignore[method-assign]

    with _patch_get_supabase(mock_sb), caplog.at_level("WARNING"):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    rates_table.update = original_update  # restore
    assert result.outcome == ResolveOutcome.FOUND
    assert result.rate is not None
    assert any("failed to update last_used_at" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# REQ-3 AC#5 — race-safe upsert via UNIQUE constraint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_upsert_targets_unique_constraint_columns(mock_sb, alta_client_mock):
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    countries_table = _MockTable("country_areals", mock_sb.recorder)
    mock_sb.tables["tnved_rates"] = rates_table
    mock_sb.tables["country_areals"] = countries_table

    call_seq = iter([
        [], [], [],                          # all 3 tiers miss
        [],                                  # upsert.execute() — don't care
        [_row()],                            # re-lookup Tier 1 hit
        [],                                  # last_used_at update — don't care
    ])

    def execute_side_effect():
        try:
            rows = next(call_seq)
        except StopIteration:
            rows = []
        return MagicMock(data=rows)

    rates_table.execute = execute_side_effect
    countries_table.execute = execute_side_effect

    alta_client_mock.get_rates.return_value = [_make_rate()]

    captured_kwargs = {}
    original_upsert = rates_table.upsert

    def capturing_upsert(payload, **kw):
        captured_kwargs.update(kw)
        return original_upsert(payload, **kw)

    rates_table.upsert = capturing_upsert  # type: ignore[method-assign]

    with _patch_get_supabase(mock_sb):
        await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    # Migration 301 added category_code to the unique key so льготные
    # variants (NDS 10% медтехника) coexist with the стандартная rate.
    assert captured_kwargs.get("on_conflict") == (
        "tnved_code,payment_type,country_or_areal,valid_from,"
        "certificate_required,sp_certificate_required,"
        "category_code"
    )


# ---------------------------------------------------------------------------
# TTL — stale cache → refetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_cache_filter_applied(mock_sb, alta_client_mock):
    """Verify the cutoff timestamp passed to .gte() is now - CACHE_TTL.
    We can't easily intercept .gte() args because our mock collapses
    them. Instead assert that CACHE_TTL is 30 days as the design specifies.
    """
    assert CACHE_TTL == timedelta(days=30)

    # And verify that the filter chain includes a .gte() call (the resolver
    # would degrade to "no TTL" if we forgot to call it).
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    rates_table.set_select([_row()])
    mock_sb.tables["tnved_rates"] = rates_table

    gte_calls = []
    original_gte = rates_table.gte

    def capturing_gte(*a, **kw):
        gte_calls.append((a, kw))
        return original_gte(*a, **kw)

    rates_table.gte = capturing_gte  # type: ignore[method-assign]

    with _patch_get_supabase(mock_sb):
        await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    assert any("source_fetched_at" in str(call) for call in gte_calls), (
        "resolver must apply source_fetched_at >= cutoff filter"
    )


# ---------------------------------------------------------------------------
# REQ-3 AC#8 — snapshot lookup for frozen quotes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_lookup_hits_for_approved_quote(mock_sb, alta_client_mock):
    """Quote in APPROVED status + snapshot has matching payment_type →
    return snapshotted rate, NEVER touch live cache or Alta.
    """
    quote_items_table = _MockTable("quote_items", mock_sb.recorder)
    quote_items_table.set_select([{
        "quote_id": "quote-uuid-1",
        "quotes": {"workflow_status": "approved"},
    }])
    mock_sb.tables["quote_items"] = quote_items_table

    versions_table = _MockTable("quote_versions", mock_sb.recorder)
    versions_table.set_select([{
        "input_variables": {
            "customs_rates": {
                "item-uuid-7": {
                    "fetched_at": "2026-04-15T10:00:00+00:00",
                    "source_at_freeze": "alta-live",
                    "rates": [{
                        "payment_type": "IMP",
                        "value_1_number": 12.5,
                        "value_1_unit": "percent",
                        "value_1_currency": None,
                        "raw_value_string": "12.5%",
                        "valid_from": "2026-04-15",
                        "source": "alta-live",
                    }],
                },
            },
        },
    }])
    mock_sb.tables["quote_versions"] = versions_table

    # Live lookup tables — must NOT be touched
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    mock_sb.tables["tnved_rates"] = rates_table

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
            quote_item_id="item-uuid-7",
        )

    assert result.outcome == ResolveOutcome.FOUND
    assert result.rate is not None
    assert result.rate.snapshot is True
    assert result.rate.value_1_number == 12.5
    assert result.rate.source == "alta-live"
    alta_client_mock.get_rates.assert_not_called()
    # tnved_rates was never queried
    table_names = [t[1] for t in mock_sb.recorder if t[0] == "table"]
    assert "tnved_rates" not in table_names


@pytest.mark.asyncio
async def test_snapshot_skipped_for_unfrozen_quote_falls_through_to_live(
    mock_sb, alta_client_mock,
):
    """Quote not in frozen status → snapshot branch returns None → live cache used."""
    quote_items_table = _MockTable("quote_items", mock_sb.recorder)
    quote_items_table.set_select([{
        "quote_id": "quote-uuid-1",
        "quotes": {"workflow_status": "draft"},  # NOT in FROZEN_STATUSES
    }])
    mock_sb.tables["quote_items"] = quote_items_table

    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    rates_table.set_select([_row(value_1_number=99.0)])
    mock_sb.tables["tnved_rates"] = rates_table

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
            quote_item_id="item-uuid-7",
        )

    # Got the live row, not the snapshot
    assert result.outcome == ResolveOutcome.FOUND
    assert result.rate is not None
    assert result.rate.value_1_number == 99.0
    assert result.rate.snapshot is False


@pytest.mark.asyncio
async def test_snapshot_skipped_when_payment_type_not_in_snapshot(
    mock_sb, alta_client_mock,
):
    """Snapshot exists, quote frozen, but no rate of requested payment_type
    in the snapshot → fall through to live cache.
    """
    quote_items_table = _MockTable("quote_items", mock_sb.recorder)
    quote_items_table.set_select([{
        "quote_id": "quote-uuid-1",
        "quotes": {"workflow_status": "deal"},  # frozen
    }])
    mock_sb.tables["quote_items"] = quote_items_table

    versions_table = _MockTable("quote_versions", mock_sb.recorder)
    versions_table.set_select([{
        "input_variables": {
            "customs_rates": {
                "item-uuid-7": {
                    "fetched_at": "2026-04-15T10:00:00+00:00",
                    "source_at_freeze": "alta-live",
                    "rates": [
                        {"payment_type": "IMP", "value_1_number": 10},
                    ],
                },
            },
        },
    }])
    mock_sb.tables["quote_versions"] = versions_table

    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    rates_table.set_select([_row(payment_type="NDS", value_1_number=20.0)])
    mock_sb.tables["tnved_rates"] = rates_table

    with _patch_get_supabase(mock_sb):
        result = await resolve_rate(
            tnved_code="8409910008",
            payment_type="NDS",  # NOT in snapshot above (only IMP is)
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
            quote_item_id="item-uuid-7",
        )

    assert result.outcome == ResolveOutcome.FOUND
    assert result.rate is not None
    assert result.rate.snapshot is False
    assert result.rate.value_1_number == 20.0


@pytest.mark.asyncio
async def test_no_quote_item_id_means_no_snapshot_lookup(mock_sb, alta_client_mock):
    """Resolver called without quote_item_id → quote_items table never queried."""
    rates_table = _MockTable("tnved_rates", mock_sb.recorder)
    rates_table.set_select([_row()])
    mock_sb.tables["tnved_rates"] = rates_table

    with _patch_get_supabase(mock_sb):
        await resolve_rate(
            tnved_code="8409910008",
            payment_type="IMP",
            country_oksm=156,
            target_date=date(2026, 5, 1),
            alta_client=alta_client_mock,
        )

    table_names = [t[1] for t in mock_sb.recorder if t[0] == "table"]
    assert "quote_items" not in table_names
    assert "quote_versions" not in table_names


# ---------------------------------------------------------------------------
# Sanity — frozen-statuses set covers every workflow boundary
# ---------------------------------------------------------------------------


def test_frozen_statuses_covers_workflow_boundary():
    """REQ-8: all post-APPROVED workflow statuses must trigger snapshot
    lookup. Sanity check the set we maintain locally to avoid a
    workflow_service circular import.

    Values match the lowercase WorkflowStatus enum values stored on
    kvota.quotes.workflow_status (see services/workflow_service.py).
    Drift detector in test_workflow_status_drift.py catches enum
    renames at unit-test time.
    """
    expected = {
        "approved",
        "sent_to_client",
        "client_negotiation",
        "pending_spec_control",
        "pending_signature",
        "deal",
        "rejected",
        "cancelled",
    }
    assert FROZEN_STATUSES == expected


def test_resolved_rate_passthrough_properties():
    """ResolvedRate.value_1_number etc must delegate to .rate transparently.
    The adapter in calculation_helpers reads these without `.rate.` indirection.
    """
    rate = _make_rate(value_1_number=15.0, value_1_unit="percent")
    rr = ResolvedRate(
        id="x",
        rate=rate,
        source="alta-live",
        source_fetched_at=datetime.now(timezone.utc),
        last_used_at=datetime.now(timezone.utc),
    )
    assert rr.value_1_number == 15.0
    assert rr.value_1_unit == "percent"
    assert rr.tnved_code == rate.tnved_code
    assert rr.payment_type == rate.payment_type


# ---------------------------------------------------------------------------
# REVIEW M4 — ResolveResult invariants
# ---------------------------------------------------------------------------


def test_resolve_result_found_requires_rate():
    """FOUND must carry a non-None ResolvedRate — guarded by __post_init__."""
    rate = ResolvedRate(
        id="r-1",
        rate=_make_rate(),
        source="alta-live",
        source_fetched_at=datetime.now(timezone.utc),
        last_used_at=datetime.now(timezone.utc),
    )
    rr = ResolveResult(ResolveOutcome.FOUND, rate)
    assert rr.outcome == ResolveOutcome.FOUND
    assert rr.rate is rate


def test_resolve_result_found_with_none_rate_raises():
    """ResolveResult(FOUND, None) is meaningless — must reject."""
    with pytest.raises(ValueError):
        ResolveResult(ResolveOutcome.FOUND, None)


def test_resolve_result_not_found_requires_no_rate():
    """NOT_FOUND must carry rate=None — invariant."""
    rr = ResolveResult(ResolveOutcome.NOT_FOUND, None)
    assert rr.outcome == ResolveOutcome.NOT_FOUND
    assert rr.rate is None


def test_resolve_result_alta_error_requires_no_rate():
    """ALTA_ERROR must carry rate=None — invariant."""
    rr = ResolveResult(ResolveOutcome.ALTA_ERROR, None)
    assert rr.outcome == ResolveOutcome.ALTA_ERROR
    assert rr.rate is None


def test_resolve_result_not_found_with_rate_raises():
    """ResolveResult(NOT_FOUND, <rate>) is contradictory — must reject."""
    rate = ResolvedRate(
        id="r-1",
        rate=_make_rate(),
        source="alta-live",
        source_fetched_at=datetime.now(timezone.utc),
        last_used_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValueError):
        ResolveResult(ResolveOutcome.NOT_FOUND, rate)
