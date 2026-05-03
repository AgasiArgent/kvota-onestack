"""Customs snapshot freeze service — REQ-8 + Q4 three-tier graceful degradation.

When a quote transitions to ``WorkflowStatus.APPROVED`` (or the user
explicitly hits "Пересчитать по текущим ставкам"), this module captures
a snapshot of every quote_item's customs rates and stores it in
``kvota.quote_versions.input_variables.customs_rates`` (Q7 simplification).
Frozen quotes thereafter resolve rates from the snapshot via
``services.rate_resolver.resolve_rate()``'s snapshot branch — so PDFs
sent months ago re-render with the same numbers.

Three-tier graceful degradation (Q4 = Option C + user notifications):

    Tier 1 (preferred) — live Alta call:
        Each item's rates fetched fresh via rate_resolver. Returns
        FreezeSnapshotResult(status='ok', source_at_freeze='alta-live').
        UI: silent.

    Tier 2 (Alta down, cache acceptable) — fallback to <30-day cache:
        For items where Alta fails AND a cached row exists with
        source_fetched_at >= now() - 30d, use it. Returns status='cache-stale'
        with per-item warnings.
        UI: non-blocking yellow toast.

    Tier 3 (Alta down, cache empty/stale) — abort:
        For items with neither live nor fresh-cache rates, abort the
        whole snapshot. Returns status='abort' and emits a Telegram
        admin alert. The workflow_service hook propagates this as a
        failed transition; UI shows red modal.

Public API:
    async def build_snapshot(quote_id, *, alta_client) -> FreezeSnapshotResult
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Literal, Union

from services.alta_client import notify_admin
from services.database import get_supabase
from services.rate_resolver import CACHE_TTL, resolve_rate

if TYPE_CHECKING:
    from services.alta_client import AltaClient

logger = logging.getLogger(__name__)


SnapshotStatus = Literal["ok", "cache-stale", "abort"]
SourceAtFreeze = Literal["alta-live", "cache-stale", "abort"]


@dataclass(frozen=True)
class OkSnapshot:
    """Tier 1 outcome — every item resolved via live Alta. UI is silent."""
    items: dict[str, dict[str, Any]]   # quote_item_id → snapshot entry

    @property
    def status(self) -> Literal["ok"]:
        return "ok"

    @property
    def source_at_freeze(self) -> Literal["alta-live"]:
        return "alta-live"

    @property
    def warnings(self) -> list[str]:
        return []

    @property
    def message(self) -> None:
        return None


@dataclass(frozen=True)
class CacheStaleSnapshot:
    """Tier 2 outcome — at least one item used <30d cache because Alta
    was unavailable. UI shows non-blocking yellow toast with warnings.
    """
    items: dict[str, dict[str, Any]]
    warnings: list[str]

    @property
    def status(self) -> Literal["cache-stale"]:
        return "cache-stale"

    @property
    def source_at_freeze(self) -> Literal["cache-stale"]:
        return "cache-stale"

    @property
    def message(self) -> None:
        return None


@dataclass(frozen=True)
class AbortSnapshot:
    """Tier 3 outcome — at least one item had neither live nor fresh
    cache. The workflow transition fails; UI shows red modal with
    `message` and any per-item warnings.
    """
    items: dict[str, dict[str, Any]]
    warnings: list[str]
    message: str

    @property
    def status(self) -> Literal["abort"]:
        return "abort"

    @property
    def source_at_freeze(self) -> Literal["abort"]:
        return "abort"


# Discriminated union — callers pattern-match on `.status` (Literal) or
# isinstance(). Backwards-compat: `.items`, `.warnings`, `.message`,
# `.source_at_freeze` remain readable on every variant.
FreezeSnapshotResult = Union[OkSnapshot, CacheStaleSnapshot, AbortSnapshot]


# Standard payment_types we capture per item — same set the API
# resolve-rates endpoint uses (skip EXP for import flow).
_DEFAULT_PAYMENT_TYPES: tuple[str, ...] = (
    "IMP", "NDS", "AKC", "IMPCOMP", "IMPDEMP", "IMPTMP", "IMPDOP",
)


async def build_snapshot(
    quote_id: str,
    *,
    alta_client: AltaClient,
) -> FreezeSnapshotResult:
    """Capture a customs-rates snapshot for every quote_item under quote_id.

    Iterates each item; per-item three-tier fallback. The aggregate
    status is the WORST tier hit across all items:
        any item Tier 3 (abort)        → result.status = 'abort'
        else any item Tier 2 (cache)   → result.status = 'cache-stale'
        else                            → result.status = 'ok'

    Items lacking the prerequisites for resolution (no tnved_code, or
    no country_of_origin_oksm) are SKIPPED — they don't block freeze
    and don't appear in the snapshot. The caller (workflow hook) can
    enforce a separate "all items must have customs data" gate
    upstream if desired.
    """
    sb = get_supabase()

    items_resp = (
        sb.table("quote_items")
          .select(
              "id, hs_code, country_of_origin_oksm, "
              "has_origin_certificate, has_fta_certificate"
          )
          .eq("quote_id", quote_id)
          .execute()
    )
    items = getattr(items_resp, "data", []) or []

    if not items:
        # No items → trivially ok with empty snapshot. The workflow
        # transition is allowed to proceed.
        return OkSnapshot(items={})

    today = date.today()
    aggregate_status: SnapshotStatus = "ok"
    snapshot_items: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    abort_messages: list[str] = []

    for item in items:
        item_id = item["id"]
        tnved_code = item.get("hs_code")
        country_oksm = item.get("country_of_origin_oksm")

        # Skip items without prerequisites — they don't block freeze
        if not tnved_code or country_oksm is None:
            continue

        item_status, item_source, rates, item_warnings, item_abort_msg = (
            await _capture_item(
                sb=sb,
                alta_client=alta_client,
                tnved_code=tnved_code,
                country_oksm=country_oksm,
                target_date=today,
                has_certificate=bool(item.get("has_origin_certificate")),
                has_sp_certificate=bool(item.get("has_fta_certificate")),
            )
        )

        # Aggregate the worst tier we've hit so far. The OkSnapshot /
        # CacheStaleSnapshot / AbortSnapshot constructors below derive
        # source_at_freeze from this status — no need to track it here.
        if item_status == "abort":
            aggregate_status = "abort"
            abort_messages.append(
                item_abort_msg or f"item={item_id}: rates unavailable"
            )
        elif item_status == "cache-stale" and aggregate_status == "ok":
            aggregate_status = "cache-stale"

        warnings.extend(item_warnings)

        snapshot_items[str(item_id)] = {
            "rates": rates,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_at_freeze": item_source,
        }

    if aggregate_status == "abort":
        message = (
            "Не удалось получить актуальные ставки для freeze. "
            "Попробуйте через несколько минут. "
            "Если проблема повторяется — обратитесь к администратору."
        )
        try:
            await notify_admin(
                f"Customs freeze ABORT for quote {quote_id}: "
                + "; ".join(abort_messages[:5])
            )
        except Exception as e:
            logger.warning("Failed to send Telegram alert for freeze abort: %s", e)
        return AbortSnapshot(
            items=snapshot_items,
            warnings=warnings,
            message=message,
        )

    if aggregate_status == "cache-stale":
        return CacheStaleSnapshot(
            items=snapshot_items,
            warnings=warnings,
        )

    return OkSnapshot(items=snapshot_items)


async def _capture_item(
    *,
    sb: Any,
    alta_client: AltaClient,
    tnved_code: str,
    country_oksm: int,
    target_date: date,
    has_certificate: bool,
    has_sp_certificate: bool,
) -> tuple[SnapshotStatus, SourceAtFreeze, list[dict[str, Any]], list[str], str | None]:
    """Three-tier capture for one item. Returns (status, source, rates, warnings, abort_msg).

    Tier 1: ``rate_resolver.resolve_rate(...)`` — uses live Alta path
            via the resolver's lazy-fetch.
    Tier 2: if Tier 1 returned None for a payment_type, query
            ``kvota.tnved_rates`` directly with no TTL filter (allow
            stale entries up to 30 days old) for a last-resort cache hit.
    Tier 3: if no rate found by either tier for ANY payment_type we'd
            normally expect AND at least one was attempted, mark the
            item as abort.

    Per-payment_type granularity: each of the 7 default payment_types
    is captured independently. Missing IMPCOMP/IMPDEMP/etc. is normal
    (only ~2-3 typically apply per code), so absence is NOT abort —
    abort fires only when the *requested-and-found-elsewhere* type is
    missing now.
    """
    rates: list[dict[str, Any]] = []
    warnings: list[str] = []
    used_cache_stale = False
    saw_any = False

    for payment_type in _DEFAULT_PAYMENT_TYPES:
        # Tier 1
        live = await resolve_rate(
            tnved_code=tnved_code,
            payment_type=payment_type,
            country_oksm=country_oksm,
            target_date=target_date,
            has_certificate=has_certificate,
            has_sp_certificate=has_sp_certificate,
            alta_client=alta_client,
        )

        if live is not None:
            saw_any = True
            rates.append(_resolved_to_snapshot_dict(live))
            continue

        # Tier 2 — last-resort cache hit (allow rows older than 30 days)
        stale = _lookup_stale_cache(
            sb=sb,
            tnved_code=tnved_code,
            payment_type=payment_type,
            country_oksm=country_oksm,
            target_date=target_date,
            has_certificate=has_certificate,
            has_sp_certificate=has_sp_certificate,
        )
        if stale is not None:
            saw_any = True
            used_cache_stale = True
            rates.append(stale)
            warnings.append(
                f"{tnved_code}/{country_oksm}/{payment_type}: использован кэш "
                f"(Alta недоступна)"
            )

    if not saw_any:
        # Tier 3 — neither live nor stale-cache produced anything for
        # ANY payment_type. This is the abort condition.
        msg = (
            f"tnved={tnved_code}, country={country_oksm}: "
            "ни live, ни кэш не вернули ставок"
        )
        return ("abort", "abort", [], warnings, msg)

    if used_cache_stale:
        return ("cache-stale", "cache-stale", rates, warnings, None)

    return ("ok", "alta-live", rates, warnings, None)


def _lookup_stale_cache(
    *,
    sb: Any,
    tnved_code: str,
    payment_type: str,
    country_oksm: int,
    target_date: date,
    has_certificate: bool,
    has_sp_certificate: bool,
) -> dict[str, Any] | None:
    """Query kvota.tnved_rates without the 30-day TTL filter — used as
    Tier 2 fallback when Alta is unavailable.

    Tries exact-country first, falls back to areal, then base. Cap is
    hard 30 days even in Tier 2 — older than that, we abort rather
    than serve genuinely stale data.

    Each supabase query is isolated with try/except: if the network
    blips or RLS regresses, we treat the lookup as a miss and let the
    next tier (or the abort path) decide. Bubbling exceptions here
    would silently kill freeze when combined with the broad except in
    workflow_service's freeze hook.
    """
    cutoff = (datetime.now(timezone.utc) - CACHE_TTL).isoformat()

    def _try(country_or_areal: str | None) -> dict[str, Any] | None:
        try:
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
            if country_or_areal is None:
                q = q.is_("country_or_areal", "null")
            else:
                q = q.eq("country_or_areal", country_or_areal)
            q = q.order("valid_from", desc=True).limit(1)
            rows = getattr(q.execute(), "data", []) or []
            return rows[0] if rows else None
        except Exception as exc:
            logger.warning(
                "freeze: stale-cache lookup failed for %s/%s/%s "
                "(country_or_areal=%s): %s",
                tnved_code, country_oksm, payment_type, country_or_areal, exc,
            )
            return None

    row = _try(f"C:{country_oksm}")
    if row is not None:
        return _row_to_snapshot_dict(row)

    # Areal tier — load areals for this country
    try:
        areals_resp = (
            sb.table("country_areals")
              .select("areal_code")
              .eq("country_oksm", country_oksm)
              .execute()
        )
        areals = getattr(areals_resp, "data", []) or []
    except Exception as exc:
        logger.warning(
            "freeze: stale-cache lookup failed for %s/%s/%s "
            "(country_areals lookup): %s",
            tnved_code, country_oksm, payment_type, exc,
        )
        areals = []

    for areal_row in areals:
        row = _try(f"A:{areal_row['areal_code']}")
        if row is not None:
            return _row_to_snapshot_dict(row)

    row = _try(None)
    if row is not None:
        return _row_to_snapshot_dict(row)

    return None


def _resolved_to_snapshot_dict(resolved: Any) -> dict[str, Any]:
    """Serialize a ResolvedRate into the JSONB shape kept in
    ``quote_versions.input_variables.customs_rates[item_id]['rates']``.

    The shape mirrors the kvota.tnved_rates row but only the columns
    rate_resolver actually reads back via _build_resolved_from_snapshot.
    """
    return {
        "tnved_code": resolved.tnved_code,
        "payment_type": resolved.payment_type,
        "country_or_areal": resolved.country_or_areal,
        "valid_from": resolved.valid_from.isoformat(),
        "value_1_number": resolved.value_1_number,
        "value_1_unit": resolved.value_1_unit,
        "value_1_currency": resolved.value_1_currency,
        "value_2_number": resolved.value_2_number,
        "value_2_unit": resolved.value_2_unit,
        "value_2_currency": resolved.value_2_currency,
        "sign_1": resolved.sign_1,
        "raw_value_string": resolved.raw_value_string,
        "source": resolved.source,
        "certificate_required": resolved.rate.certificate_required,
        "sp_certificate_required": resolved.rate.sp_certificate_required,
    }


def _row_to_snapshot_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Same shape as _resolved_to_snapshot_dict but sourced from a raw
    kvota.tnved_rates row (Tier 2 path)."""
    return {
        "tnved_code": row["tnved_code"],
        "payment_type": row["payment_type"],
        "country_or_areal": row.get("country_or_areal"),
        "valid_from": row["valid_from"],
        "value_1_number": row.get("value_1_number"),
        "value_1_unit": row.get("value_1_unit"),
        "value_1_currency": row.get("value_1_currency"),
        "value_2_number": row.get("value_2_number"),
        "value_2_unit": row.get("value_2_unit"),
        "value_2_currency": row.get("value_2_currency"),
        "sign_1": row.get("sign_1"),
        "raw_value_string": row.get("raw_value_string"),
        "source": row["source"],
        "certificate_required": bool(row.get("certificate_required", False)),
        "sp_certificate_required": bool(row.get("sp_certificate_required", False)),
    }
