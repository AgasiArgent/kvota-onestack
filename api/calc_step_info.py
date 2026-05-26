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
                "cost": number,            # in display currency (quote.currency)
                "currency": str,            # quote currency code
                "segment_count": int,
                "is_filled": bool,          # true iff at least one segment has cost > 0
                "missing_rates": [str]      # FX rates we couldn't resolve (cost partial)
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
        .select("id, invoice_number, supplier_id, logistics_completed_at")
        .eq("quote_id", quote_id)
        .order("created_at", desc=False)
        .execute()
    )
    invoices = invoices_res.data or []
    invoice_ids = [inv["id"] for inv in invoices]

    # 3. Logistics segments + expenses for those invoices (only if any).
    segments: list[dict] = []
    expenses: list[dict] = []
    if invoice_ids:
        seg_res = (
            supabase.table("logistics_route_segments")
            .select("id, invoice_id, main_cost_rub, currency_code")
            .in_("invoice_id", invoice_ids)
            .execute()
        )
        segments = seg_res.data or []

        segment_ids = [s["id"] for s in segments]
        if segment_ids:
            exp_res = (
                supabase.table("logistics_segment_expenses")
                .select("id, segment_id, cost_rub, currency_code")
                .in_("segment_id", segment_ids)
                .execute()
            )
            expenses = exp_res.data or []

    # 4. FX rates (latest foreign→RUB for the four allowed segment currencies).
    rates_to_rub: dict[str, float] = {}
    if segments or expenses:
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

    # Aggregate per-invoice cost in RUB, convert to display currency.
    # If display_currency != RUB, we additionally divide by display→RUB rate.
    display_to_rub: float | None
    if display_currency == "RUB":
        display_to_rub = 1.0
    else:
        display_to_rub = rates_to_rub.get(display_currency)

    cost_rub_by_invoice: dict[str, float] = {inv_id: 0.0 for inv_id in invoice_ids}
    seg_count_by_invoice: dict[str, int] = {inv_id: 0 for inv_id in invoice_ids}
    missing_by_invoice: dict[str, set[str]] = {inv_id: set() for inv_id in invoice_ids}

    # Map expenses by segment_id for the per-segment loop.
    expenses_by_segment: dict[str, list[dict]] = {}
    for e in expenses:
        seg_id = e.get("segment_id")
        if not seg_id:
            continue
        expenses_by_segment.setdefault(seg_id, []).append(e)

    for seg in segments:
        inv_id = seg.get("invoice_id")
        if not inv_id or inv_id not in cost_rub_by_invoice:
            continue
        seg_count_by_invoice[inv_id] += 1

        # Segment main cost.
        seg_amount = _safe_float(seg.get("main_cost_rub"))
        seg_currency = (seg.get("currency_code") or "RUB").upper()
        rub_amount = _convert_to_rub(seg_amount, seg_currency, rates_to_rub)
        if rub_amount is None:
            missing_by_invoice[inv_id].add(seg_currency)
        else:
            cost_rub_by_invoice[inv_id] += rub_amount

        # Segment expenses.
        for exp in expenses_by_segment.get(seg["id"], []):
            exp_amount = _safe_float(exp.get("cost_rub"))
            exp_currency = (exp.get("currency_code") or "RUB").upper()
            rub_amount = _convert_to_rub(exp_amount, exp_currency, rates_to_rub)
            if rub_amount is None:
                missing_by_invoice[inv_id].add(exp_currency)
            else:
                cost_rub_by_invoice[inv_id] += rub_amount

    # Build per-invoice rows in the original invoice order.
    logistics_per_invoice: list[dict] = []
    for inv in invoices:
        inv_id = inv["id"]
        cost_rub = cost_rub_by_invoice.get(inv_id, 0.0)
        if display_to_rub and display_to_rub > 0:
            cost = cost_rub / display_to_rub
            cost_currency = display_currency
        else:
            # Can't convert RUB→display because we lack the rate.
            # Surface in display currency with cost=0 and missing_rates noting it.
            cost = 0.0
            cost_currency = display_currency
            missing_by_invoice[inv_id].add(display_currency)

        seg_count = seg_count_by_invoice.get(inv_id, 0)
        # Filled iff there is at least one segment AND cost > 0.
        is_filled = seg_count > 0 and cost_rub > 0

        logistics_per_invoice.append({
            "invoice_id": inv_id,
            "invoice_number": inv.get("invoice_number"),
            "cost": round(cost, 2),
            "currency": cost_currency,
            "segment_count": seg_count,
            "is_filled": is_filled,
            "missing_rates": sorted(missing_by_invoice[inv_id]),
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
