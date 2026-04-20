"""FastHTML /approvals + /changelog + /telegram areas — archived 2026-04-20 during Phase 6C-2B-6.

Superseded by Next.js:
  - /approvals   — /quotes?status=pending_approval filter + approvals widget on /dashboard
  - /changelog   — https://app.kvotaflow.ru/changelog (reads from /api/changelog FastAPI endpoint)
  - /telegram    — https://app.kvotaflow.ru/settings/telegram (Next.js, reads from /api/integrations/*)

Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru, which
doesn't proxy these paths back to this Python container.

Contents:
  - GET    /approvals                        — Top Manager approvals workspace
  - GET    /changelog                        — timeline of product updates (reads services.changelog_service)
  - GET    /telegram                         — Telegram connection management page
  - POST   /telegram/generate-code           — generate verification code for Telegram linking
  - POST   /telegram/disconnect              — unlink Telegram account
  - GET    /telegram/status                  — HTMX endpoint for current Telegram connection status
  - helper: _telegram_status_fragment        — renders connection status UI fragment (scoped to /telegram/*)

Preserved in main.py (NOT archived here):
  - services/changelog_service.py   — still alive, consumed by /api/changelog (api.routers.public)
  - services/telegram_service.py    — still alive (webhook handler, notify_creator_of_return, etc.)
  - FastAPI /api/changelog          — served by api.routers.public via the /api mount
  - FastAPI /api/telegram/webhook   — served by api.integrations sub-app via the /api mount
  - FastAPI /api/integrations/*     — Telegram status/link/unlink endpoints consumed by Next.js
  - notify_creator_of_return import — still used by /quote-control/{quote_id}/return-to-control POST
  - sidebar/nav entries for /approvals, /changelog, /telegram (main.py lines 2571, 2726, 2727, 2740)
    left intact, become dead links post-archive, safe per Caddy cutover (user confirmed)

No /admin/* feedback or /quote-control/* routes are touched by this archive — those are separate
cluster decisions (6C-2B-12 for quote-control).

This file is NOT imported by main.py or api/app.py. Effectively dead code preserved for
reference. To resurrect a handler: copy back to main.py, restore imports (page_layout,
require_login, user_has_any_role, get_supabase, icon, format_money, NotStr, fasthtml
components, datetime, services.changelog_service, services.telegram_service
{TELEGRAM_BOT_USERNAME, get_user_telegram_status, request_verification_code,
unlink_telegram_account}), re-apply the @rt decorator, and regenerate tests if
needed. Not recommended — rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from datetime import datetime

from fasthtml.common import A, Button, Div, H1, H2, H3, I, NotStr, P, Span, Style
from starlette.responses import RedirectResponse


# ============================================================================
# TOP MANAGER APPROVALS WORKSPACE
# ============================================================================

# @rt("/approvals")  # decorator removed; file is archived and not mounted
def get(session):
    """
    Top Manager Approvals Workspace.

    Shows all quotes pending approval with:
    - Quote details (IDN, customer, amount)
    - Approval reason from controller
    - Justification from sales manager
    - Quick action buttons
    """
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user["id"]
    org_id = user["org_id"]

    # Check if user has top_manager role
    if not user_has_any_role(session, ["top_manager", "admin"]):
        return RedirectResponse("/unauthorized", status_code=303)

    supabase = get_supabase()

    # Get all quotes pending approval for this org
    quotes_result = supabase.table("quotes") \
        .select("*, customers(name, inn)") \
        .eq("organization_id", org_id) \
        .eq("workflow_status", "pending_approval") \
        .is_("deleted_at", None) \
        .order("updated_at", desc=True) \
        .execute()

    pending_quotes = quotes_result.data or []

    # Count stats
    total_pending = len(pending_quotes)
    total_amount = sum(float(q.get("total_amount") or 0) for q in pending_quotes)

    # Build quote cards
    quote_cards = []
    for q in pending_quotes:
        quote_id = q.get("id")
        idn_quote = q.get("idn_quote", f"#{quote_id[:8]}")
        customer = q.get("customers", {}) or {}
        customer_name = customer.get("name", "—")
        amount = q.get("total_amount")
        currency = q.get("currency", "RUB")
        approval_reason = q.get("approval_reason", "")
        approval_justification = q.get("approval_justification", "")
        updated_at = q.get("updated_at", "")[:10] if q.get("updated_at") else "—"

        quote_cards.append(
            Div(
                # Header row
                Div(
                    Div(
                        A(f"📋 {idn_quote}", href=f"/quotes/{quote_id}",
                          style="font-weight: 600; font-size: 1.1rem; color: #1e40af; text-decoration: none;"),
                        Span(f" • {customer_name}", style="color: #6b7280;"),
                        style="flex: 1;"
                    ),
                    Div(
                        Span(format_money(amount, currency), style="font-weight: 600; font-size: 1.1rem; color: #059669;"),
                        style="text-align: right;"
                    ),
                    style="display: flex; justify-content: space-between; margin-bottom: 0.75rem;"
                ),

                # Context section
                Div(
                    Div(
                        Span("📋 Причина:", style="font-weight: 500; font-size: 0.875rem;"),
                        Span(f" {approval_reason[:100]}{'...' if len(approval_reason) > 100 else ''}" if approval_reason else " Не указана",
                             style="font-size: 0.875rem; color: #666;"),
                        style="background: #fef3c7; padding: 0.5rem; border-radius: 4px; margin-bottom: 0.5rem;"
                    ) if approval_reason else None,
                    Div(
                        Span("💼 Обоснование:", style="font-weight: 500; font-size: 0.875rem;"),
                        Span(f" {approval_justification[:100]}{'...' if len(approval_justification) > 100 else ''}" if approval_justification else " Не указано",
                             style="font-size: 0.875rem; color: #666;"),
                        style="background: #dbeafe; padding: 0.5rem; border-radius: 4px; margin-bottom: 0.5rem;"
                    ) if approval_justification else None,
                    style="margin-bottom: 0.75rem;"
                ) if approval_reason or approval_justification else None,

                # Actions row
                Div(
                    Span(f"Обновлено: {updated_at}", style="color: #9ca3af; font-size: 0.875rem;"),
                    Div(
                        A(icon("check", size=14), " Одобрить", href=f"/quotes/{quote_id}?tab=overview",
                          style="background: #16a34a; color: white; padding: 0.375rem 0.75rem; border-radius: 6px; text-decoration: none; font-size: 0.875rem; margin-right: 0.5rem; display: inline-flex; align-items: center; gap: 0.25rem;"),
                        A(icon("eye", size=14), " Подробнее", href=f"/quotes/{quote_id}",
                          style="background: #3b82f6; color: white; padding: 0.375rem 0.75rem; border-radius: 6px; text-decoration: none; font-size: 0.875rem; display: inline-flex; align-items: center; gap: 0.25rem;"),
                    ),
                    style="display: flex; justify-content: space-between; align-items: center;"
                ),

                cls="card",
                style="margin-bottom: 1rem; border-left: 4px solid #f59e0b;"
            )
        )

    return page_layout("Согласования",
        # Header
        Div(
            H1(icon("clock", size=28), " Согласования", cls="page-header"),
            P("Коммерческие предложения, ожидающие вашего решения", style="color: #666;"),
            style="margin-bottom: 1rem;"
        ),

        # Stats cards
        Div(
            Div(
                Div(str(total_pending), style="font-size: 2rem; font-weight: 700; color: #f59e0b;"),
                Div("Ожидают решения", style="color: #666; font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 1rem;"
            ),
            Div(
                Div(format_money(total_amount, "RUB"), style="font-size: 1.5rem; font-weight: 700; color: #059669;"),
                Div("Общая сумма", style="color: #666; font-size: 0.875rem;"),
                cls="card", style="text-align: center; padding: 1rem;"
            ),
            style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;"
        ),

        # Quotes list
        Div(
            H2(f"КП на согласовании ({total_pending})", style="margin-bottom: 1rem;"),
            *quote_cards if quote_cards else [
                Div(
                    icon("check-circle", size=48),
                    H3("Все согласовано!", style="margin: 1rem 0 0.5rem;"),
                    P("Нет КП, ожидающих вашего решения.", style="color: #666;"),
                    style="text-align: center; padding: 3rem; color: #16a34a;",
                    cls="card"
                )
            ],
        ),

        session=session
    )


# ============================================================================
# CHANGELOG PAGE
# ============================================================================

# @rt("/changelog")  # decorator removed; file is archived and not mounted
def get(session):
    """Changelog page - timeline of product updates."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user.get("id")

    from services.changelog_service import get_all_entries, mark_as_read, render_entry_html, format_date_russian_human

    entries = get_all_entries()

    # Mark all entries as read for this user
    if user_id and entries:
        try:
            mark_as_read(user_id)
        except Exception:
            pass  # Non-critical, don't break the page

    # Build timeline UI
    if not entries:
        content = Div(
            Div(
                icon("newspaper", size=48, color="#94a3b8"),
                P("Записей ещё нет", style="margin-top: 12px; color: var(--text-secondary); font-size: 1rem;"),
                style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px 20px; text-align: center;"
            ),
            style="max-width: 960px; margin: 0 auto;"
        )
    else:
        timeline_items = []
        for entry in entries:
            body_html = render_entry_html(entry)
            date_label = format_date_russian_human(entry["date"])

            # Version badge (optional)
            version_badge = None
            version = entry.get("version")
            if version:
                version_badge = Span(
                    version,
                    style="background: #ede9fe; color: #6366f1; font-size: 0.7rem; font-weight: 600; padding: 2px 8px; border-radius: 10px; margin-left: 8px;"
                )

            # Category badge
            category = entry.get("category", "update")
            category_colors = {
                "feature": ("#dcfce7", "#16a34a"),
                "fix": ("#fef3c7", "#d97706"),
                "update": ("#dbeafe", "#2563eb"),
                "improvement": ("#ede9fe", "#7c3aed"),
            }
            cat_bg, cat_fg = category_colors.get(category, ("#f1f5f9", "#475569"))
            category_labels = {
                "feature": "Новое",
                "fix": "Исправление",
                "update": "Обновление",
                "improvement": "Улучшение",
            }
            cat_label = category_labels.get(category, category.capitalize())

            timeline_items.append(
                Div(
                    # Left: date
                    Div(
                        Span(date_label, style="font-size: 0.8rem; color: var(--text-secondary); white-space: nowrap;"),
                        style="width: 120px; flex-shrink: 0; text-align: right; padding-top: 18px;"
                    ),
                    # Center: timeline dot + line
                    Div(
                        Div(style="width: 12px; height: 12px; background: #6366f1; border-radius: 50%; border: 3px solid #ede9fe; position: relative; z-index: 1;"),
                        style="width: 12px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; position: relative; margin: 0 16px;"
                    ),
                    # Right: card
                    Div(
                        Div(
                            Div(
                                Span(cat_label, style=f"background: {cat_bg}; color: {cat_fg}; font-size: 0.7rem; font-weight: 600; padding: 2px 8px; border-radius: 10px;"),
                                version_badge if version_badge else None,
                                style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;"
                            ),
                            H3(entry["title"], style="margin: 0 0 10px; font-size: 1rem; font-weight: 600; color: var(--text-primary);"),
                            Div(NotStr(body_html), cls="changelog-body"),
                            cls="changelog-entry-inner"
                        ),
                        style="flex: 1; min-width: 0; padding-bottom: 24px;"
                    ),
                    style="display: flex; align-items: flex-start;"
                )
            )

        # Timeline vertical line via pseudo-element style
        content = Div(
            # Page header
            Div(
                H1("Обновления", style="margin: 0; font-size: 1.5rem;"),
                P("История изменений и улучшений системы",
                  style="margin: 4px 0 0; color: var(--text-secondary); font-size: 0.875rem;"),
                style="margin-bottom: 1.5rem;"
            ),
            # Timeline container
            Div(
                *timeline_items,
                style="position: relative;"
            ),
            # Styles for changelog body and timeline
            Style("""
                .changelog-body h2 {
                    font-size: 0.8rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    color: var(--text-secondary);
                    margin: 12px 0 6px;
                }
                .changelog-body ul {
                    margin: 0 0 10px 0;
                    padding-left: 18px;
                }
                .changelog-body li {
                    font-size: 0.875rem;
                    color: var(--text-primary);
                    margin-bottom: 3px;
                    line-height: 1.5;
                }
                .changelog-entry-inner {
                    background: var(--card-bg, #fff);
                    border: 1px solid var(--border-color, #e2e8f0);
                    border-radius: 10px;
                    padding: 16px 20px;
                }
            """),
            style="max-width: 960px; margin: 0 auto;"
        )

    return page_layout("Обновления", content, session=session, current_path="/changelog")


# ============================================================================
# TELEGRAM CONNECTION PAGE
# ============================================================================

def _telegram_status_fragment(status, user_id=None):
    """Render the connection status fragment for HTMX updates."""
    if status.is_verified:
        verified_date = ""
        if status.verified_at:
            try:
                dt = datetime.fromisoformat(status.verified_at.replace("Z", "+00:00"))
                verified_date = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                verified_date = status.verified_at
        return Div(
            Div(
                Div(
                    I(data_lucide="check-circle", style="width:20px;height:20px;color:var(--success-color);"),
                    Span("Подключён", style="font-weight:600;color:var(--success-color);font-size:1.1rem;"),
                    style="display:flex;align-items:center;gap:8px;margin-bottom:12px;"
                ),
                P(f"Telegram: @{status.telegram_username}" if status.telegram_username else "Telegram подключён",
                  style="margin:0 0 4px;"),
                P(f"Подключён: {verified_date}", style="margin:0;color:var(--text-secondary);font-size:0.875rem;") if verified_date else "",
                style="margin-bottom:16px;"
            ),
            Button(
                I(data_lucide="unlink", style="width:16px;height:16px;"),
                " Отключить",
                hx_post="/telegram/disconnect",
                hx_target="#telegram-status",
                hx_swap="innerHTML",
                hx_confirm="Отключить Telegram? Вы перестанете получать уведомления.",
                cls="btn btn-outline-danger",
                style="display:inline-flex;align-items:center;gap:6px;"
            ),
            id="telegram-status"
        )
    else:
        # Build deep link with user_id for one-click connection
        bot_username = TELEGRAM_BOT_USERNAME
        deep_link = f"https://t.me/{bot_username}?start={user_id}" if bot_username and user_id else None

        return Div(
            Div(
                I(data_lucide="link-2-off", style="width:20px;height:20px;color:var(--text-secondary);"),
                Span("Не подключён", style="font-weight:600;color:var(--text-secondary);font-size:1.1rem;"),
                style="display:flex;align-items:center;gap:8px;margin-bottom:12px;"
            ),
            P("Подключите Telegram, чтобы получать уведомления о задачах, согласованиях и статусах.",
              style="margin:0 0 16px;color:var(--text-secondary);"),
            A(
                I(data_lucide="send", style="width:16px;height:16px;"),
                " Подключить Telegram",
                href=deep_link,
                target="_blank",
                cls="btn btn-primary",
                style="display:inline-flex;align-items:center;gap:6px;"
            ) if deep_link else P("Бот не настроен. Обратитесь к администратору.", cls="text-error"),
            P("Нажмите кнопку → откроется Telegram → нажмите Start → готово!",
              style="margin:12px 0 0;color:var(--text-secondary);font-size:0.8rem;"),
            # Check button (in case user already connected via bot)
            Button(
                I(data_lucide="refresh-cw", style="width:14px;height:14px;"),
                " Уже подключили? Проверить",
                hx_get="/telegram/status",
                hx_target="#telegram-status",
                hx_swap="innerHTML",
                cls="btn btn-outline-secondary btn-sm",
                style="display:inline-flex;align-items:center;gap:6px;margin-top:12px;"
            ),
            id="telegram-status"
        )


# @rt("/telegram")  # decorator removed; file is archived and not mounted
def get_telegram_page(session):
    """Telegram connection management page."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user.get("id")
    status = get_user_telegram_status(user_id)

    content = Div(
        Div(
            H1("Telegram", style="margin:0;font-size:1.5rem;"),
            P("Управление подключением Telegram для уведомлений",
              style="margin:4px 0 0;color:var(--text-secondary);font-size:0.875rem;"),
            style="margin-bottom:1.5rem;"
        ),
        Div(
            _telegram_status_fragment(status, user_id=user_id),
            cls="card",
            style="padding:24px;max-width:500px;"
        ),
        style="max-width:800px;margin:0 auto;"
    )

    return page_layout("Telegram", content, session=session, current_path="/telegram")


# @rt("/telegram/generate-code", methods=["POST"])  # decorator removed; file is archived and not mounted
def post_telegram_generate_code(session):
    """Generate verification code for Telegram linking."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user.get("id")

    code = request_verification_code(user_id)
    if not code:
        # Already verified or error
        status = get_user_telegram_status(user_id)
        if status.is_verified:
            return _telegram_status_fragment(status)
        return Div(
            P("Не удалось сгенерировать код. Попробуйте позже.", cls="text-error"),
            id="telegram-status"
        )

    bot_username = TELEGRAM_BOT_USERNAME
    deep_link = f"https://t.me/{bot_username}?start={code}" if bot_username else None

    return Div(
        Div(
            I(data_lucide="key-round", style="width:20px;height:20px;color:var(--primary-color);"),
            Span("Код подтверждения", style="font-weight:600;font-size:1.1rem;"),
            style="display:flex;align-items:center;gap:8px;margin-bottom:16px;"
        ),
        # Code display
        Div(
            Span(code, style="font-size:2rem;font-weight:700;letter-spacing:0.3em;font-family:monospace;"),
            style="text-align:center;padding:20px;background:var(--bg-secondary);border-radius:8px;margin-bottom:16px;"
        ),
        # Deep link
        Div(
            A(
                I(data_lucide="external-link", style="width:16px;height:16px;"),
                f" Открыть @{bot_username}",
                href=deep_link,
                target="_blank",
                cls="btn btn-primary",
                style="display:inline-flex;align-items:center;gap:6px;"
            ),
            style="text-align:center;margin-bottom:16px;"
        ) if deep_link else "",
        # Instructions
        Div(
            P("1. Откройте бота по ссылке выше (или найдите его в Telegram)", style="margin:0 0 4px;"),
            P("2. Нажмите Start / Начать", style="margin:0 0 4px;"),
            P("3. Код будет автоматически отправлен боту", style="margin:0 0 4px;") if deep_link else
            P(f"3. Отправьте боту команду: /start {code}", style="margin:0 0 4px;"),
            style="font-size:0.875rem;color:var(--text-secondary);margin-bottom:16px;"
        ),
        P("Код действителен 30 минут",
          style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:16px;"),
        # Check button
        Button(
            I(data_lucide="refresh-cw", style="width:16px;height:16px;"),
            " Проверить подключение",
            hx_get="/telegram/status",
            hx_target="#telegram-status",
            hx_swap="innerHTML",
            cls="btn btn-outline-primary",
            style="display:inline-flex;align-items:center;gap:6px;"
        ),
        id="telegram-status"
    )


# @rt("/telegram/disconnect", methods=["POST"])  # decorator removed; file is archived and not mounted
def post_telegram_disconnect(session):
    """Disconnect Telegram account."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    user_id = user.get("id")
    unlink_telegram_account(user_id)

    status = get_user_telegram_status(user_id)
    return _telegram_status_fragment(status, user_id=user_id)


# @rt("/telegram/status")  # decorator removed; file is archived and not mounted
def get_telegram_status_check(session):
    """HTMX endpoint to check current Telegram connection status."""
    try:
        redirect = require_login(session)
        if redirect:
            return redirect

        user = session.get("user")
        if not user or not user.get("id"):
            return Div("Ошибка: не удалось определить пользователя", id="telegram-status", cls="text-error text-sm")

        user_id = user["id"]
        status = get_user_telegram_status(user_id)
        return _telegram_status_fragment(status, user_id=user_id)
    except Exception as e:
        print(f"Telegram status error: {e}")
        return Div("Не удалось загрузить статус", id="telegram-status", cls="text-error text-sm")
