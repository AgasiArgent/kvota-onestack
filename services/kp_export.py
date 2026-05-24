"""KP (commercial proposal) PDF renderer.

Produces a two-page A4 portrait PDF for heavy-machinery commercial proposals
in the Master Bearing brand style. Entry points:

- ``render_proposal_html(proposal, branding=MASTER_BEARING) -> str``
  Returns the full HTML document. Used by unit tests that assert structure
  without launching the browser.
- ``render_proposal_pdf_async(proposal, branding=MASTER_BEARING) -> bytes``
  Renders the HTML via headless Chromium (Playwright) and returns PDF bytes.
  Awaited by ``api/kp.py:render_pdf``.
- ``render_proposal_pdf(proposal, branding=MASTER_BEARING) -> bytes``
  Synchronous convenience wrapper around the async version, for use from
  tests and CLI scripts. Calls ``asyncio.run``; do not invoke from inside an
  active event loop (the FastAPI handler awaits the async version directly).

The renderer never touches the database (REQ-20). All inputs come from a
``KpProposal`` dataclass instance built by the API handler; all branding
values come from a ``KpBranding`` instance (default Master Bearing).

Design notes:
- Inter font is bundled at ``services/fonts/Inter/`` and embedded via
  ``@font-face`` blocks whose ``src`` is a base64 ``data:`` URI. Inlined
  rather than referenced via ``file://`` because Playwright's
  chromium-headless-shell silently drops ``file://`` font URLs and falls
  back to DejaVu — which renders Cyrillic but loses the Inter typography
  (ADR-8). The inlined fonts add ~380 KB to the in-memory HTML payload.
- Chromium renders the layout instead of WeasyPrint (ADR-9). The HTML/CSS
  port is unchanged; only the rendering engine swapped after WeasyPrint
  output was found visually unacceptable (ghost headline text, mis-sized
  hero illustration, off-grid info rows).
- Every clip-path bar is paired with an inline SVG fallback polygon so the
  bar still appears even if a particular browser mis-handles the angle
  (ADR-4 — originally written for WeasyPrint, retained as belt-and-braces).
- Item rows pad to ≥5, spec/packaging rows pad to ≥8, condition rows pad
  to ≥3 — preserves visual rhythm per REQ-4.4 / 6.3 / 7.4 / 8.3.
"""

from __future__ import annotations

import asyncio
import html
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Tuple

# playwright is imported lazily inside ``render_proposal_pdf_async`` so that
# unit tests that exercise the HTML builder, dataclasses, or helpers can run
# in environments without the chromium browser installed (CI workers without
# the playwright apt deps, local dev environments missing the runtime).
from services.kp_branding import KpBranding, MASTER_BEARING


# ---------------------------------------------------------------------------
# Immutable form-snapshot dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KpItem:
    """One row of the page-1 equipment items table."""

    name: str = ""
    model: str = ""
    qty: str = ""  # kept as a string; parsed defensively by _to_decimal
    price: str = ""


@dataclass(frozen=True)
class KpPackagingItem:
    """One row of the page-2 КОМПЛЕКТАЦИЯ checkbox list."""

    text: str = ""
    checked: bool = False


@dataclass(frozen=True)
class KpServices:
    """Six fixed page-2 additional-service checkboxes."""

    delivery: bool = False
    training: bool = False
    supervision: bool = False
    warranty: bool = False
    commissioning: bool = False
    service: bool = False


@dataclass(frozen=True)
class KpProposal:
    """Validated form snapshot. Fields are deliberately optional and default
    to empty values so the renderer never crashes on partial input.
    """

    subtitle: str = ""
    supplier: str = ""
    manager: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    basis: str = ""
    payment: str = ""
    date: str = ""
    lead: str = ""
    amount: str = ""
    price_includes: str = ""
    items: Tuple[KpItem, ...] = ()
    notes: str = ""
    specs: Tuple[str, ...] = ()
    packaging: Tuple[KpPackagingItem, ...] = ()
    conditions: Tuple[str, ...] = ()
    services: KpServices = field(default_factory=KpServices)
    notes2: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    contact_site: str = ""
    contact_address: str = ""
    foot_phone: str = ""
    foot_site: str = ""
    foot_email: str = ""


# ---------------------------------------------------------------------------
# Number helpers
# ---------------------------------------------------------------------------


# Narrow no-break space — used as the Russian thousands separator.
_NNBSP = " "


def _to_decimal(value: object) -> Decimal | None:
    """Parse a user-entered numeric string defensively.

    Strips ASCII / non-breaking / narrow no-break spaces, allows comma OR
    dot as the decimal mark. Returns ``None`` on parse failure or empty.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Strip all flavours of space the user might paste in.
    cleaned = (
        s.replace(" ", "")
        .replace("\xa0", "")  # non-breaking
        .replace(" ", "")  # narrow no-break
        .replace(",", ".")
    )
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _fmt_ru(value: object) -> str:
    """Format a numeric-ish value with Russian thousand separators.

    Behavior:
    - ``None`` / empty → empty string.
    - Parseable number → grouped with U+202F (narrow no-break space) and
      decimal mark as ``,`` per Russian locale.
    - Unparseable string → returned verbatim (the user sees what they typed
      rather than "NaN" or a crash) per REQ-3.4.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    parsed = _to_decimal(s)
    if parsed is None:
        return s
    # Normalize: integer part with thousand-separator, decimal part if any.
    sign = "-" if parsed < 0 else ""
    abs_val = abs(parsed)
    int_part, _, frac_part = format(abs_val, "f").partition(".")
    # Strip trailing zeros from fraction (matches "ru-RU" toLocaleString
    # with maximumFractionDigits: 2 from the design JS).
    if frac_part:
        frac_part = frac_part.rstrip("0")
    # Group integer part in 3-digit blocks from the right.
    grouped = ""
    for i, ch in enumerate(reversed(int_part)):
        if i > 0 and i % 3 == 0:
            grouped = _NNBSP + grouped
        grouped = ch + grouped
    if frac_part:
        return f"{sign}{grouped},{frac_part}"
    return f"{sign}{grouped}"


def calc_row_total(item: KpItem) -> Decimal | None:
    """Per-row total (qty * price). Returns None when either side is invalid.

    Used by the renderer to fill the rightmost ``Сумма`` cell; ``None`` →
    blank cell per REQ-4.7.
    """
    qty = _to_decimal(item.qty)
    price = _to_decimal(item.price)
    if qty is None or price is None:
        return None
    return qty * price


def calc_grand_total(items: Tuple[KpItem, ...]) -> Decimal:
    """Sum of valid row totals. Rows with invalid qty or price contribute 0."""
    total = Decimal("0")
    for item in items:
        rt = calc_row_total(item)
        if rt is not None:
            total += rt
    return total


# ---------------------------------------------------------------------------
# Padding helpers — preserve visual rhythm even when the user under-fills
# ---------------------------------------------------------------------------


def _pad_items(items: Tuple[KpItem, ...], minimum: int) -> Tuple[KpItem, ...]:
    """Return at least ``minimum`` item rows, padding with empty KpItem."""
    if len(items) >= minimum:
        return items
    padding = tuple(KpItem() for _ in range(minimum - len(items)))
    return items + padding


def _pad_strings(values: Tuple[str, ...], minimum: int) -> Tuple[str, ...]:
    if len(values) >= minimum:
        return values
    return values + tuple("" for _ in range(minimum - len(values)))


def _pad_packaging(
    values: Tuple[KpPackagingItem, ...], minimum: int
) -> Tuple[KpPackagingItem, ...]:
    if len(values) >= minimum:
        return values
    return values + tuple(KpPackagingItem() for _ in range(minimum - len(values)))


def _e(value: object) -> str:
    """HTML-escape user-supplied text."""
    if value is None:
        return ""
    return html.escape(str(value))


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _kp_styles(branding: KpBranding) -> str:
    """Return the inlined CSS used by both pages.

    Brand colors are interpolated from the ``KpBranding`` instance; the rest
    is a near-verbatim port of ``kp.css`` from the design prototype with:
    - ``@font-face`` blocks embedding the bundled Inter TTFs as base64
      ``data:`` URIs (Playwright's chromium-headless-shell ignores
      ``file://`` src URLs as a security default, leaving the renderer to
      fall back to DejaVu and quietly break Cyrillic glyphs).
    - ``font-family: 'Inter'`` everywhere the design said Plus Jakarta Sans
      (Cyrillic coverage, see ADR-8).

    ``KpBranding`` is ``@dataclass(frozen=True)`` so it's hashable —
    caching by the branding instance keeps the per-render cost at ~zero
    once a brand has been seen for the first time. Iteration 1 ships a
    single brand so the cache holds one entry; ``maxsize=4`` leaves
    headroom for the multi-brand future without unbounded growth.
    """
    import base64

    blue = branding.primary_blue
    red = branding.primary_red
    cream = branding.accent_cream

    # Map weight → bundled filename. The font files were dropped in by
    # Wave 1 with the names below; if a future weight is added, extend the
    # tuple and the @font-face block.
    #
    # We base64-inline the font bytes directly into the @font-face src so
    # the rendering Chromium never has to touch the file system. This adds
    # ~380 KB to the HTML payload (4 weights × ~94 KB each), traded for
    # guaranteed font embedding regardless of how the browser was launched.
    font_face_blocks = []
    for weight, fname in (
        (400, "Inter-regular.ttf"),
        (500, "Inter-500.ttf"),
        (600, "Inter-600.ttf"),
        (700, "Inter-700.ttf"),
    ):
        ttf_path = branding.font_dir / fname
        b64 = base64.b64encode(ttf_path.read_bytes()).decode("ascii")
        font_face_blocks.append(
            f"""@font-face {{
            font-family: 'Inter';
            font-style: normal;
            font-weight: {weight};
            src: url('data:font/ttf;base64,{b64}') format('truetype');
        }}"""
        )
    font_face = "\n".join(font_face_blocks)

    return f"""
{font_face}

@page {{ size: A4 portrait; margin: 0; }}

html, body {{
    margin: 0;
    padding: 0;
    background: #fff;
    font-family: 'Inter', sans-serif;
}}

.kp-page {{
    width: 210mm;
    height: 297mm;
    background: #fff;
    color: #0c1730;
    position: relative;
    overflow: hidden;
    page-break-after: always;
}}
.kp-page:last-child {{ page-break-after: auto; }}
.kp-page * {{ box-sizing: border-box; }}

/* Brand color tokens (interpolated from KpBranding) */
.kp-page {{
    --kp-blue: {blue};
    --kp-red: {red};
    --kp-cream: {cream};
    --kp-text: #0c1730;
    --kp-text-muted: #5b6378;
    --kp-line: #c5cee4;
    --kp-line-soft: #dee5f3;
}}

/* ============================================================
   Logo (MASTER BEARING wordmark)
   ============================================================ */
.kp-logo {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: #fff;
    font-weight: 700;
    letter-spacing: 0.02em;
}}
.kp-logo svg {{ width: 38px; height: 38px; flex-shrink: 0; }}
.kp-logo__text {{
    display: inline-flex;
    flex-direction: column;
    line-height: 0.95;
    font-size: 17px;
    letter-spacing: 0.04em;
}}
.kp-logo__text span {{ font-weight: 700; }}

/* ============================================================
   PAGE 1 — Header
   ============================================================ */
.kp1-head {{ height: 290px; position: relative; overflow: hidden; }}
.kp1-head__bluebar {{
    position: absolute; top: 0; left: 0;
    width: 410px; height: 110px;
    background: {blue};
    clip-path: polygon(0 0, 100% 0, calc(100% - 56px) 100%, 0 100%);
}}
.kp1-head__bluebar svg {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
}}
.kp1-head__redbar {{
    position: absolute; top: 0; left: 408px;
    width: 70px; height: 110px;
    background: {red};
    clip-path: polygon(56px 0, 100% 0, calc(100% - 56px) 100%, 0 100%);
}}
.kp1-head__redbar svg {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
}}
.kp1-head__logo {{ position: absolute; top: 30px; left: 38px; z-index: 2; }}
.kp1-head__illu {{
    position: absolute; top: 78px; right: 24px;
    width: 380px; height: 220px;
}}
.kp1-head__illu img {{ width: 100%; height: 100%; object-fit: contain; object-position: right center; }}

.kp1-title {{ position: absolute; left: 38px; top: 130px; z-index: 3; }}
.kp1-title h1 {{
    margin: 0;
    font-size: 44px;
    font-weight: 700;
    color: {blue};
    letter-spacing: -0.01em;
    line-height: 0.98;
    text-transform: uppercase;
}}
.kp1-title .sub {{
    margin-top: 14px;
    font-size: 15px;
    color: #0c1730;
    font-weight: 500;
}}
.kp1-title .underline {{
    width: 56px; height: 3px;
    background: {red};
    margin-top: 12px;
    border-radius: 2px;
}}

/* ============================================================
   Section headers
   ============================================================ */
.kp-section-h {{
    display: flex; align-items: center; gap: 10px;
    margin: 6px 0 14px;
}}
.kp-section-h .icon-sq {{
    width: 22px; height: 22px;
    background: {blue};
    border-radius: 4px;
    display: inline-flex; align-items: center; justify-content: center;
    color: #fff;
}}
.kp-section-h .icon-sq svg {{ width: 14px; height: 14px; stroke: #fff; }}
.kp-section-h .label {{
    font-size: 14px;
    font-weight: 700;
    color: {blue};
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}

/* ============================================================
   PAGE 1 — Body
   ============================================================ */
.kp1-body {{
    position: absolute;
    inset: 290px 38px 100px 38px;
    display: flex; flex-direction: column;
}}
.kp-info-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 26px;
    margin-bottom: 14px;
}}
.kp-field {{
    display: grid;
    grid-template-columns: 22px 110px 1fr;
    align-items: center;
    gap: 8px;
    min-height: 34px;
}}
.kp-field__ico {{
    width: 22px; height: 22px;
    background: {blue};
    border-radius: 4px;
    color: #fff;
    display: inline-flex; align-items: center; justify-content: center;
}}
.kp-field__ico svg {{ width: 13px; height: 13px; stroke: #fff; }}
.kp-field__label {{
    font-size: 11.5px;
    color: #0c1730;
    font-weight: 500;
}}
.kp-field__value {{
    border: 1px solid #c5cee4;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 11.5px;
    color: #0c1730;
    background: #fff;
    min-height: 26px;
    display: flex; align-items: center;
    white-space: pre-wrap;
    word-break: break-word;
    position: relative;
}}
.kp-field__value.tall {{
    min-height: 56px;
    align-items: flex-start;
    line-height: 1.4;
}}
.kp-field__value.with-suffix {{ padding-right: 22px; }}
.kp-field__value .suffix {{
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: #5b6378;
    font-size: 12px;
}}

/* ============================================================
   PAGE 1 — Items table
   ============================================================ */
.kp-table {{
    margin-top: 8px;
    border: 1px solid {blue};
    border-radius: 4px;
    overflow: hidden;
    font-size: 11px;
}}
.kp-table__head, .kp-table__row {{
    display: grid;
    grid-template-columns: 36px 1.8fr 1.8fr 0.7fr 1fr 1fr;
}}
.kp-table__head {{
    background: {blue};
    color: #fff;
}}
.kp-table__head > div {{
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 600;
    border-right: 1px solid rgba(255,255,255,0.25);
    text-align: left;
}}
.kp-table__head > div:last-child {{ border-right: none; }}
.kp-table__head .right {{ text-align: center; }}

.kp-table__row {{
    background: #fff;
    border-top: 1px solid #c5cee4;
}}
.kp-table__row > div {{
    padding: 8px 10px;
    border-right: 1px solid #c5cee4;
    min-height: 32px;
    font-size: 11.5px;
}}
.kp-table__row > div:last-child {{ border-right: none; }}
.kp-table__row .num {{ text-align: right; }}
.kp-table__row .center {{ text-align: center; color: #5b6378; }}

.kp-table__total {{
    display: grid;
    grid-template-columns: 36px 1.8fr 1.8fr 0.7fr 1fr 1fr;
    border-top: 1px solid {blue};
}}
.kp-table__total .gap {{ background: #fff; }}
.kp-table__total .label {{
    grid-column: 5;
    background: {blue};
    color: #fff;
    padding: 10px 12px;
    font-size: 13px;
    font-weight: 700;
    text-align: right;
    letter-spacing: 0.02em;
}}
.kp-table__total .value {{
    background: #fff;
    padding: 10px 12px;
    font-size: 13px;
    font-weight: 700;
    text-align: right;
    color: #0c1730;
    border-left: 1px solid {blue};
}}

/* ============================================================
   PAGE 1 — Notes + signatures
   ============================================================ */
.kp1-notes {{
    margin-top: 18px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
    align-items: end;
}}
.kp1-notes .l {{ font-size: 11.5px; color: #0c1730; margin-bottom: 6px; }}
.kp1-notes .box {{
    min-height: 64px;
    border: 1px solid #c5cee4;
    border-radius: 4px;
    padding: 8px 10px;
    font-size: 11px;
    color: #0c1730;
    white-space: pre-wrap;
}}
.kp1-sigs {{
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 24px;
    align-items: end;
    padding-bottom: 6px;
}}
.kp1-sigs .sig {{
    display: flex; flex-direction: column;
    align-items: center; gap: 4px;
}}
.kp1-sigs .sig .line {{
    width: 100%;
    border-bottom: 1px solid #0c1730;
    height: 26px;
}}
.kp1-sigs .sig .cap {{ font-size: 11px; color: #0c1730; }}

/* ============================================================
   PAGE 1 — Footer
   ============================================================ */
.kp1-foot {{
    position: absolute;
    left: 0; right: 0; bottom: 0;
    height: 90px;
    background: {blue};
    display: flex;
    align-items: center;
    color: #fff;
    overflow: hidden;
}}
.kp1-foot__red {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 60px;
    background: {red};
    clip-path: polygon(0 0, 100% 0, calc(100% - 40px) 100%, 0 100%);
}}
.kp1-foot__red svg {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
.kp1-foot__items {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    flex: 1;
    padding: 0 40px 0 80px;
    gap: 16px;
}}
.kp1-foot__item {{ display: flex; align-items: center; gap: 12px; }}
.kp1-foot__item .ico {{
    width: 30px; height: 30px;
    border: 1.5px solid #fff;
    border-radius: 999px;
    display: inline-flex; align-items: center; justify-content: center;
}}
.kp1-foot__item .ico svg {{ width: 16px; height: 16px; stroke: #fff; }}
.kp1-foot__item .txt {{
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    line-height: 1.15;
}}

/* ============================================================
   PAGE 2 — Header
   ============================================================ */
.kp2-head {{
    height: 110px;
    position: relative;
}}
.kp2-head__bluebar {{
    position: absolute;
    top: 0; left: 0;
    width: 280px;
    height: 100%;
    background: {blue};
    clip-path: polygon(0 0, 100% 0, calc(100% - 38px) 100%, 0 100%);
}}
.kp2-head__bluebar svg {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
.kp2-head__logo {{
    position: absolute;
    top: 50%; left: 38px;
    transform: translateY(-50%);
    z-index: 2;
}}
.kp2-head__title {{
    position: absolute;
    left: 290px; top: 50%;
    transform: translateY(-50%);
    z-index: 1;
}}
.kp2-head__title h2 {{
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    color: {blue};
    text-transform: uppercase;
    letter-spacing: -0.005em;
    line-height: 1.05;
}}
.kp2-head__title .sub {{
    margin-top: 4px;
    font-size: 12px;
    color: #0c1730;
}}
.kp2-head__pageno {{
    position: absolute;
    right: 0; top: 24px;
    background: {red};
    color: #fff;
    padding: 8px 18px;
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 0.04em;
}}

/* ============================================================
   PAGE 2 — Body
   ============================================================ */
.kp2-body {{
    padding: 24px 38px 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
    position: absolute;
    inset: 110px 0 60px 0;
}}
.kp2-twocol {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
}}
.kp-block {{
    border: 1px solid #c5cee4;
    border-radius: 4px;
    background: #fff;
    overflow: hidden;
    display: flex; flex-direction: column;
}}
.kp-block__head {{
    background: {blue};
    color: #fff;
    padding: 8px 14px;
    display: flex; align-items: center; gap: 8px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
.kp-block__head svg {{ width: 14px; height: 14px; stroke: #fff; }}
.kp-block__body {{ padding: 10px 14px; flex: 1; }}

.kp-bullet-list {{
    display: flex; flex-direction: column;
    gap: 10px;
    padding: 6px 0 0;
}}
.kp-bullet-list .item {{
    display: grid;
    grid-template-columns: 12px 1fr;
    gap: 8px;
    align-items: end;
    min-height: 26px;
}}
.kp-bullet-list .item .b {{
    width: 4px; height: 4px;
    border-radius: 999px;
    background: #0c1730;
    margin-bottom: 8px;
}}
.kp-bullet-list .item .v {{
    border-bottom: 1px solid #c5cee4;
    font-size: 11.5px;
    min-height: 18px;
    padding-bottom: 2px;
}}

.kp-check-list {{
    display: flex; flex-direction: column;
    gap: 10px;
    padding: 6px 0 0;
}}
.kp-check-list .item {{
    display: grid;
    grid-template-columns: 14px 1fr;
    gap: 10px;
    align-items: end;
    min-height: 26px;
}}
.kp-check-list .item .c {{
    width: 12px; height: 12px;
    border: 1.2px solid {blue};
    border-radius: 2px;
    margin-bottom: 5px;
    position: relative;
}}
.kp-check-list .item .c.checked {{
    background: {blue};
}}
.kp-check-list .item .v {{
    border-bottom: 1px solid #c5cee4;
    font-size: 11.5px;
    min-height: 18px;
    padding-bottom: 2px;
}}

.kp-conditions {{
    display: flex; flex-direction: column; gap: 8px;
}}
.kp-conditions .row {{
    display: grid;
    grid-template-columns: 12px 1fr;
    gap: 10px;
    align-items: end;
    min-height: 22px;
}}
.kp-conditions .row .b {{
    width: 4px; height: 4px;
    border-radius: 999px;
    background: #0c1730;
    margin-bottom: 7px;
}}
.kp-conditions .row .v {{
    font-size: 12px;
    border-bottom: 1px solid #c5cee4;
    padding-bottom: 2px;
    min-height: 18px;
}}

.kp2-services {{
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 14px;
}}
.kp-services {{
    border: 1px solid #c5cee4;
    border-radius: 4px;
    padding: 12px 16px;
}}
.kp-services__head {{
    display: flex; align-items: baseline; gap: 8px;
    font-size: 12px; font-weight: 700;
    color: {blue};
    text-transform: uppercase; letter-spacing: 0.06em;
    margin-bottom: 10px;
}}
.kp-services__head .ico {{
    width: 18px; height: 18px;
    background: {blue};
    border-radius: 3px;
    display: inline-flex; align-items: center; justify-content: center;
    align-self: center;
}}
.kp-services__head .ico svg {{ width: 11px; height: 11px; stroke: #fff; }}
.kp-services__head .req {{
    text-transform: none;
    font-weight: 500;
    font-size: 11px;
    color: #5b6378;
}}
.kp-services__grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 12px;
}}
.kp-services__item {{
    display: grid;
    grid-template-columns: 18px 1fr 14px;
    gap: 8px;
    align-items: center;
    font-size: 11.5px;
}}
.kp-services__item .ico {{
    width: 18px; height: 18px;
    background: {blue};
    border-radius: 3px;
    display: inline-flex; align-items: center; justify-content: center;
}}
.kp-services__item .ico svg {{ width: 11px; height: 11px; stroke: #fff; }}
.kp-services__item .c {{
    width: 12px; height: 12px;
    border: 1.2px solid {blue};
    border-radius: 2px;
}}
.kp-services__item .c.checked {{ background: {blue}; }}

.kp-notes-box {{
    border: 1px dashed #c5cee4;
    border-radius: 4px;
    padding: 12px 16px;
    display: flex; flex-direction: column;
}}
.kp-notes-box__head {{
    font-size: 12px;
    font-weight: 700;
    color: {blue};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 10px;
}}
.kp-notes-box__body {{
    flex: 1;
    font-size: 11.5px;
    color: #0c1730;
    white-space: pre-wrap;
}}

.kp2-contacts {{
    display: grid;
    grid-template-columns: 1.1fr 1.2fr;
    gap: 24px;
    position: relative;
    margin-top: 4px;
    padding-bottom: 8px;
}}
.kp-contacts {{ display: flex; flex-direction: column; gap: 8px; }}
.kp-contacts__head {{
    font-size: 14px;
    font-weight: 700;
    color: {blue};
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}}
.kp-contacts__row {{
    display: grid;
    grid-template-columns: 22px 60px 1fr;
    align-items: end;
    gap: 8px;
    min-height: 26px;
}}
.kp-contacts__row .ico {{
    width: 22px; height: 22px;
    background: {blue};
    border-radius: 4px;
    display: inline-flex; align-items: center; justify-content: center;
}}
.kp-contacts__row .ico svg {{ width: 13px; height: 13px; stroke: #fff; }}
.kp-contacts__row .l {{
    font-size: 11.5px; color: #0c1730;
    padding-bottom: 2px;
}}
.kp-contacts__row .v {{
    font-size: 11.5px;
    color: #0c1730;
    border-bottom: 1px solid #c5cee4;
    padding: 2px 4px;
    min-height: 20px;
}}

.kp-thanks {{
    position: relative;
    padding-right: 20px;
}}
.kp-thanks__text {{
    font-size: 15px;
    color: #0c1730;
    line-height: 1.4;
}}
.kp-thanks__mtn {{
    position: absolute;
    right: -20px; bottom: -8px;
    width: 300px; height: 130px;
}}
.kp-thanks__mtn img {{
    width: 100%; height: 100%;
    object-fit: contain;
    object-position: right bottom;
}}

.kp2-foot {{
    position: absolute;
    left: 0; right: 0; bottom: 0;
    height: 60px;
    background: {blue};
    display: flex;
    align-items: center;
    color: #fff;
    overflow: hidden;
}}
.kp2-foot__red {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 60px;
    background: {red};
    clip-path: polygon(0 0, 100% 0, calc(100% - 40px) 100%, 0 100%);
}}
.kp2-foot__red svg {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
.kp2-foot__items {{
    display: grid;
    grid-template-columns: 1fr 1.2fr 1.4fr;
    flex: 1;
    padding: 0 32px 0 78px;
    gap: 16px;
    align-items: center;
}}
.kp2-foot__item {{
    display: flex; align-items: center; gap: 10px;
    font-size: 12.5px;
    font-weight: 500;
}}
.kp2-foot__item .ico {{
    width: 26px; height: 26px;
    border: 1.5px solid #fff;
    border-radius: 999px;
    display: inline-flex; align-items: center; justify-content: center;
}}
.kp2-foot__item .ico svg {{ width: 13px; height: 13px; stroke: #fff; }}
"""


# ---------------------------------------------------------------------------
# Inline icon library — borrowed from services/static/kp/icons/*.svg
# ---------------------------------------------------------------------------


# Cache: load every SVG once per (branding, name). Keyed by branding so a
# future second brand with its own icon dir doesn't poison the cache.
_ICONS_CACHE: dict[tuple[int, str], str] = {}


def _icon(branding: KpBranding, name: str) -> str:
    """Return an inline SVG fragment for a named icon.

    A missing icon file is a deploy / asset-bundle bug, not a runtime
    condition to paper over — the SVGs are committed alongside the code.
    Raise so the failure surfaces during build, render, and tests instead
    of silently shipping a half-rendered PDF.
    """
    cache_key = (id(branding), name)
    if cache_key in _ICONS_CACHE:
        return _ICONS_CACHE[cache_key]
    path = branding.icon_dir / f"{name}.svg"
    if not path.is_file():
        raise FileNotFoundError(
            f"KP icon missing: {name} (expected at {path})"
        )
    svg = path.read_text(encoding="utf-8")
    _ICONS_CACHE[cache_key] = svg
    return svg


# ---------------------------------------------------------------------------
# SVG polygon fallbacks for clip-path bars (ADR-4 — belt and braces)
# ---------------------------------------------------------------------------


def _svg_polygon(points: str, fill: str, viewbox: str = "0 0 100 100") -> str:
    """Return an inline SVG polygon as a clip-path fallback."""
    return (
        f'<svg preserveAspectRatio="none" viewBox="{viewbox}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<polygon points="{points}" fill="{fill}"/>'
        f"</svg>"
    )


# ---------------------------------------------------------------------------
# Page 1
# ---------------------------------------------------------------------------


def _kp_field(
    branding: KpBranding,
    icon_name: str,
    label: str,
    value: str,
    suffix: str = "",
    tall: bool = False,
) -> str:
    """One row of the page-1 info grid."""
    suffix_html = f'<span class="suffix">{_e(suffix)}</span>' if suffix else ""
    value_classes = []
    if suffix:
        value_classes.append("with-suffix")
    if tall:
        value_classes.append("tall")
    cls = (" " + " ".join(value_classes)) if value_classes else ""
    return f"""
    <div class="kp-field">
        <div class="kp-field__ico">{_icon(branding, icon_name)}</div>
        <div class="kp-field__label">{_e(label)}</div>
        <div class="kp-field__value{cls}">{_e(value)}{suffix_html}</div>
    </div>
    """


def _page_1(proposal: KpProposal, branding: KpBranding) -> str:
    """Build page-1 HTML.

    Sections: corner blue/red bars, hero illustration, headline, info grid
    (11 fields), items table padded to ≥5 rows with auto-total, notes box
    and signatures row, four footer feature tiles.
    """
    subtitle = proposal.subtitle or branding.default_subtitle

    # Header bars — clip-path with SVG polygon fallback (ADR-4).
    blue_poly = _svg_polygon(
        points="0,0 100,0 86,100 0,100", fill=branding.primary_blue
    )
    red_poly = _svg_polygon(
        points="80,0 100,0 20,100 0,100", fill=branding.primary_red
    )
    foot_red_poly = _svg_polygon(
        points="0,0 100,0 33,100 0,100", fill=branding.primary_red
    )

    hero_uri = branding.hero_machinery_path.resolve().as_uri()

    # Info-grid field rows (REQ-3.1: 11 labelled fields).
    info_rows = "".join(
        [
            _kp_field(branding, "user-badge", "Поставщик:", proposal.supplier),
            _kp_field(branding, "doc", "Условия оплаты:", proposal.payment),
            _kp_field(branding, "user-tie", "Менеджер отдела продаж:", proposal.manager),
            _kp_field(branding, "cal", "Дата предоставления:", proposal.date),
            _kp_field(branding, "phone", "Телефон:", proposal.phone),
            _kp_field(branding, "clock", "Срок поставки:", proposal.lead),
            _kp_field(branding, "mail", "E-mail:", proposal.email),
            _kp_field(
                branding,
                "ruble",
                "Сумма КП:",
                _fmt_ru(proposal.amount) if proposal.amount else "",
                suffix="₽",
            ),
            _kp_field(branding, "pin", "Адрес поставки:", proposal.address),
            _kp_field(branding, "pkg", "Цена включает:", proposal.price_includes, tall=True),
            _kp_field(branding, "truck", "Базис поставки:", proposal.basis),
        ]
    )

    # Items table — pad to ≥5 rows.
    items = _pad_items(proposal.items, minimum=5)
    item_rows_html = []
    for idx, item in enumerate(items):
        non_empty = bool(
            item.name or item.model or item.qty or item.price
        )
        row_total = calc_row_total(item)
        row_total_str = _fmt_ru(str(row_total)) if row_total is not None else ""
        item_rows_html.append(
            f"""
            <div class="kp-table__row">
                <div class="center">{(idx + 1) if non_empty else ""}</div>
                <div>{_e(item.name)}</div>
                <div>{_e(item.model)}</div>
                <div class="num">{_e(item.qty)}</div>
                <div class="num">{_fmt_ru(item.price) if item.price else ""}</div>
                <div class="num">{row_total_str}</div>
            </div>
            """
        )
    grand_total = calc_grand_total(proposal.items)
    grand_total_str = (
        f"{_fmt_ru(str(grand_total))} ₽" if grand_total > 0 else ""
    )

    # Footer features — exactly four tiles from branding (REQ-15.5).
    feature_tiles = "".join(
        f"""
        <div class="kp1-foot__item">
            <div class="ico">{ff.icon_svg}</div>
            <div class="txt">{_e(ff.title_line_1)}<br/>{_e(ff.title_line_2)}</div>
        </div>
        """
        for ff in branding.page1_footer_features
    )

    return f"""
    <div class="kp-page">
        <div class="kp1-head">
            <div class="kp1-head__bluebar">{blue_poly}</div>
            <div class="kp1-head__redbar">{red_poly}</div>
            <div class="kp1-head__logo">
                <div class="kp-logo">
                    {branding.logo_svg}
                    <div class="kp-logo__text">
                        <span>MASTER</span><span>BEARING</span>
                    </div>
                </div>
            </div>
            <div class="kp1-head__illu">
                <img src="{hero_uri}" alt=""/>
            </div>
            <div class="kp1-title">
                <h1>КОММЕРЧЕСКОЕ<br/>ПРЕДЛОЖЕНИЕ</h1>
                <div class="sub">{_e(subtitle)}</div>
                <div class="underline"></div>
            </div>
        </div>

        <div class="kp1-body">
            <div class="kp-section-h">
                <div class="icon-sq">{_icon(branding, "shield-doc")}</div>
                <div class="label">ИНФОРМАЦИЯ О ПРЕДЛОЖЕНИИ</div>
            </div>
            <div class="kp-info-grid">{info_rows}</div>

            <div class="kp-section-h" style="margin-top: 16px">
                <div class="icon-sq">{_icon(branding, "list")}</div>
                <div class="label">ПЕРЕЧЕНЬ ТЕХНИКИ И СТОИМОСТЬ</div>
            </div>

            <div class="kp-table">
                <div class="kp-table__head">
                    <div>№</div>
                    <div>Наименование техники</div>
                    <div>Модель / Характеристики</div>
                    <div class="right">Кол-во</div>
                    <div class="right">Цена за ед., ₽</div>
                    <div class="right">Сумма, ₽</div>
                </div>
                {''.join(item_rows_html)}
                <div class="kp-table__total">
                    <div class="label">ИТОГО:</div>
                    <div class="value">{_e(grand_total_str)}</div>
                </div>
            </div>

            <div class="kp1-notes">
                <div class="kp1-notes__notes">
                    <div class="l">Примечания / Дополнительная информация:</div>
                    <div class="box">{_e(proposal.notes)}</div>
                </div>
                <div class="kp1-sigs">
                    <div class="sig">
                        <div class="line"></div>
                        <div class="cap">Подпись</div>
                    </div>
                    <div class="sig">
                        <div class="line"></div>
                        <div class="cap">М.П.</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="kp1-foot">
            <div class="kp1-foot__red">{foot_red_poly}</div>
            <div class="kp1-foot__items">{feature_tiles}</div>
        </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Page 2
# ---------------------------------------------------------------------------


# REQ-9.3 — fixed order + Russian labels for the six service tiles.
_SERVICE_ROWS: Tuple[Tuple[str, str, str], ...] = (
    ("delivery", "truck", "Доставка"),
    ("training", "user-badge", "Обучение операторов"),
    ("supervision", "wrench", "Шеф-монтаж"),
    ("warranty", "shield-check", "Расширенная гарантия"),
    ("commissioning", "cog", "Пусконаладочные работы"),
    ("service", "settings", "Сервисное обслуживание"),
)


def _page_2(proposal: KpProposal, branding: KpBranding) -> str:
    """Build page-2 HTML.

    Sections: header strip with 2/2 page indicator, two-column
    specs+packaging cards (min 8 slots each), conditions list (min 3),
    six service checkbox rows, notes-2 box, contacts panel with mountains
    illustration, page-2 footer.
    """
    subtitle = proposal.subtitle or branding.default_subtitle
    specs = _pad_strings(proposal.specs, minimum=8)
    pkg = _pad_packaging(proposal.packaging, minimum=8)
    conditions = _pad_strings(proposal.conditions, minimum=3)

    blue_poly = _svg_polygon(
        points="0,0 100,0 86,100 0,100", fill=branding.primary_blue
    )
    foot_red_poly = _svg_polygon(
        points="0,0 100,0 33,100 0,100", fill=branding.primary_red
    )
    mountains_uri = branding.mountains_path.resolve().as_uri()

    spec_rows = "".join(
        f"""
        <div class="item">
            <div class="b"></div>
            <div class="v">{_e(s)}</div>
        </div>
        """
        for s in specs
    )
    pkg_rows = "".join(
        f"""
        <div class="item">
            <div class="c{' checked' if p.checked else ''}"></div>
            <div class="v">{_e(p.text)}</div>
        </div>
        """
        for p in pkg
    )
    condition_rows = "".join(
        f"""
        <div class="row">
            <div class="b"></div>
            <div class="v">{_e(c)}</div>
        </div>
        """
        for c in conditions
    )

    services_html = "".join(
        f"""
        <div class="kp-services__item">
            <div class="ico">{_icon(branding, icon_name)}</div>
            <div>{_e(label)}</div>
            <div class="c{' checked' if getattr(proposal.services, attr) else ''}"></div>
        </div>
        """
        for attr, icon_name, label in _SERVICE_ROWS
    )

    foot_items = "".join(
        f"""
        <div class="kp2-foot__item">
            <div class="ico">{_icon(branding, icon_name)}</div>
            <span>{_e(value or default)}</span>
        </div>
        """
        for icon_name, value, default in (
            ("phone", proposal.foot_phone, branding.page2_footer_phone),
            ("globe", proposal.foot_site, branding.page2_footer_site),
            ("mail", proposal.foot_email, branding.page2_footer_email),
        )
    )

    return f"""
    <div class="kp-page">
        <div class="kp2-head">
            <div class="kp2-head__bluebar">{blue_poly}</div>
            <div class="kp2-head__logo">
                <div class="kp-logo">
                    {branding.logo_svg}
                    <div class="kp-logo__text">
                        <span>MASTER</span><span>BEARING</span>
                    </div>
                </div>
            </div>
            <div class="kp2-head__title">
                <h2>КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ</h2>
                <div class="sub">{_e(subtitle)}</div>
            </div>
            <div class="kp2-head__pageno">2/2</div>
        </div>

        <div class="kp2-body">
            <div class="kp-section-h" style="margin: 0">
                <div class="icon-sq">{_icon(branding, "settings")}</div>
                <div class="label">ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ И КОМПЛЕКТАЦИЯ</div>
            </div>

            <div class="kp2-twocol">
                <div class="kp-block">
                    <div class="kp-block__head">
                        {_icon(branding, "gear")}
                        <span>ОСНОВНЫЕ ХАРАКТЕРИСТИКИ</span>
                    </div>
                    <div class="kp-block__body">
                        <div class="kp-bullet-list">{spec_rows}</div>
                    </div>
                </div>
                <div class="kp-block">
                    <div class="kp-block__head">
                        {_icon(branding, "clock")}
                        <span>КОМПЛЕКТАЦИЯ</span>
                    </div>
                    <div class="kp-block__body">
                        <div class="kp-check-list">{pkg_rows}</div>
                    </div>
                </div>
            </div>

            <div>
                <div class="kp-section-h" style="margin: 4px 0 8px">
                    <div class="icon-sq">{_icon(branding, "shield")}</div>
                    <div class="label">УСЛОВИЯ И ГАРАНТИИ</div>
                </div>
                <div class="kp-conditions">{condition_rows}</div>
            </div>

            <div class="kp2-services">
                <div class="kp-services">
                    <div class="kp-services__head">
                        <div class="ico">{_icon(branding, "tools")}</div>
                        <span>ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ</span>
                        <span class="req">(по запросу)</span>
                    </div>
                    <div class="kp-services__grid">{services_html}</div>
                </div>
                <div class="kp-notes-box">
                    <div class="kp-notes-box__head">ДЛЯ ЗАМЕТОК</div>
                    <div class="kp-notes-box__body">{_e(proposal.notes2)}</div>
                </div>
            </div>

            <div class="kp2-contacts">
                <div class="kp-contacts">
                    <div class="kp-contacts__head">КОНТАКТЫ</div>
                    <div class="kp-contacts__row">
                        <div class="ico">{_icon(branding, "phone")}</div>
                        <div class="l">Телефон:</div>
                        <div class="v">{_e(proposal.contact_phone)}</div>
                    </div>
                    <div class="kp-contacts__row">
                        <div class="ico">{_icon(branding, "mail")}</div>
                        <div class="l">E-mail:</div>
                        <div class="v">{_e(proposal.contact_email)}</div>
                    </div>
                    <div class="kp-contacts__row">
                        <div class="ico">{_icon(branding, "globe")}</div>
                        <div class="l">Сайт:</div>
                        <div class="v">{_e(proposal.contact_site)}</div>
                    </div>
                    <div class="kp-contacts__row">
                        <div class="ico">{_icon(branding, "pin")}</div>
                        <div class="l">Адрес:</div>
                        <div class="v">{_e(proposal.contact_address)}</div>
                    </div>
                </div>
                <div class="kp-thanks">
                    <div class="kp-thanks__text">
                        Благодарим за обращение!<br/>Будем рады сотрудничеству.
                    </div>
                    <div class="kp-thanks__mtn">
                        <img src="{mountains_uri}" alt=""/>
                    </div>
                </div>
            </div>
        </div>

        <div class="kp2-foot">
            <div class="kp2-foot__red">{foot_red_poly}</div>
            <div class="kp2-foot__items">{foot_items}</div>
        </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def render_proposal_html(
    proposal: KpProposal, branding: KpBranding = MASTER_BEARING
) -> str:
    """Compose the full two-page HTML document for the proposal.

    Used by tests that assert structural invariants without paying the
    WeasyPrint cost. Also useful for debugging visual issues by opening
    the result in a browser.
    """
    styles = _kp_styles(branding)
    page1 = _page_1(proposal, branding)
    page2 = _page_2(proposal, branding)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>КП — {_e(proposal.supplier or branding.name)}</title>
<style>{styles}</style>
</head>
<body>
{page1}
{page2}
</body>
</html>"""


async def render_proposal_pdf_async(
    proposal: KpProposal, branding: KpBranding = MASTER_BEARING
) -> bytes:
    """Render the proposal to PDF bytes via headless Chromium.

    Async because the FastAPI handler is async; using ``sync_playwright``
    inside an asyncio event loop raises at runtime. The browser is launched
    once per call (cheap enough at the human-triggered cadence the KP
    Builder sees — ~1 click per minute at most). Header/footer chrome
    suppressed and zero page margins so the proposal's own ``@page`` rules
    own the layout.
    """
    # Lazy import: keep unit tests runnable without playwright installed.
    from playwright.async_api import async_playwright

    html_doc = render_proposal_html(proposal, branding)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        try:
            page = await browser.new_page()
            # ``networkidle`` waits for fonts / images to finish loading
            # so embedded Inter glyphs and the hero PNG land before print.
            await page.set_content(html_doc, wait_until="networkidle")
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                prefer_css_page_size=True,
            )
        finally:
            await browser.close()
    return pdf_bytes


def render_proposal_pdf(
    proposal: KpProposal, branding: KpBranding = MASTER_BEARING
) -> bytes:
    """Synchronous wrapper around :func:`render_proposal_pdf_async`.

    For use from pytest and CLI scripts. The FastAPI handler awaits the
    async version directly — do not call this wrapper from inside an
    active event loop (``asyncio.run`` would raise ``RuntimeError``).
    """
    return asyncio.run(render_proposal_pdf_async(proposal, branding))
