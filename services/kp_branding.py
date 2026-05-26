"""Master Bearing КП branding constants.

Single source of truth for every brand-specific value the KP renderer uses:
palette, logo HTML fragment, hero illustration paths, page-1 footer feature
tiles, default footer phone/site/email, default subtitle, and the font
directory.

This iteration ships exactly one brand (Master Bearing). Adding a second
brand later means adding one more ``KpBranding`` constant in this module
and a lookup function — no renderer code changes (see design.md ADR-2).

The renderer must never reach into the file system on its own — anything
brand-related must come through a ``KpBranding`` instance. That contract is
what isolates layout code from brand identity.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

_KP_STATIC = Path(__file__).parent / "static" / "kp"
_KP_ICONS = _KP_STATIC / "icons"
_KP_FONTS = Path(__file__).parent / "fonts" / "Inter"


def _load_svg(name: str) -> str:
    """Read an inline SVG fragment from ``services/static/kp/icons``."""
    return (_KP_ICONS / name).read_text(encoding="utf-8")


def _load_logo() -> str:
    """Return an ``<img>`` tag embedding the brand logo as a base64 data URI.

    Inlined rather than referenced via ``file://`` for the same reason fonts
    are inlined in ``kp_export`` — chromium-headless-shell drops ``file://``
    asset URLs and renders an alt-text fallback (ADR-8). Base64 adds ~220 KB
    to the in-memory HTML payload, acceptable for a single render pass.

    The logo PNG is blue-on-transparent. The CSS ``.kp-logo`` rule applies
    ``filter: brightness(0) invert(1)`` so it renders white on the blue
    header bar — preserving the original layout's white-mark-on-blue look
    without needing two separate logo assets.
    """
    png_bytes = (_KP_STATIC / "master-bearing-logo.png").read_bytes()
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return (
        f'<img class="kp-logo__img" '
        f'src="data:image/png;base64,{b64}" '
        f'alt="Master Bearing"/>'
    )


@dataclass(frozen=True)
class FooterFeature:
    """One tile in the page-1 footer feature strip.

    The Master Bearing layout reserves the four-column strip for these tiles
    (e.g. НАДЕЖНЫЕ ПОСТАВКИ). Each tile is icon + two short uppercase lines.
    """

    icon_svg: str
    title_line_1: str
    title_line_2: str


@dataclass(frozen=True)
class KpBranding:
    """All brand-specific values consumed by the КП renderer.

    Fields are immutable. Anything that varies between brands lives here;
    anything that's layout-only (grid columns, paddings, font weights) lives
    in the renderer's CSS.
    """

    name: str
    primary_blue: str
    primary_red: str
    accent_cream: str
    logo_html: str
    hero_machinery_path: Path
    mountains_path: Path
    default_subtitle: str
    page1_footer_features: Tuple[FooterFeature, FooterFeature, FooterFeature, FooterFeature]
    page2_footer_phone: str
    page2_footer_site: str
    page2_footer_email: str
    font_dir: Path
    icon_dir: Path


MASTER_BEARING: KpBranding = KpBranding(
    name="Master Bearing",
    primary_blue="#1c3e87",
    primary_red="#d6202a",
    accent_cream="#fbf6ec",
    logo_html=_load_logo(),
    hero_machinery_path=_KP_STATIC / "hero-machinery.png",
    mountains_path=_KP_STATIC / "mountains.png",
    default_subtitle="на поставку крупной спецтехники",
    page1_footer_features=(
        FooterFeature(
            icon_svg=_load_svg("shield.svg"),
            title_line_1="НАДЕЖНЫЕ",
            title_line_2="ПОСТАВКИ",
        ),
        FooterFeature(
            icon_svg=_load_svg("shield-check.svg"),
            title_line_1="КАЧЕСТВЕННАЯ",
            title_line_2="ПРОДУКЦИЯ",
        ),
        FooterFeature(
            icon_svg=_load_svg("cog.svg"),
            title_line_1="ТЕХНИЧЕСКАЯ",
            title_line_2="ПОДДЕРЖКА",
        ),
        FooterFeature(
            icon_svg=_load_svg("handshake.svg"),
            title_line_1="ИНДИВИДУАЛЬНЫЙ",
            title_line_2="ПОДХОД",
        ),
    ),
    page2_footer_phone="8-800-350-21-34",
    page2_footer_site="www.masterbearing.ru",
    page2_footer_email="order@masterbearing.ru",
    font_dir=_KP_FONTS,
    icon_dir=_KP_ICONS,
)
