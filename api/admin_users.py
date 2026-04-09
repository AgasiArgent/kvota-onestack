"""
Admin User Management API endpoints for Next.js frontend.

POST   /api/admin/users                — Create user with roles and profile
PATCH  /api/admin/users/{user_id}      — Activate or deactivate user
PATCH  /api/admin/users/{user_id}/roles — Atomically update user roles

Auth: JWT via ApiAuthMiddleware (request.state.api_user).
Roles: admin only — all endpoints require admin role.
"""

import logging
import re
from typing import Any

from starlette.responses import JSONResponse

from services.database import get_supabase

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


def _rows(response: Any) -> list[dict[str, Any]]:
    """Extract typed rows from Supabase response."""
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _get_admin_user(request) -> tuple[dict | None, JSONResponse | None]:
    """Extract authenticated admin user from JWT.

    Returns (user_dict, None) on success or (None, error_response) on failure.
    user_dict contains: id, email, org_id.
    """
    api_user = getattr(request.state, "api_user", None)
    if not api_user:
        return None, JSONResponse(
            {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Authentication required"}},
            status_code=401,
        )

    user_id = str(api_user.id)
    sb = get_supabase()

    # Resolve org_id from organization_members (never from request body)
    om = (
        sb.table("organization_members")
        .select("organization_id")
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    om_rows = _rows(om)
    if not om_rows:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "User has no active organization"}},
            status_code=403,
        )

    org_id: str = str(om_rows[0].get("organization_id", ""))

    # Check admin role
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

    if "admin" not in role_slugs:
        return None, JSONResponse(
            {"success": False, "error": {"code": "FORBIDDEN", "message": "Admin role required"}},
            status_code=403,
        )

    return {
        "id": user_id,
        "email": api_user.email or "",
        "org_id": org_id,
    }, None


def _verify_user_in_org(user_id: str, org_id: str) -> tuple[dict | None, JSONResponse | None]:
    """Verify target user belongs to the same organization.

    Returns (member_row, None) on success or (None, error_response) on failure.
    """
    sb = get_supabase()
    result = (
        sb.table("organization_members")
        .select("user_id, organization_id, status")
        .eq("user_id", user_id)
        .eq("organization_id", org_id)
        .limit(1)
        .execute()
    )
    rows = _rows(result)
    if not rows:
        return None, JSONResponse(
            {"success": False, "error": {"code": "NOT_FOUND", "message": "User not found in organization"}},
            status_code=404,
        )
    return rows[0], None


async def create_user(request) -> JSONResponse:
    """Create a new user with roles and profile.

    Path: POST /api/admin/users
    Params:
        email: str (required) - User email
        password: str (required) - Initial password (min 8 chars)
        full_name: str (required) - Display name
        role_slugs: list[str] (required) - At least one role slug
        position: str (optional) - Job title
        sales_group_id: str (optional) - Sales group UUID
        department_id: str (optional) - Department UUID
    Returns:
        user_id: str - Created user UUID
        email: str - User email
    Side Effects:
        - Creates auth.users record via Supabase Admin API
        - Inserts into organization_members (status: active)
        - Inserts into user_profiles (full_name, position)
        - Inserts into user_roles (one per slug)
        - On failure after auth creation: deletes auth user (cleanup)
    Roles: admin
    """
    admin_user, auth_err = _get_admin_user(request)
    if auth_err:
        return auth_err
    assert admin_user is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    # Validate required fields
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    full_name = (body.get("full_name") or "").strip()
    role_slugs = body.get("role_slugs") or []
    position = (body.get("position") or "").strip() or None
    sales_group_id = body.get("sales_group_id") or None
    department_id = body.get("department_id") or None

    errors: dict[str, str] = {}
    if not email:
        errors["email"] = "Email is required"
    elif not EMAIL_REGEX.match(email):
        errors["email"] = "Invalid email format"
    if not password:
        errors["password"] = "Password is required"
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors["password"] = f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if not full_name:
        errors["full_name"] = "Full name is required"
    if not role_slugs or not isinstance(role_slugs, list):
        errors["role_slugs"] = "At least one role is required"

    if errors:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Validation failed", "fields": errors}},
            status_code=400,
        )

    org_id = admin_user["org_id"]
    sb = get_supabase()

    # Validate role slugs exist in DB
    roles_result = (
        sb.table("roles")
        .select("id, slug")
        .in_("slug", role_slugs)
        .execute()
    )
    role_rows = _rows(roles_result)
    found_slugs = {str(r.get("slug", "")) for r in role_rows}
    invalid_slugs = set(role_slugs) - found_slugs
    if invalid_slugs:
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": f"Invalid role slugs: {', '.join(sorted(invalid_slugs))}"}},
            status_code=400,
        )

    role_id_map = {str(r.get("slug", "")): r.get("id") for r in role_rows}

    # Step 1: Create auth user via Supabase Admin API
    auth_user_id = None
    try:
        user_response = sb.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        auth_user_id = str(user_response.user.id)
    except Exception as e:
        error_msg = str(e)
        if "already been registered" in error_msg or "already exists" in error_msg.lower():
            return JSONResponse(
                {"success": False, "error": {"code": "USER_EXISTS", "message": "A user with this email already exists"}},
                status_code=409,
            )
        logger.error("Failed to create auth user for %s: %s", email, e)
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to create user in auth system"}},
            status_code=500,
        )

    # Steps 2-4: Insert into organization tables (with cleanup on failure)
    try:
        # Step 2: organization_members
        sb.table("organization_members").insert({
            "user_id": auth_user_id,
            "organization_id": org_id,
            "status": "active",
            "is_owner": False,
        }).execute()

        # Step 3: user_profiles
        profile_data = {
            "user_id": auth_user_id,
            "organization_id": org_id,
            "full_name": full_name,
        }
        if position:
            profile_data["position"] = position
        if sales_group_id:
            profile_data["sales_group_id"] = sales_group_id
        if department_id:
            profile_data["department_id"] = department_id

        sb.table("user_profiles").insert(profile_data).execute()

        # Step 4: user_roles (one per slug)
        for slug in role_slugs:
            sb.table("user_roles").insert({
                "user_id": auth_user_id,
                "organization_id": org_id,
                "role_id": role_id_map[slug],
            }).execute()

    except Exception as e:
        # Cleanup: delete the auth user to avoid orphaned records
        logger.error("Failed to insert org data for user %s, cleaning up: %s", auth_user_id, e)
        try:
            sb.auth.admin.delete_user(auth_user_id)
        except Exception as cleanup_err:
            logger.error("Failed to cleanup auth user %s: %s", auth_user_id, cleanup_err)
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to create user records"}},
            status_code=500,
        )

    return JSONResponse(
        {"success": True, "data": {"user_id": auth_user_id, "email": email}},
        status_code=201,
    )


async def update_user_status(request, user_id: str) -> JSONResponse:
    """Activate or deactivate a user.

    Path: PATCH /api/admin/users/{user_id}
    Params:
        status: str (required) - "active" or "suspended"
    Returns:
        user_id: str
        status: str - New status
    Side Effects:
        - Deactivate: bans auth user (100yr duration), updates org_members.status
        - Activate: unbans auth user, updates org_members.status
    Roles: admin
    """
    admin_user, auth_err = _get_admin_user(request)
    if auth_err:
        return auth_err
    assert admin_user is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    new_status = (body.get("status") or "").strip()
    if new_status not in ("active", "suspended"):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Status must be 'active' or 'suspended'"}},
            status_code=400,
        )

    org_id = admin_user["org_id"]

    # Verify target user belongs to admin's org
    _, member_err = _verify_user_in_org(user_id, org_id)
    if member_err:
        return member_err

    sb = get_supabase()

    # Last-admin guard: prevent deactivating the last active admin
    if new_status == "suspended":
        # Check if target user has admin role
        target_roles = (
            sb.table("user_roles")
            .select("roles!inner(slug)")
            .eq("user_id", user_id)
            .eq("organization_id", org_id)
            .execute()
        )
        target_is_admin = any(
            (row.get("roles") or {}).get("slug") == "admin"
            for row in _rows(target_roles)
        )

        if target_is_admin:
            # Two queries instead of N+1: one for admin user_ids, one for active members
            admin_role_rows = (
                sb.table("user_roles")
                .select("user_id, roles!inner(slug)")
                .eq("organization_id", org_id)
                .neq("user_id", user_id)
                .execute()
            )
            other_admin_user_ids = [
                row["user_id"] for row in _rows(admin_role_rows)
                if (row.get("roles") or {}).get("slug") == "admin"
            ]

            other_active_admins = 0
            if other_admin_user_ids:
                active_members = (
                    sb.table("organization_members")
                    .select("user_id")
                    .eq("organization_id", org_id)
                    .eq("status", "active")
                    .in_("user_id", other_admin_user_ids)
                    .execute()
                )
                other_active_admins = len(_rows(active_members))

            if other_active_admins == 0:
                return JSONResponse(
                    {"success": False, "error": {"code": "LAST_ADMIN", "message": "Cannot deactivate the last active administrator"}},
                    status_code=422,
                )

    try:
        if new_status == "suspended":
            # Ban the user in Supabase Auth (100 years = effectively permanent)
            sb.auth.admin.update_user_by_id(user_id, {"ban_duration": "876000h"})
        else:
            # Unban the user
            sb.auth.admin.update_user_by_id(user_id, {"ban_duration": "none"})

        # Update organization_members status
        sb.table("organization_members").update(
            {"status": new_status}
        ).eq("user_id", user_id).eq("organization_id", org_id).execute()

    except Exception as e:
        logger.error("Failed to update user status for %s: %s", user_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to update user status"}},
            status_code=500,
        )

    return JSONResponse(
        {"success": True, "data": {"user_id": user_id, "status": new_status}},
    )


async def update_user_roles(request, user_id: str) -> JSONResponse:
    """Atomically update user roles via Postgres function.

    Path: PATCH /api/admin/users/{user_id}/roles
    Params:
        role_slugs: list[str] (required) - New role set (replaces all current roles)
    Returns:
        user_id: str
        roles: list[str] - Applied role slugs
    Side Effects:
        - Calls kvota.update_user_roles() Postgres function
        - Atomic DELETE + INSERT in single transaction
    Roles: admin
    """
    admin_user, auth_err = _get_admin_user(request)
    if auth_err:
        return auth_err
    assert admin_user is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid JSON body"}},
            status_code=400,
        )

    role_slugs = body.get("role_slugs") or []
    if not role_slugs or not isinstance(role_slugs, list):
        return JSONResponse(
            {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "At least one role is required"}},
            status_code=400,
        )

    org_id = admin_user["org_id"]

    # Verify target user belongs to admin's org
    _, member_err = _verify_user_in_org(user_id, org_id)
    if member_err:
        return member_err

    sb = get_supabase()

    try:
        sb.rpc("update_user_roles", {
            "p_user_id": user_id,
            "p_org_id": org_id,
            "p_role_slugs": role_slugs,
        }).execute()
    except Exception as e:
        error_msg = str(e)
        if "last administrator" in error_msg.lower():
            return JSONResponse(
                {"success": False, "error": {"code": "LAST_ADMIN", "message": "Cannot remove admin role from the last administrator"}},
                status_code=422,
            )
        if "invalid role slugs" in error_msg.lower():
            return JSONResponse(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": error_msg}},
                status_code=400,
            )
        if "must not be empty" in error_msg.lower():
            return JSONResponse(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "At least one role is required"}},
                status_code=400,
            )
        logger.error("Failed to update roles for user %s: %s", user_id, e)
        return JSONResponse(
            {"success": False, "error": {"code": "SERVER_ERROR", "message": "Failed to update user roles"}},
            status_code=500,
        )

    return JSONResponse(
        {"success": True, "data": {"user_id": user_id, "roles": role_slugs}},
    )
