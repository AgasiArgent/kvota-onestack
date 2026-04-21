"""FastHTML UI helpers for legacy HTMX response fragments.

Relocated from main.py in Phase 6C-3 (2026-04-21). These helpers keep
`api/feedback.py` working: its form-submit handler still returns HTML that
the (now-archived) feedback modal rendered into `#feedback-result`.

Only the two helpers still reachable from live FastAPI handlers are
preserved here. The rest of the main.py UI helpers (status_badge_v2,
dismissible_hint, etc.) stayed tied to archived FastHTML routes and were
deleted with the main.py retirement.
"""

from fasthtml.common import Button, I


def icon(name: str, size: int = 20, cls: str = "", color: str = "", style: str = ""):
    """Lucide icon helper — renders `<i data-lucide="name">` picked up by client JS.

    See main.py (pre-6C-3) for the full icon → emoji mapping. Kept minimal here
    because only `btn(icon_name=...)` consumes it at runtime.
    """
    style_parts = [f"width: {size}px; height: {size}px;"]
    if color:
        style_parts.append(f"color: {color};")
    if style:
        style_parts.append(style)

    return I(
        data_lucide=name,
        cls=f"lucide-icon {cls}".strip(),
        style=" ".join(style_parts),
    )


def btn(
    label: str,
    variant: str = "primary",
    size: str | None = None,
    icon_name: str | None = None,
    icon_right: bool = False,
    full_width: bool = False,
    disabled: bool = False,
    loading: bool = False,
    **kwargs,
):
    """Standardized button helper using BEM classes.

    Args:
        label: Button text
        variant: 'primary', 'secondary', 'success', 'danger', 'ghost'
        size: None (default), 'sm' (small), 'lg' (large)
        icon_name: Lucide icon name (e.g., 'check', 'x', 'send')
        icon_right: Place icon on the right side
        full_width: Make button full width
        disabled: Disable the button
        loading: Show loading spinner
        **kwargs: Extra button attrs (type, onclick, name, value, cls, etc.)
    """
    classes = ["btn", f"btn--{variant}"]

    if size:
        classes.append(f"btn--{size}")
    if full_width:
        classes.append("btn--full")
    if disabled:
        classes.append("btn--disabled")
    if loading:
        classes.append("btn--loading")

    if "cls" in kwargs:
        classes.append(kwargs.pop("cls"))

    content = []
    icon_size = 14 if size == "sm" else (18 if size == "lg" else 16)

    if icon_name and not icon_right:
        content.append(icon(icon_name, size=icon_size))

    if label:
        content.append(label)

    if icon_name and icon_right:
        content.append(icon(icon_name, size=icon_size))

    return Button(
        *content,
        cls=" ".join(classes),
        disabled=disabled or loading,
        **kwargs,
    )
