"""Calc-step info card endpoint — aggregates logistics + customs + certs.

Handler module (not router). Registered via thin wrapper in
``api/routers/quotes.py``. Backs Testing 2 rows 36 + 48:

* Row 36 — «На этапе расчета необходимо выводить информацию о пошлинах и
  сертификации»
* Row 48 — «Необходимо указать стоимость логистики для данного заказа»

The calc-step page already has the calculation form, but procurement /
sales need a glanceable summary of WHAT logistics will be paid, WHAT
customs duties apply, and WHAT certificates have been collected — without
hopping into the logistics + customs sub-tabs. The numbers all live in
DB already; this endpoint just consolidates them.

Auth: dual — JWT (Next.js) via ApiAuthMiddleware (request.state.api_user),
or legacy session (FastHTML) via Starlette's SessionMiddleware. Read-only.
Roles: any authenticated org member (RLS-enforced on underlying tables).
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

from api.lib.errors import error_response
from services.database import get_supabase

logger = logging.getLogger(__name__)

__all__ = ["get_calc_step_info"]


# Currency codes the segment editor allows (matches m309 CHECK constraint).
# Mirrors logistics-segment/types.ts SEGMENT_CURRENCIES.
_SEGMENT_CURRENCIES = ("USD", "EUR", "CNY")  # RUB is the implicit base


def _safe_float(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _convert_to_rub(amount: float, currency: str, rates: dict[str, float]) -> float | None:
    """foreign → RUB. Returns None when the rate is missing (caller surfaces
    the gap in `missing_rates`)."""
    if amount == 0:
        return 0.0
    code = (currency or "RUB").upper()
    if code == "RUB":
        return amount
    rate = rates.get(code)
    if not rate or rate <= 0:
        return None
    return amount * rate


def _build_segment_label(seg: dict) -> str:
    """Derive a segment label, mirroring location-chip.tsx ``buildLabel``.

    Order of precedence:
        1. Free-text ``label`` when present.
        2. ``from → to`` where each side is ``country · city`` (or just
           ``country`` when city is null), joined with an arrow.

    Locations are nullable since m317 — a null endpoint renders as
    «Не выбрано» so the row stays informative rather than blank.
    """
    free = (seg.get("label") or "").strip()
    if free:
        return free

    def _loc_label(loc: dict | None) -> str:
        if not loc:
            return "Не выбрано"
        country = (loc.get("country") or "").strip()
        city = (loc.get("city") or "").strip()
        if country and city:
            return f"{country} · {city}"
        return country or "Не выбрано"

    return f"{_loc_label(seg.get('from_location'))} → {_loc_label(seg.get('to_location'))}"


def _resolve_auth(request: Request) -> tuple[dict | None, JSONResponse | None]:
    """Dual auth: JWT first, then legacy session.

    Returns (user_dict, None) on success — user dict has ``id`` and ``org_id``.
    Returns (None, error_response) on failure.
    """
    api_user = getattr(request.state, "api_user", None)
    if api_user:
        user_id = str(api_user.id)
        supabase = get_supabase()
        om = (
            supabase.table("organization_members")
            .select("organization_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        org_id = om.data[0]["organization_id"] if om.data else None
        if not org_id:
            return None, error_response("FORBIDDEN", "No organization", 403)
        return {"id": user_id, "org_id": org_id}, None

    try:
        session = request.session
    except (AssertionError, AttributeError):
        session = None
    if not session or not session.get("user"):
        return None, error_response("UNAUTHORIZED", "Unauthorized", 401)

    user_data = session.get("user", {})
    user_id = user_data.get("id")
    org_id = user_data.get("org_id")
    if not user_id:
        return None, error_response("UNAUTHORIZED", "Unauthorized", 401)
    if not org_id:
        return None, error_response("FORBIDDEN", "No organization", 403)
    return {"id": user_id, "org_id": org_id}, None


async def get_calc_step_info(
    request: Request,
    quote_id: str,
) -> JSONResponse:
    """Return per-invoice logistics + per-item customs + certifications.

    Path: GET /api/quotes/{quote_id}/calc-step-info
    Auth: dual — JWT (Next.js) first, then legacy session (FastHTML).
    Returns:
        {
          "success": true,
          "data": {
            "logistics_per_invoice": [
              {
                "invoice_id": str,
                "invoice_number": str,
                "segment_count": int,
                "is_filled": bool,          # true iff a segment has cost > 0
                "missing_rates": [str],     # FX rates we couldn't resolve
                "segments": [               # per-segment rows, ordered by sequence_order
                  {
                    "segment_id": str,
                    "invoice_id": str,
                    "label": str,           # free-text label or "from → to"
                    "cost": number,         # main cost in quote currency
                    "currency": str,        # quote currency code
                    "transit_days": int | null,
                    "missing_rate": bool    # cost unresolved (rate missing)
                  },
                  ...
                ]
              },
              ...
            ],
            "customs": [
              {
                "item_id": str,
                "brand": str | null,
                "product_name": str | null,
                "hs_code": str | null,      # ТН ВЭД
                "customs_duty": number | null  # percent
              },
              ...
            ],
            "certifications": [
              {
                "id": str,
                "type": str,
                "display_name": str | null,
                "cost": number,
                "currency": str
              },
              ...
            ]
          }
        }
    Errors:
        401 UNAUTHORIZED — no JWT and no session
        403 FORBIDDEN — auth ok but no organization membership
        404 NOT_FOUND — quote doesn't exist for this org
    Side Effects: none — read-only.
    Roles: any authenticated org member (RLS scopes data).
    """
    user, err = _resolve_auth(request)
    if err is not None:
        return err
    assert user is not None  # narrowed by err check
    org_id = user["org_id"]

    supabase = get_supabase()

    # 1. Verify quote exists in caller's org (cheap RLS-equivalent guard).
    quote_res = (
        supabase.table("quotes")
        .select("id, currency, organization_id")
        .eq("id", quote_id)
        .eq("organization_id", org_id)
        .is_("deleted_at", None)
        .limit(1)
        .execute()
    )
    quote_rows = quote_res.data or []
    if not quote_rows:
        return error_response("NOT_FOUND", "Quote not found", 404)
    quote = quote_rows[0]
    display_currency = (quote.get("currency") or "RUB").upper()

    # 2. Invoices for this quote.
    invoices_res = (
        supabase.table("invoices")
        .select("id, invoice_number")
        .eq("quote_id", quote_id)
        .order("created_at", desc=False)
        .execute()
    )
    invoices = invoices_res.data or []
    invoice_ids = [inv["id"] for inv in invoices]

    # 3. Logistics segments for those invoices (only if any). We show the
    # segment MAIN cost only — logistics_segment_expenses are intentionally
    # NOT folded in here (Row 48a: per-segment rows display main cost).
    # Location joins reuse the FK names from
    # frontend/src/entities/logistics-segment/queries.ts so the label can be
    # derived without a second query.
    segments: list[dict] = []
    if invoice_ids:
        seg_res = (
            supabase.table("logistics_route_segments")
            .select(
                "id, invoice_id, sequence_order, transit_days, label, "
                "main_cost_rub, currency_code, "
                "from_location_id, to_location_id, "
                "from_location:locations!logistics_route_segments_from_location_id_fkey("
                "id, country, city, location_type), "
                "to_location:locations!logistics_route_segments_to_location_id_fkey("
                "id, country, city, location_type)"
            )
            .in_("invoice_id", invoice_ids)
            .order("sequence_order", desc=False)
            .execute()
        )
        segments = seg_res.data or []

    # 4. FX rates (latest foreign→RUB for the four allowed segment currencies).
    rates_to_rub: dict[str, float] = {}
    if segments:
        fx_res = (
            supabase.table("exchange_rates")
            .select("from_currency, rate, fetched_at")
            .eq("to_currency", "RUB")
            .in_("from_currency", list(_SEGMENT_CURRENCIES))
            .order("fetched_at", desc=True)
            .limit(20)
            .execute()
        )
        for row in fx_res.data or []:
            code = (row.get("from_currency") or "").upper()
            if not code or code in rates_to_rub:
                continue  # most recent wins (rows ordered DESC)
            r = _safe_float(row.get("rate"))
            if r > 0:
                rates_to_rub[code] = r

    # Each segment's main cost is denominated in its own currency_code; we
    # convert foreign → RUB → quote currency. RUB→quote needs the display
    # rate (1.0 when the quote itself is in RUB).
    display_to_rub: float | None
    if display_currency == "RUB":
        display_to_rub = 1.0
    else:
        display_to_rub = rates_to_rub.get(display_currency)

    def _segment_cost_in_quote(
        amount: float, currency: str
    ) -> tuple[float, str | None]:
        """Convert a segment's main cost to the quote currency.

        Returns ``(cost, missing_currency)``. ``missing_currency`` is the
        currency code whose rate could not be resolved (the segment's own
        currency for the foreign→RUB leg, or the display currency for the
        RUB→quote leg) — None when both legs converted cleanly. When a rate
        is missing the returned cost is 0.0 and the gap is surfaced upward.
        """
        rub = _convert_to_rub(amount, currency, rates_to_rub)
        if rub is None:
            return 0.0, (currency or "RUB").upper()
        if not display_to_rub or display_to_rub <= 0:
            return 0.0, display_currency
        return round(rub / display_to_rub, 2), None

    # Group segments per invoice (already ordered by sequence_order from the
    # query). Each row carries its converted quote-currency cost + flags.
    segments_by_invoice: dict[str, list[dict]] = {inv_id: [] for inv_id in invoice_ids}
    missing_by_invoice: dict[str, set[str]] = {inv_id: set() for inv_id in invoice_ids}
    for seg in segments:
        inv_id = seg.get("invoice_id")
        if not inv_id or inv_id not in segments_by_invoice:
            continue
        seg_amount = _safe_float(seg.get("main_cost_rub"))
        seg_currency = (seg.get("currency_code") or "RUB").upper()
        cost, missing_currency = _segment_cost_in_quote(seg_amount, seg_currency)
        if missing_currency:
            missing_by_invoice[inv_id].add(missing_currency)
        transit = seg.get("transit_days")
        segments_by_invoice[inv_id].append({
            "segment_id": seg["id"],
            "invoice_id": inv_id,
            "label": _build_segment_label(seg),
            "cost": cost,
            "currency": display_currency,
            "transit_days": int(transit) if transit is not None else None,
            "missing_rate": missing_currency is not None,
        })

    # Build per-invoice groups in the original invoice order. The per-invoice
    # ``is_filled`` / ``missing_rates`` signals are retained so the FE hint +
    # deep link still work.
    logistics_per_invoice: list[dict] = []
    for inv in invoices:
        inv_id = inv["id"]
        inv_segments = segments_by_invoice.get(inv_id, [])
        missing_rates = sorted(missing_by_invoice.get(inv_id, set()))
        # Filled iff at least one segment has a resolved cost > 0.
        is_filled = any(
            (not s["missing_rate"]) and s["cost"] > 0 for s in inv_segments
        )

        logistics_per_invoice.append({
            "invoice_id": inv_id,
            "invoice_number": inv.get("invoice_number"),
            "segment_count": len(inv_segments),
            "is_filled": is_filled,
            "missing_rates": missing_rates,
            "segments": inv_segments,
        })

    # 5. Customs per item — pull from quote_items for hs_code + customs_duty.
    items_res = (
        supabase.table("quote_items")
        .select("id, brand, product_name, hs_code, customs_duty")
        .eq("quote_id", quote_id)
        .order("position", desc=False)
        .execute()
    )
    customs_rows = [
        {
            "item_id": row["id"],
            "brand": row.get("brand"),
            "product_name": row.get("product_name"),
            "hs_code": row.get("hs_code"),
            "customs_duty": (
                _safe_float(row.get("customs_duty"))
                if row.get("customs_duty") is not None
                else None
            ),
        }
        for row in items_res.data or []
    ]

    # 6. Certifications for the quote.
    certs_res = (
        supabase.table("quote_certificates")
        .select("id, type, display_name, cost_original, cost_currency")
        .eq("quote_id", quote_id)
        .order("created_at", desc=True)
        .execute()
    )
    certifications = [
        {
            "id": row["id"],
            "type": row.get("type"),
            "display_name": row.get("display_name"),
            "cost": _safe_float(row.get("cost_original")),
            "currency": (row.get("cost_currency") or "RUB").upper(),
        }
        for row in certs_res.data or []
    ]

    return JSONResponse({
        "success": True,
        "data": {
            "logistics_per_invoice": logistics_per_invoice,
            "customs": customs_rows,
            "certifications": certifications,
        },
    })
