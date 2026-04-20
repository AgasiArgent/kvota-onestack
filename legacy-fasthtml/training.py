"""FastHTML /training area — archived 2026-04-20 during Phase 6C-2B-5.

Replaced by Next.js at https://app.kvotaflow.ru/training.
Routes unreachable post-Caddy-cutover: kvotaflow.ru 301→app.kvotaflow.ru,
which doesn't proxy these paths back to this Python container.

Contents:
  - GET    /training                              — videos registry page with category tabs + player modal
  - GET    /training/videos                       — HTMX partial: filtered video grid
  - GET    /training/new-form                     — HTMX partial: create video form (admin only)
  - POST   /training/new                          — create video handler (admin only)
  - GET    /training/{video_id}/edit-form         — HTMX partial: edit video form (admin only)
  - POST   /training/{video_id}/edit              — update video handler (admin only)
  - DELETE /training/{video_id}/delete            — delete video handler (admin only)
  - helpers: _get_embed_url, _get_thumbnail_url, _render_video_cards
  - module constant: _PLATFORM_LABELS

Preserved in main.py (NOT archived here):
  - services/training_video_service.py  — service layer remains in services/ (becomes
    effectively dead code after this archive, but not touched per task scope)
  - sidebar/nav entries for /training   — left intact, become dead links post-archive,
    safe per Caddy cutover (user confirmed)
  - training_manager role infrastructure (sidebar impersonation dropdown, impersonation
    route, ROLE_LABELS_RU entry) — still alive, unrelated to this archive

No /api/training/* FastAPI sub-app exists; no /admin/* training routes exist. All
FastHTML /training URLs confirmed via grep (exactly 7 @rt entries).

This file is NOT imported by main.py or api/app.py. Effectively dead code
preserved for reference. To resurrect a handler: copy back to main.py,
restore imports (page_layout, require_login, user_has_any_role, get_supabase,
btn, icon, services.training_video_service, A, Button, Div, Form, H1, H2,
Iframe, Input, Label, P, Script, Small, Span, Style, Textarea), re-apply
the @rt decorator, and regenerate tests if needed. Not recommended —
rewrite via Next.js instead.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import (
    A, Button, Div, Form, H1, H2, Iframe, Input, Label, P, Script, Small,
    Span, Style, Textarea,
)


# ============================================================================
# TRAINING VIDEOS
# ============================================================================

# @rt("/training")  # decorator removed; file is archived and not mounted
def get(session):
    """Training videos page - knowledge base with YouTube embeds and category filtering."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user.get("org_id")
    roles = user.get("roles", [])
    is_admin = "admin" in roles

    from services.training_video_service import get_all_videos, get_categories

    categories = get_categories(org_id)
    videos = get_all_videos(org_id)

    # Category tabs
    category_tabs = [
        A("Все",
          hx_get="/training/videos",
          hx_target="#video-grid",
          hx_swap="outerHTML",
          cls="training-tab active",
          data_category="all",
          onclick="setActiveTab(this)")
    ]
    for cat in categories:
        category_tabs.append(
            A(cat,
              hx_get=f"/training/videos?category={cat}",
              hx_target="#video-grid",
              hx_swap="outerHTML",
              cls="training-tab",
              data_category=cat,
              onclick="setActiveTab(this)")
        )

    # Video cards
    video_cards = _render_video_cards(videos, is_admin)

    # Admin add button
    admin_controls = []
    if is_admin:
        admin_controls.append(
            btn("Добавить видео", variant="primary", icon_name="plus",
                hx_get="/training/new-form",
                hx_target="#training-modal-container",
                hx_swap="innerHTML")
        )

    content = Div(
        # Page header
        Div(
            Div(
                H1("Обучение", style="margin: 0; font-size: 1.5rem;"),
                P("Видеоматериалы по работе с системой. Создание заявки = Создание КП (коммерческого предложения).",
                  style="margin: 4px 0 0; color: var(--text-secondary); font-size: 0.875rem;"),
                style="flex: 1;"
            ),
            Div(*admin_controls) if admin_controls else None,
            style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem; padding-top: 24px;"
        ),
        # Category tabs
        Div(
            *category_tabs,
            cls="training-tabs",
            style="display: flex; gap: 6px; margin-bottom: 1.25rem; flex-wrap: wrap;"
        ),
        # Video grid — 3 columns, compact
        Div(
            *video_cards,
            id="video-grid",
            cls="tv-grid"
        ),
        # Video player modal (single shared iframe)
        Div(
            Div(
                Div(
                    Span(id="tv-modal-title", style="font-weight: 600; font-size: 0.9rem;"),
                    Button("✕", onclick="closeVideoPlayer()", cls="tv-modal-close"),
                    cls="tv-modal-header"
                ),
                Div(
                    Iframe(id="tv-modal-iframe", src="", width="100%", height="100%",
                           frameborder="0", allowfullscreen=True,
                           allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"),
                    cls="tv-modal-video"
                ),
                cls="tv-modal-content"
            ),
            id="tv-player-modal",
            cls="tv-modal",
            onclick="if(event.target===this)closeVideoPlayer()"
        ),
        # Modal container for admin forms
        Div(id="training-modal-container"),
        # Scripts
        Script("""
            function setActiveTab(el) {
                document.querySelectorAll('.training-tab').forEach(t => t.classList.remove('active'));
                el.classList.add('active');
            }
            function openVideoPlayer(el) {
                var modal = document.getElementById('tv-player-modal');
                var iframe = document.getElementById('tv-modal-iframe');
                var title = document.getElementById('tv-modal-title');
                iframe.src = el.dataset.embed;
                title.textContent = el.dataset.title;
                modal.classList.add('tv-modal--open');
                document.body.style.overflow = 'hidden';
            }
            function closeVideoPlayer() {
                var modal = document.getElementById('tv-player-modal');
                var iframe = document.getElementById('tv-modal-iframe');
                modal.classList.remove('tv-modal--open');
                iframe.src = '';
                document.body.style.overflow = '';
            }
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeVideoPlayer();
            });
        """),
        # Styles
        Style("""
            /* --- Category tabs --- */
            .training-tab {
                padding: 5px 14px;
                border-radius: 6px;
                font-size: 0.8rem;
                font-weight: 500;
                cursor: pointer;
                background: var(--bg-secondary, #f1f5f9);
                color: var(--text-secondary, #64748b);
                text-decoration: none;
                border: 1px solid var(--border-color, #e2e8f0);
                transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
            }
            .training-tab:hover {
                color: var(--text-primary);
                border-color: var(--accent, #3b82f6);
            }
            .training-tab.active {
                background: var(--accent, #3b82f6);
                color: var(--text-on-accent, #fff);
                border-color: var(--accent, #3b82f6);
            }

            /* --- Grid --- */
            .tv-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
                gap: 1rem;
            }

            /* --- Card --- */
            .tv-card {
                border-radius: 10px;
                overflow: hidden;
                border: 1px solid var(--border-color, #e2e8f0);
                background: var(--bg-card, #fff);
                animation: tvFadeIn 0.35s ease both;
            }
            /* tv-card:hover removed — cards are static containers */
            @keyframes tvFadeIn {
                from { opacity: 0; transform: translateY(8px); }
                to { opacity: 1; transform: translateY(0); }
            }

            /* --- Thumbnail --- */
            .tv-thumb {
                position: relative;
                aspect-ratio: 16 / 9;
                background-size: cover;
                background-position: center;
                cursor: pointer;
                overflow: hidden;
            }
            .tv-thumb::after {
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(0deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.05) 50%, rgba(0,0,0,0.1) 100%);
                transition: background 0.2s;
            }
            .tv-card:hover .tv-thumb::after {
                background: linear-gradient(0deg, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.15) 100%);
            }
            /* Fallback gradients per platform */
            .tv-thumb--loom { background-color: #625df5; }
            .tv-thumb--youtube { background-color: #cc0000; }
            .tv-thumb--rutube { background-color: #1b9d5b; }

            /* --- Play button --- */
            .tv-play-btn {
                position: absolute;
                top: 65%; left: 50%;
                transform: translate(-50%, -50%);
                z-index: 2;
                width: 44px; height: 44px;
                border-radius: 50%;
                background: rgba(255,255,255,0.92);
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 2px 12px rgba(0,0,0,0.2);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }
            .tv-card:hover .tv-play-btn {
                transform: translate(-50%, -50%) scale(1.1);
                box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            }
            .tv-play-triangle {
                width: 0; height: 0;
                border-style: solid;
                border-width: 8px 0 8px 14px;
                border-color: transparent transparent transparent #1e293b;
                margin-left: 3px;
            }

            /* --- Platform badge --- */
            .tv-badge {
                position: absolute;
                top: 8px; left: 8px;
                z-index: 2;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 0.65rem;
                font-weight: 600;
                letter-spacing: 0.03em;
                text-transform: uppercase;
                color: #fff;
                background: rgba(0,0,0,0.45);
                backdrop-filter: blur(4px);
            }

            /* --- Card body --- */
            .tv-body {
                padding: 10px 12px 10px;
                display: flex;
                flex-direction: column;
                gap: 2px;
            }
            .tv-title {
                font-size: 0.875rem;
                font-weight: 600;
                color: var(--text-primary);
                line-height: 1.3;
            }
            .tv-desc {
                font-size: 0.75rem;
                color: var(--text-secondary);
                line-height: 1.4;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }
            .tv-footer {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 6px;
            }
            .tv-cat {
                font-size: 0.7rem;
                font-weight: 500;
                color: var(--text-secondary);
                background: var(--bg-secondary, #f1f5f9);
                padding: 2px 8px;
                border-radius: 4px;
            }

            /* --- Admin icon buttons --- */
            .tv-actions { display: flex; gap: 4px; }
            .tv-icon-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 28px; height: 28px;
                border-radius: 6px;
                border: 1px solid var(--border-color, #e2e8f0);
                background: var(--bg-secondary, #f8fafc);
                color: var(--text-secondary);
                cursor: pointer;
                transition: border-color 0.15s ease, color 0.15s ease, background-color 0.15s ease;
                padding: 0;
            }
            .tv-icon-btn:hover {
                border-color: var(--accent);
                color: var(--accent);
                background: var(--accent-light, rgba(59,130,246,0.08));
            }
            .tv-icon-btn--del:hover {
                border-color: #ef4444;
                color: #ef4444;
                background: rgba(239,68,68,0.08);
            }

            /* --- Video Player Modal --- */
            .tv-modal {
                display: none;
                position: fixed;
                inset: 0;
                z-index: 9999;
                background: rgba(0,0,0,0.75);
                backdrop-filter: blur(4px);
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }
            .tv-modal--open {
                display: flex;
                animation: tvModalIn 0.2s ease;
            }
            @keyframes tvModalIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            .tv-modal-content {
                width: 100%;
                max-width: 900px;
                border-radius: 12px;
                overflow: hidden;
                background: #000;
                box-shadow: 0 24px 64px rgba(0,0,0,0.5);
                animation: tvModalSlide 0.25s ease;
            }
            @keyframes tvModalSlide {
                from { opacity: 0; transform: scale(0.96) translateY(10px); }
                to { opacity: 1; transform: scale(1) translateY(0); }
            }
            .tv-modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 16px;
                background: #111;
                color: #fff;
            }
            .tv-modal-close {
                background: none;
                border: none;
                color: #999;
                font-size: 1.2rem;
                cursor: pointer;
                padding: 4px 8px;
                border-radius: 6px;
                transition: color 0.15s ease, background-color 0.15s ease;
            }
            .tv-modal-close:hover {
                color: #fff;
                background: rgba(255,255,255,0.1);
            }
            .tv-modal-video {
                aspect-ratio: 16 / 9;
            }
            .tv-modal-video iframe {
                display: block;
            }

            @media (max-width: 640px) {
                .tv-grid { grid-template-columns: 1fr; }
                .tv-modal { padding: 1rem; }
            }
        """)
    )

    return page_layout("Обучение", content, session=session, current_path="/training")


def _get_embed_url(video_id: str, platform: str) -> str:
    """Get the embed URL based on platform."""
    if platform == "youtube":
        return f"https://www.youtube.com/embed/{video_id}?autoplay=1"
    elif platform == "loom":
        return f"https://www.loom.com/embed/{video_id}?autoplay=1"
    elif platform == "rutube":
        # Private videos store ID as "hash?p=TOKEN" — use & for extra params
        sep = "&" if "?" in video_id else "?"
        return f"https://rutube.ru/play/embed/{video_id}{sep}autoplay=1"
    else:
        sep = "&" if "?" in video_id else "?"
        return f"https://rutube.ru/play/embed/{video_id}{sep}autoplay=1"


def _get_thumbnail_url(video) -> str:
    """Get thumbnail image URL for video preview card.

    Uses stored thumbnail_url from DB (fetched via oEmbed on creation).
    Falls back to deterministic CDN URLs for YouTube.
    """
    # Prefer stored thumbnail (from oEmbed API)
    if video.thumbnail_url:
        return video.thumbnail_url
    # Fallback for YouTube (deterministic CDN)
    if video.platform == "youtube":
        return f"https://img.youtube.com/vi/{video.youtube_id}/hqdefault.jpg"
    return ""


_PLATFORM_LABELS = {"loom": "Loom", "youtube": "YouTube", "rutube": "Rutube"}


def _render_video_cards(videos, is_admin=False):
    """Render compact video cards with click-to-play thumbnails."""
    if not videos:
        return [
            Div(
                Div(
                    icon("film", size=32, style="opacity: 0.3; margin-bottom: 8px;"),
                    P("Пока нет обучающих видео", style="margin: 0; color: var(--text-secondary); font-size: 0.875rem;"),
                    style="display: flex; flex-direction: column; align-items: center; padding: 3rem;"
                ),
                style="grid-column: 1 / -1;"
            )
        ]

    cards = []
    for i, v in enumerate(videos):
        thumb_url = _get_thumbnail_url(v)
        embed_url = _get_embed_url(v.youtube_id, v.platform)

        # Thumbnail with play overlay
        thumb_bg = f"background-image: url('{thumb_url}');" if thumb_url else ""
        thumbnail = Div(
            Span(_PLATFORM_LABELS.get(v.platform, v.platform), cls=f"tv-badge tv-badge--{v.platform}"),
            Div(
                Div(cls="tv-play-triangle"),
                cls="tv-play-btn"
            ),
            cls=f"tv-thumb tv-thumb--{v.platform}",
            style=thumb_bg,
            data_embed=embed_url,
            data_title=v.title,
            onclick="openVideoPlayer(this)"
        )

        # Card body - compact
        body = [Div(v.title, cls="tv-title")]

        if v.description:
            body.append(Div(v.description, cls="tv-desc"))

        # Footer with category + admin actions
        footer_items = [Span(v.category, cls="tv-cat")]
        if is_admin:
            footer_items.append(
                Div(
                    Button(icon("pencil", size=13), cls="tv-icon-btn",
                           hx_get=f"/training/{v.id}/edit-form",
                           hx_target="#training-modal-container",
                           hx_swap="innerHTML", title="Изменить"),
                    Button(icon("trash-2", size=13), cls="tv-icon-btn tv-icon-btn--del",
                           hx_delete=f"/training/{v.id}/delete",
                           hx_target="#video-grid", hx_swap="outerHTML",
                           hx_confirm="Удалить это видео?", title="Удалить"),
                    cls="tv-actions"
                )
            )

        cards.append(
            Div(
                thumbnail,
                Div(*body, Div(*footer_items, cls="tv-footer"), cls="tv-body"),
                cls="tv-card",
                style=f"animation-delay: {i * 60}ms;"
            )
        )
    return cards


# @rt("/training/videos")  # decorator removed; file is archived and not mounted
def get(session, category: str = ""):
    """HTMX partial - filtered video grid."""
    redirect = require_login(session)
    if redirect:
        return redirect

    user = session["user"]
    org_id = user.get("org_id")
    roles = user.get("roles", [])
    is_admin = "admin" in roles

    from services.training_video_service import get_all_videos

    videos = get_all_videos(org_id, category=category if category else None)
    cards = _render_video_cards(videos, is_admin)
    return Div(*cards, id="video-grid", cls="tv-grid")


# @rt("/training/new-form")  # decorator removed; file is archived and not mounted
def get(session):
    """HTMX partial - create video form (admin only)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin"]):
        return Div(P("Доступ запрещён"), style="color: red;")

    form = Div(
        Div(
            Div(
                H2("Добавить видео", style="margin: 0;"),
                Button("✕", onclick="document.getElementById('training-modal-container').innerHTML=''",
                       style="background: none; border: none; font-size: 1.2rem; cursor: pointer; padding: 4px;"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"
            ),
            Form(
                Div(
                    Label("Название *"),
                    Input(name="title", placeholder="Как создать КП за 5 минут", required=True, cls="form-control"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    Label("Ссылка на видео *"),
                    Input(name="youtube_url", placeholder="https://rutube.ru/video/... или https://youtube.com/watch?v=...", required=True, cls="form-control"),
                    Small("Поддерживается: Rutube, YouTube, Loom", style="color: var(--text-secondary); font-size: 0.75rem;"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    Label("Категория"),
                    Input(name="category", placeholder="Продажи, Закупки, Логистика...", value="Общее", cls="form-control"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    Label("Описание"),
                    Textarea(name="description", placeholder="Краткое описание видео...", rows="3", cls="form-control"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    Label("Порядок сортировки"),
                    Input(name="sort_order", type="number", value="0", cls="form-control"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn("Отмена", variant="ghost", type="button",
                        onclick="document.getElementById('training-modal-container').innerHTML=''"),
                    style="display: flex; gap: 8px;"
                ),
                hx_post="/training/new",
                hx_target="#video-grid",
                hx_swap="outerHTML",
            ),
            style="background: var(--bg-card, white); border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px; padding: 1.5rem; max-width: 500px; margin: 0 auto;"
        ),
        style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;"
    )
    return form


# @rt("/training/new")  # decorator removed; file is archived and not mounted
def post(session, title: str = "", youtube_url: str = "", category: str = "", description: str = "", sort_order: int = 0):
    """Handle create video (admin only)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin"]):
        return Div(P("Доступ запрещён"), style="color: red;")

    user = session["user"]
    org_id = user.get("org_id")
    user_id = user.get("id")

    from services.training_video_service import create_video, get_all_videos, extract_video_info

    video_info = extract_video_info(youtube_url)
    video_id_val = video_info["video_id"]
    platform = video_info["platform"]

    result = create_video(
        organization_id=org_id,
        title=title,
        youtube_id=video_id_val,
        category=category,
        description=description if description else None,
        created_by=user_id,
        sort_order=sort_order,
        platform=platform,
    )

    if not result:
        return Div(P("Ошибка при сохранении видео", style="color: red; text-align: center; padding: 1rem;"))

    # Clear modal and return updated grid
    videos = get_all_videos(org_id)
    cards = _render_video_cards(videos, is_admin=True)
    return Div(
        *cards,
        Script("document.getElementById('training-modal-container').innerHTML='';"),
        id="video-grid", cls="tv-grid"
    )


# @rt("/training/{video_id}/edit-form")  # decorator removed; file is archived and not mounted
def get(session, video_id: str):
    """HTMX partial - edit video form (admin only)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin"]):
        return Div(P("Доступ запрещён"), style="color: red;")

    user = session["user"]
    org_id = user.get("org_id")

    from services.training_video_service import get_video

    video = get_video(video_id)
    if not video or video.organization_id != org_id:
        return Div(P("Видео не найдено"), style="color: red;")

    # Reconstruct URL from stored ID + platform so re-save doesn't corrupt platform
    if video.platform == "youtube":
        display_url = f"https://www.youtube.com/watch?v={video.youtube_id}"
    elif video.platform == "loom":
        display_url = f"https://www.loom.com/share/{video.youtube_id}"
    else:
        # Private videos: hash?p=TOKEN → /video/private/hash/?p=TOKEN
        if "?p=" in video.youtube_id:
            bare_id, token = video.youtube_id.split("?p=", 1)
            display_url = f"https://rutube.ru/video/private/{bare_id}/?p={token}"
        else:
            display_url = f"https://rutube.ru/video/{video.youtube_id}/"

    form = Div(
        Div(
            Div(
                H2("Редактировать видео", style="margin: 0;"),
                Button("✕", onclick="document.getElementById('training-modal-container').innerHTML=''",
                       style="background: none; border: none; font-size: 1.2rem; cursor: pointer; padding: 4px;"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"
            ),
            Form(
                Div(
                    Label("Название *"),
                    Input(name="title", value=video.title, required=True, cls="form-control"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    Label("Ссылка на видео *"),
                    Input(name="youtube_id", value=display_url, required=True, cls="form-control"),
                    Small("Поддерживается: Rutube, YouTube, Loom", style="color: var(--text-secondary); font-size: 0.75rem;"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    Label("Категория"),
                    Input(name="category", value=video.category, cls="form-control"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    Label("Описание"),
                    Textarea(video.description or "", name="description", rows="3", cls="form-control"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    Label("Порядок сортировки"),
                    Input(name="sort_order", type="number", value=str(video.sort_order), cls="form-control"),
                    cls="form-group", style="margin-bottom: 0.75rem;"
                ),
                Div(
                    btn("Сохранить", variant="primary", icon_name="check", type="submit"),
                    btn("Отмена", variant="ghost", type="button",
                        onclick="document.getElementById('training-modal-container').innerHTML=''"),
                    style="display: flex; gap: 8px;"
                ),
                hx_post=f"/training/{video_id}/edit",
                hx_target="#video-grid",
                hx_swap="outerHTML",
            ),
            style="background: var(--bg-card, white); border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px; padding: 1.5rem; max-width: 500px; margin: 0 auto;"
        ),
        style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;"
    )
    return form


# @rt("/training/{video_id}/edit")  # decorator removed; file is archived and not mounted
def post(session, video_id: str, title: str = "", youtube_id: str = "", category: str = "", description: str = "", sort_order: int = 0):
    """Handle edit video (admin only)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin"]):
        return Div(P("Доступ запрещён"), style="color: red;")

    user = session["user"]
    org_id = user.get("org_id")

    from services.training_video_service import get_video, update_video, get_all_videos, extract_video_info

    video = get_video(video_id)
    if not video or video.organization_id != org_id:
        return Div(P("Видео не найдено"), style="color: red;")

    video_info = extract_video_info(youtube_id)
    video_id_val = video_info["video_id"]
    platform = video_info["platform"]

    update_video(
        video_id,
        title=title,
        youtube_id=video_id_val,
        category=category,
        description=description if description else None,
        sort_order=sort_order,
        platform=platform,
    )

    # Return updated grid
    videos = get_all_videos(org_id)
    cards = _render_video_cards(videos, is_admin=True)
    return Div(
        *cards,
        Script("document.getElementById('training-modal-container').innerHTML='';"),
        id="video-grid", cls="tv-grid"
    )


# @rt("/training/{video_id}/delete")  # decorator removed; file is archived and not mounted
def delete(session, video_id: str):
    """Handle delete video (admin only)."""
    redirect = require_login(session)
    if redirect:
        return redirect

    if not user_has_any_role(session, ["admin"]):
        return Div(P("Доступ запрещён"), style="color: red;")

    user = session["user"]
    org_id = user.get("org_id")

    from services.training_video_service import get_video, delete_video, get_all_videos

    video = get_video(video_id)
    if not video or video.organization_id != org_id:
        videos = get_all_videos(org_id)
        cards = _render_video_cards(videos, is_admin=True)
        return Div(*cards, id="video-grid", cls="tv-grid")

    delete_video(video_id)

    # Return updated grid
    videos = get_all_videos(org_id)
    cards = _render_video_cards(videos, is_admin=True)
    return Div(*cards, id="video-grid", cls="tv-grid")
