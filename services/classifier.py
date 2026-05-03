"""TN ВЭД classifier — wraps Alta Express batch ML classifier.

Phase 2 customs entry-point for "подбор кода ТН ВЭД по названию".

Flow:
  1. UI sends one or many product names + optional brand/description
  2. ``classify_items`` builds a stable `request_id` (sha256 of inputs +
     today's date — Express is idempotent on this key for ~24h, so retries
     don't burn extra packets) and calls ``alta_client.classify_batch``
  3. Each prediction is enriched with a description from the local
     ``kvota.tnved_codes`` cache when available — Express itself returns
     only code+probability, no human-readable label
  4. Returns ``ClassifyResult`` per input. Audit row is written to
     ``kvota.tnved_classification_log`` with method='express' so we can
     see what was suggested and what was eventually picked.

Selection (``log_classification_choice``) is a separate function called by
the API handler when the customs-specialist confirms a code from the
candidates: writes a follow-up log row with ``chosen_code`` and updates
``quote_items.hs_code``.

Phase 3 will add АПУ wizard for low-confidence Express predictions.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from services.alta_client import AltaApiError, AltaClient, ExpressItem
from services.database import get_supabase

logger = logging.getLogger(__name__)


# Alta Express returns up to 5 candidates per item. We surface all so the
# UI can show low-confidence options too — customs picks the right one.
_TOP_K = 5

# Below this packet level we refuse new classify calls — protects the cron
# revalidation budget. 100 matches the Phase-1 packet alert threshold.
_PACKET_FLOOR = 50


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassifyInput:
    """Single item to classify. ``quote_item_id`` ties suggestions back to
    a row so the API can write per-item audit log entries. May be None
    when classification happens from a free-form modal (no target row)."""
    name: str
    brand: str | None = None
    description: str | None = None
    quote_item_id: str | None = None


@dataclass(frozen=True)
class Candidate:
    """One suggested TN ВЭД code from Alta Express."""
    code: str                  # 10-digit ТН ВЭД
    probability: float         # 0.0..1.0 — Alta ML confidence
    code_weight: int           # Alta-internal ranking signal
    description: str | None    # Best-effort label from kvota.tnved_codes (None if unknown)


@dataclass(frozen=True)
class ClassifyResult:
    """Suggestions for one input item."""
    input_idx: int                       # 1-based, matches ExpressItem id
    name: str                            # echo for UI
    quote_item_id: str | None
    candidates: list[Candidate]
    error: str | None = None             # populated when Alta returned
                                         # nothing for this row (low quality
                                         # input or out-of-domain)


@dataclass(frozen=True)
class ClassifyOutcome:
    """Top-level response — collects per-row results plus metadata."""
    results: list[ClassifyResult]
    packet_left: int | None              # Surface to UI for ops awareness
    packet_used: int | None
    request_id: str                      # Audit + idempotency key


class ClassifierError(Exception):
    """Wrapper for failures that should map to a structured API error.

    ``code`` mirrors the customs-API error vocabulary (ALTA_UNAVAILABLE,
    PACKET_EXHAUSTED, BAD_REQUEST, ...).
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def classify_items(
    inputs: list[ClassifyInput],
    *,
    alta_client: AltaClient,
    user_id: str | None = None,
    today: date | None = None,
) -> ClassifyOutcome:
    """Run Alta Express on a batch of product descriptions.

    Idempotent: sending the same inputs on the same day reuses Alta's
    cached batch (request_id = stable sha256). Retries don't burn
    additional packets within ~24h.

    Raises:
        ClassifierError(BAD_REQUEST) — empty inputs.
        ClassifierError(PACKET_EXHAUSTED) — left_count below floor;
            blocks new calls so the cron revalidation budget is preserved.
        ClassifierError(ALTA_UNAVAILABLE) — AltaApiError or network error.

    Side effects:
        Writes one audit row per input to ``kvota.tnved_classification_log``
        (method='express'). The row carries the suggested codes; the
        ``chosen_code`` column is filled later by ``log_classification_choice``
        when the customs-specialist confirms a pick.
    """
    if not inputs:
        raise ClassifierError("BAD_REQUEST", "items list must not be empty")

    today = today or date.today()
    request_id = _build_request_id(inputs, today)

    # Pre-flight packet check: refuse if Alta is running low. last_packet_left
    # is populated by Alta Такса/xml_nodes calls earlier in the session;
    # may be None on a fresh process — we let the call proceed in that case
    # and rely on the post-call alerting (Phase 1 packet warning) for ops.
    if (
        alta_client.last_packet_left is not None
        and alta_client.last_packet_left < _PACKET_FLOOR
    ):
        raise ClassifierError(
            "PACKET_EXHAUSTED",
            f"Alta packet running low ({alta_client.last_packet_left} remaining). "
            "Classification deferred — top up the prepaid quota.",
        )

    express_items = [
        ExpressItem(id=idx, name=_compose_query(inp))
        for idx, inp in enumerate(inputs, start=1)
    ]

    try:
        response = await alta_client.classify_batch(
            express_items, request_id=request_id,
        )
    except AltaApiError as e:
        logger.error(
            "classifier: Alta error %s for request_id=%s: %s",
            e.code, request_id, e.message,
        )
        raise ClassifierError("ALTA_UNAVAILABLE", e.message) from e
    except Exception as e:
        logger.error(
            "classifier: Alta call crashed for request_id=%s: %s",
            request_id, e,
        )
        raise ClassifierError("ALTA_UNAVAILABLE", str(e)) from e

    # Group predictions by the 1-based id we set on each ExpressItem.
    # Alta returns the top candidates flat — UI wants top-K per input.
    by_id: dict[int, list[Any]] = {}
    for pred in response.predictions:
        by_id.setdefault(pred.id, []).append(pred)
    for preds in by_id.values():
        preds.sort(
            key=lambda p: (p.probability, p.code_weight),
            reverse=True,
        )

    # Best-effort description enrichment from the local cache. One round-
    # trip total — we collect every code first.
    all_codes = sorted({p.code for preds in by_id.values() for p in preds})
    description_by_code = _fetch_descriptions(all_codes)

    results: list[ClassifyResult] = []
    for idx, inp in enumerate(inputs, start=1):
        preds = (by_id.get(idx) or [])[:_TOP_K]
        candidates = [
            Candidate(
                code=p.code,
                probability=p.probability,
                code_weight=p.code_weight,
                description=description_by_code.get(p.code),
            )
            for p in preds
        ]
        error = None if candidates else "No candidates returned by Alta"
        results.append(
            ClassifyResult(
                input_idx=idx,
                name=inp.name,
                quote_item_id=inp.quote_item_id,
                candidates=candidates,
                error=error,
            )
        )

    # Audit log — fire-and-forget, never block the response.
    _log_classifications(
        results=results,
        user_id=user_id,
        method="express",
    )

    return ClassifyOutcome(
        results=results,
        packet_left=response.packet_left,
        packet_used=response.packet_used,
        request_id=request_id,
    )


def log_classification_choice(
    *,
    quote_item_id: str,
    chosen_code: str,
    candidates: list[Candidate],
    user_id: str | None,
    method: str = "express",
    input_text: str = "",
) -> None:
    """Persist the customs-specialist's pick so we can audit accuracy later.

    Writes one row to ``kvota.tnved_classification_log``. Suppresses any
    DB error — losing an audit row must never block the user-visible
    save. Caller is expected to update ``quote_items.hs_code`` separately.
    """
    sb = get_supabase()
    try:
        sb.table("tnved_classification_log").insert({
            "quote_item_id": quote_item_id,
            "method": method,
            "input_text": input_text,
            "suggested_codes": [
                {
                    "code": c.code,
                    "probability": c.probability,
                    "code_weight": c.code_weight,
                }
                for c in candidates
            ],
            "chosen_code": chosen_code,
            "user_id": user_id,
        }).execute()
    except Exception as e:
        # Never block the user save on audit-log failure.
        logger.warning(
            "classifier: failed to log classification choice for %s: %s",
            quote_item_id, e,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compose_query(inp: ClassifyInput) -> str:
    """Combine name + brand + description into one string for Alta.

    Alta Express ML weighs the whole text. Brand alone is rarely useful
    but adding it after the name (e.g., "Шайба М6 SuperRotors") gives
    the classifier slightly more context without confusing it.
    """
    parts = [inp.name.strip()]
    if inp.brand and inp.brand.strip():
        parts.append(inp.brand.strip())
    if inp.description and inp.description.strip():
        parts.append(inp.description.strip())
    return " ".join(parts)


def _build_request_id(inputs: list[ClassifyInput], today: date) -> str:
    """Stable sha256 of (sorted inputs + today's date).

    Same inputs same day → same request_id → Alta returns the cached
    response without spending another packet. Retries on transient
    failures are free.
    """
    serialized = "\n".join(
        f"{_compose_query(inp)}|{inp.quote_item_id or ''}"
        for inp in inputs
    )
    raw = f"{today.isoformat()}|{serialized}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _fetch_descriptions(codes: list[str]) -> dict[str, str]:
    """Best-effort lookup of code → description from the local cache.

    Returns {} on any error — UI gracefully shows codes without labels.
    """
    if not codes:
        return {}
    try:
        sb = get_supabase()
        resp = (
            sb.table("tnved_codes")
              .select("code, description")
              .in_("code", codes)
              .execute()
        )
        rows = getattr(resp, "data", []) or []
        return {
            row["code"]: row["description"]
            for row in rows
            if row.get("description")
        }
    except Exception as e:
        logger.warning("classifier: tnved_codes lookup failed: %s", e)
        return {}


def _log_classifications(
    *,
    results: list[ClassifyResult],
    user_id: str | None,
    method: str,
) -> None:
    """Insert one audit row per result. Suppresses DB errors."""
    rows = [
        {
            "quote_item_id": r.quote_item_id,
            "method": method,
            "input_text": r.name,
            "suggested_codes": [
                {
                    "code": c.code,
                    "probability": c.probability,
                    "code_weight": c.code_weight,
                }
                for c in r.candidates
            ],
            "chosen_code": None,  # filled when user confirms via /select
            "user_id": user_id,
        }
        for r in results
        if r.candidates  # don't pollute the log with no-op queries
    ]
    if not rows:
        return
    try:
        sb = get_supabase()
        sb.table("tnved_classification_log").insert(rows).execute()
    except Exception as e:
        logger.warning(
            "classifier: failed to write %d audit rows: %s",
            len(rows), e,
        )
