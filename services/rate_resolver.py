"""Customs rate resolver — three-tier priority lookup with Alta lazy-fetch.

Public API: ``resolve_rate(...)`` returns a ``ResolveResult`` carrying both
an outcome discriminator (FOUND / NOT_FOUND / ALTA_ERROR) and an optional
``ResolvedRate``. Callers MUST inspect ``.outcome`` to distinguish
"Alta is genuinely down" (retry-worthy → 503) from "rate doesn't exist
for this code+country" (terminal → 404 RATE_NOT_FOUND).

Priority (REQ-3 AC#1):
    1. Exact country  — kvota.tnved_rates.country_or_areal = 'C:{oksm}'
    2. Areal          — for each areal in country_areals: 'A:{areal_code}'
    3. Base           — country_or_areal IS NULL

TTL: 30 days. A cache row older than that is treated as absent and triggers
a lazy-fetch through ``services.alta_client.AltaClient.get_rates(...)``.

Snapshot lookup (REQ-3 AC#8 with Q7 simplification): when ``quote_item_id``
is provided AND the parent quote is past the freeze boundary (status APPROVED
or beyond), the resolver reads from
``kvota.quote_versions.input_variables.customs_rates[<item_id>]`` instead of
the live cache. This guarantees PDFs sent months ago re-render with the
same numbers.

Concurrency: race-safe upsert via the UNIQUE constraint
``uq_tnved_rates`` on (tnved_code, payment_type, country_or_areal,
valid_from, certificate_required, sp_certificate_required) — see
migration 298.

Side effects: each successful resolve fires ``UPDATE tnved_rates SET
last_used_at = now() WHERE id = $1`` (Q3 decision). Used by the weekly
cron to revalidate the top-1000 most-used pairs.

`is_unfriendly` flag is NOT consulted (REQ-3 AC#10) — Alta encodes
elevated tariffs in the response itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from services.alta_client import AltaApiError, Rate
from services.database import get_supabase

if TYPE_CHECKING:
    from services.alta_client import AltaClient

logger = logging.getLogger(__name__)

# Cache freshness window. Older entries are treated as cache misses.
CACHE_TTL = timedelta(days=30)

# Rolling counter for last_used_at update failures. Crossing thresholds
# escalates the log level so a flaky / RLS-broken UPDATE shows up in
# alerts instead of silently degrading the cron's top-1000 ranking.
_touch_failure_count: int = 0
_TOUCH_FAILURE_THRESHOLDS = (10, 100, 1000)

# Workflow statuses where the customs snapshot must be honored over a
# live resolve. Mirrors services/workflow_service.WorkflowStatus values
# from the freeze boundary (REQ-8). Kept here as plain strings to avoid
# a circular import with workflow_service.
# Drift detector lives in tests/services/test_workflow_status_drift.py —
# update it (and this set) if WorkflowStatus enum values are renamed.
FROZEN_STATUSES = frozenset({
    "approved",
    "sent_to_client",
    "client_negotiation",
    "pending_spec_control",
    "pending_signature",
    "deal",
    "rejected",
    "cancelled",
})


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedRate:
    """A rate with DB-side metadata attached.

    Composes ``services.alta_client.Rate`` (the pure XML-derived shape)
    with the columns ``kvota.tnved_rates`` adds at storage time:
    ``id``, ``source``, ``source_fetched_at``, ``last_used_at``.

    The ``source`` field is the discriminator the calc-engine adapter
    (``services.calculation_helpers.build_calculation_inputs``) uses to
    decide between the legacy combined-rate formula and the new
    ``services.customs_calc.calculate_duty()`` path (Q1 decision).

    Invariant (enforced in __post_init__):
        snapshot=True  ⇔ id is None
        snapshot=False ⇔ id is a non-None DB uuid.

    Snapshot rates live in JSONB (``quote_versions.input_variables``),
    have no DB row, and carry id=None to make accidental UPDATEs against
    a synthesized pseudo-id impossible.
    """
    id: str | None                         # uuid as string for live rows; None for snapshot
    rate: Rate                             # immutable XML-derived shape
    source: str                            # 'alta-live' | 'alta-revalidate' | 'manual'
    source_fetched_at: datetime
    last_used_at: datetime
    snapshot: bool = False                 # True = read from quote_versions, not live cache

    def __post_init__(self) -> None:
        if self.snapshot and self.id is not None:
            raise ValueError(
                "snapshot ResolvedRate must have id=None "
                f"(got id={self.id!r})"
            )
        if not self.snapshot and self.id is None:
            raise ValueError(
                "non-snapshot ResolvedRate must have a non-None DB id"
            )

    # DEPRECATED — use `.rate.<field>` directly; will remove in Phase 2.
    # Pass-through accessors so adapter code can write `r.value_1_number`
    # without `.rate.` indirection. Risk of silent None on a missed
    # forwarding mapping, so prefer reading `.rate.<field>` in new code.
    @property
    def tnved_code(self) -> str: return self.rate.tnved_code
    @property
    def payment_type(self) -> str: return self.rate.payment_type
    @property
    def country_or_areal(self) -> str | None: return self.rate.country_or_areal
    @property
    def valid_from(self) -> date: return self.rate.valid_from
    @property
    def value_1_number(self) -> float | None: return self.rate.value_1_number
    @property
    def value_1_unit(self) -> str | None: return self.rate.value_1_unit
    @property
    def value_1_currency(self) -> str | None: return self.rate.value_1_currency
    @property
    def value_2_number(self) -> float | None: return self.rate.value_2_number
    @property
    def value_2_unit(self) -> str | None: return self.rate.value_2_unit
    @property
    def value_2_currency(self) -> str | None: return self.rate.value_2_currency
    @property
    def sign_1(self) -> str | None: return self.rate.sign_1
    @property
    def raw_value_string(self) -> str | None: return self.rate.raw_value_string


class ResolveOutcome(Enum):
    """Why ``resolve_rate`` returned what it did. Use this to distinguish
    "Alta is down" (retry-worthy) from "rate genuinely doesn't exist"
    (terminal — the user must enter the rate manually).

    Review fix M4 (PR #83): both states used to collapse into ``None``,
    so the API handler's 503 ALTA_UNAVAILABLE response would tell users
    to retry forever for codes that simply have no Alta data.
    """
    FOUND = "found"           # rate is the matched ResolvedRate (DB cache or snapshot or Alta-fetched)
    NOT_FOUND = "not_found"   # cache empty AND Alta call SUCCEEDED with empty list
    ALTA_ERROR = "alta_error" # AltaApiError | network failure | parse failure (cache also missed)


@dataclass(frozen=True)
class ResolveResult:
    """Discriminated result for ``resolve_rate``.

    Pattern-match by reading ``.outcome`` (a ``ResolveOutcome``); the
    ``.rate`` is only populated when ``outcome == FOUND``. Using a
    typed dataclass instead of a 2-tuple keeps callsites self-documenting
    and reserves room for future fields (e.g. cache-age signal).
    """
    outcome: ResolveOutcome
    rate: ResolvedRate | None

    def __post_init__(self) -> None:
        if self.outcome == ResolveOutcome.FOUND and self.rate is None:
            raise ValueError("ResolveResult(FOUND, None) is invalid — must carry a rate")
        if self.outcome != ResolveOutcome.FOUND and self.rate is not None:
            raise ValueError(
                f"ResolveResult({self.outcome.name}, ...) must carry rate=None"
            )


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


async def resolve_rate(
    tnved_code: str,
    payment_type: str,
    country_oksm: int,
    target_date: date,
    has_certificate: bool = False,
    has_sp_certificate: bool = False,
    *,
    alta_client: AltaClient,
    quote_item_id: str | None = None,
) -> ResolveResult:
    """Resolve a single customs rate.

    Returns a ``ResolveResult`` with one of three outcomes:

    * ``FOUND``      — the highest-priority cache or freshly-fetched rate
                       matched. ``result.rate`` is a ``ResolvedRate``.
    * ``NOT_FOUND``  — Alta call succeeded but returned no rates for this
                       (tnved_code, country) pair. The user must enter the
                       rate manually. Retrying won't help.
    * ``ALTA_ERROR`` — AltaApiError / network failure / parse failure AND
                       no cache row was usable. Retrying may succeed.

    Review fix M4 (PR #83): previously returned ``None`` for both
    NOT_FOUND and ALTA_ERROR, which the API handler couldn't distinguish.

    Args:
        tnved_code: 10-digit ТН ВЭД code.
        payment_type: 'IMP' | 'NDS' | 'AKC' | ... (kvota.payment_types.code)
        country_oksm: ОКСМ digital code for country of origin.
        target_date: Date for which the rate must be valid.
        has_certificate: Origin certificate flag (affects matching).
        has_sp_certificate: SP certificate flag.
        alta_client: Injected (Q6 — testable via app.dependency_overrides).
        quote_item_id: Optional. Triggers snapshot lookup for frozen quotes.
    """
    sb = get_supabase()

    # 1. Snapshot branch — frozen quote reads from quote_versions
    if quote_item_id is not None:
        snapshot_rate = _lookup_snapshot(sb, quote_item_id, payment_type)
        if snapshot_rate is not None:
            return ResolveResult(ResolveOutcome.FOUND, snapshot_rate)

    # 2. Live cache lookup, three tiers
    rate = _lookup_db(
        sb,
        tnved_code=tnved_code,
        payment_type=payment_type,
        country_oksm=country_oksm,
        target_date=target_date,
        has_certificate=has_certificate,
        has_sp_certificate=has_sp_certificate,
    )
    if rate is not None:
        _touch_last_used_at(sb, rate.id)
        return ResolveResult(ResolveOutcome.FOUND, rate)

    # 3. Lazy-fetch from Alta on full miss
    try:
        fetched = await alta_client.get_rates(
            tncode=tnved_code,
            country=country_oksm,
            date_=target_date,
            certificate=has_certificate,
            sp_certificate=has_sp_certificate,
        )
    except AltaApiError as e:
        logger.error(
            "rate_resolver: Alta error %s for tnved_code=%s country=%s — returning ALTA_ERROR",
            e.code, tnved_code, country_oksm,
        )
        return ResolveResult(ResolveOutcome.ALTA_ERROR, None)
    except Exception as e:  # network errors, parse failures
        logger.error(
            "rate_resolver: Alta call failed for tnved_code=%s country=%s: %s",
            tnved_code, country_oksm, e,
        )
        return ResolveResult(ResolveOutcome.ALTA_ERROR, None)

    if not fetched:
        # Alta call SUCCEEDED but returned no rates for this code+country.
        # Distinct from ALTA_ERROR — retrying won't help; user must enter manually.
        return ResolveResult(ResolveOutcome.NOT_FOUND, None)

    # 4. Bulk upsert all returned rates (REQ-3 AC#4 — comprehensive response)
    _bulk_upsert(sb, fetched, source="alta-live")

    # 5. Re-run lookup — now the cache has the row
    rate = _lookup_db(
        sb,
        tnved_code=tnved_code,
        payment_type=payment_type,
        country_oksm=country_oksm,
        target_date=target_date,
        has_certificate=has_certificate,
        has_sp_certificate=has_sp_certificate,
    )
    if rate is not None:
        _touch_last_used_at(sb, rate.id)
        return ResolveResult(ResolveOutcome.FOUND, rate)

    # Defensive: Alta returned rates but the re-lookup missed (e.g. the
    # returned rates didn't include the requested payment_type, or
    # certificate flags didn't match). Treat as NOT_FOUND — Alta did
    # respond, just without the specific slot we asked for.
    return ResolveResult(ResolveOutcome.NOT_FOUND, None)


async def resolve_all_payment_types(
    tnved_code: str,
    country_oksm: int,
    target_date: date,
    payment_types: tuple[str, ...] | list[str],
    has_certificate: bool = False,
    has_sp_certificate: bool = False,
    *,
    alta_client: AltaClient,
) -> tuple[dict[str, list[ResolvedRate]], dict[str, ResolveOutcome]]:
    """Resolve variants for many payment_types using ONE Alta call.

    Phase 1 packet-efficiency optimisation. ``resolve_rate_variants`` makes
    one Alta call per payment_type — but Alta Такса returns ALL payment
    types in a single response, so 7 separate calls waste 6 packets per
    autofill click.

    Strategy:
      1. Try cache-only first for every payment_type. If all hit, return.
      2. Otherwise fire ONE Alta call. The response covers all payment
         types — bulk-upsert the lot, then re-query the cache per type.

    Returns:
      ``(by_payment_type, outcomes)``
        - ``by_payment_type[pt]`` — list of ResolvedRate variants (empty if
          NOT_FOUND or ALTA_ERROR for that pt).
        - ``outcomes[pt]`` — FOUND | NOT_FOUND | ALTA_ERROR.
    """
    sb = get_supabase()

    # Step 1 — cache-only sweep
    by_pt: dict[str, list[ResolvedRate]] = {}
    outcomes: dict[str, ResolveOutcome] = {}
    cache_misses: list[str] = []
    for pt in payment_types:
        variants = _lookup_all_variants(
            sb,
            tnved_code=tnved_code,
            payment_type=pt,
            country_oksm=country_oksm,
            target_date=target_date,
            has_certificate=has_certificate,
            has_sp_certificate=has_sp_certificate,
        )
        if variants:
            by_pt[pt] = variants
            outcomes[pt] = ResolveOutcome.FOUND
            for v in variants:
                if v.id is not None:
                    _touch_last_used_at(sb, v.id)
        else:
            cache_misses.append(pt)

    if not cache_misses:
        return by_pt, outcomes

    # Step 2 — single Alta call covers all missing payment types
    try:
        fetched = await alta_client.get_rates(
            tncode=tnved_code,
            country=country_oksm,
            date_=target_date,
            certificate=has_certificate,
            sp_certificate=has_sp_certificate,
        )
    except AltaApiError as e:
        logger.error(
            "rate_resolver.resolve_all: Alta error %s for tnved_code=%s "
            "country=%s — marking %s as ALTA_ERROR",
            e.code, tnved_code, country_oksm, ",".join(cache_misses),
        )
        for pt in cache_misses:
            by_pt.setdefault(pt, [])
            outcomes[pt] = ResolveOutcome.ALTA_ERROR
        return by_pt, outcomes
    except Exception as e:
        logger.error(
            "rate_resolver.resolve_all: Alta call failed for tnved_code=%s "
            "country=%s: %s",
            tnved_code, country_oksm, e,
        )
        for pt in cache_misses:
            by_pt.setdefault(pt, [])
            outcomes[pt] = ResolveOutcome.ALTA_ERROR
        return by_pt, outcomes

    if fetched:
        _bulk_upsert(sb, fetched, source="alta-live")

    # Step 3 — re-query cache for each missing payment_type
    for pt in cache_misses:
        variants = _lookup_all_variants(
            sb,
            tnved_code=tnved_code,
            payment_type=pt,
            country_oksm=country_oksm,
            target_date=target_date,
            has_certificate=has_certificate,
            has_sp_certificate=has_sp_certificate,
        )
        by_pt[pt] = variants
        if variants:
            outcomes[pt] = ResolveOutcome.FOUND
            for v in variants:
                if v.id is not None:
                    _touch_last_used_at(sb, v.id)
        else:
            # Alta call succeeded but no rates of this payment_type came
            # back — terminal NOT_FOUND, not retry-worthy.
            outcomes[pt] = ResolveOutcome.NOT_FOUND

    return by_pt, outcomes


async def resolve_rate_variants(
    tnved_code: str,
    payment_type: str,
    country_oksm: int,
    target_date: date,
    has_certificate: bool = False,
    has_sp_certificate: bool = False,
    *,
    alta_client: AltaClient,
    quote_item_id: str | None = None,
) -> tuple[ResolveOutcome, list[ResolvedRate]]:
    """Resolve ALL variants of a rate (migration 301 multi-variant flow).

    Where ``resolve_rate`` returns one default-winning variant for the
    calc engine, this function returns every льготная + стандартная row
    so the UI can render a selector. The customs-specialist picks the
    one applicable to the actual product (medical / "прочее" / etc.).

    Returns ``(outcome, rates)`` where ``rates`` is empty unless
    ``outcome == FOUND``. Variants are ordered with ``is_default=true``
    first (the safe pre-selected option), then by valid_from desc.

    Lazy-fetch behavior matches ``resolve_rate``: cache miss triggers an
    Alta call, which populates the cache before re-querying.

    Snapshot branch (``quote_item_id`` provided + quote frozen): returns
    the single saved variant wrapped in a list so the UI surface stays
    uniform. Frozen quotes only carry one chosen rate per payment_type.
    """
    sb = get_supabase()

    if quote_item_id is not None:
        snapshot_rate = _lookup_snapshot(sb, quote_item_id, payment_type)
        if snapshot_rate is not None:
            return ResolveOutcome.FOUND, [snapshot_rate]

    variants = _lookup_all_variants(
        sb,
        tnved_code=tnved_code,
        payment_type=payment_type,
        country_oksm=country_oksm,
        target_date=target_date,
        has_certificate=has_certificate,
        has_sp_certificate=has_sp_certificate,
    )
    if variants:
        for v in variants:
            if v.id is not None:
                _touch_last_used_at(sb, v.id)
        return ResolveOutcome.FOUND, variants

    # Lazy-fetch from Alta on full miss
    try:
        fetched = await alta_client.get_rates(
            tncode=tnved_code,
            country=country_oksm,
            date_=target_date,
            certificate=has_certificate,
            sp_certificate=has_sp_certificate,
        )
    except AltaApiError as e:
        logger.error(
            "rate_resolver: Alta error %s for tnved_code=%s country=%s — "
            "returning ALTA_ERROR (variants flow)",
            e.code, tnved_code, country_oksm,
        )
        return ResolveOutcome.ALTA_ERROR, []
    except Exception as e:
        logger.error(
            "rate_resolver: Alta call failed for tnved_code=%s country=%s "
            "(variants flow): %s",
            tnved_code, country_oksm, e,
        )
        return ResolveOutcome.ALTA_ERROR, []

    if not fetched:
        return ResolveOutcome.NOT_FOUND, []

    _bulk_upsert(sb, fetched, source="alta-live")

    variants = _lookup_all_variants(
        sb,
        tnved_code=tnved_code,
        payment_type=payment_type,
        country_oksm=country_oksm,
        target_date=target_date,
        has_certificate=has_certificate,
        has_sp_certificate=has_sp_certificate,
    )
    if variants:
        for v in variants:
            if v.id is not None:
                _touch_last_used_at(sb, v.id)
        return ResolveOutcome.FOUND, variants

    # Alta returned rates but none matched the requested payment_type/certs.
    return ResolveOutcome.NOT_FOUND, []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _lookup_snapshot(
    sb: Any,
    quote_item_id: str,
    payment_type: str,
) -> ResolvedRate | None:
    """Read a snapshotted rate from quote_versions.input_variables.

    Returns None if the parent quote is not in a frozen state OR the
    snapshot doesn't carry rates for this item OR no rate of the
    requested payment_type is in the snapshot.
    """
    # Look up quote_id + workflow_status from the quote_item.
    # Column name is `workflow_status` on kvota.quotes — `status` does not
    # exist; the join key in the resulting dict mirrors the column name.
    item_resp = (
        sb.table("quote_items")
          .select("quote_id, quotes(workflow_status)")
          .eq("id", quote_item_id)
          .single()
          .execute()
    )
    item_row = getattr(item_resp, "data", None)
    if not item_row:
        return None

    quote = item_row.get("quotes") or {}
    quote_status = quote.get("workflow_status")
    if quote_status not in FROZEN_STATUSES:
        return None

    quote_id = item_row.get("quote_id")
    if not quote_id:
        return None

    # Latest version of this quote
    versions_resp = (
        sb.table("quote_versions")
          .select("input_variables")
          .eq("quote_id", quote_id)
          .order("version", desc=True)
          .limit(1)
          .execute()
    )
    versions = getattr(versions_resp, "data", []) or []
    if not versions:
        return None

    iv = versions[0].get("input_variables") or {}
    customs_rates = (iv.get("customs_rates") or {}).get(str(quote_item_id))
    if not customs_rates:
        return None

    rates_list = customs_rates.get("rates") or []
    matching = next(
        (r for r in rates_list if r.get("payment_type") == payment_type),
        None,
    )
    if matching is None:
        return None

    fetched_at = _parse_iso_timestamp(customs_rates.get("fetched_at"))
    return _build_resolved_from_snapshot(matching, fetched_at)


def _lookup_db(
    sb: Any,
    *,
    tnved_code: str,
    payment_type: str,
    country_oksm: int,
    target_date: date,
    has_certificate: bool,
    has_sp_certificate: bool,
) -> ResolvedRate | None:
    """Three-tier cache lookup. Returns the first matching ResolvedRate
    or None if all tiers dry / stale.

    A row is considered fresh if ``source_fetched_at >= now() - 30d``.
    Stale rows are treated as cache misses (REQ-3 AC#2).
    """
    cutoff = (datetime.now(timezone.utc) - CACHE_TTL).isoformat()

    def _fetch_for_key(country_or_areal: str | None) -> ResolvedRate | None:
        q = (
            sb.table("tnved_rates")
              .select("*")
              .eq("tnved_code", tnved_code)
              .eq("payment_type", payment_type)
              .eq("certificate_required", has_certificate)
              .eq("sp_certificate_required", has_sp_certificate)
              .lte("valid_from", target_date.isoformat())
              .gte("source_fetched_at", cutoff)
        )
        # Migration 302: NULL replaced by '__base__' sentinel so uq_tnved_rates_v2
        # actually enforces uniqueness for all-country rates.
        q = q.eq("country_or_areal", country_or_areal or "__base__")
        # Default variant wins ties (migration 301): a льготная row with
        # is_default=false (e.g., NDS 0% медизделия) must NOT override the
        # стандартная rate (NDS 22% Прочие, is_default=true) — that was the
        # whole reason production showed "НДС 0%" for shaybas.
        q = (q.order("is_default", desc=True)
              .order("valid_from", desc=True)
              .limit(1))
        resp = q.execute()
        rows = getattr(resp, "data", []) or []
        if not rows:
            return None
        row = rows[0]
        valid_to_text = row.get("valid_to")
        if valid_to_text:
            valid_to = date.fromisoformat(valid_to_text)
            if valid_to <= target_date:
                return None
        return _row_to_resolved(row)

    # Tier 1 — exact country
    hit = _fetch_for_key(f"C:{country_oksm}")
    if hit is not None:
        return hit

    # Tier 2 — areals
    for areal in _areals_for_country(sb, country_oksm):
        hit = _fetch_for_key(f"A:{areal}")
        if hit is not None:
            return hit

    # Tier 3 — base rate
    return _fetch_for_key(None)


def _lookup_all_variants(
    sb: Any,
    *,
    tnved_code: str,
    payment_type: str,
    country_oksm: int,
    target_date: date,
    has_certificate: bool,
    has_sp_certificate: bool,
) -> list[ResolvedRate]:
    """Three-tier cache lookup that returns ALL variants for the FIRST
    matching tier (rather than the single default-winning row).

    Migration 301 multi-variant flow: the API endpoint exposes every
    льготная row so customs-specialist sees full context. Tier order is
    the same as ``_lookup_db`` (exact country → areals → base) but each
    tier returns the full set when ANY row matches.

    Returns [] when the cache misses on every tier (caller will lazy-fetch).
    """
    cutoff = (datetime.now(timezone.utc) - CACHE_TTL).isoformat()

    def _fetch_for_key(country_or_areal: str | None) -> list[ResolvedRate]:
        q = (
            sb.table("tnved_rates")
              .select("*")
              .eq("tnved_code", tnved_code)
              .eq("payment_type", payment_type)
              .eq("certificate_required", has_certificate)
              .eq("sp_certificate_required", has_sp_certificate)
              .lte("valid_from", target_date.isoformat())
              .gte("source_fetched_at", cutoff)
        )
        # Migration 302: NULL replaced by '__base__' sentinel so uq_tnved_rates_v2
        # actually enforces uniqueness for all-country rates.
        q = q.eq("country_or_areal", country_or_areal or "__base__")
        q = q.order("is_default", desc=True).order("valid_from", desc=True)
        resp = q.execute()
        rows = getattr(resp, "data", []) or []
        kept: list[ResolvedRate] = []
        for row in rows:
            valid_to_text = row.get("valid_to")
            if valid_to_text:
                valid_to = date.fromisoformat(valid_to_text)
                if valid_to <= target_date:
                    continue
            kept.append(_row_to_resolved(row))
        return kept

    # Tier 1 — exact country
    hits = _fetch_for_key(f"C:{country_oksm}")
    if hits:
        return hits

    # Tier 2 — areals
    for areal in _areals_for_country(sb, country_oksm):
        hits = _fetch_for_key(f"A:{areal}")
        if hits:
            return hits

    # Tier 3 — base rate
    return _fetch_for_key(None)


def _areals_for_country(sb: Any, country_oksm: int) -> list[str]:
    """Return all areal codes the country is mapped into via country_areals."""
    resp = (
        sb.table("country_areals")
          .select("areal_code")
          .eq("country_oksm", country_oksm)
          .execute()
    )
    rows = getattr(resp, "data", []) or []
    return [r["areal_code"] for r in rows if r.get("areal_code")]


def _bulk_upsert(sb: Any, rates: list[Rate], source: str) -> None:
    """Insert all returned rates with race-safe ON CONFLICT DO UPDATE.

    The Supabase Python client's ``upsert(..., on_conflict='<col,col,...>')``
    targets the UNIQUE constraint name's columns (uq_tnved_rates).

    Foreign-key prep: the migration only seeds 99 two-digit chapter roots
    in ``kvota.tnved_codes``; leaf codes (e.g., 7326909807) accrue
    organically as Alta returns them. Before inserting rates, ensure
    every unique tnved_code is present in ``tnved_codes`` — without this,
    the FK constraint ``tnved_rates_tnved_code_fkey`` rejects the upsert
    and the resolver crashes (verified on prod 2026-05-03 with HTTP 503
    return on every /api/customs/resolve-rates call for an unknown code).
    """
    if not rates:
        return

    # 1. Ensure parent codes exist in tnved_codes (FK prerequisite).
    unique_codes = {r.tnved_code for r in rates}
    code_payload = [
        {
            "code": code,
            # Parent = first 2 digits (chapter root, seeded by migration 298).
            # Falls back to NULL when caller passes a sub-2-digit value
            # (shouldn't happen for ТН ВЭД but defensive).
            "parent_code": code[:2] if len(code) > 2 else None,
            "description": f"Auto-inserted from Alta resolve ({source})",
            "fetched_from": "alta",
        }
        for code in unique_codes
    ]
    sb.table("tnved_codes").upsert(
        code_payload, on_conflict="code"
    ).execute()

    # 2. Now safe to upsert the rates themselves.
    # uq_tnved_rates_v3 (migration 303) includes description so льготные
    # variants WITHIN a category (e.g., nds_inv "- 29..." vs "- 31...")
    # coexist instead of colliding on ON CONFLICT.
    now = datetime.now(timezone.utc).isoformat()
    payload = [_rate_to_row(r, source=source, now_iso=now) for r in rates]
    sb.table("tnved_rates").upsert(
        payload,
        on_conflict="tnved_code,payment_type,country_or_areal,valid_from,"
                    "certificate_required,sp_certificate_required,"
                    "category_code,description",
    ).execute()


def _touch_last_used_at(sb: Any, rate_id: str) -> None:
    """Fire-and-forget update; suppresses errors so a flaky write doesn't
    break the resolve. The cron uses last_used_at to pick the top-1000;
    losing a stray write here just defers a row's revalidation by a week.

    Snapshot rates carry no DB id (id=None) — the early return prevents
    a wasteful UPDATE and a potential RLS error against a synthesized id.

    Failures accumulate in ``_touch_failure_count``; crossing an alert
    threshold (10/100/1000) escalates to logger.error so a systematic
    regression (e.g. RLS policy break) becomes visible.
    """
    if rate_id is None:
        return
    global _touch_failure_count
    try:
        (
            sb.table("tnved_rates")
              .update({"last_used_at": datetime.now(timezone.utc).isoformat()})
              .eq("id", rate_id)
              .execute()
        )
    except Exception as e:
        _touch_failure_count += 1
        if _touch_failure_count in _TOUCH_FAILURE_THRESHOLDS:
            logger.error(
                "rate_resolver: last_used_at update failure threshold reached "
                "(%d failures since process start). Latest rate_id=%s err=%s",
                _touch_failure_count, rate_id, e,
            )
        else:
            logger.warning(
                "rate_resolver: failed to update last_used_at for %s: %s "
                "(rolling failure count=%d)",
                rate_id, e, _touch_failure_count,
            )


# ---------------------------------------------------------------------------
# Row ↔ dataclass conversions
# ---------------------------------------------------------------------------


def _row_to_resolved(row: dict[str, Any]) -> ResolvedRate:
    """Hydrate a kvota.tnved_rates row into a ResolvedRate.

    Populates ``Rate.source`` from the DB column too, so the calc-engine
    adapter (services/calculation_helpers.py:_resolve_import_tariff_pct)
    can read ``.source`` whether the caller passes the wrapping
    ``ResolvedRate`` or just unwraps to the inner ``Rate``.
    """
    rate = Rate(
        tnved_code=row["tnved_code"],
        payment_type=row["payment_type"],
        country_or_areal=row.get("country_or_areal"),
        valid_from=date.fromisoformat(row["valid_from"]),
        valid_to=date.fromisoformat(row["valid_to"]) if row.get("valid_to") else None,
        value_1_number=row.get("value_1_number"),
        value_1_unit=row.get("value_1_unit"),
        value_1_currency=row.get("value_1_currency"),
        value_2_number=row.get("value_2_number"),
        value_2_unit=row.get("value_2_unit"),
        value_2_currency=row.get("value_2_currency"),
        sign_1=row.get("sign_1"),
        value_3_number=row.get("value_3_number"),
        value_3_unit=row.get("value_3_unit"),
        value_3_currency=row.get("value_3_currency"),
        sign_2=row.get("sign_2"),
        raw_value_string=row.get("raw_value_string"),
        certificate_required=bool(row.get("certificate_required", False)),
        sp_certificate_required=bool(row.get("sp_certificate_required", False)),
        description=row.get("description"),
        category_code=row.get("category_code"),
        category_ru=row.get("category_ru"),
        condition_text=row.get("condition_text"),
        legal_document=row.get("legal_document"),
        legal_link=row.get("legal_link"),
        order_ref=row.get("order_ref"),
        is_default=bool(row.get("is_default", False)),
        source=row["source"],
    )
    return ResolvedRate(
        id=row["id"],
        rate=rate,
        source=row["source"],
        source_fetched_at=_parse_iso_timestamp(row["source_fetched_at"]),
        last_used_at=_parse_iso_timestamp(row.get("last_used_at") or row["source_fetched_at"]),
    )


def _rate_to_row(rate: Rate, *, source: str, now_iso: str) -> dict[str, Any]:
    """Serialize a Rate into a kvota.tnved_rates row for upsert."""
    return {
        "tnved_code": rate.tnved_code,
        "payment_type": rate.payment_type,
        "country_or_areal": rate.country_or_areal,
        "valid_from": rate.valid_from.isoformat(),
        "valid_to": rate.valid_to.isoformat() if rate.valid_to else None,
        "value_1_number": rate.value_1_number,
        "value_1_unit": rate.value_1_unit,
        "value_1_currency": rate.value_1_currency,
        "value_2_number": rate.value_2_number,
        "value_2_unit": rate.value_2_unit,
        "value_2_currency": rate.value_2_currency,
        "sign_1": rate.sign_1,
        "value_3_number": rate.value_3_number,
        "value_3_unit": rate.value_3_unit,
        "value_3_currency": rate.value_3_currency,
        "sign_2": rate.sign_2,
        "raw_value_string": rate.raw_value_string,
        "certificate_required": rate.certificate_required,
        "sp_certificate_required": rate.sp_certificate_required,
        # Variant metadata (migrations 301-303). category_code AND description
        # are NOT NULL in DB with default '' — coerce None at the boundary so
        # the unique key uq_tnved_rates_v3 actually distinguishes льготные
        # variants from each other within a single category.
        "description": rate.description or "",
        "category_code": rate.category_code or "",
        "category_ru": rate.category_ru,
        "condition_text": rate.condition_text,
        "legal_document": rate.legal_document,
        "legal_link": rate.legal_link,
        "order_ref": rate.order_ref,
        "is_default": rate.is_default,
        "source": source,
        "source_fetched_at": now_iso,
        "last_used_at": now_iso,
    }


def _build_resolved_from_snapshot(
    snapshot_entry: dict[str, Any],
    fetched_at: datetime,
) -> ResolvedRate:
    """Hydrate a snapshot entry (subset of kvota.tnved_rates fields written
    by services/customs_freeze_service.py) into a ResolvedRate.

    Snapshot rates carry no DB id — they live in JSONB inside
    ``quote_versions.input_variables.customs_rates``. We pass id=None
    explicitly; the ResolvedRate invariant guards against accidentally
    issuing an UPDATE against a non-existent row. ``Rate.source`` is
    populated so the calc adapter sees the right discriminator.
    """
    snapshot_source = snapshot_entry.get("source", "alta-live")
    rate = Rate(
        tnved_code=snapshot_entry.get("tnved_code", ""),
        payment_type=snapshot_entry["payment_type"],
        country_or_areal=snapshot_entry.get("country_or_areal"),
        valid_from=date.fromisoformat(snapshot_entry["valid_from"])
                    if snapshot_entry.get("valid_from") else fetched_at.date(),
        valid_to=date.fromisoformat(snapshot_entry["valid_to"])
                  if snapshot_entry.get("valid_to") else None,
        value_1_number=snapshot_entry.get("value_1_number"),
        value_1_unit=snapshot_entry.get("value_1_unit"),
        value_1_currency=snapshot_entry.get("value_1_currency"),
        value_2_number=snapshot_entry.get("value_2_number"),
        value_2_unit=snapshot_entry.get("value_2_unit"),
        value_2_currency=snapshot_entry.get("value_2_currency"),
        sign_1=snapshot_entry.get("sign_1"),
        raw_value_string=snapshot_entry.get("raw_value_string"),
        certificate_required=bool(snapshot_entry.get("certificate_required", False)),
        sp_certificate_required=bool(snapshot_entry.get("sp_certificate_required", False)),
        source=snapshot_source,
    )
    return ResolvedRate(
        id=None,
        rate=rate,
        source=snapshot_source,
        source_fetched_at=fetched_at,
        last_used_at=fetched_at,
        snapshot=True,
    )


def _parse_iso_timestamp(value: str | None) -> datetime:
    """Parse ISO-8601 timestamp from Postgres / JSONB into aware datetime."""
    if value is None:
        return datetime.now(timezone.utc)
    # Postgres serialises with '+00:00' or 'Z'. fromisoformat handles both
    # in 3.11+; coerce 'Z' for older Pythons.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
