"""
PHMB API endpoints for Next.js frontend.

POST /api/phmb/calculate  — Run PHMB calculation for a quote
POST /api/phmb/export-pdf — Generate commercial offer PDF for a PHMB quote

These are JSON API endpoints called by the Next.js frontend.
Auth: JWT via ApiAuthMiddleware (request.state.api_user).
"""

import logging
from decimal import Decimal
from html import escape

from starlette.responses import JSONResponse, Response

from services.database import get_supabase
from services.phmb_calculator import calculate_phmb_quote
from services.phmb_price_service import get_phmb_settings, get_phmb_items
from services.cbr_rates_service import get_today_cny_usd_rate

logger = logging.getLogger(__name__)


def _get_api_user(request):
    """Extract authenticated user from JWT. Returns (user_dict, error_response).

    On success: (user_dict, None)
    On failure: (None, JSONResponse)
    """
    api_user = getattr(request.state, "api_user", None)
    if not api_user:
        return None, JSONResponse(
            {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Authentication required"}},
            status_code=401,
        )

    user_meta = api_user.user_metadata or {}
    org_id = user_meta.get("org_id")
    if not org_id:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "User has no organization"}},
            status_code=403,
        )

    user = {
        "id": str(api_user.id),
        "email": api_user.email or "",
        "org_id": org_id,
    }
    return user, None


def _decimal_to_float(obj):
    """Recursively convert Decimals to floats for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(item) for item in obj]
    return obj


async def phmb_calculate(request):
    """POST /api/phmb/calculate

    Run PHMB calculation for all items in a quote and persist results.

    Input JSON: { "quote_id": "uuid" }
    Returns: { "success": true, "data": { "items": [...], "totals": {...} } }
    """
    user, err = _get_api_user(request)
    if err:
        return err

    # Parse request body
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    quote_id = body.get("quote_id")
    if not quote_id:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "quote_id is required"}},
            status_code=400,
        )

    org_id = user["org_id"]
    sb = get_supabase()

    # Fetch quote and verify access
    quote_result = sb.table("quotes").select("*").eq("id", quote_id).eq("organization_id", org_id).execute()
    if not quote_result.data:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Quote not found"}},
            status_code=404,
        )
    quote = quote_result.data[0]

    if not quote.get("is_phmb"):
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Quote is not a PHMB quote"}},
            status_code=400,
        )

    # Fetch PHMB settings
    settings = get_phmb_settings(org_id)
    if not settings:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "PHMB settings not configured for this organization"}},
            status_code=404,
        )

    # Fetch items
    items = get_phmb_items(quote_id)
    if not items:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "No items to calculate"}},
            status_code=400,
        )

    # Get CNY/USD exchange rate from CBR
    cny_usd_rate = get_today_cny_usd_rate()
    if not cny_usd_rate:
        return JSONResponse(
            {"success": False, "error": {"code": "RATE_UNAVAILABLE", "message": "CNY/USD exchange rate unavailable from CBR"}},
            status_code=500,
        )

    # Build calculation params (same logic as the FastHTML route)
    quote_params = {
        "advance_pct": float(quote.get("phmb_advance_pct") or settings.get("default_advance_pct", 0)),
        "markup_pct": float(quote.get("phmb_markup_pct") or settings.get("default_markup_pct", 10)),
        "payment_days": int(quote.get("phmb_payment_days") or settings.get("default_payment_days", 30)),
        "cny_to_usd_rate": float(cny_usd_rate),
    }

    # Run calculation
    try:
        result = calculate_phmb_quote(items, settings, quote_params)
    except Exception as e:
        logger.error(f"PHMB calculation failed for quote {quote_id}: {e}")
        return JSONResponse(
            {"success": False, "error": {"code": "CALCULATION_ERROR", "message": "Calculation failed"}},
            status_code=500,
        )

    # Persist calculated values to phmb_quote_items
    for calc_item in result["items"]:
        item_id = calc_item.get("id")
        if not item_id:
            continue
        sb.table("phmb_quote_items").update({
            "exw_price_usd": float(calc_item["exw_price_usd"]),
            "cogs_usd": float(calc_item["cogs_usd"]),
            "financial_cost_usd": float(calc_item["financial_cost_usd"]),
            "total_price_usd": float(calc_item["total_price_usd"]),
            "total_price_with_vat_usd": float(calc_item["total_price_with_vat_usd"]),
        }).eq("id", item_id).execute()

    # Persist quote totals
    totals = result["totals"]
    sb.table("quotes").update({
        "subtotal_usd": float(totals["total_price_usd"]),
        "total_amount_usd": float(totals["total_price_with_vat_usd"]),
    }).eq("id", quote_id).execute()

    # Build response items (subset of fields relevant to the frontend)
    response_items = []
    for calc_item in result["items"]:
        response_items.append({
            "id": calc_item.get("id"),
            "cat_number": calc_item.get("cat_number"),
            "product_name": calc_item.get("product_name"),
            "brand": calc_item.get("brand"),
            "quantity": calc_item.get("quantity"),
            "list_price_rmb": _decimal_to_float(calc_item.get("list_price_rmb")),
            "discount_pct": _decimal_to_float(calc_item.get("discount_pct")),
            "exw_price_usd": _decimal_to_float(calc_item["exw_price_usd"]),
            "cogs_usd": _decimal_to_float(calc_item["cogs_usd"]),
            "financial_cost_usd": _decimal_to_float(calc_item["financial_cost_usd"]),
            "total_price_usd": _decimal_to_float(calc_item["total_price_usd"]),
            "total_price_with_vat_usd": _decimal_to_float(calc_item["total_price_with_vat_usd"]),
            "line_total_usd": _decimal_to_float(calc_item.get("line_total_usd")),
            "line_total_with_vat_usd": _decimal_to_float(calc_item.get("line_total_with_vat_usd")),
        })

    response_totals = {
        "subtotal_usd": _decimal_to_float(totals["total_price_usd"]),
        "total_usd": _decimal_to_float(totals["total_price_with_vat_usd"]),
        "total_exw_usd": _decimal_to_float(totals["total_exw_usd"]),
        "total_cogs_usd": _decimal_to_float(totals["total_cogs_usd"]),
        "total_quantity": totals["total_quantity"],
        "cny_to_usd_rate": float(cny_usd_rate),
    }

    return JSONResponse({
        "success": True,
        "data": {
            "items": response_items,
            "totals": response_totals,
        },
    })


async def phmb_export_pdf(request):
    """POST /api/phmb/export-pdf

    Generate a commercial offer PDF for a PHMB quote.

    Input JSON: { "quote_id": "uuid" }
    Returns: PDF binary with Content-Type: application/pdf
    """
    user, err = _get_api_user(request)
    if err:
        return err

    # Parse request body
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    quote_id = body.get("quote_id")
    if not quote_id:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "quote_id is required"}},
            status_code=400,
        )

    org_id = user["org_id"]
    sb = get_supabase()

    # Fetch quote and verify access
    quote_result = (
        sb.table("quotes")
        .select("*, customers!customer_id(company_name, name)")
        .eq("id", quote_id)
        .eq("organization_id", org_id)
        .execute()
    )
    if not quote_result.data:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Quote not found"}},
            status_code=404,
        )
    quote = quote_result.data[0]

    if not quote.get("is_phmb"):
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Quote is not a PHMB quote"}},
            status_code=400,
        )

    # Fetch calculated items
    items = get_phmb_items(quote_id)
    if not items:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "No items in this quote"}},
            status_code=400,
        )

    # Check items have been calculated
    first_item = items[0]
    if first_item.get("total_price_usd") is None:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Items have not been calculated yet. Run /api/phmb/calculate first."}},
            status_code=400,
        )

    # Fetch organization info for the PDF header
    org_result = sb.table("organizations").select("name, legal_name").eq("id", org_id).execute()
    org = org_result.data[0] if org_result.data else {}

    # Generate PDF
    try:
        customer = (quote.get("customers") or {})
        customer_name = customer.get("company_name") or customer.get("name") or ""
        quote_number = quote.get("idn_quote", "")

        html = _build_phmb_pdf_html(
            quote=quote,
            items=items,
            customer_name=customer_name,
            org_name=org.get("legal_name") or org.get("name", ""),
        )

        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()

        safe_number = "".join(c if c.isalnum() or c in "-_" else "_" for c in quote_number)
        filename = f"PHMB_Offer_{safe_number}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ImportError:
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "PDF generation library (weasyprint) not available"}},
            status_code=500,
        )
    except Exception as e:
        logger.error(f"PHMB PDF export failed for quote {quote_id}: {e}")
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to generate PDF"}},
            status_code=500,
        )


def _build_phmb_pdf_html(
    quote: dict,
    items: list[dict],
    customer_name: str,
    org_name: str,
) -> str:
    """Build HTML for the PHMB commercial offer PDF.

    Uses inline styles for WeasyPrint compatibility (no external CSS).
    """
    quote_number = escape(quote.get("idn_quote", ""))
    created_at = quote.get("created_at", "")[:10]  # YYYY-MM-DD

    # Build items table rows
    rows_html = ""
    for idx, item in enumerate(items, 1):
        qty = item.get("quantity", 0)
        unit_price = item.get("total_price_usd") or 0
        line_total = float(unit_price) * qty if unit_price else 0

        rows_html += f"""
        <tr>
            <td style="text-align: center;">{idx}</td>
            <td>{escape(str(item.get('cat_number', '') or ''))}</td>
            <td>{escape(str(item.get('product_name', '') or ''))}</td>
            <td>{escape(str(item.get('brand', '') or ''))}</td>
            <td style="text-align: center;">{qty}</td>
            <td style="text-align: right;">{float(unit_price):,.2f}</td>
            <td style="text-align: right;">{line_total:,.2f}</td>
        </tr>"""

    subtotal = float(quote.get("subtotal_usd") or 0)
    total = float(quote.get("total_amount_usd") or 0)

    advance_pct = quote.get("phmb_advance_pct") or 0
    markup_pct = quote.get("phmb_markup_pct") or 0
    payment_days = quote.get("phmb_payment_days") or 30

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 20mm 15mm;
        }}
        body {{
            font-family: Arial, Helvetica, sans-serif;
            font-size: 11px;
            color: #1e293b;
            line-height: 1.4;
        }}
        h1 {{
            font-size: 18px;
            margin: 0 0 4px 0;
            color: #0f172a;
        }}
        .header {{
            margin-bottom: 20px;
            border-bottom: 2px solid #334155;
            padding-bottom: 12px;
        }}
        .meta {{
            font-size: 12px;
            color: #64748b;
            margin-bottom: 4px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }}
        th {{
            background: #f1f5f9;
            font-weight: 600;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            padding: 8px 6px;
            border: 1px solid #cbd5e1;
            text-align: left;
        }}
        td {{
            padding: 6px;
            border: 1px solid #e2e8f0;
            font-size: 11px;
        }}
        tr:nth-child(even) {{
            background: #f8fafc;
        }}
        .totals {{
            margin-top: 16px;
            text-align: right;
        }}
        .totals p {{
            margin: 4px 0;
            font-size: 12px;
        }}
        .totals .grand-total {{
            font-size: 14px;
            font-weight: 700;
        }}
        .conditions {{
            margin-top: 24px;
            font-size: 11px;
        }}
        .conditions h3 {{
            font-size: 12px;
            margin-bottom: 6px;
        }}
        .conditions ul {{
            padding-left: 18px;
            margin: 0;
        }}
        .conditions li {{
            margin-bottom: 4px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Коммерческое предложение {quote_number}</h1>
        <div class="meta">Дата: {escape(created_at)}</div>
        <div class="meta">Поставщик: {escape(org_name)}</div>
        <div class="meta">Покупатель: {escape(customer_name)}</div>
    </div>

    <table>
        <thead>
            <tr>
                <th style="width: 30px; text-align: center;">№</th>
                <th style="width: 100px;">Артикул</th>
                <th>Наименование</th>
                <th style="width: 90px;">Бренд</th>
                <th style="width: 40px; text-align: center;">Кол-во</th>
                <th style="width: 80px; text-align: right;">Цена, USD</th>
                <th style="width: 90px; text-align: right;">Сумма, USD</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

    <div class="totals">
        <p>Итого без НДС: <strong>{subtotal:,.2f} USD</strong></p>
        <p class="grand-total">Итого с НДС (20%): {total:,.2f} USD</p>
    </div>

    <div class="conditions">
        <h3>Условия</h3>
        <ul>
            <li>Авансовый платёж: {float(advance_pct):.0f}%</li>
            <li>Наценка: {float(markup_pct):.1f}%</li>
            <li>Срок оплаты: {int(payment_days)} дней</li>
        </ul>
    </div>
</body>
</html>"""
