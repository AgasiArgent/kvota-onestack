"""FastHTML /admin cluster (Mega-E: 25 routes across user/feedback/brand/
procurement-group/impersonation admin surfaces) — archived 2026-04-20 during
Phase 6C-2B Mega-E. This is the FINAL FastHTML archive before the 6C-3 Docker
uvicorn switch — after this merges, main.py contains zero @rt routes and the
container will be flipped to uvicorn-only serving the FastAPI sub-app.

The /admin cluster hosts organization admin tooling — user listing + role
assignment, bug-feedback triage with ClickUp sync, brand→procurement-manager
assignment, sales-group→procurement-manager routing, and role impersonation
for admin/training_manager. All five areas are replaced by Next.js pages
reading `/api/admin/*`, `/api/feedback/*`, and related FastAPI routers.
Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru,
which doesn't proxy these paths back to this Python container. Preserved
here for reference / future copy-back.

Bundle rationale (Mega-E):
    All 25 routes share the /admin URL prefix and are gated by the same
    "admin" role check (with /admin/impersonate/*:exit also granting
    training_manager). They operate on org-scoped admin data (users,
    roles, brands, sales groups, feedback) and are logically one cluster.
    Co-archiving in a single PR reduces review overhead versus 5 sub-PRs.

Contents (25 @rt routes + 3 module-level constants, ~2,460 LOC total):

Area 1 — /admin + /admin/users redirect (2 routes):
  - GET  /admin/users                     — 303 redirect to /admin (legacy)
  - GET  /admin                           — Admin home: user list + role badges
                                            + Telegram status + action buttons
                                            to brands/procurement-groups pages

Area 2 — /admin/feedback cluster (4 routes):
  - GET    /admin/feedback                              — Feedback list with
                                                          status filter tabs +
                                                          ClickUp task column
  - POST   /admin/feedback/{short_id}/status            — HTMX status update
                                                          (calls ClickUp +
                                                          Telegram sync via
                                                          services.feedback_service.
                                                          update_feedback_status)
  - POST   /admin/feedback/{short_id}/sync-clickup      — HTMX pull of ClickUp
                                                          status → local DB
                                                          (one-way sync, uses
                                                          services.clickup_service.
                                                          get_clickup_task_status)
  - GET    /admin/feedback/{short_id}                   — Detail page with
                                                          screenshot, debug
                                                          context (console
                                                          errors + network
                                                          requests), status
                                                          form, ClickUp link

Area 3 — /admin/users/{user_id}/roles* cluster (5 routes):
  - GET  /admin/users/{user_id}/roles/edit              — HTMX: inline role
                                                          checkboxes form
                                                          (swapped into table
                                                          row)
  - POST /admin/users/{user_id}/roles/update            — HTMX: save roles,
                                                          return updated
                                                          badges (safety:
                                                          min 1 role; admin
                                                          cannot remove own
                                                          admin role)
  - GET  /admin/users/{user_id}/roles/cancel            — HTMX: revert to
                                                          display state (no
                                                          save)
  - GET  /admin/users/{user_id}/roles                   — Standalone page:
                                                          card-style role
                                                          picker with two-
                                                          column layout
                                                          (current roles +
                                                          selection form)
  - POST /admin/users/{user_id}/roles                   — Handle role update
                                                          from standalone page
                                                          (same safety checks
                                                          as HTMX endpoint)

Area 4 — /admin/brands cluster (6 routes):
  - GET  /admin/brands                                  — Registry: 4-card
                                                          stats grid +
                                                          unassigned-brands
                                                          section + current-
                                                          assignments table
  - GET  /admin/brands/new                              — Create form
                                                          (pre-fill brand
                                                          name via ?brand=
                                                          query param from
                                                          unassigned list)
  - POST /admin/brands/new                              — Insert new brand
                                                          assignment
  - GET  /admin/brands/{assignment_id}/edit             — Edit form (change
                                                          the assigned
                                                          procurement user)
  - POST /admin/brands/{assignment_id}/edit             — Update assignment
  - POST /admin/brands/{assignment_id}/delete           — Delete assignment

Area 5 — /admin/procurement-groups cluster (6 routes):
  - GET  /admin/procurement-groups                      — Registry: 4-card
                                                          stats grid +
                                                          unassigned-groups
                                                          section + current-
                                                          assignments table +
                                                          cascade-priority
                                                          help card
  - GET  /admin/procurement-groups/new                  — Create form
                                                          (pre-fill group_id
                                                          via ?group_id= from
                                                          unassigned list)
  - POST /admin/procurement-groups/new                  — Validate user_id
                                                          is procurement
                                                          role + insert new
                                                          assignment
  - GET  /admin/procurement-groups/{assignment_id}/edit — Edit form
  - POST /admin/procurement-groups/{assignment_id}/edit — Update assignment
                                                          (same user_id
                                                          validation)
  - POST /admin/procurement-groups/{assignment_id}/delete — Delete assignment

Area 6 — /admin/impersonate cluster (2 routes):
  - GET  /admin/impersonate                             — Set or clear
                                                          impersonated_role
                                                          in session (admin
                                                          OR training_manager;
                                                          role must be in
                                                          VALID_IMPERSONATION_ROLES
                                                          — operational roles
                                                          only, never admin
                                                          itself)
  - GET  /admin/impersonate/exit                        — Clear impersonation
                                                          (unconditional; no
                                                          role check because
                                                          the operation is
                                                          always safe)

Module-level constants archived alongside their callers (all exclusive to the
admin cluster, no external consumers in preserved main.py):
  - STATUS_LABELS           — dict: feedback status code → (label, badge-css)
                              used only by /admin/feedback list + detail +
                              status POST + sync POST
  - FEEDBACK_TYPE_LABELS_RU — dict: feedback type code → Russian label
                              used only by /admin/feedback list + detail
  - VALID_IMPERSONATION_ROLES — frozenset of operational roles allowed in
                                /admin/impersonate; critical security
                                invariant: must NOT contain "admin" or
                                "training_manager" (prevents privilege
                                escalation via direct URL access)

Preserved in main.py (consumed by /api/* FastAPI routers, middleware, or
remaining page-layout helpers):
  - ROLE_LABELS_RU (line 74) — used by sidebar + impersonation banner
                                (both alive)
  - require_login(session)    — used by preserved `@app.get /quotes/{id}/
                                cost-analysis` and future legacy fallback;
                                also imported back into archives for
                                recovery reference only
  - page_layout, icon, btn, btn_link, format_date_russian —
                                rendering helpers used by the preserved
                                cost-analysis route + potential future
                                surfaces; remain alive
  - get_supabase               — used by preserved cost-analysis + other
                                surfaces
  - get_user_role_codes (top-level import, line 37) — used by
                                user_has_any_role helper at main.py:4364
                                (alive) for role-check fallback
  - ANNOTATION_EDITOR_JS + feedback_modal() (main.py:3206, 3528) — frontend
                                screenshot annotation widget + bug-report
                                modal; remain alive (rendered on every page
                                via page_layout); consumed by POST
                                /api/feedback in FastAPI (alive)
  - Sidebar entry "Обращения" → /admin/feedback (main.py:2738) — dead link
                                post-archive; left intact, safe per Caddy
                                cutover plan
  - FastAPI sub-app mount at /api — unchanged by this archive; hosts
                                /api/admin/* router (api/routers/admin.py,
                                alive, covered by tests/test_api_routers_admin.py)

Preserved service layers (all alive):
  - services/role_service.py              — consumed by user_has_any_role +
                                             api/admin.py + other live surfaces
  - services/brand_service.py             — service file alive; no remaining
                                             main.py callers after archive
                                             (future: consumed by Next.js +
                                             /api/admin/brands post-cutover);
                                             covered by brand-service tests
  - services/route_procurement_assignment_service.py — same disposition as
                                             brand_service (alive, no main.py
                                             callers post-archive)
  - services/feedback_service.py          — consumed by api/feedback.py (alive)
  - services/clickup_service.py           — consumed by api/feedback.py +
                                             services/feedback_service.py
                                             (both alive)
  - services/user_profile_service.py      — consumed by services.user_service
                                             + api/profile.py (alive)

Service-import cleanup in main.py:
  - NONE. All service imports inside the archived handlers were inline
    `from services.X import ...` statements, so they go out with the
    archive body. The top-level `from services.role_service import
    get_user_role_codes` line stays (still consumed by user_has_any_role
    helper at main.py:4364). The top-level
    `from services.workflow_service import (...)` line stays (still consumed
    by preserved workflow_status_badge/quote_header helpers). No
    service-layer files are deleted; all remain alive for future use via
    FastAPI or Next.js.

Post-archive main.py surface:
  - Top imports + FastHTML app init + middleware registration (SessionMiddleware,
    Sentry, ApiAuthMiddleware)
  - Shared helpers/constants (ROLE_LABELS_RU, page_layout, icon, btn,
    btn_link, require_login, sidebar, etc.) — dead after admin archive
    but preserved for 6C-3 cleanup
  - Remaining business-logic helpers (build_calculation_inputs,
    quote_header, workflow_*, finance-tab helpers, etc.) consumed by
    api/quotes.py FastAPI handlers and preserved `@app.get /quotes/
    {id}/cost-analysis` route
  - Feedback modal + annotation editor JS (alive, consumed by /api/feedback)
  - `app.mount("/api", api_app)` at bottom
  - 0 @rt routes (zero — Mega-E is the last archive)

Known-dead-on-archive (not fixed; goes out with archive):
  - POST /admin/feedback/{short_id}/sync-clickup (line 6584 in main.py pre-
    archive) references `logger.error(...)` without an imported `logger`.
    This was a latent bug in the original handler — it would have raised
    NameError on any exception path. Preserved as-is in this archive; no
    value in fixing dead code. Future reimplementation via FastAPI should
    use `structlog`/`logging` module explicitly.

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore inline service imports, re-apply the @rt decorator. Not recommended
— rewrite via Next.js + FastAPI /api/admin/* instead.
"""
# flake8: noqa
# type: ignore

# Imports here mirror what main.py's archived handlers consumed. These are
# kept explicit (versus `from fasthtml.common import *`) because this file
# is NOT executed — it's a reference preserve. Each import names only what
# the archived handlers actually use, making the dependency surface clear
# for future copy-back.

from datetime import datetime
import json

from fasthtml.common import (
    A, Button, Div, Form, H1, H2, H4, I, Img, Input, Label, Option,
    P, Pre, Script, Select, Span, Table, Tbody, Td, Th, Thead, Tr,
)
from starlette.responses import RedirectResponse

# Service imports that the archived handlers do inline in the live code.
# Listed here so a reader of the archive can trace dependencies without
# opening main.py.
#
# from services.database import get_supabase
# from services.export_data_mapper import format_date_russian
# from services.role_service import (
#     get_all_roles, get_user_role_codes, get_users_by_role,
#     get_role_by_code, assign_role, remove_role,
# )
# from services.brand_service import (
#     get_all_brand_assignments, get_unique_brands_in_org,
#     count_assignments_by_user, get_brand_assignment,
#     get_brand_assignment_by_brand, create_brand_assignment,
#     update_brand_assignment, delete_brand_assignment,
# )
# from services.route_procurement_assignment_service import (
#     get_all_with_details, get_assignment, get_assignment_by_group,
#     create_assignment, update_assignment, delete_assignment,
# )
# from services.user_profile_service import (
#     get_sales_groups, get_organization_users,
# )
# from services.feedback_service import update_feedback_status
# from services.clickup_service import get_clickup_task_status


# These helpers are defined in main.py (preserved there) and would be
# imported at runtime if this archive were resurrected:
#   require_login, page_layout, icon, btn, btn_link


# ============================================================================
# ADMIN: USER MANAGEMENT
# Feature #84: Страница /admin/users
# ============================================================================

# @rt("/admin/users")
def get_admin_users_redirect(session):
    """Redirect old /admin/users to new /admin"""
    return RedirectResponse("/admin", status_code=303)


# @rt("/admin")
def get(session):
    """Admin page - user management.

    Feature #84: Страница /admin
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    # Only admins can access this page
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get all organization members with their roles and Telegram status
    members_result = supabase.table("organization_members").select(
        "user_id, status, created_at"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    members = members_result.data if members_result.data else []

    # Get all available roles for this organization (system roles + org-specific roles)
    from services.role_service import get_all_roles
    all_roles = get_all_roles(organization_id=org_id)

    # Build user data with roles
    users_data = []
    for member in members:
        member_user_id = member["user_id"]

        # Get user roles (DB uses 'slug', we call it 'code' in UI)
        user_roles_result = supabase.table("user_roles").select(
            "id, role_id, roles(slug, name)"
        ).eq("user_id", member_user_id).eq("organization_id", org_id).execute()

        member_roles = user_roles_result.data if user_roles_result.data else []
        role_codes = [(r.get("roles") or {}).get("slug", "") for r in member_roles if r.get("roles")]
        role_names = [(r.get("roles") or {}).get("name", "") for r in member_roles if r.get("roles")]

        # Get Telegram status
        tg_result = supabase.table("telegram_users").select(
            "telegram_id, telegram_username, verified_at"
        ).eq("user_id", member_user_id).limit(1).execute()

        tg_data = tg_result.data[0] if tg_result.data else None

        # Query user_profiles for full_name to display in the FIO column
        profile_result = supabase.table("user_profiles").select(
            "full_name"
        ).eq("user_id", member_user_id).limit(1).execute()

        profile_data = profile_result.data[0] if profile_result.data else None
        profile_full_name = profile_data.get("full_name") if profile_data else None

        # Use full_name from user_profiles, fall back to truncated UUID only if no profile
        email_display = profile_full_name if profile_full_name else (member_user_id[:8] + "...")

        users_data.append({
            "user_id": member_user_id,
            "email": email_display,
            "roles": role_codes,
            "role_names": role_names,
            "telegram": tg_data,
            "joined_at": format_date_russian(member["created_at"]) if member.get("created_at") else "-"
        })

    # Build users table rows
    user_rows = []
    for u in users_data:
        # Roles badges - using status-badge style
        role_badges = []
        for i, code in enumerate(u["roles"]):
            name = u["role_names"][i] if i < len(u["role_names"]) else code
            # Map roles to unified badge colors
            badge_class = {
                "admin": "status-error",
                "sales": "status-info",
                "procurement": "status-success",
                "logistics": "status-warning",
                "customs": "status-progress",
                "quote_controller": "status-new",
                "spec_controller": "status-info",
                "finance": "status-success",
                "top_manager": "status-warning",
                "head_of_sales": "status-info",
                "head_of_procurement": "status-success",
                "head_of_logistics": "status-warning",
                "training_manager": "status-neutral",
            }.get(code, "status-neutral")
            role_badges.append(
                Span(name, cls=f"status-badge {badge_class}", style="margin-right: 4px;")
            )

        # Telegram status
        if u["telegram"] and u["telegram"].get("verified_at"):
            tg_status = Span("✓ @" + (u["telegram"].get("username") or str(u["telegram"]["telegram_id"])),
                style="color: #10b981; font-size: 0.875rem;")
        else:
            tg_status = Span("—", style="color: #9ca3af;")

        # Make roles cell clickable for inline editing
        roles_cell = Td(
            Div(
                *role_badges if role_badges else [Span("—", style="color: #9ca3af;")],
                id=f"roles-display-{u['user_id']}",
                style="cursor: pointer;",
                hx_get=f"/admin/users/{u['user_id']}/roles/edit",
                hx_target=f"#roles-cell-{u['user_id']}",
                hx_swap="innerHTML",
                title="Кликните для редактирования ролей"
            ),
            id=f"roles-cell-{u['user_id']}"
        )

        user_rows.append(Tr(
            Td(u["email"]),
            roles_cell,
            Td(tg_status),
            Td(u["joined_at"])
        ))

    users_content = Div(
        # Stats
        Div(
            Div(
                Div(str(len(users_data)), cls="stat-value", style="color: #3b82f6;"),
                Div("Всего пользователей", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(sum(1 for u in users_data if u["telegram"])), cls="stat-value", style="color: #10b981;"),
                Div("С Telegram", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            Div(
                Div(str(len(all_roles)), cls="stat-value", style="color: #8b7cf6;"),
                Div("Доступных ролей", style="font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 16px;"
            ),
            style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px;"
        ),

        # Users table
        Div(
            Div(
                Div(H4("Пользователи организации", style="margin: 0;"), cls="table-header-left"),
                cls="table-header"
            ),
            Div(
                Table(
                    Thead(Tr(
                        Th("ФИО"),
                        Th("РОЛИ"),
                        Th("TELEGRAM"),
                        Th("ДАТА")
                    )),
                    Tbody(*user_rows) if user_rows else Tbody(Tr(Td("Нет пользователей", colspan="4", style="text-align: center; padding: 2rem; color: #9ca3af;"))),
                    cls="unified-table"
                ),
                cls="table-responsive"
            ),
            Div(Span(f"Всего: {len(users_data)} пользователей"), cls="table-footer"),
            cls="table-container", style="margin: 0;"
        ),

        # Navigation
        Div(
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            btn_link("Назначение брендов", href="/admin/brands", variant="secondary", icon_name="tag"),
            btn_link("Маршрутизация закупок", href="/admin/procurement-groups", variant="primary", icon_name="git-branch"),
            style="margin-top: 24px; display: flex; gap: 12px;"
        ),
    )

    # Design system styles for admin page
    header_card_style = """
        background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px 24px;
        margin-bottom: 20px;
    """

    return page_layout("Пользователи",
        # Header card with gradient
        Div(
            Div(
                icon("settings", size=24, color="#475569"),
                Span(" Пользователи", style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
                style="display: flex; align-items: center;"
            ),
            P("Управление пользователями и ролями",
              style="margin: 6px 0 0 0; font-size: 13px; color: #64748b;"),
            style=header_card_style
        ),

        # Users content (no tabs needed - only users here now)
        users_content,

        session=session
    )


# ============================================================================
# ADMIN FEEDBACK LIST - /admin/feedback
# ============================================================================

STATUS_LABELS = {
    "new": ("Новое", "status-error"),
    "in_progress": ("В работе", "status-warning"),
    "resolved": ("Решено", "status-success"),
    "closed": ("Закрыто", "status-neutral"),
}

FEEDBACK_TYPE_LABELS_RU = {
    "bug": "Ошибка",
    "ux_ui": "UX/UI",
    "suggestion": "Предложение",
    "question": "Вопрос",
}


# @rt("/admin/feedback")
def get(session, status_filter: str = ""):
    """Admin page - list all user feedback / bug reports."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if "admin" not in user.get("roles", []):
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            session=session
        )

    supabase = get_supabase()

    # Fetch list - deliberately exclude screenshot_data (potentially large)
    query = supabase.table("user_feedback").select(
        "id, short_id, user_name, user_email, organization_name, "
        "feedback_type, description, status, clickup_task_id, created_at, page_url"
    ).order("created_at", desc=True).limit(200)

    if status_filter:
        query = query.eq("status", status_filter)

    result = query.execute()
    items = result.data if result.data else []

    # Status filter tabs
    all_statuses = [("", "Все"), ("new", "Новые"), ("in_progress", "В работе"),
                    ("resolved", "Решено"), ("closed", "Закрыто")]
    filter_tabs = Div(
        *[
            A(label,
              href=f"/admin/feedback{'?status_filter=' + s if s else ''}",
              cls=f"tab-btn {'active' if status_filter == s else ''}")
            for s, label in all_statuses
        ],
        cls="tabs-nav", style="margin-bottom: 20px;"
    )

    # Table rows
    rows = []
    for item in items:
        status_label, status_cls = STATUS_LABELS.get(item.get("status", "new"), ("—", "status-neutral"))
        type_label = FEEDBACK_TYPE_LABELS_RU.get(item.get("feedback_type", ""), item.get("feedback_type", ""))
        desc_preview = (item.get("description") or "")[:80]
        if len(item.get("description") or "") > 80:
            desc_preview += "..."

        clickup_cell = Td("—")
        if item.get("clickup_task_id"):
            clickup_cell = Td(
                A(item["clickup_task_id"],
                  href=f"https://app.clickup.com/t/{item['clickup_task_id']}",
                  target="_blank",
                  style="font-size: 0.75rem; color: #6366f1;")
            )

        item_short_id = item.get("short_id", "—")
        rows.append(Tr(
            Td(A(item_short_id,
                 href=f"/admin/feedback/{item_short_id}",
                 style="font-weight: 600; font-family: monospace; color: #3b82f6;")),
            Td(Span(type_label, cls="status-badge status-neutral")),
            Td(desc_preview, style="max-width: 300px; font-size: 0.875rem;"),
            Td(item.get("user_name") or item.get("user_email") or "—", style="font-size: 0.875rem;"),
            Td(Span(status_label, cls=f"status-badge {status_cls}")),
            clickup_cell,
            Td(format_date_russian(item.get("created_at")) if item.get("created_at") else "—",
               style="font-size: 0.75rem; white-space: nowrap;"),
            cls="clickable-row",
            onclick=f"window.location='/admin/feedback/{item_short_id}'"
        ))

    table = Div(
        Div(
            Div(H4(f"Обращения ({len(items)})", style="margin: 0;"), cls="table-header-left"),
            cls="table-header"
        ),
        Div(
            Table(
                Thead(Tr(
                    Th("ID"), Th("Тип"), Th("Описание"), Th("Пользователь"),
                    Th("Статус"), Th("ClickUp"), Th("Дата")
                )),
                Tbody(*rows) if rows else Tbody(Tr(
                    Td("Нет обращений", colspan="7",
                       style="text-align: center; padding: 2rem; color: #9ca3af;")
                )),
                cls="unified-table"
            ),
            cls="table-responsive"
        ),
        cls="table-container", style="margin: 0;"
    )

    return page_layout("Обращения",
        Div(
            icon("message-square", size=24, color="#475569"),
            Span(" Обращения пользователей",
                 style="font-size: 20px; font-weight: 600; color: #1e293b; margin-left: 8px;"),
            style="display: flex; align-items: center; margin-bottom: 6px;"
        ),
        filter_tabs,
        table,
        Div(
            btn_link("Назад", href="/admin", variant="secondary", icon_name="arrow-left"),
            style="margin-top: 20px;"
        ),
        session=session,
        current_path="/admin/feedback"
    )


# @rt("/admin/feedback/{short_id}/status", methods=["POST"])
async def post_feedback_status(session, short_id: str, status: str = "new"):
    """HTMX endpoint to update feedback status. Syncs to ClickUp + Telegram."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if "admin" not in user.get("roles", []):
        return Div("Нет прав", cls="text-error")

    from services.feedback_service import update_feedback_status
    result = await update_feedback_status(short_id, status)

    if not result.success:
        return Div(f"Ошибка: {result.message}", cls="text-error text-sm")

    status_label, _ = STATUS_LABELS.get(status, ("—", ""))
    extras = []
    if result.clickup_synced:
        extras.append("ClickUp обновлён")
    if result.telegram_notified:
        extras.append("Telegram уведомлён")
    suffix = f" ({', '.join(extras)})" if extras else ""
    return Span(f"Сохранено: {status_label}{suffix}", cls="text-success text-sm")


# /api/internal/feedback/{short_id}/status was extracted to
# api/feedback.py::update_feedback_status in Phase 6B-8. The INTERNAL_API_KEY
# env var is still required in production — it is read there.


# @rt("/admin" + "/feedback/{short_id}/sync-clickup", methods=["POST"])
async def post_feedback_sync_clickup(session, short_id: str):
    """HTMX endpoint to pull ClickUp task status and update local feedback status."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if "admin" not in user.get("roles", []):
        return Div("Нет прав", cls="text-error")

    supabase = get_supabase()
    try:
        result = supabase.table("user_feedback").select("clickup_task_id, status").eq("short_id", short_id).limit(1).execute()
        if not result.data:
            return Span("Обращение не найдено", cls="text-error text-sm")

        task_id = (result.data[0] or {}).get("clickup_task_id")
        if not task_id:
            return Span("Нет привязки к ClickUp", cls="text-warning text-sm")

        from services.clickup_service import get_clickup_task_status
        new_admin_status = await get_clickup_task_status(task_id)
        if not new_admin_status:
            return Span("Не удалось получить статус из ClickUp", cls="text-error text-sm")

        current_status = result.data[0].get("status", "new")
        if new_admin_status == current_status:
            status_label, _ = STATUS_LABELS.get(current_status, ("—", ""))
            return Span(f"Статусы совпадают: {status_label}", cls="text-info text-sm")

        supabase.table("user_feedback").update({
            "status": new_admin_status,
            "updated_at": datetime.now().isoformat()
        }).eq("short_id", short_id).execute()

        old_label, _ = STATUS_LABELS.get(current_status, ("—", ""))
        new_label, _ = STATUS_LABELS.get(new_admin_status, ("—", ""))
        return Span(f"Синхронизировано: {old_label} → {new_label}", cls="text-success text-sm")
    except Exception as e:
        logger.error(f"ClickUp sync failed for {short_id}: {e}")
        return Span(f"Ошибка: {e}", cls="text-error text-sm")


# @rt("/admin/feedback/{short_id}")
def get(session, short_id: str):
    """Admin feedback detail page - shows full description, screenshot, context, status form."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    if "admin" not in user.get("roles", []):
        return page_layout("Доступ запрещён", H1("Доступ запрещён"), session=session)

    supabase = get_supabase()

    # Fetch full record including screenshot_data
    result = supabase.table("user_feedback").select("*").eq("short_id", short_id).limit(1).execute()
    if not result.data:
        return page_layout("Не найдено",
            H1("Обращение не найдено"),
            P(f"ID: {short_id}"),
            btn_link("К списку", href="/admin/feedback", variant="secondary"),
            session=session
        )

    item = result.data[0]

    status_label, status_cls = STATUS_LABELS.get(item.get("status", "new"), ("—", "status-neutral"))
    type_label = FEEDBACK_TYPE_LABELS_RU.get(item.get("feedback_type", ""), item.get("feedback_type", ""))

    # Screenshot display (prefer URL from Supabase Storage, fall back to base64)
    screenshot_section = None
    screenshot_url = item.get("screenshot_url")
    screenshot_b64 = item.get("screenshot_data")
    if screenshot_url:
        screenshot_section = Div(
            H4("Скриншот", style="margin-bottom: 8px; font-weight: 600;"),
            Img(
                src=screenshot_url,
                style="max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; max-height: 500px;"
            ),
            style="margin-bottom: 20px;"
        )
    elif screenshot_b64:
        screenshot_section = Div(
            H4("Скриншот", style="margin-bottom: 8px; font-weight: 600;"),
            Img(
                src=f"data:image/jpeg;base64,{screenshot_b64}",
                style="max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; max-height: 500px;"
            ),
            style="margin-bottom: 20px;"
        )

    # Debug context display
    context_section = None
    if item.get("debug_context"):
        ctx = item["debug_context"]
        if isinstance(ctx, str):
            try:
                ctx = json.loads(ctx)
            except Exception:
                ctx = {}
        ua = ctx.get("userAgent", "")
        browser = "Chrome" if "Chrome" in ua else "Firefox" if "Firefox" in ua else "Other"
        context_lines = [
            f"Browser: {browser}",
            f"Screen: {ctx.get('screenSize', '—')}",
            f"URL: {ctx.get('url', '—')}",
        ]
        errors = ctx.get("consoleErrors", [])
        if errors:
            context_lines.append(f"Console errors ({len(errors)}):")
            for err in errors:
                context_lines.append(f"  [{err.get('type', 'error')}] {str(err.get('message', ''))[:120]}")
        requests_data = ctx.get("recentRequests", [])
        if requests_data:
            context_lines.append(f"Recent requests ({len(requests_data)}):")
            for req in requests_data:
                status_code = req.get("status", "?")
                line = f"  {req.get('method', 'GET')} {req.get('url', '?')}: {status_code}"
                if isinstance(status_code, int) and status_code >= 400:
                    line += " [FAILED]"
                context_lines.append(line)

        context_section = Div(
            H4("Debug контекст", style="margin-bottom: 8px; font-weight: 600;"),
            Pre(
                "\n".join(context_lines),
                style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; font-size: 0.75rem; overflow-x: auto; white-space: pre-wrap;"
            ),
            style="margin-bottom: 20px;"
        )

    # Status update form (HTMX)
    status_form = Div(
        H4("Обновить статус", style="margin-bottom: 8px; font-weight: 600;"),
        Form(
            Select(
                Option("Новое", value="new", selected=(item.get("status") == "new")),
                Option("В работе", value="in_progress", selected=(item.get("status") == "in_progress")),
                Option("Решено", value="resolved", selected=(item.get("status") == "resolved")),
                Option("Закрыто", value="closed", selected=(item.get("status") == "closed")),
                name="status",
                cls="select select-bordered"
            ),
            Button("Сохранить", type="submit", cls="btn btn-sm btn-primary", style="margin-left: 8px;"),
            Div(id=f"status-result-{short_id}"),
            hx_post=f"/admin/feedback/{short_id}/status",
            hx_target=f"#status-result-{short_id}",
            hx_swap="innerHTML",
            style="display: flex; align-items: center; gap: 8px;"
        ),
        style="margin-bottom: 20px;"
    )

    # ClickUp link and sync button if available
    clickup_section = None
    if item.get("clickup_task_id"):
        clickup_section = Div(
            Div(
                A(
                    icon("external-link", size=14),
                    f" Открыть в ClickUp ({item['clickup_task_id']})",
                    href=f"https://app.clickup.com/t/{item['clickup_task_id']}",
                    target="_blank",
                    style="color: #6366f1; text-decoration: none; font-size: 0.875rem;"
                ),
                Button(
                    icon("refresh-cw", size=14),
                    " Синхронизировать из ClickUp",
                    hx_post=f"/admin/feedback/{short_id}/sync-clickup",
                    hx_target=f"#clickup-sync-result-{short_id}",
                    hx_swap="innerHTML",
                    cls="btn btn-sm btn-secondary",
                    style="margin-left: 12px; font-size: 0.75rem;"
                ),
                style="display: flex; align-items: center; gap: 8px;"
            ),
            Div(id=f"clickup-sync-result-{short_id}"),
            style="margin-bottom: 16px;"
        )

    content_parts = [
        Div(
            btn_link("К списку", href="/admin/feedback", variant="secondary", icon_name="arrow-left"),
            style="margin-bottom: 16px;"
        ),
        Div(
            Div(
                Span(type_label, cls="status-badge status-neutral", style="margin-right: 8px;"),
                Span(status_label, cls=f"status-badge {status_cls}"),
                style="margin-bottom: 8px;"
            ),
            H2(item.get("short_id", ""), style="font-family: monospace; margin-bottom: 4px;"),
            P(f"От: {item.get('user_name') or '—'} ({item.get('user_email') or '—'})",
              style="color: #64748b; font-size: 0.875rem; margin: 0;"),
            P(f"Организация: {item.get('organization_name') or '—'}",
              style="color: #64748b; font-size: 0.875rem; margin: 0;"),
            P(f"Страница: {item.get('page_url') or '—'}",
              style="color: #64748b; font-size: 0.875rem; margin: 4px 0 0 0;"),
            style="margin-bottom: 20px;"
        ),
        Div(
            H4("Описание", style="margin-bottom: 8px; font-weight: 600;"),
            P(item.get("description") or "—",
              style="background: #f8fafc; border-left: 3px solid #3b82f6; padding: 12px; border-radius: 0 6px 6px 0;"),
            style="margin-bottom: 20px;"
        ),
    ]
    if clickup_section:
        content_parts.append(clickup_section)
    content_parts.append(status_form)
    if screenshot_section:
        content_parts.append(screenshot_section)
    if context_section:
        content_parts.append(context_section)

    return page_layout(f"Обращение {short_id}",
        *content_parts,
        session=session,
        current_path="/admin/feedback"
    )


# @rt("/admin/users/{user_id}/roles/edit")
def get(user_id: str, session):
    """Inline role editor - returns form HTML fragment for HTMX."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])
    org_id = admin_user["org_id"]

    # Only admins can edit roles
    if "admin" not in roles:
        return Div("Нет прав", style="color: #ef4444;")

    supabase = get_supabase()
    from services.role_service import get_all_roles, get_user_role_codes

    # Get available roles for organization
    all_roles = get_all_roles(organization_id=org_id)

    # Get current user roles
    current_role_codes = get_user_role_codes(user_id, org_id)

    # Build checkboxes for each role
    role_checkboxes = []
    for role in all_roles:
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316",
            "head_of_sales": "#d97706",
            "head_of_procurement": "#ca8a04",
            "head_of_logistics": "#2563eb",
        }.get(role.code, "#6b7280")

        is_checked = role.code in current_role_codes

        role_checkboxes.append(
            Label(
                Input(
                    type="checkbox",
                    name="roles",
                    value=role.code,
                    checked=is_checked,
                    style="margin-right: 6px;"
                ),
                Span(role.name, style=f"background: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem;"),
                style="display: flex; align-items: center; gap: 4px; margin-bottom: 6px; cursor: pointer;"
            )
        )

    # Return inline form
    return Form(
        Div(
            *role_checkboxes,
            style="display: flex; flex-direction: column; background: #f9fafb; padding: 12px; border-radius: 8px; margin: 4px 0;"
        ),
        Div(
            btn("Сохранить", variant="primary", icon_name="check", type="submit", size="sm"),
            btn("Отмена", variant="ghost", size="sm", type="button",
                hx_get=f"/admin/users/{user_id}/roles/cancel",
                hx_target=f"#roles-cell-{user_id}",
                hx_swap="innerHTML"),
            style="display: flex; gap: 8px; margin-top: 8px;"
        ),
        hx_post=f"/admin/users/{user_id}/roles/update",
        hx_target=f"#roles-cell-{user_id}",
        hx_swap="innerHTML",
        style="margin: 0;"
    )


# @rt("/admin/users/{user_id}/roles/update")
def post(user_id: str, session, roles: list = None):
    """Update user roles inline - returns updated badges HTML fragment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    admin_roles = admin_user.get("roles", [])
    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    # Only admins can edit roles
    if "admin" not in admin_roles:
        return Div("Нет прав", style="color: #ef4444;")

    from services.role_service import (
        get_user_role_codes, assign_role, remove_role,
        get_all_roles, get_role_by_code
    )

    # Get current roles
    current_roles = get_user_role_codes(user_id, org_id)

    # Normalize input
    if roles is None:
        roles = []
    elif isinstance(roles, str):
        roles = [roles]

    # Safety: prevent empty roles (user must have at least 1 role)
    if not roles:
        return Div("Ошибка: нельзя убрать все роли. Выберите хотя бы одну.", style="color: #ef4444; padding: 8px; font-size: 0.875rem;")

    # Safety: prevent admin from removing admin role from themselves
    if user_id == admin_id and "admin" in current_roles and "admin" not in roles:
        return Div("Ошибка: нельзя снять роль admin с самого себя.", style="color: #ef4444; padding: 8px; font-size: 0.875rem;")

    # Determine which roles to add/remove
    roles_to_add = [r for r in roles if r not in current_roles]
    roles_to_remove = [r for r in current_roles if r not in roles]

    # Add new roles
    for role_code in roles_to_add:
        assign_role(user_id, org_id, role_code, admin_id)

    # Remove old roles
    for role_code in roles_to_remove:
        remove_role(user_id, org_id, role_code)

    # Get updated roles
    updated_role_codes = get_user_role_codes(user_id, org_id)

    # Build updated badges
    role_badges = []
    all_roles_dict = {r.code: r.name for r in get_all_roles(organization_id=org_id)}

    for code in updated_role_codes:
        name = all_roles_dict.get(code, code)
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316",
            "head_of_sales": "#d97706",
            "head_of_procurement": "#ca8a04",
            "head_of_logistics": "#2563eb",
        }.get(code, "#6b7280")

        role_badges.append(
            Span(name, style=f"background: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; margin-right: 4px;")
        )

    # Return updated display
    return Div(
        *role_badges if role_badges else [Span("—", style="color: #9ca3af;")],
        id=f"roles-display-{user_id}",
        style="cursor: pointer;",
        hx_get=f"/admin/users/{user_id}/roles/edit",
        hx_target=f"#roles-cell-{user_id}",
        hx_swap="innerHTML",
        title="Кликните для редактирования ролей"
    )


# @rt("/admin/users/{user_id}/roles/cancel")
def get(user_id: str, session):
    """Cancel inline editing - returns original badges HTML fragment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    org_id = admin_user["org_id"]

    from services.role_service import get_user_role_codes, get_all_roles

    # Get current roles
    role_codes = get_user_role_codes(user_id, org_id)

    # Build badges
    role_badges = []
    all_roles_dict = {r.code: r.name for r in get_all_roles(organization_id=org_id)}

    for code in role_codes:
        name = all_roles_dict.get(code, code)
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316",
            "head_of_sales": "#d97706",
            "head_of_procurement": "#ca8a04",
            "head_of_logistics": "#2563eb",
        }.get(code, "#6b7280")

        role_badges.append(
            Span(name, style=f"background: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; margin-right: 4px;")
        )

    # Return original display
    return Div(
        *role_badges if role_badges else [Span("—", style="color: #9ca3af;")],
        id=f"roles-display-{user_id}",
        style="cursor: pointer;",
        hx_get=f"/admin/users/{user_id}/roles/edit",
        hx_target=f"#roles-cell-{user_id}",
        hx_swap="innerHTML",
        title="Кликните для редактирования ролей"
    )


# @rt("/admin/users/{user_id}/roles")
def get(user_id: str, session):
    """Page to manage roles for a specific user.

    Shows all available roles and allows admin to toggle them on/off.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    # Only admins can access this page
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = admin_user["org_id"]

    # Get all available roles (filter by org to avoid showing irrelevant roles)
    from services.role_service import get_all_roles, get_user_role_codes
    all_roles = get_all_roles(organization_id=org_id)

    # Get current user roles
    current_roles = get_user_role_codes(user_id, org_id)

    # Build role checkboxes with modern card styling
    role_inputs = []
    for r in all_roles:
        checked = r.code in current_roles
        color = {
            "admin": "#ef4444",
            "sales": "#3b82f6",
            "procurement": "#10b981",
            "logistics": "#f59e0b",
            "customs": "#8b5cf6",
            "quote_controller": "#ec4899",
            "spec_controller": "#06b6d4",
            "finance": "#84cc16",
            "top_manager": "#f97316",
            "head_of_sales": "#d97706",
            "head_of_procurement": "#ca8a04",
            "head_of_logistics": "#2563eb",
        }.get(r.code, "#6b7280")

        card_bg = f"{color}10" if checked else "#f8fafc"
        card_border = color if checked else "#e2e8f0"

        role_inputs.append(
            Label(
                Div(
                    Div(
                        Input(type="checkbox", name="roles", value=r.code, checked=checked, style="width: 16px; height: 16px; accent-color: " + color + ";"),
                        style="margin-right: 12px; display: flex; align-items: center;"
                    ),
                    Div(
                        Div(
                            Span(r.name, style=f"color: {color}; font-weight: 600; font-size: 14px;"),
                            Span(f" ({r.code})", style="color: #94a3b8; font-size: 12px; margin-left: 4px;"),
                        ),
                        Span(r.description or "", style="color: #64748b; font-size: 12px; display: block; margin-top: 2px;") if r.description else None,
                        style="flex: 1;"
                    ),
                    style="display: flex; align-items: flex-start;"
                ),
                style=f"display: block; padding: 12px; margin-bottom: 8px; border-radius: 8px; cursor: pointer; background: {card_bg}; border: 1px solid {card_border};"
            )
        )

    return page_layout(f"Управление ролями",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К списку пользователей",
                href="/admin",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content
            Div(
                Div(
                    icon("shield", size=28, color="#6366f1"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Управление ролями", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    Span(f"ID: {user_id[:8]}...", style="color: #64748b; font-size: 13px;"),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Two-column layout
        Div(
            # Left column - Current roles
            Div(
                Div(
                    icon("user-check", size=14, color="#64748b"),
                    Span("ТЕКУЩИЕ РОЛИ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
                ),
                Div(
                    *[Span(code, style="display: inline-block; background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500; margin: 0 6px 6px 0;") for code in current_roles]
                    if current_roles else [Span("Нет назначенных ролей", style="color: #94a3b8; font-size: 14px;")]
                ),
                Div(
                    Span(f"{len(current_roles)} ", style="font-weight: 600; color: #1e293b;"),
                    Span("из ", style="color: #64748b;"),
                    Span(f"{len(all_roles)} ", style="font-weight: 600; color: #1e293b;"),
                    Span("ролей назначено", style="color: #64748b;"),
                    style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 13px;"
                ),
                style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            # Right column - Role selection form
            Form(
                Div(
                    icon("settings", size=14, color="#64748b"),
                    Span("ВЫБОР РОЛЕЙ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
                ),
                Div(
                    *role_inputs,
                    style="max-height: 400px; overflow-y: auto; padding-right: 8px;"
                ),
                Input(type="hidden", name="user_id", value=user_id),
                Div(
                    btn("Сохранить роли", variant="primary", icon_name="check", type="submit"),
                    style="margin-top: 20px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ),
                method="POST",
                action=f"/admin/users/{user_id}/roles",
                style="background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="display: grid; grid-template-columns: 1fr 2fr; gap: 20px;"
        ),

        session=session
    )


# @rt("/admin/users/{user_id}/roles")
def post(user_id: str, session, roles: list = None):
    """Handle role updates for a user.

    Compares submitted roles with current roles and adds/removes as needed.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    admin_roles = admin_user.get("roles", [])

    # Only admins can access this page
    if "admin" not in admin_roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    # Handle empty roles list (none selected)
    if roles is None:
        roles = []
    elif isinstance(roles, str):
        roles = [roles]

    # Get current user roles
    from services.role_service import get_user_role_codes, assign_role, remove_role
    current_roles = get_user_role_codes(user_id, org_id)

    # Safety: prevent empty roles (user must have at least 1 role)
    if not roles:
        return page_layout("Ошибка",
            H1("Ошибка обновления ролей"),
            P("Нельзя убрать все роли у пользователя. Выберите хотя бы одну роль."),
            btn_link("Назад", href=f"/admin/users/{user_id}/roles", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Safety: prevent admin from removing admin role from themselves
    if user_id == admin_id and "admin" in current_roles and "admin" not in roles:
        return page_layout("Ошибка",
            H1("Ошибка обновления ролей"),
            P("Нельзя снять роль admin с самого себя. Попросите другого администратора."),
            btn_link("Назад", href=f"/admin/users/{user_id}/roles", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    submitted_roles = set(roles)
    current_roles_set = set(current_roles)

    # Roles to add
    to_add = submitted_roles - current_roles_set
    for role_code in to_add:
        result = assign_role(user_id, org_id, role_code, admin_id)
        if result:
            print(f"Added role {role_code} to user {user_id}")

    # Roles to remove
    to_remove = current_roles_set - submitted_roles
    for role_code in to_remove:
        result = remove_role(user_id, org_id, role_code)
        if result:
            print(f"Removed role {role_code} from user {user_id}")

    # Success message
    return page_layout("Роли обновлены",
        H1("✓ Роли обновлены"),
        P(f"Пользователь: {user_id[:8]}..."),
        P(f"Добавлено ролей: {len(to_add)}" if to_add else ""),
        P(f"Удалено ролей: {len(to_remove)}" if to_remove else ""),
        Div(
            H4("Текущие роли:", style="margin-bottom: 8px;"),
            Div(
                *[Span(code, style="background: #10b981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.875rem; margin-right: 4px;") for code in sorted(submitted_roles)]
                if submitted_roles else [Span("Нет ролей", style="color: #9ca3af;")]
            ),
            style="background: #f0fdf4; padding: 12px; border-radius: 8px; margin-top: 16px;"
        ),
        Div(
            btn_link("Назад к списку", href="/admin/users", variant="secondary", icon_name="arrow-left"),
            style="margin-top: 24px;"
        ),
        session=session
    )


# ============================================================================
# ADMIN: BRAND MANAGEMENT
# Feature #85: Страница /admin/brands
# ============================================================================

# @rt("/admin/brands")
def get(session):
    """Admin page for brand assignments.

    Feature #85: Страница /admin/brands

    This page allows admins to:
    - View all brand assignments (brand → procurement manager)
    - Import new brands from existing quotes
    - Assign/reassign brands to procurement managers
    - Delete brand assignments
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    # Only admins can access this page
    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Import brand service functions
    from services.brand_service import (
        get_all_brand_assignments,
        get_unique_brands_in_org,
        count_assignments_by_user
    )

    # Get all current brand assignments
    assignments = get_all_brand_assignments(org_id)

    # Get unique brands from quote_items in this organization
    # This is for "import from quotes" functionality
    quote_items_result = supabase.table("quote_items").select(
        "brand, quotes!inner(organization_id)"
    ).eq("quotes.organization_id", org_id).execute()

    all_quote_brands = set()
    for item in (quote_items_result.data or []):
        if item.get("brand"):
            all_quote_brands.add(item["brand"])

    # Get already assigned brands
    assigned_brands = set(a.brand.lower() for a in assignments)

    # Find unassigned brands
    unassigned_brands = [b for b in sorted(all_quote_brands) if b.lower() not in assigned_brands]

    # Get procurement users for assignments
    from services.role_service import get_user_role_codes

    # Get all active organization members
    members_result = supabase.table("organization_members").select(
        "user_id"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    # Filter to only users who have the procurement role
    procurement_users = []
    for member in (members_result.data or []):
        user_id = member["user_id"]
        user_roles = get_user_role_codes(user_id, org_id)
        if "procurement" in user_roles:
            procurement_users.append(user_id)

    # Get assignment counts per user
    assignment_counts = count_assignments_by_user(org_id)

    # Build assignment table rows
    assignment_rows = []
    for a in assignments:
        # Get user display (shortened ID)
        user_display = a.user_id[:8] + "..."
        brand_count = assignment_counts.get(a.user_id, 0)

        assignment_rows.append(Tr(
            Td(Span(a.brand, style="font-weight: 600;")),
            Td(user_display),
            Td(str(brand_count)),
            Td(a.created_at.strftime("%Y-%m-%d") if a.created_at else "-"),
            Td(
                Div(
                    btn_link("Изменить", href=f"/admin/brands/{a.id}/edit", variant="secondary", size="sm"),
                    Form(
                        btn("Удалить", variant="danger", size="sm", type="submit"),
                        method="POST",
                        action=f"/admin/brands/{a.id}/delete",
                        style="display: inline;"
                    ),
                    style="display: flex; align-items: center; gap: 0.5rem;"
                )
            )
        ))

    # Build unassigned brands list with modern styling
    unassigned_items = []
    for brand in unassigned_brands:
        unassigned_items.append(
            Div(
                Span(brand, style="font-weight: 600; color: #1e293b; margin-right: 12px;"),
                btn_link("Назначить", href=f"/admin/brands/new?brand={brand}", variant="secondary", size="sm"),
                style="display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; margin-bottom: 6px; background: white; border-radius: 8px; border: 1px solid #e2e8f0;"
            )
        )

    # Table styles
    th_style = "padding: 12px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
    td_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    return page_layout("Управление брендами",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К администрированию",
                href="/admin",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content with action button
            Div(
                Div(
                    Div(
                        icon("tag", size=28, color="#8b5cf6"),
                        style="width: 48px; height: 48px; background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                    ),
                    Div(
                        H1("Управление брендами", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        P("Назначение брендов менеджерам по закупкам", style="margin: 0; color: #64748b; font-size: 14px;"),
                        style="flex: 1;"
                    ),
                    style="display: flex; align-items: center; flex: 1;"
                ),
                btn_link("Добавить назначение", href="/admin/brands/new", variant="success", icon_name="plus"),
                style="display: flex; align-items: center; justify-content: space-between;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Stats grid
        Div(
            Div(
                Span(str(len(assignments)), style="font-size: 28px; font-weight: 700; color: #10b981; display: block;"),
                Span("Назначено брендов", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(unassigned_brands)), style="font-size: 28px; font-weight: 700; color: #f59e0b; display: block;"),
                Span("Без назначения", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(procurement_users)), style="font-size: 28px; font-weight: 700; color: #3b82f6; display: block;"),
                Span("Менеджеров закупок", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(all_quote_brands)), style="font-size: 28px; font-weight: 700; color: #8b5cf6; display: block;"),
                Span("Всего брендов в КП", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px;"
        ),

        # Unassigned brands section
        Div(
            Div(
                icon("alert-circle", size=14, color="#d97706"),
                Span("БРЕНДЫ БЕЗ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #d97706; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center;"
            ),
            Div(
                *unassigned_items if unassigned_items else [
                    Div(
                        icon("check-circle", size=16, color="#10b981"),
                        Span(" Все бренды из КП назначены менеджерам", style="color: #10b981; font-size: 14px; margin-left: 8px;"),
                        style="display: flex; align-items: center;"
                    )
                ],
                style="max-height: 200px; overflow-y: auto;"
            ),
            style=f"background: {'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)' if unassigned_items else 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)'}; border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; border: 1px solid {'#fcd34d' if unassigned_items else '#86efac'};"
        ) if all_quote_brands else None,

        # Current assignments table section
        Div(
            Div(
                icon("list", size=14, color="#64748b"),
                Span("ТЕКУЩИЕ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
            ),
            Div(
                Table(
                    Thead(Tr(
                        Th("Бренд", style=th_style),
                        Th("Менеджер", style=th_style),
                        Th("Всего брендов", style=th_style),
                        Th("Дата назначения", style=th_style),
                        Th("Действия", style=th_style)
                    )),
                    Tbody(*[Tr(
                        Td(Span(a.brand, style="font-weight: 600; color: #8b5cf6;"), style=td_style),
                        Td(a.user_id[:8] + "...", style=td_style),
                        Td(str(assignment_counts.get(a.user_id, 0)), style=td_style),
                        Td(a.created_at.strftime("%Y-%m-%d") if a.created_at else "-", style=td_style),
                        Td(
                            Div(
                                btn_link("Изменить", href=f"/admin/brands/{a.id}/edit", variant="secondary", size="sm"),
                                Form(
                                    btn("Удалить", variant="danger", size="sm", type="submit"),
                                    method="POST",
                                    action=f"/admin/brands/{a.id}/delete",
                                    style="display: inline;"
                                ),
                                style="display: flex; align-items: center; gap: 8px;"
                            ),
                            style=td_style
                        )
                    ) for a in assignments]) if assignment_rows else Tbody(
                        Tr(Td(
                            Div(
                                icon("inbox", size=32, color="#94a3b8"),
                                P("Нет назначений", style="color: #64748b; margin: 8px 0 0 0;"),
                                style="text-align: center; padding: 32px;"
                            ),
                            colspan="5"
                        ))
                    ),
                    style="width: 100%; border-collapse: collapse;"
                ),
                style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
        ),

        session=session
    )


# @rt("/admin/brands/new")
def get(session, brand: str = None):
    """Form to create new brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get procurement users
    # First get all active organization members
    members_result = supabase.table("organization_members").select(
        "user_id"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    # Filter to only users who have the procurement role
    from services.role_service import get_user_role_codes
    procurement_users = []
    for member in (members_result.data or []):
        user_id = member["user_id"]
        user_roles = get_user_role_codes(user_id, org_id)
        if "procurement" in user_roles:
            procurement_users.append({
                "user_id": user_id,
                "display": user_id[:8] + "..."
            })

    # Build user options
    user_options = [
        Option(u["display"], value=u["user_id"])
        for u in procurement_users
    ]

    # Form input styles
    input_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"

    return page_layout("Новое назначение бренда",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К списку брендов",
                href="/admin/brands",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content
            Div(
                Div(
                    icon("plus-circle", size=28, color="#10b981"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Новое назначение бренда", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    P("Назначьте бренд менеджеру по закупкам", style="margin: 0; color: #64748b; font-size: 14px;"),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Form card
        Div(
            Form(
                Div(
                    icon("tag", size=14, color="#64748b"),
                    Span("ДАННЫЕ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center;"
                ),

                # Brand name
                Div(
                    Label("Название бренда *", fr="brand", style=label_style),
                    Input(type="text", name="brand", id="brand", value=brand or "", required=True,
                          placeholder="Например: BOSCH", style=input_style),
                    style="margin-bottom: 16px;"
                ),

                # Manager select
                Div(
                    Label("Менеджер по закупкам *", fr="user_id", style=label_style),
                    Select(
                        Option("— Выберите менеджера —", value="", disabled=True, selected=True),
                        *user_options,
                        name="user_id",
                        id="user_id",
                        required=True,
                        style=select_style
                    ) if user_options else Div(
                        Div(
                            icon("alert-triangle", size=16, color="#ef4444"),
                            Span(" Нет пользователей с ролью 'procurement'", style="color: #ef4444; font-size: 14px; margin-left: 8px;"),
                            style="display: flex; align-items: center; margin-bottom: 8px;"
                        ),
                        P("Сначала назначьте роль менеджера по закупкам на ",
                          A("странице пользователей", href="/admin", style="color: #3b82f6; text-decoration: underline;"), ".",
                          style="color: #64748b; font-size: 13px; margin: 0;"),
                        style="padding: 16px; background: #fef2f2; border-radius: 8px; border: 1px solid #fecaca;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Submit button
                Div(
                    btn("Создать назначение", variant="success", icon_name="plus", type="submit"),
                    btn_link("Отмена", href="/admin/brands", variant="secondary"),
                    style="display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ) if user_options else None,

                method="POST",
                action="/admin/brands/new"
            ),
            style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; max-width: 500px;"
        ),

        session=session
    )


# @rt("/admin/brands/new")
def post(session, brand: str, user_id: str):
    """Create new brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    from services.brand_service import create_brand_assignment, get_brand_assignment_by_brand

    # Check if brand is already assigned
    existing = get_brand_assignment_by_brand(org_id, brand)
    if existing:
        return page_layout("Ошибка",
            H1(icon("alert-triangle", size=28), " Бренд уже назначен", cls="page-header"),
            P(f"Бренд '{brand}' уже назначен другому менеджеру."),
            P("Используйте функцию редактирования для изменения назначения."),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Create the assignment
    result = create_brand_assignment(
        organization_id=org_id,
        brand=brand.strip(),
        user_id=user_id,
        created_by=admin_id
    )

    if result:
        return page_layout("Назначение создано",
            H1("✓ Назначение создано"),
            P(f"Бренд '{brand}' успешно назначен менеджеру."),
            Div(
                Span(brand, style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;"),
                Span(" → ", style="margin: 0 8px;"),
                Span(user_id[:8] + "...", style="color: #6b7280;"),
                style="margin: 16px 0;"
            ),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка создания", cls="page-header"),
            P("Не удалось создать назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# @rt("/admin/brands/{assignment_id}/edit")
def get(assignment_id: str, session):
    """Edit form for brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.brand_service import get_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    if not assignment:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    supabase = get_supabase()
    org_id = user["org_id"]

    # Get procurement users
    from services.role_service import get_user_role_codes

    # Get all active organization members
    members_result = supabase.table("organization_members").select(
        "user_id"
    ).eq("organization_id", org_id).eq("status", "active").execute()

    # Filter to only users who have the procurement role
    procurement_users = []
    for member in (members_result.data or []):
        user_id = member["user_id"]
        user_roles = get_user_role_codes(user_id, org_id)
        if "procurement" in user_roles:
            procurement_users.append({
                "user_id": user_id,
                "display": user_id[:8] + "..."
            })

    # Build user options
    user_options = [
        Option(u["display"], value=u["user_id"], selected=(u["user_id"] == assignment.user_id))
        for u in procurement_users
    ]

    # Form input styles
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"

    return page_layout("Редактирование назначения",
        # Modern gradient header card
        Div(
            # Back link
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К списку брендов",
                href="/admin/brands",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            # Header content
            Div(
                Div(
                    icon("edit-3", size=28, color="#f59e0b"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Редактирование назначения", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    Div(
                        Span("Бренд: ", style="color: #64748b; font-size: 14px;"),
                        Span(assignment.brand, style="color: #8b5cf6; font-size: 14px; font-weight: 600;"),
                    ),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Form card
        Div(
            Form(
                Div(
                    icon("user", size=14, color="#64748b"),
                    Span("ИЗМЕНИТЬ МЕНЕДЖЕРА", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center;"
                ),

                Input(type="hidden", name="brand", value=assignment.brand),

                # Current assignment info
                Div(
                    Span("Текущий менеджер: ", style="color: #64748b; font-size: 13px;"),
                    Span(assignment.user_id[:8] + "...", style="color: #1e293b; font-weight: 500; font-size: 13px;"),
                    style="padding: 12px; background: #f8fafc; border-radius: 8px; margin-bottom: 16px;"
                ),

                # Manager select
                Div(
                    Label("Новый менеджер по закупкам *", fr="user_id", style=label_style),
                    Select(
                        *user_options,
                        name="user_id",
                        id="user_id",
                        required=True,
                        style=select_style
                    ) if user_options else P("Нет менеджеров с ролью procurement", style="color: #ef4444; font-size: 14px;"),
                    style="margin-bottom: 20px;"
                ),

                # Submit button
                Div(
                    btn("Сохранить изменения", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href="/admin/brands", variant="secondary"),
                    style="display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ) if user_options else None,

                method="POST",
                action=f"/admin/brands/{assignment_id}/edit"
            ),
            style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; max-width: 500px;"
        ),

        session=session
    )


# @rt("/admin/brands/{assignment_id}/edit")
def post(assignment_id: str, session, user_id: str, brand: str = None):
    """Update brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.brand_service import update_brand_assignment, get_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    if not assignment:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Update the assignment
    result = update_brand_assignment(assignment_id, user_id)

    if result:
        return page_layout("Назначение обновлено",
            H1("✓ Назначение обновлено"),
            P(f"Бренд '{assignment.brand}' переназначен новому менеджеру."),
            Div(
                Span(assignment.brand, style="background: #10b981; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;"),
                Span(" → ", style="margin: 0 8px;"),
                Span(user_id[:8] + "...", style="color: #6b7280;"),
                style="margin: 16px 0;"
            ),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка обновления", cls="page-header"),
            P("Не удалось обновить назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# @rt("/admin/brands/{assignment_id}/delete")
def post(assignment_id: str, session):
    """Delete brand assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.brand_service import get_brand_assignment, delete_brand_assignment

    assignment = get_brand_assignment(assignment_id)
    brand_name = assignment.brand if assignment else "Unknown"

    result = delete_brand_assignment(assignment_id)

    if result:
        return page_layout("Назначение удалено",
            H1("✓ Назначение удалено"),
            P(f"Бренд '{brand_name}' больше не назначен менеджеру."),
            P("Бренд вернулся в список неназначенных.", style="color: #6b7280;"),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка удаления", cls="page-header"),
            P("Не удалось удалить назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/brands", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# ============================================================================
# ADMIN: PROCUREMENT GROUP ROUTING
# Маршрутизация закупок: группа продаж → менеджер по закупкам
# ============================================================================

# @rt("/admin/procurement-groups")
def get(session):
    """Admin page for procurement group routing assignments.

    Maps sales groups to procurement users. When a quote is created by a
    sales manager in a sales group, all items are routed to the assigned
    procurement user.
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = user["org_id"]

    from services.route_procurement_assignment_service import get_all_with_details
    from services.user_profile_service import get_sales_groups, get_organization_users
    from services.role_service import get_users_by_role

    # Get all assignments with joined group names
    assignments_with_details = get_all_with_details(org_id)

    # Get all sales groups
    all_groups = get_sales_groups(org_id)

    # Get all org users for display names
    org_users = get_organization_users(org_id)
    user_name_map = {u["id"]: u.get("full_name") or u.get("email", u["id"][:8] + "...") for u in org_users}

    # Find assigned group IDs
    assigned_group_ids = set(a["sales_group_id"] for a in assignments_with_details)

    # Find unassigned groups
    unassigned_groups = [g for g in all_groups if g["id"] not in assigned_group_ids]

    # Count procurement users (single query via role_service)
    procurement_role_users = get_users_by_role(org_id, "procurement")
    procurement_user_count = len(procurement_role_users)

    # Table styles
    th_style = "padding: 12px 16px; text-align: left; font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; background: #f8fafc; border-bottom: 2px solid #e2e8f0;"
    td_style = "padding: 12px 16px; font-size: 14px; color: #1e293b; border-bottom: 1px solid #f1f5f9;"

    # Build assignment table rows
    assignment_rows = []
    for a in assignments_with_details:
        user_display = user_name_map.get(a["user_id"], a["user_id"][:8] + "...")
        group_name = a.get("sales_group_name") or a["sales_group_id"][:8] + "..."
        created_at = ""
        if a.get("created_at"):
            try:
                dt = datetime.fromisoformat(a["created_at"].replace("Z", "+00:00"))
                created_at = dt.strftime("%Y-%m-%d")
            except Exception:
                created_at = str(a["created_at"])[:10]

        assignment_rows.append(Tr(
            Td(Span(group_name, style="font-weight: 600; color: #3b82f6;"), style=td_style),
            Td(user_display, style=td_style),
            Td(created_at or "-", style=td_style),
            Td(
                Div(
                    btn_link("Изменить", href=f"/admin/procurement-groups/{a['id']}/edit", variant="secondary", size="sm"),
                    Form(
                        btn("Удалить", variant="danger", size="sm", type="submit"),
                        method="POST",
                        action=f"/admin/procurement-groups/{a['id']}/delete",
                        style="display: inline;"
                    ),
                    style="display: flex; align-items: center; gap: 8px;"
                ),
                style=td_style
            )
        ))

    # Build unassigned groups list
    unassigned_items = []
    for group in unassigned_groups:
        unassigned_items.append(
            Div(
                Span(group["name"], style="font-weight: 600; color: #1e293b; margin-right: 12px;"),
                btn_link("Назначить", href=f"/admin/procurement-groups/new?group_id={group['id']}", variant="secondary", size="sm"),
                style="display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; margin-bottom: 6px; background: white; border-radius: 8px; border: 1px solid #e2e8f0;"
            )
        )

    return page_layout("Маршрутизация закупок",
        # Header card
        Div(
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К администрированию",
                href="/admin",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    Div(
                        icon("git-branch", size=28, color="#3b82f6"),
                        style="width: 48px; height: 48px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                    ),
                    Div(
                        H1("Маршрутизация закупок", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                        P("Назначение групп продаж менеджерам по закупкам", style="margin: 0; color: #64748b; font-size: 14px;"),
                        style="flex: 1;"
                    ),
                    style="display: flex; align-items: center; flex: 1;"
                ),
                btn_link("Добавить назначение", href="/admin/procurement-groups/new", variant="success", icon_name="plus"),
                style="display: flex; align-items: center; justify-content: space-between;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Stats grid
        Div(
            Div(
                Span(str(len(assignments_with_details)), style="font-size: 28px; font-weight: 700; color: #10b981; display: block;"),
                Span("Назначено групп", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(unassigned_groups)), style="font-size: 28px; font-weight: 700; color: #f59e0b; display: block;"),
                Span("Без назначения", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(procurement_user_count), style="font-size: 28px; font-weight: 700; color: #3b82f6; display: block;"),
                Span("Менеджеров закупок", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            Div(
                Span(str(len(all_groups)), style="font-size: 28px; font-weight: 700; color: #8b5cf6; display: block;"),
                Span("Всего групп продаж", style="font-size: 12px; color: #64748b;"),
                style="text-align: center; padding: 20px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
            style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px;"
        ),

        # Unassigned groups section
        Div(
            Div(
                icon("alert-circle", size=14, color="#d97706"),
                Span("ГРУППЫ БЕЗ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #d97706; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center;"
            ),
            Div(
                *unassigned_items if unassigned_items else [
                    Div(
                        icon("check-circle", size=16, color="#10b981"),
                        Span(" Все группы продаж назначены менеджерам", style="color: #10b981; font-size: 14px; margin-left: 8px;"),
                        style="display: flex; align-items: center;"
                    )
                ],
                style="max-height: 200px; overflow-y: auto;"
            ),
            style=f"background: {'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)' if unassigned_items else 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)'}; border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; border: 1px solid {'#fcd34d' if unassigned_items else '#86efac'};"
        ) if all_groups else None,

        # Current assignments table
        Div(
            Div(
                icon("list", size=14, color="#64748b"),
                Span("ТЕКУЩИЕ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 16px; display: flex; align-items: center;"
            ),
            Div(
                Table(
                    Thead(Tr(
                        Th("Группа продаж", style=th_style),
                        Th("Менеджер по закупкам", style=th_style),
                        Th("Дата назначения", style=th_style),
                        Th("Действия", style=th_style)
                    )),
                    Tbody(*assignment_rows) if assignment_rows else Tbody(
                        Tr(Td(
                            Div(
                                icon("inbox", size=32, color="#94a3b8"),
                                P("Нет назначений", style="color: #64748b; margin: 8px 0 0 0;"),
                                style="text-align: center; padding: 32px;"
                            ),
                            colspan="4"
                        ))
                    ),
                    style="width: 100%; border-collapse: collapse;"
                ),
                style="background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0;"
            ),
        ),

        # Help card: cascade priority
        Div(
            Div(
                icon("info", size=14, color="#3b82f6"),
                Span("КАК РАБОТАЕТ МАРШРУТИЗАЦИЯ", style="margin-left: 6px;"),
                style="font-size: 11px; font-weight: 600; color: #3b82f6; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 12px; display: flex; align-items: center;"
            ),
            Div(
                P("1. Группа продаж (высший приоритет) - если менеджер продаж состоит в группе, все позиции КП направляются назначенному закупщику", style="margin: 0 0 8px 0; font-size: 13px; color: #475569;"),
                P("2. Бренд (запасной вариант) - если нет назначения по группе, позиции направляются по назначению брендов", style="margin: 0 0 8px 0; font-size: 13px; color: #475569;"),
                P("3. ПХМБ-КП исключены из маршрутизации", style="margin: 0; font-size: 13px; color: #94a3b8;"),
            ),
            style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 12px; padding: 16px 20px; margin-top: 24px; border: 1px solid #93c5fd;"
        ),

        session=session
    )


# @rt("/admin/procurement-groups/new")
def get(session, group_id: str = None):
    """Form to create new procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = user["org_id"]
    from services.user_profile_service import get_sales_groups, get_organization_users
    from services.role_service import get_users_by_role

    # Get all sales groups
    all_groups = get_sales_groups(org_id)

    # Build group options
    group_options = [
        Option(g["name"], value=g["id"], selected=(g["id"] == group_id))
        for g in all_groups
    ]

    # Get procurement users (single query via role_service)
    org_users = get_organization_users(org_id)
    user_name_map = {u["id"]: u.get("full_name") or u.get("email", u["id"][:8] + "...") for u in org_users}

    procurement_role_users = get_users_by_role(org_id, "procurement")
    procurement_users = [
        {"user_id": u["user_id"], "display": user_name_map.get(u["user_id"], u["user_id"][:8] + "...")}
        for u in procurement_role_users
    ]

    # Build user options
    user_options = [
        Option(u["display"], value=u["user_id"])
        for u in procurement_users
    ]

    # Form styles
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"

    return page_layout("Новое назначение группы",
        # Header card
        Div(
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К маршрутизации закупок",
                href="/admin/procurement-groups",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    icon("plus-circle", size=28, color="#10b981"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Новое назначение", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    P("Назначьте группу продаж менеджеру по закупкам", style="margin: 0; color: #64748b; font-size: 14px;"),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Form card
        Div(
            Form(
                Div(
                    icon("git-branch", size=14, color="#64748b"),
                    Span("ДАННЫЕ НАЗНАЧЕНИЯ", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center;"
                ),

                # Sales group select
                Div(
                    Label("Группа продаж *", fr="sales_group_id", style=label_style),
                    Select(
                        Option("-- Выберите группу --", value="", disabled=True, selected=(not group_id)),
                        *group_options,
                        name="sales_group_id",
                        id="sales_group_id",
                        required=True,
                        style=select_style
                    ) if group_options else Div(
                        Div(
                            icon("alert-triangle", size=16, color="#ef4444"),
                            Span(" Нет групп продаж", style="color: #ef4444; font-size: 14px; margin-left: 8px;"),
                            style="display: flex; align-items: center; margin-bottom: 8px;"
                        ),
                        P("Сначала создайте группы продаж в настройках.", style="color: #64748b; font-size: 13px; margin: 0;"),
                        style="padding: 16px; background: #fef2f2; border-radius: 8px; border: 1px solid #fecaca;"
                    ),
                    style="margin-bottom: 16px;"
                ),

                # Procurement user select
                Div(
                    Label("Менеджер по закупкам *", fr="user_id", style=label_style),
                    Select(
                        Option("-- Выберите менеджера --", value="", disabled=True, selected=True),
                        *user_options,
                        name="user_id",
                        id="user_id",
                        required=True,
                        style=select_style
                    ) if user_options else Div(
                        Div(
                            icon("alert-triangle", size=16, color="#ef4444"),
                            Span(" Нет пользователей с ролью 'procurement'", style="color: #ef4444; font-size: 14px; margin-left: 8px;"),
                            style="display: flex; align-items: center; margin-bottom: 8px;"
                        ),
                        P("Сначала назначьте роль менеджера по закупкам на ",
                          A("странице пользователей", href="/admin", style="color: #3b82f6; text-decoration: underline;"), ".",
                          style="color: #64748b; font-size: 13px; margin: 0;"),
                        style="padding: 16px; background: #fef2f2; border-radius: 8px; border: 1px solid #fecaca;"
                    ),
                    style="margin-bottom: 20px;"
                ),

                # Submit button
                Div(
                    btn("Создать назначение", variant="success", icon_name="plus", type="submit"),
                    btn_link("Отмена", href="/admin/procurement-groups", variant="secondary"),
                    style="display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ) if (group_options and user_options) else None,

                method="POST",
                action="/admin/procurement-groups/new"
            ),
            style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; max-width: 500px;"
        ),

        session=session
    )


# @rt("/admin/procurement-groups/new")
def post(session, sales_group_id: str, user_id: str):
    """Create new procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    org_id = admin_user["org_id"]
    admin_id = admin_user["id"]

    from services.route_procurement_assignment_service import create_assignment, get_assignment_by_group
    from services.role_service import get_users_by_role

    # Validate user_id belongs to this org's procurement users
    valid_user_ids = {u["user_id"] for u in get_users_by_role(org_id, "procurement")}
    if user_id not in valid_user_ids:
        return page_layout("Ошибка",
            H1(icon("alert-triangle", size=28), " Недопустимый пользователь", cls="page-header"),
            P("Выбранный пользователь не является менеджером по закупкам в вашей организации."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Check if group is already assigned
    existing = get_assignment_by_group(org_id, sales_group_id)
    if existing:
        return page_layout("Ошибка",
            H1(icon("alert-triangle", size=28), " Группа уже назначена", cls="page-header"),
            P("Эта группа продаж уже назначена менеджеру по закупкам."),
            P("Используйте функцию редактирования для изменения назначения."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Create the assignment
    result = create_assignment(
        organization_id=org_id,
        sales_group_id=sales_group_id,
        user_id=user_id,
        created_by=admin_id
    )

    if result:
        return RedirectResponse(url="/admin/procurement-groups", status_code=303)
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка создания", cls="page-header"),
            P("Не удалось создать назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# @rt("/admin/procurement-groups/{assignment_id}/edit")
def get(assignment_id: str, session):
    """Edit form for procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    roles = user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.route_procurement_assignment_service import get_assignment
    from services.user_profile_service import get_sales_groups, get_organization_users
    from services.role_service import get_users_by_role

    org_id = user["org_id"]

    assignment = get_assignment(assignment_id)
    if not assignment or assignment.organization_id != org_id:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Get sales group name
    all_groups = get_sales_groups(org_id)
    group_name_map = {g["id"]: g["name"] for g in all_groups}
    current_group_name = group_name_map.get(assignment.sales_group_id, assignment.sales_group_id[:8] + "...")

    # Get procurement users (single query via role_service)
    org_users = get_organization_users(org_id)
    user_name_map = {u["id"]: u.get("full_name") or u.get("email", u["id"][:8] + "...") for u in org_users}

    procurement_role_users = get_users_by_role(org_id, "procurement")
    procurement_users = [
        {"user_id": u["user_id"], "display": user_name_map.get(u["user_id"], u["user_id"][:8] + "...")}
        for u in procurement_role_users
    ]

    # Build user options with current selected
    user_options = [
        Option(u["display"], value=u["user_id"], selected=(u["user_id"] == assignment.user_id))
        for u in procurement_users
    ]

    # Form styles
    label_style = "display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px;"
    select_style = "width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; background: #f8fafc;"

    current_user_display = user_name_map.get(assignment.user_id, assignment.user_id[:8] + "...")

    return page_layout("Редактирование назначения",
        # Header card
        Div(
            A(
                Span(icon("arrow-left", size=14), style="margin-right: 6px;"),
                "К маршрутизации закупок",
                href="/admin/procurement-groups",
                style="color: #64748b; text-decoration: none; font-size: 13px; display: inline-flex; align-items: center; margin-bottom: 16px;"
            ),
            Div(
                Div(
                    icon("edit-3", size=28, color="#f59e0b"),
                    style="width: 48px; height: 48px; background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 16px;"
                ),
                Div(
                    H1("Редактирование назначения", style="margin: 0 0 4px 0; font-size: 1.5rem; font-weight: 600; color: #1e293b;"),
                    Div(
                        Span("Группа: ", style="color: #64748b; font-size: 14px;"),
                        Span(current_group_name, style="color: #3b82f6; font-size: 14px; font-weight: 600;"),
                    ),
                    style="flex: 1;"
                ),
                style="display: flex; align-items: center;"
            ),
            style="background: linear-gradient(135deg, #fafbfc 0%, #f1f5f9 100%); border-radius: 16px; padding: 20px 24px; margin-bottom: 24px; border: 1px solid #e2e8f0;"
        ),

        # Form card
        Div(
            Form(
                Div(
                    icon("user", size=14, color="#64748b"),
                    Span("ИЗМЕНИТЬ МЕНЕДЖЕРА", style="margin-left: 6px;"),
                    style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center;"
                ),

                # Current assignment info
                Div(
                    Span("Текущий менеджер: ", style="color: #64748b; font-size: 13px;"),
                    Span(current_user_display, style="color: #1e293b; font-weight: 500; font-size: 13px;"),
                    style="padding: 12px; background: #f8fafc; border-radius: 8px; margin-bottom: 16px;"
                ),

                # Manager select
                Div(
                    Label("Новый менеджер по закупкам *", fr="user_id", style=label_style),
                    Select(
                        *user_options,
                        name="user_id",
                        id="user_id",
                        required=True,
                        style=select_style
                    ) if user_options else P("Нет менеджеров с ролью procurement", style="color: #ef4444; font-size: 14px;"),
                    style="margin-bottom: 20px;"
                ),

                # Submit button
                Div(
                    btn("Сохранить изменения", variant="primary", icon_name="check", type="submit"),
                    btn_link("Отмена", href="/admin/procurement-groups", variant="secondary"),
                    style="display: flex; gap: 12px; padding-top: 16px; border-top: 1px solid #e2e8f0;"
                ) if user_options else None,

                method="POST",
                action=f"/admin/procurement-groups/{assignment_id}/edit"
            ),
            style="background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 1px solid #e2e8f0; max-width: 500px;"
        ),

        session=session
    )


# @rt("/admin/procurement-groups/{assignment_id}/edit")
def post(assignment_id: str, session, user_id: str):
    """Update procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.route_procurement_assignment_service import update_assignment, get_assignment
    from services.role_service import get_users_by_role

    org_id = admin_user["org_id"]
    assignment = get_assignment(assignment_id)
    if not assignment or assignment.organization_id != org_id:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    # Validate user_id belongs to this org's procurement users
    valid_user_ids = {u["user_id"] for u in get_users_by_role(org_id, "procurement")}
    if user_id not in valid_user_ids:
        return page_layout("Ошибка",
            H1(icon("alert-triangle", size=28), " Недопустимый пользователь", cls="page-header"),
            P("Выбранный пользователь не является менеджером по закупкам в вашей организации."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    result = update_assignment(assignment_id, user_id)

    if result:
        return RedirectResponse(url="/admin/procurement-groups", status_code=303)
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка обновления", cls="page-header"),
            P("Не удалось обновить назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# @rt("/admin/procurement-groups/{assignment_id}/delete")
def post(assignment_id: str, session):
    """Delete procurement group routing assignment."""
    redirect = require_login(session)
    if redirect:
        return redirect

    admin_user = session["user"]
    roles = admin_user.get("roles", [])

    if "admin" not in roles:
        return page_layout("Доступ запрещён",
            H1("Доступ запрещён"),
            P("Эта страница доступна только администраторам."),
            btn_link("На главную", href="/dashboard", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    from services.route_procurement_assignment_service import get_assignment, delete_assignment

    org_id = admin_user["org_id"]
    assignment = get_assignment(assignment_id)
    if not assignment or assignment.organization_id != org_id:
        return page_layout("Не найдено",
            H1("Назначение не найдено"),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )

    result = delete_assignment(assignment_id)

    if result:
        return RedirectResponse(url="/admin/procurement-groups", status_code=303)
    else:
        return page_layout("Ошибка",
            H1(icon("x-circle", size=28), " Ошибка удаления", cls="page-header"),
            P("Не удалось удалить назначение. Попробуйте ещё раз."),
            btn_link("Назад к списку", href="/admin/procurement-groups", variant="secondary", icon_name="arrow-left"),
            session=session
        )


# ============================================================================
# ADMIN IMPERSONATION ROUTES
# ============================================================================

VALID_IMPERSONATION_ROLES = {
    "sales", "procurement", "logistics", "customs",
    "quote_controller", "spec_controller", "finance",
    "top_manager", "head_of_sales", "head_of_procurement", "head_of_logistics",
    "currency_controller",
}

# @rt("/admin/impersonate")
def get(session, role: str = ""):
    """GET /admin/impersonate - Set or clear role impersonation (admin and training_manager)."""
    user = session.get("user")
    user_roles = user.get("roles", []) if user else []
    if not user or ("admin" not in user_roles and "training_manager" not in user_roles):
        return RedirectResponse("/", status_code=303)

    if role:
        if role not in VALID_IMPERSONATION_ROLES:
            return RedirectResponse("/", status_code=303)
        session["impersonated_role"] = role
    else:
        session.pop("impersonated_role", None)

    return RedirectResponse("/", status_code=303)


# @rt("/admin/impersonate/exit")
def get(session):
    """GET /admin/impersonate/exit - Clear role impersonation."""
    session.pop("impersonated_role", None)
    return RedirectResponse("/", status_code=303)

