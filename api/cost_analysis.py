"""Cost Analysis (КА) API endpoint — read-only P&L waterfall for a quote.

Path: GET /api/quotes/{quote_id}/cost-analysis
Auth: Bearer JWT via ``ApiAuthMiddleware`` (``request.state.api_user``).
Roles: finance, top_manager, admin, quote_controller. All other roles are
       rejected with 403 FORBIDDEN.

Ports the logic from the FastHTML handler in ``main.py`` L5834-6140 to a
JSON envelope consumable by the Next.js frontend. Business calculations are
NOT changed — this endpoint only aggregates pre-computed phase results from
``quote_calculation_results`` and surfaces the ``quote_calculation_variables``
logistics breakdown.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from services.database import get_supabase

logger = logging.getLogger(__name__)

__all__ = ["get_cost_analysis"]


_ALLOWED_ROLES: set[str] = {
    "finance",
    "top_manager",
    "admin",
    "quote_controller",
}


# phase_results keys aggregated across items.
_AGGREGATE_KEYS: tuple[str, ...] = (
    "AK16",  # revenue_no_vat
    "AL16",  # revenue_with_vat
    "S16",   # purchase
    "V16",   # logistics
    "Y16",   # customs
    "Z16",   # excise
    "AG16",  # dm_fee
    "AH16",  # forex
    "AI16",  # financial_agent_fee
    "BB16",  # financing
)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _err(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status,
    )


def _resolve_user(
    request: Request,
) -> tuple[dict | None, JSONResponse | None]:
    """Authenticate via JWT and pull org_id + role slugs.

    Returns (user_dict, None) on success or (None, error_response).
    user_dict keys: id, org_id, roles (set[str]).
    """
    api_user = getattr(request.state, "api_user", None)
    if not api_user:
        return None, _err("UNAUTHORIZED", "Authentication required", 401)

    user_id = str(api_user.id)
    sb = get_supabase()

    om_result = (
        sb.table("organization_members")
        .select("organization_id")
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    om_rows = _rows(om_result)
    if not om_rows:
        return None, _err("FORBIDDEN", "User has no active organization", 403)
    org_id = str(om_rows[0].get("organization_id", ""))

    roles_result = (
        sb.table("user_roles")
        .select("roles!inner(slug)")
        .eq("user_id", user_id)
        .eq("organization_id", org_id)
        .execute()
    )
    role_slugs: set[str] = set()
    for row in _rows(roles_result):
        role_data = row.get("roles")
        if isinstance(role_data, dict) and role_data.get("slug"):
            role_slugs.add(str(role_data["slug"]))

    if not role_slugs & _ALLOWED_ROLES:
        return None, _err(
            "FORBIDDEN",
            "Role not permitted for cost analysis",
            403,
        )

    return {"id": user_id, "org_id": org_id, "roles": role_slugs}, None


def _empty_totals() -> dict[str, float]:
    return {
        "revenue_no_vat": 0.0,
        "revenue_with_vat": 0.0,
        "purchase": 0.0,
        "logistics": 0.0,
        "customs": 0.0,
        "excise": 0.0,
        "dm_fee": 0.0,
        "forex": 0.0,
        "financial_agent_fee": 0.0,
        "financing": 0.0,
    }


def _empty_logistics() -> dict[str, float]:
    return {
        "W2_supplier_hub": 0.0,
        "W3_hub_customs": 0.0,
        "W4_customs_client": 0.0,
        "W5_brokerage_hub": 0.0,
        "W6_brokerage_customs": 0.0,
        "W7_warehousing": 0.0,
        "W8_documentation": 0.0,
        "W9_extra": 0.0,
        "W10_insurance": 0.0,
    }


def _empty_derived() -> dict[str, float]:
    return {
        "direct_costs": 0.0,
        "gross_profit": 0.0,
        "financial_expenses": 0.0,
        "net_profit": 0.0,
        "markup_pct": 0.0,
        "sale_purchase_ratio": 0.0,
    }


def _aggregate_phase_results(
    rows: list[dict[str, Any]],
) -> dict[str, float]:
    """SUM each phase_results key across all calculation rows."""
    totals = {key: 0.0 for key in _AGGREGATE_KEYS}
    for row in rows:
        pr = row.get("phase_results") or {}
        if not isinstance(pr, dict):
            continue
        for key in _AGGREGATE_KEYS:
            try:
                totals[key] += float(pr.get(key, 0) or 0)
            except (TypeError, ValueError):
                # Malformed value — skip rather than 500 the whole request.
                continue
    return totals


def _map_totals(raw: dict[str, float]) -> dict[str, float]:
    """Map the Excel-like keys (AK16...) to the readable response fields."""
    return {
        "revenue_no_vat": raw["AK16"],
        "revenue_with_vat": raw["AL16"],
        "purchase": raw["S16"],
        "logistics": raw["V16"],
        "customs": raw["Y16"],
        "excise": raw["Z16"],
        "dm_fee": raw["AG16"],
        "forex": raw["AH16"],
        "financial_agent_fee": raw["AI16"],
        "financing": raw["BB16"],
    }


def _logistics_breakdown(
    variables: dict[str, Any] | None,
) -> dict[str, float]:
    """Extract W2-W10 logistics breakdown from quote_calculation_variables."""
    if not isinstance(variables, dict):
        return _empty_logistics()

    def _num(key: str) -> float:
        try:
            return float(variables.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    return {
        "W2_supplier_hub": _num("logistics_supplier_hub"),
        "W3_hub_customs": _num("logistics_hub_customs"),
        "W4_customs_client": _num("logistics_customs_client"),
        "W5_brokerage_hub": _num("brokerage_hub"),
        "W6_brokerage_customs": _num("brokerage_customs"),
        "W7_warehousing": _num("warehousing_at_customs"),
        "W8_documentation": _num("customs_documentation"),
        "W9_extra": _num("brokerage_extra"),
        "W10_insurance": _num("rate_insurance"),
    }


def _derived_metrics(totals: dict[str, float]) -> dict[str, float]:
    """Compute P&L derivations from the mapped totals."""
    revenue = totals["revenue_no_vat"]
    purchase = totals["purchase"]

    direct_costs = (
        purchase
        + totals["logistics"]
        + totals["customs"]
        + totals["excise"]
    )
    gross_profit = revenue - direct_costs

    financial_expenses = (
        totals["dm_fee"]
        + totals["forex"]
        + totals["financial_agent_fee"]
        + totals["financing"]
    )
    net_profit = gross_profit - financial_expenses

    if purchase > 0:
        markup_pct = (revenue / purchase - 1) * 100
        sale_purchase_ratio = revenue / purchase
    else:
        markup_pct = 0.0
        sale_purchase_ratio = 0.0

    return {
        "direct_costs": direct_costs,
        "gross_profit": gross_profit,
        "financial_expenses": financial_expenses,
        "net_profit": net_profit,
        "markup_pct": markup_pct,
        "sale_purchase_ratio": sale_purchase_ratio,
    }


async def get_cost_analysis(
    request: Request,
    quote_id: str,
) -> JSONResponse:
    """Return the P&L waterfall data for one quote.

    Path: GET /api/quotes/{quote_id}/cost-analysis
    Auth: Bearer JWT (ApiAuthMiddleware).
    Params:
        quote_id: str (path) — UUID of the quote.
    Returns:
        quote: {id, idn_quote, title, currency, workflow_status, customer_name}
        has_calculation: bool — False when no calculation rows exist
        totals: {revenue_no_vat, revenue_with_vat, purchase, logistics, customs,
                 excise, dm_fee, forex, financial_agent_fee, financing}
        logistics_breakdown: {W2_supplier_hub ... W10_insurance}
        derived: {direct_costs, gross_profit, financial_expenses, net_profit,
                  markup_pct, sale_purchase_ratio}
    Side Effects: none (read-only).
    Roles: finance, top_manager, admin, quote_controller.
    """
    user, err = _resolve_user(request)
    if err is not None:
        return err
    assert user is not None  # for type-checker

    sb = get_supabase()

    # Fetch the quote with customer name. ``customers!customer_id`` disambiguates
    # the FK per project convention — ``customers`` auto-detection would be
    # ambiguous if the table grows more FK paths.
    quote_result = (
        sb.table("quotes")
        .select(
            "id, organization_id, idn_quote, title, currency, "
            "workflow_status, customers!customer_id(name)"
        )
        .eq("id", quote_id)
        .is_("deleted_at", None)
        .limit(1)
        .execute()
    )
    quote_rows = _rows(quote_result)
    if not quote_rows:
        return _err("NOT_FOUND", "Quote not found", 404)

    quote = quote_rows[0]
    if str(quote.get("organization_id") or "") != user["org_id"]:
        return _err("FORBIDDEN", "Quote belongs to a different organization", 403)

    customers = quote.get("customers")
    customer_name = (
        customers.get("name") if isinstance(customers, dict) else None
    ) or ""

    quote_payload = {
        "id": str(quote.get("id") or ""),
        "idn_quote": quote.get("idn_quote") or "",
        "title": quote.get("title") or "",
        "currency": quote.get("currency") or "USD",
        "workflow_status": quote.get("workflow_status") or "draft",
        "customer_name": customer_name,
    }

    # Aggregate calculation results.
    calc_result = (
        sb.table("quote_calculation_results")
        .select("quote_item_id, phase_results")
        .eq("quote_id", quote_id)
        .execute()
    )
    calc_rows = _rows(calc_result)

    if not calc_rows:
        return JSONResponse(
            {
                "success": True,
                "data": {
                    "quote": quote_payload,
                    "has_calculation": False,
                    "totals": _empty_totals(),
                    "logistics_breakdown": _empty_logistics(),
                    "derived": _empty_derived(),
                },
            }
        )

    totals_raw = _aggregate_phase_results(calc_rows)
    totals = _map_totals(totals_raw)

    vars_result = (
        sb.table("quote_calculation_variables")
        .select("variables")
        .eq("quote_id", quote_id)
        .limit(1)
        .execute()
    )
    vars_rows = _rows(vars_result)
    variables = vars_rows[0].get("variables") if vars_rows else None
    logistics_breakdown = _logistics_breakdown(
        variables if isinstance(variables, dict) else None
    )

    derived = _derived_metrics(totals)

    return JSONResponse(
        {
            "success": True,
            "data": {
                "quote": quote_payload,
                "has_calculation": True,
                "totals": totals,
                "logistics_breakdown": logistics_breakdown,
                "derived": derived,
            },
        }
    )
