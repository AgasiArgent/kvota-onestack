"""Shim: golden JSON → production ``items`` / ``variables`` shape.

Track A1 of the Calculation Engine verification. This module is the
"тупой шим" the design (§6) calls for: it converts a golden fixture's
``inputs`` block into the exact ``items: list[dict]`` + ``variables: dict``
pair that ``composition_service.get_composed_items()`` produces and
``services.calculation_helpers.build_calculation_inputs()`` consumes.

It performs NO business logic — only a mechanical cell→key remap. All
calculation lives downstream in the locked engine.

Key reconstruction — the эталон base price
-------------------------------------------
The Excel form's purchase-price chain is:

    N16 = IF(country="Китай", K16, K16 / (1 + M16))      # strip supplier VAT
    P16 = N16 * (1 - O16)                                # apply discount

where K16 = "Цена закупки в Ориг. с НДС" (raw input) and N16 = the
VAT-stripped price. In two of the three corpus files K16 is blank — the
form's author typed the price straight into N16. So the *cached* эталон
purchase value is always N16.

``build_calculation_inputs`` feeds the engine ``base_price_VAT`` (= the
engine's K16) and the engine re-derives N16 itself via the same
``K16 / (1 + M16)`` formula, where the engine's M16 comes from the
supplier-country VAT zone.

To make the production path reproduce the эталон N16 we therefore feed:

    purchase_price_original = эталон_N16 * (1 + эталон_M16)
    price_includes_vat      = True

so the engine computes ``N16_engine = (эталон_N16 · (1+M)) / (1+M_engine)``.
When the engine's zone VAT rate ``M_engine`` equals the эталон's ``M16``
(it should — both read the same supplier country) this is эталон_N16
exactly. If they diverge, that divergence is REAL — a genuine
input-mapping defect — and the golden-master test surfaces it rather than
hiding it. (We deliberately do not bypass the engine's VAT step by forcing
a zero-VAT zone: that would mask exactly the kind of mapping bug A1 exists
to catch.)

Pinned live data
----------------
``build_calculation_inputs`` calls ``convert_amount`` (FX) and resolves
import tariffs. The golden-master test monkeypatches those; this shim's
job is only to carry the эталон's per-product FX rate (col Q) and tariff
(col X) into the item dicts so the pinned stubs can read them back.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal

# Excel supplier-country VAT rates ("Ставка НДС в закупке %", col M16) — the
# engine's VAT_SELLER_COUNTRY_MAP, keyed by the SupplierCountry enum value
# that resolve_vat_zone() yields. Used to reconstruct K16 from эталон N16.
# (Kept here, not imported from the engine, because calculation_engine.py is
# frozen and importing it for a constant would couple the shim to it.)
_ZONE_VAT_RATE = {
    "Турция": 0.20,
    "Россия": 0.22,
    "Китай": 0.13,
    "Литва": 0.21,
    "Латвия": 0.21,
    "Болгария": 0.20,
    "Польша": 0.23,
    "ЕС (между странами ЕС)": 0.00,
    "ОАЭ": 0.05,
    "Прочие": 0.00,
}


def _to_pct(fraction) -> float:
    """Excel stores ratios as fractions (0.2112); the engine wants percent.

    ``build_calculation_inputs`` → ``map_variables_to_calculation_input``
    feeds ``markup`` / ``supplier_discount`` / ``import_tariff`` straight
    into the engine, which divides them by 100. So a fraction must be
    scaled ×100 here. A value already ≥1 is assumed to be a percent
    already and passed through.
    """
    if fraction is None:
        return 0.0
    f = float(fraction)
    return f * 100.0 if abs(f) <= 1.0 else f


def golden_to_items_and_variables(golden: dict) -> tuple[list[dict], dict]:
    """Convert one golden fixture into ``(items, variables)``.

    Args:
        golden: A fixture dict as emitted by ``scripts/refresh_golden.py``.

    Returns:
        ``(items, variables)`` ready to feed ``build_calculation_inputs``.
        ``items`` is one dict per product row, in the ``get_composed_items``
        shape. ``variables`` is the flat quote-level dict.

    Engine quote-currency selection
    -------------------------------
    ``build_calculation_inputs`` derives the engine's per-item exchange
    rate by calling ``convert_amount(1, quote_currency, item_currency)`` —
    but ONLY when ``item_currency != quote_currency``; when they are equal
    it hard-codes the rate to 1.0 and never calls ``convert_amount``.

    The эталон's col-Q rate is the engine's required exchange_rate. For
    multi-currency files (col Q ≠ 1) the эталон's D8 "Валюта КП" cell is
    stale (rubli_zakaz15 reads "EUR" but its numbers are RUB-magnitude with
    Q ≈ 0.0112). If the shim left ``currency_of_quote`` equal to the item
    currency, ``build_calculation_inputs`` would short-circuit the rate to
    1.0 and the эталон Q rate would be ignored — an orders-of-magnitude
    miss. So when col Q ≠ 1 the shim sets the engine's working quote
    currency to one DISTINCT from the item currency, forcing the
    ``convert_amount`` branch (which the test pins to return col Q). The
    engine's ``FinancialParams.currency_of_quote`` is itself always USD
    internally — the currency label is bookkeeping only, the math is
    pre-converted — so this choice changes nothing but which code path
    resolves the rate.
    """
    src_vars = golden["inputs"]["variables"]
    products = golden["inputs"]["products"]

    # Item currency the эталон products use (uniform per file; col J).
    item_currency = _uniform_item_currency(products)
    # The эталон col-Q FX rate (uniform per file).
    fx_rate = _uniform_fx_rate(products)

    # Engine working quote currency. When col Q == 1 the price IS already in
    # quote currency → keep it equal to the item currency (rate hard-codes
    # to 1.0, correct). When col Q ≠ 1 → pick a distinct currency so the
    # exchange-rate branch fires.
    if abs(fx_rate - 1.0) < 1e-12:
        engine_quote_currency = item_currency
    else:
        engine_quote_currency = "RUB" if item_currency != "RUB" else "USD"

    variables = _build_variables(src_vars, engine_quote_currency)
    items = [_build_item(p, item_currency) for p in products]
    return items, variables


def _uniform_item_currency(products: list[dict]) -> str:
    """Return the эталон item currency (col J), defaulting to EUR.

    ``build_calculation_inputs`` itself defaults a missing item currency to
    'USD' via ``purchase_currency or currency_of_base_price or 'USD'`` —
    the shim writes ``purchase_currency`` explicitly (see ``_build_item``)
    so this only picks the value the JSON carries. The corpus is uniform
    per file; the first non-empty value wins.
    """
    for p in products:
        ccy = p.get("currency_of_base_price")
        if ccy:
            return str(ccy)
    return "EUR"


def _uniform_fx_rate(products: list[dict]) -> float:
    """Return the эталон col-Q FX rate (uniform per file), defaulting to 1.0."""
    for p in products:
        fx = p.get("fx_rate")
        if fx is not None:
            return float(fx)
    return 1.0


def _build_variables(src_vars: dict, quote_currency: str) -> dict:
    """Map quote-level эталон settings → the flat ``variables`` dict.

    Logistics: the Excel T16/U16 formulas distribute the pre-summed legend
    leg totals (``V11`` first-leg, ``W11`` second-leg) by BD16. The engine's
    Phase 3 sums ``logistics_supplier_hub + logistics_hub_customs +
    brokerage_hub + customs_documentation`` into its own first leg and
    ``logistics_customs_client + brokerage_customs + warehousing_at_customs
    + brokerage_extra`` into its second leg. To feed the engine an identical
    leg split we route the эталон first-leg total through
    ``logistics_supplier_hub`` and the entire second-leg total through
    ``logistics_customs_client`` (all other leg, brokerage fields → 0).

    Insurance: Excel's ``V11`` first-leg total *already includes* the
    "Страховка" legend line, but the engine computes insurance itself
    (``AY13 × rate_insurance``) and adds it to T16 in Phase 3. Feeding V11
    directly would double-count insurance. So the shim feeds
    ``logistics_first_leg_excl_insurance`` (V11 − insurance line) — the
    engine then re-adds an insurance amount that reconstructs the эталон
    T16. (The extractor exposes this excl-insurance field precisely so the
    shim need do no arithmetic of its own.)

    Since ``build_calculation_inputs`` converts logistics from USD →
    quote-currency, we pass the totals already in quote currency and the
    test pins ``convert_amount`` to identity for same-currency, so the
    values arrive at the engine unchanged.

    Percentages: ``advance_from_client`` / ``advance_to_supplier`` are
    decimal fractions in Excel (1.0 = 100%); ``map_variables_to_calculation_input``
    feeds them into PaymentTerms which the engine divides by 100 — so they
    are scaled ×100 here.
    """
    return {
        "currency_of_quote": quote_currency,
        "seller_company": _normalise_seller_company(src_vars.get("seller_company")),
        "offer_sale_type": src_vars.get("offer_sale_type"),
        "offer_incoterms": src_vars.get("offer_incoterms"),
        "delivery_time": src_vars.get("delivery_time"),
        # Payment terms — fraction → percent.
        "advance_from_client": _to_pct(src_vars.get("advance_from_client")),
        "advance_to_supplier": _to_pct(src_vars.get("advance_to_supplier")),
        "time_to_advance": src_vars.get("time_to_advance", 0),
        "time_to_advance_on_receiving": src_vars.get("time_to_advance_on_receiving", 0),
        # Logistics — first leg WITHOUT the insurance line (engine re-adds
        # insurance in Phase 3); second leg whole. Currencies already in
        # quote currency (build_calculation_inputs converts 'USD'→quote, the
        # test pins that to identity for same-currency totals).
        "logistics_supplier_hub": src_vars.get("logistics_first_leg_excl_insurance") or 0.0,
        "logistics_hub_customs": 0.0,
        "logistics_customs_client": src_vars.get("logistics_second_leg_total") or 0.0,
        "logistics_supplier_hub_currency": quote_currency,
        "logistics_hub_customs_currency": quote_currency,
        "logistics_customs_client_currency": quote_currency,
        # Brokerage — already folded into the leg totals above.
        "brokerage_hub": 0.0,
        "brokerage_customs": 0.0,
        "warehousing_at_customs": 0.0,
        "customs_documentation": 0.0,
        "brokerage_extra": 0.0,
        # DM fee — resolved by the extractor from the эталон's AG3/AF4:AG7
        # legend. Two of the three corpus files carry a zero fee; forma
        # carries a 10% percentage fee.
        "dm_fee_type": src_vars.get("dm_fee_type", "fixed"),
        "dm_fee_value": src_vars.get("dm_fee_value", 0.0) or 0.0,
        "dm_fee_currency": quote_currency,
        # Admin rates.
        "rate_forex_risk": src_vars.get("rate_forex_risk"),
        "rate_insurance": 0.00047,  # helpsheet E14 — same across the corpus
    }


def _build_item(product: dict, item_currency: str) -> dict:
    """Map one эталон product row → a ``get_composed_items``-shape dict.

    The base price fed to the engine is reconstructed so the engine's own
    VAT-strip step lands back on the эталон N16 — see the module docstring.
    The эталон's per-product FX rate (col Q) and import tariff (col X) ride
    along on the item so the golden-master test's pinned stubs can serve
    them deterministically.

    ``item_currency`` is the uniform эталон purchase currency (col J),
    written explicitly to ``purchase_currency`` — should a file leave col J
    blank, passing it through here pins the item currency rather than
    letting ``build_calculation_inputs`` silently default it to 'USD'.
    """
    zone = _resolve_zone(product.get("supplier_country"))
    zone_vat = _ZONE_VAT_RATE.get(zone, 0.0)

    price_no_vat = float(product.get("price_no_vat") or 0.0)
    # Reconstruct the with-VAT base price (engine's K16). For a zero-VAT
    # zone this equals N16; otherwise it grosses N16 up by the zone rate.
    base_price_with_vat = price_no_vat * (1.0 + zone_vat)

    return {
        # Identity.
        "product_name": product.get("name") or product.get("article"),
        "supplier_sku": product.get("article"),
        "quantity": product.get("quantity"),
        # Pricing — reconstructed with-VAT base price; engine re-strips VAT.
        "purchase_price_original": base_price_with_vat,
        "purchase_currency": item_currency,
        "base_price_vat": base_price_with_vat,
        "price_includes_vat": True,
        # Supplier-side attributes. supplier_country is normalised to a
        # canonical SupplierCountry zone value: the эталон form uses
        # template-label variants (e.g. "ЕС (закупка между странами ЕС)")
        # that the production resolve_vat_zone() does NOT recognise — it
        # would fall them back to "Прочие", changing the internal-markup
        # zone. The procurement UI stores canonical enum values, so emitting
        # the canonical value here reproduces the get_composed_items shape
        # faithfully (mechanical normalisation, not a workaround for an
        # engine defect).
        "weight_in_kg": product.get("weight_in_kg") or 0.0,
        "customs_code": _normalise_customs_code(product.get("customs_code")),
        "supplier_country": zone,
        # Customer-side sales params — Excel fractions → engine percent.
        "markup": _to_pct(product.get("markup")),
        "supplier_discount": _to_pct(product.get("supplier_discount")),
        # Import tariff: Excel col X is a fraction; the engine wants percent.
        # build_calculation_inputs routes this through _resolve_import_tariff_pct
        # → legacy _calc_combined_duty, which returns the `import_tariff`
        # field as-is. The golden-master test pins _resolve_import_tariff_pct
        # to read this value directly, so we store the эталон percent here.
        "import_tariff": _to_pct(product.get("import_tariff")),
        # Per-product FX rate (col Q) — carried for the pinned convert_amount.
        "_etalon_fx_rate": product.get("fx_rate"),
        # License costs — none in the эталон corpus.
        "license_ds_cost": None,
        "license_ss_cost": None,
        "license_sgr_cost": None,
        # Flags.
        "is_unavailable": False,
        "import_banned": False,
        "vat_rate": product.get("vat_rate"),
    }


# ---------------------------------------------------------------------------
# Small normalisers
# ---------------------------------------------------------------------------

# SupplierCountry enum values the calculation engine accepts (via
# resolve_vat_zone). The эталон "Страна Закупки" cell carries either an exact
# enum value or a near-variant; map the variants the corpus actually uses.
_COUNTRY_VARIANTS = {
    "ЕС (закупка между странами ЕС)": "ЕС (между странами ЕС)",
}

_VALID_ZONES = set(_ZONE_VAT_RATE.keys())


def _resolve_zone(country_raw) -> str:
    """Map an эталон 'Страна Закупки' cell to a SupplierCountry zone value.

    Mirrors what ``resolve_vat_zone`` settles on for these corpus countries
    so the shim can compute the matching VAT rate for base-price
    reconstruction. ``build_calculation_inputs`` still calls the real
    ``resolve_vat_zone`` at runtime — this is only for the price math here.
    """
    if not country_raw:
        return "Прочие"
    c = str(country_raw).strip()
    c = _COUNTRY_VARIANTS.get(c, c)
    return c if c in _VALID_ZONES else "Прочие"


def _normalise_customs_code(code) -> str:
    """Coerce a customs code to the 10-digit string the engine validates.

    The эталон cell may be an int, a spaced string ("9026 80 200 0"), or
    blank. ``ProductInfo.customs_code`` requires exactly 10 digits; fall
    back to a zero placeholder when the cell can't yield 10 digits — the
    customs code does not affect any monetary checkpoint.
    """
    if code is None:
        return "0000000000"
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) == 10:
        return digits
    return "0000000000"


def _normalise_seller_company(name) -> str:
    """Strip the parenthetical ИНН/country suffix off the эталон seller name.

    The эталон D5 cell reads e.g. "МАСТЕР БЭРИНГ ООО (ИНН 0242013464)",
    whereas the engine's ``SellerCompany`` enum expects the bare legal
    name. Trim at the first " (".
    """
    if not name:
        return "МАСТЕР БЭРИНГ ООО"
    s = str(name)
    idx = s.find(" (")
    return s[:idx].strip() if idx != -1 else s.strip()


# ===========================================================================
# Track B — shared comparison-computation logic.
#
# Design: ``docs/plans/2026-05-18-calc-engine-verification-design.md`` §8.
#
# Track B builds an offline engine-vs-эталон comparison .xlsx for non-coding
# reviewers (``scripts/generate_calc_comparison.py``). The deviation %, the
# PASS/FAIL verdict and the segment-rule classification all live HERE so the
# script and its TDD test (``tests/test_calc_comparison.py``) share one
# definition rather than re-deriving the rule.
#
# This module is the SINGLE SOURCE for the tolerance, the checkpoint cell maps
# and the segment-classification sets below — both Track B and Track A1
# (``tests/test_calc_engine_golden_master.py``) import them from here. A1's
# import block (``from tests.golden_support import ABS_TOL, EPS,
# EXPECTED_SEGMENT_DIFFS, PRODUCT_CHECKPOINTS, REL_TOL, SEGMENT_INFO_CELLS,
# TOTAL_CHECKPOINTS``) pulls these definitions directly — there is no second,
# inline copy in A1 to keep in sync.
# ===========================================================================

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GOLDEN_DIR = os.path.join(_REPO_ROOT, "tests", "golden")


# ---------------------------------------------------------------------------
# Tolerance (design §5) — identical to Track A1's REL_TOL / EPS / ABS_TOL.
# ---------------------------------------------------------------------------

# |engine − эталон| / max(|эталон|, EPS) ≤ REL_TOL
REL_TOL = Decimal("1e-4")          # 0.01%
EPS = Decimal("1e-6")              # near-zero floor for the relative form
ABS_TOL = Decimal("0.01")          # absolute criterion when |эталон| < EPS


# ---------------------------------------------------------------------------
# Checkpoint maps (design §6) — эталон cell → ProductCalculationResult attr.
# Identical to Track A1's PRODUCT_CHECKPOINTS / SEGMENT_INFO_CELLS /
# TOTAL_CHECKPOINTS. Phase-ordered.
# ---------------------------------------------------------------------------

# Verdict-bearing per-product checkpoints.
PRODUCT_CHECKPOINTS: list[tuple[str, str]] = [
    ("N16", "purchase_price_no_vat"),
    ("P16", "purchase_price_after_discount"),
    ("R16", "purchase_price_per_unit_quote_currency"),
    ("S16", "purchase_price_total_quote_currency"),
    ("AA16", "cogs_per_unit"),
    ("AB16", "cogs_per_product"),
    ("AD16", "sale_price_per_unit_excl_financial"),
    ("AE16", "sale_price_total_excl_financial"),
    ("AF16", "profit"),
    ("AG16", "dm_fee"),
    ("AH16", "forex_reserve"),
    ("AI16", "financial_agent_fee"),
    ("BA16", "financing_cost_initial"),
    ("BB16", "financing_cost_credit"),
    ("AJ16", "sales_price_per_unit_no_vat"),
    ("AK16", "sales_price_total_no_vat"),
    ("AL16", "sales_price_total_with_vat"),
    ("AN16", "vat_from_sales"),
    ("AO16", "vat_on_import"),
    ("AP16", "vat_net_payable"),
    ("AY16", "internal_sale_price_total"),
    ("AQ16", "transit_commission"),
]

# Per-position logistics & customs cells — INFORMATIONAL ONLY (segment rule,
# design §5). No pass/fail verdict ever derives from them.
SEGMENT_INFO_CELLS: list[tuple[str, str]] = [
    ("T16", "logistics_first_leg"),
    ("U16", "logistics_last_leg"),
    ("V16", "logistics_total"),
    ("Y16", "customs_fee"),
    ("Z16", "excise_tax_amount"),
]

# Quote-level totals (row 13). V13/Y13 (logistics/customs) ARE verdict-bearing
# — the segment rule judges logistics & customs at the total level only.
TOTAL_CHECKPOINTS: list[tuple[str, str]] = [
    ("S13", "purchase_price_total_quote_currency"),
    ("V13", "logistics_total"),
    ("Y13", "customs_fee"),
    ("AB13", "cogs_per_product"),
    ("AF13", "profit"),
    ("AK13", "sales_price_total_no_vat"),
    ("AL13", "sales_price_total_with_vat"),
]

# Cells whose эталон currency the JSON does not stamp (the .xlsm leaves Z16
# blank for the no-excise corpus); excluded from the currency-mismatch test.
_NULL_OK_CELLS = {"Z16"}


# ---------------------------------------------------------------------------
# Segment-rule classification (design §5) — identical to A1's
# SEGMENT_INFO_CELLS + EXPECTED_SEGMENT_DIFFS.
#
# A cell is "segment-informational" — diverges as the expected, correct
# consequence of Kvotaflow's variable-segment logistics model, NOT a bug —
# when it is either a per-position logistics/customs cell (always, every
# file) or a downstream per-product cell that inherits the per-position
# logistics reallocation (only for ``rubli_zakaz15``, the one corpus file
# with product weights AND a multi-segment split).
# ---------------------------------------------------------------------------

# Per-position logistics/customs cell names — segment-informational for every
# corpus file.
_SEGMENT_PER_POSITION_CELLS = {cell for cell, _ in SEGMENT_INFO_CELLS}

# Downstream per-product cells that inherit rubli's weight-based logistics
# reallocation — segment-informational for rubli only.
EXPECTED_SEGMENT_DIFFS: dict[str, set[str]] = {
    "rubli_zakaz15.xlsm": {
        "AA16", "AB16", "AD16", "AE16", "AF16", "AH16", "AI16", "AJ16",
        "AK16", "AL16", "AN16", "AO16", "AP16", "BA16",
    },
}


# ---------------------------------------------------------------------------
# Verdict labels — the .xlsx colour-codes on these.
# ---------------------------------------------------------------------------

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
# Expected per-segment divergence (design §5) — informational, never a FAIL.
VERDICT_SEGMENT = "ожидаемое посегментное расхождение"


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------


def coerce_decimal(value) -> Decimal:
    """Coerce a JSON/engine numeric to ``Decimal``; None/blank → 0."""
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def within_tolerance(engine_val: Decimal, etalon_val: Decimal) -> tuple[bool, Decimal]:
    """Return ``(passes, deviation)`` for one cell — design §5 tolerance.

    Relative criterion ``|Δ| / max(|эталон|, EPS) ≤ REL_TOL``; when
    ``|эталон| < EPS`` falls back to the absolute ``|Δ| ≤ ABS_TOL``.
    ``deviation`` is the relative deviation as a percentage (for display);
    near zero it is the absolute delta.
    """
    diff = abs(engine_val - etalon_val)
    if abs(etalon_val) < EPS:
        return diff <= ABS_TOL, diff
    rel = diff / abs(etalon_val)
    return rel <= REL_TOL, rel * Decimal("100")


def is_segment_informational(source_xlsm: str, cell: str) -> bool:
    """True if ``cell`` carries NO pass/fail verdict for ``source_xlsm``.

    Per the segment rule (design §5): per-position logistics/customs cells
    (T16/U16/V16/Y16/Z16) are segment-informational for every file; the
    downstream per-product cells that inherit rubli's weight-based logistics
    reallocation are segment-informational for ``rubli_zakaz15`` only.
    Logistics/customs TOTALS (V13/Y13) are NOT segment-informational — they
    carry the verdict.
    """
    if cell in _SEGMENT_PER_POSITION_CELLS:
        return True
    return cell in EXPECTED_SEGMENT_DIFFS.get(source_xlsm, set())


# ---------------------------------------------------------------------------
# Comparison row / result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ComparisonRow:
    """One engine-vs-эталон comparison cell — a row of the «Сравнение» sheet.

    Attributes:
        position: human position label ("поз. 1") or "ИТОГО" for a total.
        cell: эталон cell name (e.g. "S16", "V13").
        field: the ProductCalculationResult attribute compared.
        engine_val: the engine's value.
        etalon_val: the эталон .xlsm's own cached value.
        abs_delta: ``|engine − эталон|``.
        deviation_pct: relative deviation as a percentage (abs delta near 0).
        verdict: one of ``VERDICT_PASS`` / ``VERDICT_FAIL`` / ``VERDICT_SEGMENT``.
        currency_mismatch: True when engine & эталон currency labels differ.
    """

    position: str
    cell: str
    field: str
    engine_val: Decimal
    etalon_val: Decimal
    abs_delta: Decimal
    deviation_pct: Decimal
    verdict: str
    currency_mismatch: bool


@dataclass
class InputRow:
    """One position's visible inputs — a row of the «Входные данные» sheet."""

    position: str
    product_name: str
    quantity: object
    price: Decimal
    currency: str
    country: str
    grouping: str


@dataclass
class ComparisonResult:
    """Everything needed to render one quote's comparison .xlsx."""

    source_xlsm: str
    quote_idn: str
    quote_currency: str
    banner: str
    rows: list[ComparisonRow] = field(default_factory=list)
    input_rows: list[InputRow] = field(default_factory=list)


def classify_cell(
    source: str,
    cell: str,
    field: str,
    engine_val: Decimal,
    etalon_val: Decimal,
    is_total: bool,
    engine_currency: str | None = None,
    etalon_currency: str | None = None,
) -> ComparisonRow:
    """Compare one cell engine-vs-эталон and assign its verdict.

    The verdict follows the segment rule (design §5):

      * a currency mismatch is always ``VERDICT_FAIL``;
      * a per-position logistics/customs cell, or a rubli downstream cell,
        is ``VERDICT_SEGMENT`` when it diverges and ``VERDICT_PASS`` when it
        does not — it never becomes a FAIL (``is_total`` overrides this:
        V13/Y13 totals ARE verdict-bearing);
      * any other cell is ``VERDICT_PASS`` / ``VERDICT_FAIL`` by tolerance.

    ``deviation_pct`` is always populated (informational even for segment
    rows). ``engine_currency`` defaults to ``etalon_currency`` — most cells
    are same-currency by construction; pass both only to test a mismatch.
    """
    abs_delta = abs(engine_val - etalon_val)
    passes, deviation = within_tolerance(engine_val, etalon_val)

    if etalon_currency is None:
        currency_mismatch = False
    else:
        eng_ccy = engine_currency if engine_currency is not None else etalon_currency
        currency_mismatch = eng_ccy != etalon_currency

    if currency_mismatch:
        verdict = VERDICT_FAIL
    elif not is_total and is_segment_informational(source, cell):
        # Segment rule §5: per-position / rubli-downstream cells never FAIL.
        verdict = VERDICT_PASS if passes else VERDICT_SEGMENT
    else:
        verdict = VERDICT_PASS if passes else VERDICT_FAIL

    return ComparisonRow(
        position="",  # set by the caller
        cell=cell,
        field=field,
        engine_val=engine_val,
        etalon_val=etalon_val,
        abs_delta=abs_delta,
        deviation_pct=deviation,
        verdict=verdict,
        currency_mismatch=currency_mismatch,
    )


def build_verdict_banner(rows: list[ComparisonRow]) -> str:
    """Build the top-of-sheet verdict banner from the comparison rows.

    Only verdict-bearing rows (PASS/FAIL) drive the banner — ``VERDICT_SEGMENT``
    rows are an EXPECTED design §5 difference and never count toward failures
    nor toward the reported max deviation. The banner reads either
    «ВСЁ СХОДИТСЯ — макс. откл. X%» or «РАСХОЖДЕНИЕ — N ячеек вне допуска,
    макс. X%».
    """
    verdict_rows = [r for r in rows if r.verdict in (VERDICT_PASS, VERDICT_FAIL)]
    failures = [r for r in verdict_rows if r.verdict == VERDICT_FAIL]

    if failures:
        max_dev = max(r.deviation_pct for r in failures)
        return (
            f"РАСХОЖДЕНИЕ — {len(failures)} ячеек вне допуска, "
            f"макс. {max_dev:.4f}%"
        )
    max_dev = max((r.deviation_pct for r in verdict_rows), default=Decimal("0"))
    return f"ВСЁ СХОДИТСЯ — макс. откл. {max_dev:.4f}%"


# ---------------------------------------------------------------------------
# Live-data pinning — identical strategy to Track A1.
#
# ``build_calculation_inputs`` makes three live-data lookups (FX conversion,
# import-tariff resolution, default admin settings). Track B pins all three
# to the эталон's own values exactly as A1 does, so an engine-vs-эталон
# difference localises to the input mapping or the engine — never to drift
# in reference data.
# ---------------------------------------------------------------------------


def _make_convert_amount_stub(
    fx_quote_to_item: Decimal, quote_currency: str, item_currency: str
):
    """``convert_amount`` stub pinned to one fixture's эталон FX rate.

    ``build_calculation_inputs`` calls ``convert_amount`` for the per-item
    exchange-rate probe (``convert_amount(1, quote_ccy, item_ccy)`` — return
    the эталон col-Q rate) and for logistics conversion (return identity —
    the shim already passes leg totals in quote-currency magnitude).
    """

    # ``_rate_date`` mirrors the real ``convert_amount`` signature so the stub
    # is a drop-in monkeypatch; ``build_calculation_inputs`` never passes it.
    def _stub(amount, from_currency, to_currency, _rate_date=None):
        amt = Decimal(str(amount))
        if from_currency == to_currency:
            return amt
        if (
            amt == Decimal("1")
            and from_currency == quote_currency
            and to_currency == item_currency
        ):
            return fx_quote_to_item
        return amt

    return _stub


def _make_import_tariff_stub():
    """Pin ``_resolve_import_tariff_pct`` to the эталон col-X tariff on the item."""

    # ``_quote_currency`` mirrors the real ``_resolve_import_tariff_pct``
    # signature (the caller passes it positionally); the эталон tariff rides
    # on the item, so the stub ignores it.
    def _stub(item, _quote_currency):
        return float(item.get("import_tariff") or 0.0)

    return _stub


def _make_admin_settings_stub(rate_forex_risk_fraction):
    """Pin ``get_default_admin_settings`` to the эталон's forex-risk rate.

    ``rate_forex_risk`` is a live admin-data input — pinned to the эталон
    AH11/AI11 cell exactly as A1 does. The other rates match the эталон
    helpsheet (E13/E11/E27), uniform across the corpus.
    """
    forex_pct = float(rate_forex_risk_fraction or 0.0) * 100.0

    def _stub():
        return {
            "rate_forex_risk": Decimal(str(forex_pct)),
            "rate_fin_comm": Decimal("2"),
            "rate_loan_interest_annual": Decimal("0.25"),
            "customs_logistics_pmt_due": 10,
        }

    return _stub


def run_engine(golden: dict):
    """Shim → production input mapper → locked engine. Returns the result list.

    Mirrors Track A1's engine path exactly: the golden fixture goes through
    ``golden_to_items_and_variables`` → the production
    ``build_calculation_inputs`` → the locked ``calculate_multiproduct_quote``,
    with FX / import-tariff / admin-rate all pinned to the эталон's own
    values for the duration of the call.
    """
    # Imported here (not at module top) so the simple shim functions above
    # stay importable without the engine on the path.
    import calculation_mapper
    import services.calculation_helpers as calculation_helpers
    import services.currency_service as currency_service
    from calculation_engine import calculate_multiproduct_quote
    from services.calculation_helpers import build_calculation_inputs

    items, variables = golden_to_items_and_variables(golden)

    fx = coerce_decimal(items[0].get("_etalon_fx_rate") or 1)
    fx = fx if fx != 0 else Decimal("1")
    engine_quote_currency = variables["currency_of_quote"]
    item_currency = items[0].get("purchase_currency") or "USD"

    convert_stub = _make_convert_amount_stub(fx, engine_quote_currency, item_currency)
    tariff_stub = _make_import_tariff_stub()
    admin_stub = _make_admin_settings_stub(
        golden["inputs"]["variables"].get("rate_forex_risk")
    )

    orig_convert = currency_service.convert_amount
    orig_tariff = calculation_helpers._resolve_import_tariff_pct
    orig_admin = calculation_mapper.get_default_admin_settings
    try:
        currency_service.convert_amount = convert_stub
        calculation_helpers._resolve_import_tariff_pct = tariff_stub
        calculation_mapper.get_default_admin_settings = admin_stub
        calc_inputs = build_calculation_inputs(items, variables)
        results = calculate_multiproduct_quote(calc_inputs)
    finally:
        currency_service.convert_amount = orig_convert
        calculation_helpers._resolve_import_tariff_pct = orig_tariff
        calculation_mapper.get_default_admin_settings = orig_admin

    return results


def load_golden(json_name: str) -> dict:
    """Load one golden fixture JSON from ``tests/golden/``."""
    with open(os.path.join(_GOLDEN_DIR, json_name), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Input layer — the «Входные данные» sheet
# ---------------------------------------------------------------------------


def _build_input_rows(golden: dict) -> list[InputRow]:
    """Build the visible-inputs rows from a golden fixture's эталон products.

    Reads straight from the эталон inputs (not the shim) so a reviewer sees
    exactly what the .xlsm carried: кол-во / цена / валюта / страна.
    """
    products = golden["inputs"]["products"]
    rows: list[InputRow] = []
    for idx, product in enumerate(products, start=1):
        rows.append(
            InputRow(
                position=f"поз. {idx}",
                product_name=str(
                    product.get("name") or product.get("article") or ""
                ),
                quantity=product.get("quantity"),
                price=coerce_decimal(product.get("price_no_vat")),
                currency=str(product.get("currency_of_base_price") or ""),
                country=str(product.get("supplier_country") or ""),
                grouping=str(product.get("customs_code") or ""),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# build_comparison — the whole engine-vs-эталон comparison for one fixture
# ---------------------------------------------------------------------------


def build_comparison(json_name: str) -> ComparisonResult:
    """Run one golden fixture through the engine and compare it to the эталон.

    Produces a fully classified ``ComparisonResult`` — the per-position /
    per-cell comparison rows, the input-layer rows, and the verdict banner —
    ready for ``scripts/generate_calc_comparison.py`` to render as .xlsx.

    Per design §5 the per-position logistics/customs cells and rubli's
    downstream per-product cells carry ``VERDICT_SEGMENT`` (informational);
    logistics & customs get a real verdict only at the V13/Y13 totals.
    """
    golden = load_golden(json_name)
    source = golden["source_xlsm"]
    currency = golden["quote_currency"]
    results = run_engine(golden)
    exp_products = golden["expected"]["products"]
    totals = golden["expected"]["totals"]

    rows: list[ComparisonRow] = []

    # Per-product checkpoints + per-position logistics/customs cells.
    per_product_cells = PRODUCT_CHECKPOINTS + SEGMENT_INFO_CELLS
    for idx, (result, exp) in enumerate(zip(results, exp_products), start=1):
        position = f"поз. {idx}"
        for cell, attr in per_product_cells:
            etalon_cell = exp.get(cell)
            if etalon_cell is None:
                continue
            etalon_val = coerce_decimal(etalon_cell.get("value"))
            etalon_ccy = etalon_cell.get("currency")
            engine_val = coerce_decimal(getattr(result, attr, None))

            # Currency check: the эталон stamps every monetary cell; a blank
            # currency on a known-null cell (Z16) is not a mismatch.
            etalon_ccy_for_check = etalon_ccy
            if etalon_ccy is None and cell in _NULL_OK_CELLS:
                etalon_ccy_for_check = currency

            row = classify_cell(
                source=source,
                cell=cell,
                field=attr,
                engine_val=engine_val,
                etalon_val=etalon_val,
                is_total=False,
                engine_currency=currency,
                etalon_currency=etalon_ccy_for_check,
            )
            row.position = position
            rows.append(row)

    # Quote-level totals — summed from the per-product engine results.
    for cell, attr in TOTAL_CHECKPOINTS:
        etalon_cell = totals.get(cell)
        if etalon_cell is None:
            continue
        etalon_val = coerce_decimal(etalon_cell.get("value"))
        etalon_ccy = etalon_cell.get("currency")
        engine_total = sum(
            (coerce_decimal(getattr(r, attr, None)) for r in results), Decimal("0")
        )
        row = classify_cell(
            source=source,
            cell=cell,
            field=attr,
            engine_val=engine_total,
            etalon_val=etalon_val,
            is_total=True,
            engine_currency=currency,
            etalon_currency=etalon_ccy,
        )
        row.position = "ИТОГО"
        rows.append(row)

    return ComparisonResult(
        source_xlsm=source,
        quote_idn=golden.get("quote_idn", ""),
        quote_currency=currency,
        banner=build_verdict_banner(rows),
        rows=rows,
        input_rows=_build_input_rows(golden),
    )
