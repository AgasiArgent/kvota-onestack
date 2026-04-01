"""
Plan-Fact API endpoints for Next.js frontend.

GET    /api/plan-fact/{deal_id}/items       — List items with category join
POST   /api/plan-fact/{deal_id}/items       — Create planned payment item
PATCH  /api/plan-fact/{deal_id}/items/{id}  — Update planned or actual fields
DELETE /api/plan-fact/{deal_id}/items/{id}  — Delete (only if no actual_amount)
GET    /api/plan-fact/categories             — List active categories
GET    /api/quotes/search?q={query}          — Search quotes with linked deals

Auth: JWT via ApiAuthMiddleware (request.state.api_user).
Roles: finance/admin = full CRUD, top_manager = read-only.
"""

import logging
from decimal import Decimal

from starlette.responses import JSONResponse

from services.database import get_supabase

logger = logging.getLogger(__name__)

# Roles that can read plan-fact data
READ_ROLES = {"finance", "admin", "top_manager"}
# Roles that can create/update/delete plan-fact data
WRITE_ROLES = {"finance", "admin"}


def _decimal_to_float(obj):
    """Recursively convert Decimals to floats for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(item) for item in obj]
    return obj


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
    print(f"[plan_fact] user_id={api_user.id}, email={api_user.email}, org_id={org_id}, meta_keys={list(user_meta.keys())}")
    if not org_id:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "User has no organization"}},
            status_code=403,
        )

    return {
        "id": str(api_user.id),
        "email": api_user.email or "",
        "org_id": org_id,
    }, None


def _get_user_roles(user_id: str, org_id: str) -> set[str]:
    """Fetch user's role slugs from user_roles table."""
    sb = get_supabase()
    result = (
        sb.table("user_roles")
        .select("roles!inner(slug)")
        .eq("user_id", user_id)
        .eq("organization_id", org_id)
        .execute()
    )
    roles = set()
    print(f"[plan_fact] role query result: {result.data}")
    for row in result.data or []:
        role_data = row.get("roles")
        if isinstance(role_data, dict):
            slug = role_data.get("slug")
            if slug:
                roles.add(slug)
    print(f"[plan_fact] resolved roles: {roles}")
    return roles


def _check_read_access(roles: set[str]):
    """Return error response if user lacks read access, else None."""
    if not roles.intersection(READ_ROLES):
        return JSONResponse(
            {"success": False, "error": {"code": "INSUFFICIENT_PERMISSIONS", "message": "Access denied"}},
            status_code=403,
        )
    return None


def _check_write_access(roles: set[str]):
    """Return error response if user lacks write access, else None."""
    if not roles.intersection(WRITE_ROLES):
        return JSONResponse(
            {"success": False, "error": {"code": "INSUFFICIENT_PERMISSIONS", "message": "Write access denied"}},
            status_code=403,
        )
    return None


def _verify_deal_org(deal_id: str, org_id: str):
    """Verify deal belongs to user's org. Returns (deal_row, error_response)."""
    sb = get_supabase()
    result = (
        sb.table("deals")
        .select("id, organization_id")
        .eq("id", deal_id)
        .execute()
    )
    if not result.data:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Deal not found"}},
            status_code=404,
        )

    deal = result.data[0]
    if deal["organization_id"] != org_id:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Deal not found"}},
            status_code=404,
        )

    return deal, None


def _fetch_item_with_category(item_id: str):
    """Fetch a single plan_fact_item joined with its category."""
    sb = get_supabase()
    result = (
        sb.table("plan_fact_items")
        .select(
            "id, deal_id, category_id, description, "
            "planned_amount, planned_currency, planned_date, "
            "actual_amount, actual_currency, actual_date, "
            "variance_amount, payment_document, notes, status, created_at, "
            "plan_fact_categories!category_id(id, code, name, name_ru, is_income)"
        )
        .eq("id", item_id)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]


def _format_item(row: dict) -> dict:
    """Format a plan_fact_item row with nested category for API response."""
    cat = (row.get("plan_fact_categories") or {})
    return _decimal_to_float({
        "id": row["id"],
        "deal_id": row["deal_id"],
        "category": {
            "id": cat.get("id"),
            "code": cat.get("code"),
            "name": cat.get("name"),
            "name_ru": cat.get("name_ru"),
            "is_income": cat.get("is_income"),
        },
        "description": row.get("description"),
        "planned_amount": row.get("planned_amount"),
        "planned_currency": row.get("planned_currency"),
        "planned_date": row.get("planned_date"),
        "actual_amount": row.get("actual_amount"),
        "actual_currency": row.get("actual_currency"),
        "actual_date": row.get("actual_date"),
        "variance_amount": row.get("variance_amount"),
        "payment_document": row.get("payment_document"),
        "notes": row.get("notes"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
    })


async def plan_fact_list_items(request, deal_id: str):
    """GET /api/plan-fact/{deal_id}/items

    List plan-fact items for a deal, joined with categories, sorted by planned_date.
    """
    user, err = _get_api_user(request)
    if err:
        return err

    roles = _get_user_roles(user["id"], user["org_id"])

    access_err = _check_read_access(roles)
    if access_err:
        return access_err

    _, org_err = _verify_deal_org(deal_id, user["org_id"])
    if org_err:
        return org_err

    sb = get_supabase()
    result = (
        sb.table("plan_fact_items")
        .select(
            "id, deal_id, category_id, description, "
            "planned_amount, planned_currency, planned_date, "
            "actual_amount, actual_currency, actual_date, "
            "variance_amount, payment_document, notes, status, created_at, "
            "plan_fact_categories!category_id(id, code, name, name_ru, is_income)"
        )
        .eq("deal_id", deal_id)
        .order("planned_date")
        .execute()
    )

    items = [_format_item(row) for row in (result.data or [])]

    return JSONResponse({"success": True, "data": items})


async def plan_fact_create_item(request, deal_id: str):
    """POST /api/plan-fact/{deal_id}/items

    Create a new planned payment item.
    Required fields: category_id, planned_amount, planned_currency, planned_date.
    """
    user, err = _get_api_user(request)
    if err:
        return err

    roles = _get_user_roles(user["id"], user["org_id"])

    write_err = _check_write_access(roles)
    if write_err:
        return write_err

    _, org_err = _verify_deal_org(deal_id, user["org_id"])
    if org_err:
        return org_err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    # Validate required fields
    errors = {}
    if not body.get("category_id"):
        errors["category_id"] = "Category is required"
    if body.get("planned_amount") is None:
        errors["planned_amount"] = "Planned amount is required"
    if not body.get("planned_currency"):
        errors["planned_currency"] = "Planned currency is required"
    if not body.get("planned_date"):
        errors["planned_date"] = "Planned date is required"

    if errors:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Missing required fields", "fields": errors}},
            status_code=400,
        )

    # Validate currency
    valid_currencies = {"RUB", "USD", "EUR"}
    if body["planned_currency"] not in valid_currencies:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": f"Currency must be one of: {', '.join(sorted(valid_currencies))}"}},
            status_code=400,
        )

    sb = get_supabase()

    insert_data = {
        "deal_id": deal_id,
        "category_id": body["category_id"],
        "description": body.get("description", ""),
        "planned_amount": body["planned_amount"],
        "planned_currency": body["planned_currency"],
        "planned_date": body["planned_date"],
        "created_by": user["id"],
    }

    try:
        result = sb.table("plan_fact_items").insert(insert_data).execute()
    except Exception as e:
        logger.error(f"Failed to create plan-fact item for deal {deal_id}: {e}")
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to create item"}},
            status_code=500,
        )

    if not result.data:
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to create item"}},
            status_code=500,
        )

    # Re-fetch with category join for complete response
    created_item = _fetch_item_with_category(result.data[0]["id"])
    if not created_item:
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Item created but could not be retrieved"}},
            status_code=500,
        )

    return JSONResponse(
        {"success": True, "data": _format_item(created_item)},
        status_code=201,
    )


async def plan_fact_update_item(request, deal_id: str, item_id: str):
    """PATCH /api/plan-fact/{deal_id}/items/{id}

    Update actual or planned fields on an existing item.
    """
    user, err = _get_api_user(request)
    if err:
        return err

    roles = _get_user_roles(user["id"], user["org_id"])

    write_err = _check_write_access(roles)
    if write_err:
        return write_err

    _, org_err = _verify_deal_org(deal_id, user["org_id"])
    if org_err:
        return org_err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    sb = get_supabase()

    # Verify item exists and belongs to the deal
    existing = (
        sb.table("plan_fact_items")
        .select("id, deal_id")
        .eq("id", item_id)
        .eq("deal_id", deal_id)
        .execute()
    )
    if not existing.data:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Item not found"}},
            status_code=404,
        )

    # Build update payload from allowed fields
    allowed_fields = {
        "category_id", "description",
        "planned_amount", "planned_currency", "planned_date",
        "actual_amount", "actual_currency", "actual_date",
        "payment_document", "notes",
    }
    update_data = {k: v for k, v in body.items() if k in allowed_fields}

    if not update_data:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "No valid fields to update"}},
            status_code=400,
        )

    # Validate currency if provided
    valid_currencies = {"RUB", "USD", "EUR"}
    for currency_field in ("planned_currency", "actual_currency"):
        if currency_field in update_data and update_data[currency_field] not in valid_currencies:
            return JSONResponse(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": f"{currency_field} must be one of: {', '.join(sorted(valid_currencies))}"}},
                status_code=400,
            )

    try:
        sb.table("plan_fact_items").update(update_data).eq("id", item_id).execute()
    except Exception as e:
        logger.error(f"Failed to update plan-fact item {item_id}: {e}")
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to update item"}},
            status_code=500,
        )

    # Re-fetch with category join for complete response (includes trigger-calculated variance)
    updated_item = _fetch_item_with_category(item_id)
    if not updated_item:
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Item updated but could not be retrieved"}},
            status_code=500,
        )

    return JSONResponse({"success": True, "data": _format_item(updated_item)})


async def plan_fact_delete_item(request, deal_id: str, item_id: str):
    """DELETE /api/plan-fact/{deal_id}/items/{id}

    Delete a plan-fact item. Only allowed if actual_amount is NULL.
    """
    user, err = _get_api_user(request)
    if err:
        return err

    roles = _get_user_roles(user["id"], user["org_id"])

    write_err = _check_write_access(roles)
    if write_err:
        return write_err

    _, org_err = _verify_deal_org(deal_id, user["org_id"])
    if org_err:
        return org_err

    sb = get_supabase()

    # Fetch item to check actual_amount
    existing = (
        sb.table("plan_fact_items")
        .select("id, deal_id, actual_amount")
        .eq("id", item_id)
        .eq("deal_id", deal_id)
        .execute()
    )
    if not existing.data:
        return JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "Item not found"}},
            status_code=404,
        )

    item = existing.data[0]
    if item.get("actual_amount") is not None:
        return JSONResponse(
            {"success": False, "error": {"code": "ITEM_HAS_ACTUAL", "message": "Cannot delete item with recorded actual payment"}},
            status_code=409,
        )

    try:
        sb.table("plan_fact_items").delete().eq("id", item_id).execute()
    except Exception as e:
        logger.error(f"Failed to delete plan-fact item {item_id}: {e}")
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to delete item"}},
            status_code=500,
        )

    return JSONResponse(None, status_code=204)


async def plan_fact_list_categories(request):
    """GET /api/plan-fact/categories

    Return all active plan_fact_categories ordered by sort_order.
    """
    user, err = _get_api_user(request)
    if err:
        return err

    roles = _get_user_roles(user["id"], user["org_id"])

    access_err = _check_read_access(roles)
    if access_err:
        return access_err

    sb = get_supabase()
    result = (
        sb.table("plan_fact_categories")
        .select("id, code, name, name_ru, is_income, sort_order")
        .order("sort_order")
        .execute()
    )

    categories = [
        {
            "id": row["id"],
            "code": row["code"],
            "name": row["name"],
            "name_ru": row.get("name_ru"),
            "is_income": row["is_income"],
            "sort_order": row["sort_order"],
        }
        for row in (result.data or [])
    ]

    return JSONResponse({"success": True, "data": categories})


async def quotes_search(request):
    """GET /api/quotes/search?q={query}

    Search quotes by idn_quote (ILIKE), returning only those with a linked deal.
    Joins: quotes -> specifications -> deals, quotes -> customers.
    """
    user, err = _get_api_user(request)
    if err:
        return err

    roles = _get_user_roles(user["id"], user["org_id"])

    access_err = _check_read_access(roles)
    if access_err:
        return access_err

    q = request.query_params.get("q", "").strip()
    if len(q) < 3:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Query must be at least 3 characters"}},
            status_code=400,
        )

    sb = get_supabase()

    # Search quotes by idn_quote, scoped to user's org
    result = (
        sb.table("quotes")
        .select(
            "id, idn_quote, "
            "customers!customer_id(name), "
            "specifications(id, deals(id, deal_number))"
        )
        .eq("organization_id", user["org_id"])
        .ilike("idn_quote", f"%{q}%")
        .limit(20)
        .execute()
    )

    data = []
    for row in (result.data or []):
        # Navigate the FK chain: quote -> specifications -> deals
        specs = row.get("specifications") or []
        if not isinstance(specs, list):
            specs = [specs]

        for spec in specs:
            deals = (spec.get("deals") if spec else None) or []
            if not isinstance(deals, list):
                deals = [deals]

            for deal in deals:
                if not deal or not deal.get("id"):
                    continue
                customer = (row.get("customers") or {})
                data.append({
                    "id": row["id"],
                    "idn": row.get("idn_quote"),
                    "customer_name": customer.get("name") if isinstance(customer, dict) else None,
                    "deal_id": deal["id"],
                    "deal_number": deal.get("deal_number"),
                })

    return JSONResponse({"success": True, "data": data})
