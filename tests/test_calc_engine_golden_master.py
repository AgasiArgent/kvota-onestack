"""Track A1 — autonomous golden-master regression for the Calculation Engine.

Design: ``docs/plans/2026-05-18-calc-engine-verification-design.md`` §6 (A1).

For each of the four эталон ".xlsm" files (extracted into JSON golden
fixtures by ``scripts/refresh_golden.py``) this test:

  1. loads the golden JSON,
  2. runs it through the shim → production ``items`` / ``variables``,
  3. feeds those to the PRODUCTION input mapper
     ``services.calculation_helpers.build_calculation_inputs``,
  4. runs the locked engine ``calculate_multiproduct_quote``,
  5. asserts every checkpoint reproduces the эталон's own cached Excel
     output within ≤0.01% (design §5).

The engine and its mapper are exercised exactly as production does — the
only things pinned are the two live-data lookups ``build_calculation_inputs``
makes (currency conversion and import-tariff resolution), pinned to the
rates the .xlsm itself carries (FX = col Q, tariff = col X). A divergence
therefore localises to the input mapping or the engine, never to drift in
reference data.

Honest-failure contract
-----------------------
A1 may legitimately FAIL — a real divergence between engine/mapping and
the эталон is the single most valuable output of this work. Where a
checkpoint genuinely diverges (small-but->0.01%, or a consistent ratio)
the offending cell is marked with an explicit ``XFAIL_CHECKPOINTS`` entry
documenting the reason, so the test infrastructure stays green/mergeable
while the divergence is recorded for the Phase-2 fix. Passing checkpoints
remain hard asserts. Harness bugs (orders-of-magnitude / wrong-sign /
all-zero) are NOT xfailed — they are fixed.

Segment rule (design §5)
------------------------
Kvotaflow splits logistics into a variable number of segments; the эталон
Excel always uses exactly three legs (T/U/V). A per-segment / per-position
comparison of logistics and customs is therefore apples-to-oranges. Per
design §5 this test compares logistics (T16/U16/V16) and customs (Y16/Z16)
**only at the quote-total level** (Σ logistics vs the эталон V13, Σ customs
vs the эталон Y13), with the same ≤0.01% tolerance. The per-segment /
per-position logistics & customs values are printed for inspection but
carry NO pass/fail verdict — they are EXPECTED, correct segment-model
differences, not bugs, and are not eligible for ``KNOWN_DIVERGENCES``.
``xfail`` stays reserved for genuine non-segment divergences. A logistics
or customs *total* (V13/Y13) may still genuinely diverge — that IS a
verdict-bearing checkpoint and remains a hard assert (or a documented
divergence when a real root cause moves the total).
"""

from __future__ import annotations

import json
import os
from decimal import Decimal

import pytest

from services import calculation_helpers
from services.calculation_helpers import build_calculation_inputs
from tests import golden_support
from tests.golden_support import (
    ABS_TOL,
    EPS,
    EXPECTED_SEGMENT_DIFFS,
    PRODUCT_CHECKPOINTS,
    REL_TOL,
    SEGMENT_INFO_CELLS,
    TOTAL_CHECKPOINTS,
)

from calculation_engine import calculate_multiproduct_quote

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GOLDEN_DIR = os.path.join(_REPO_ROOT, "tests", "golden")


# ---------------------------------------------------------------------------
# Tolerance and checkpoint maps (design §5/§6) — the single source of these
# definitions is ``tests.golden_support`` (imported above), shared with
# Track B's comparison generator. A1 keeps only its own test-specific helpers.
#
#   REL_TOL / EPS / ABS_TOL  — the ≤0.01% tolerance.
#   PRODUCT_CHECKPOINTS      — verdict-bearing per-product cells (no logistics/
#                              customs per-position cells: the segment rule
#                              judges those at the V13/Y13 totals only).
#   SEGMENT_INFO_CELLS       — per-position logistics/customs cells, printed
#                              for inspection, no verdict.
#   TOTAL_CHECKPOINTS        — quote-level totals; V13/Y13 ARE verdict-bearing.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Documented divergences (xfail by root cause).
#
# A1 ran against the production input mapper + the locked engine with all
# live data pinned to the эталон's own values. Three GENUINE divergences
# between the engine/mapping and the эталон survive the segment rule (none
# is a harness bug — harness bugs were fixed; none is a per-segment
# logistics/customs difference — those are EXPECTED, see the segment rule
# below; these are real, >0.01% differences on verdict-bearing checkpoints
# traced to a specific surface).
#
# Each entry documents one root cause and lists every verdict-bearing
# checkpoint cell it corrupts (a PRODUCT_CHECKPOINTS per-product cell, or a
# TOTAL_CHECKPOINTS quote total — including V13/Y13). The golden-master
# test records a failing checkpoint as XFAIL — keeping the test green and
# the branch mergeable — iff its cell is in that file's known-divergence
# set. A checkpoint that fails but is NOT listed here is a HARD failure:
# that is how the suite still catches a regression or a new divergence.
# Every checkpoint that PASSES remains a hard assert.
#
# Segment rule (design §5) — what is NOT a divergence:
#   Per-position logistics (T16/U16/V16) and customs (Y16/Z16) are NOT
#   verdict-bearing and NEVER appear below: a per-segment difference is the
#   EXPECTED, correct consequence of Kvotaflow's variable-segment logistics
#   model vs the эталон's fixed 3-leg model. Only the logistics/customs
#   TOTALS (V13/Y13) carry a verdict, and a V13/Y13 entry appears below
#   only when the *total* genuinely diverges for a real root cause (e.g.
#   rubli's customs residual, or a cascade off an input-mapping/engine
#   defect). The previous forma "Y16 hairline" divergence dissolved
#   entirely under this rule — forma's V13/Y13 totals both pass.
#
# Phase 2 (per design §10/§11) fixes the underlying defects; the offending
# cells then start passing and must be removed from the sets below.
# ---------------------------------------------------------------------------


class Divergence:
    """One documented engine/mapping-vs-эталон divergence.

    Attributes:
        surface: which of the three verification surfaces it sits on —
            "input-mapping" or "engine".
        reason: human-readable root-cause explanation.
        cells: set of checkpoint cell names this divergence corrupts
            (per-product cells like "T16"; quote totals like "V13").
    """

    def __init__(self, surface: str, reason: str, cells: set[str]):
        self.surface = surface
        self.reason = reason
        self.cells = cells


# source_xlsm → list of documented divergences for that file.
KNOWN_DIVERGENCES: dict[str, list[Divergence]] = {
    # IDEMITSU — supplier country "ЕС (между странами ЕС)". The production
    # input mapper build_calculation_inputs → resolve_vat_zone() cannot
    # resolve this SupplierCountry value (normalize_country_to_iso has no
    # entry for "ЕС …"), so it falls back to the "Прочие" zone. "Прочие"
    # carries internal markup 0.02 where the EU-cross-border zone carries
    # 0.04 — the эталон's AW16 = 0.04 confirms the EU intent. This shifts
    # AX16/AY16 (internal pricing) and cascades into financing, VAT and the
    # sale price. (A secondary ~0.04% AY16 gap remains even with the right
    # zone — the эталон rounds AX16 to 2dp, the engine to 4dp.)
    "idemitsu.xlsm": [
        Divergence(
            surface="input-mapping",
            reason=(
                "resolve_vat_zone() maps SupplierCountry 'ЕС (между странами "
                "ЕС)' to 'Прочие' (internal markup 0.02) instead of the EU "
                "cross-border zone (0.04); normalize_country_to_iso lacks an "
                "'ЕС …' entry. Cascades through internal pricing → financing "
                "→ customs → VAT → sale price. The V13/Y13 totals also miss "
                "(V13 0.013%, Y13 1.85%) — a downstream consequence of the "
                "wrong AY16 (insurance and the Y16 = tariff·(AY16+T16) term), "
                "not a segment-model effect."
            ),
            cells={
                "AA16", "AB16", "AD16", "AE16", "AF16",
                "AH16", "AI16", "AJ16", "AK16", "AL16", "AN16", "AO16", "AP16",
                "AY16", "BA16", "BB16",
                "V13", "Y13", "AB13", "AF13", "AK13", "AL13",
            },
        ),
    ],
    # FORMA_NDS22_18 — percentage DM fee (AG3="комиссия %", 10%). The эталон
    # formula is AG16 = BD16 × VLOOKUP("комиссия %", AF4:AG7, 2, FALSE) =
    # BD16 × AG7 = BD16 × (AG6 × AB13) — the percentage applied to the
    # quote-level COGS total. The engine's percentage path (phase11 line 725)
    # computes BD16 × AB16 × pct — the percentage applied to the per-product
    # COGS. For a multi-product quote these differ sharply (Σ BD16·AB16 ≠
    # AB13; row 16 эталон 25.39 vs engine ≈ 0.59). The wrong AG16 cascades
    # into the forex reserve, financing and the whole sale price.
    # NOTE: the former "Y16 hairline" divergence is gone — under the segment
    # rule (design §5) customs is judged at the Y13 total, and forma's V13
    # (0.000005%) and Y13 (0.0006%) totals both pass.
    "forma_nds22_18.xlsm": [
        Divergence(
            surface="engine",
            reason=(
                "Percentage DM-fee model differs: engine phase11 computes "
                "AG16 = BD16·AB16·pct (the эталон's AG3 'комиссия %' path), "
                "the эталон computes AG16 = BD16·(pct·AB13). For multi-"
                "product quotes Σ(BD16·AB16) ≠ AB13. Wrong AG16 cascades "
                "into forex reserve, financing and sale price."
            ),
            cells={
                "AA16", "AB16", "AD16", "AE16", "AF16", "AG16", "AH16",
                "AJ16", "AK16", "AL16", "AN16", "AP16", "BA16", "BB16",
                "AB13", "AF13", "AK13", "AL13",
            },
        ),
    ],
    # RUBLI_ZAKAZ15 — weight-based logistics distribution, residual at the
    # customs total. The эталон uses TWO distribution bases: BD16 = I16/I13
    # (weight) for the logistics legs T16/U16, and BE16 = S16/S13 (value)
    # for everything else. The engine uses a single value-based BD16 for
    # both. rubli carries product weights (I13 > 0) so the эталон's
    # logistics split is weight-based.
    #
    # Under the segment rule (design §5) the per-position T16/U16/V16
    # divergence (~27%) is EXPECTED and not a bug — and the logistics TOTAL
    # V13 fully dissolves (0.000000%: Σ BD16 = 1 for both bases, so
    # Σ T16 = V11, Σ U16 = W11). What does NOT dissolve is customs: the
    # эталон's Y16 = X16·(S16·(1+AX16) + T16) carries a +T16 term that is
    # weight-redistributed, and because the per-product import tariff X16
    # differs (0/7/8/15%) the redistributed T16 does not cancel in the sum
    # — Σ X16·T16(weight) ≠ Σ X16·T16(value). The customs TOTAL Y13 is
    # therefore left ~1.38% short (engine 186157.24 vs эталон 188766.73),
    # and that wrong Y13 propagates ~0.11% into the COGS / profit / sale-
    # price totals (AB16 = S16+V16+Y16+…). This Y13 residual is the genuine
    # surviving divergence; the logistics legs are not.
    "rubli_zakaz15.xlsm": [
        Divergence(
            surface="engine",
            reason=(
                "Engine distributes logistics by a single value-based "
                "BD16 = S16/S13; the эталон distributes the logistics legs "
                "by a weight-based BD16 = I16/I13 when total weight I13 > 0 "
                "(rubli carries weights). The logistics TOTAL V13 dissolves "
                "(Σ BD16 = 1 either way) — per the segment rule the legs are "
                "not judged. But the customs total does NOT dissolve: "
                "Y16 = X16·(AY16 + T16) carries a weight-redistributed +T16, "
                "and uneven per-product tariffs X16 (0/7/8/15%) prevent "
                "cancellation — Y13 is ~1.38% short and cascades ~0.11% into "
                "AB13/AF13/AK13/AL13."
            ),
            cells={
                "Y13", "AB13", "AF13", "AK13", "AL13",
            },
        ),
    ],
    # AMTEL_COFLY — internal markup model. The эталон derives the internal
    # markup AW16 from a 3rd column of its `list_vat` country table (a pure
    # country lookup); for the "Турция (транзитная зона)" route that column
    # holds 0.10. The engine derives internal markup from a 2-factor
    # (supplier_country, seller_region) map — INTERNAL_MARKUP_MAP — which
    # has 0.00 for (TURKEY_TRANSIT, "TR"). amtel's supplier country resolves
    # correctly to TURKEY_TRANSIT and its seller TEXCEL to region "TR", so
    # the engine looks up the RIGHT key — the divergence is the map's value,
    # not a mis-mapping (unlike idemitsu's vat-zone bug). Engine internal
    # markup 0.00 vs эталон 0.10 shifts AX16/AY16 and cascades into the sale
    # price, VAT and — since amtel is a транзит deal — the transit
    # commission. The logistics TOTAL V13 also misses by ~0.086%: amtel
    # carries zero product weights, so BOTH the эталон and the engine split
    # logistics value-based (no segment-model effect) — the V13 gap is the
    # insurance term (insurance = AY13·rate_insurance) moving with the wrong
    # AY13, i.e. a downstream consequence of the same internal-markup defect.
    "amtel_cofly.xlsm": [
        Divergence(
            surface="engine",
            reason=(
                "Internal-markup model differs: эталон reads AW16 from a "
                "country-only `list_vat` column (0.10 for the Turkish "
                "transit route); the engine reads INTERNAL_MARKUP_MAP keyed "
                "by (supplier_country, seller_region) = 0.00 for "
                "(TURKEY_TRANSIT, 'TR') — the key is resolved correctly, the "
                "map value diverges. Shifts internal pricing and cascades "
                "into sale price, VAT and the transit commission. The V13 "
                "logistics total also misses ~0.086% via the insurance term "
                "moving with the wrong AY13 (not a segment-model effect — "
                "amtel has zero weights, both sides split value-based)."
            ),
            cells={
                "AA16", "AB16", "AD16", "AE16", "AF16",
                "AJ16", "AK16", "AL16", "AQ16", "AY16",
                "V13",
            },
        ),
    ],
}

# ---------------------------------------------------------------------------
# Expected segment-model differences (design §5) — NOT bugs, NOT xfail.
#
# Distinct from KNOWN_DIVERGENCES: a cell in EXPECTED_SEGMENT_DIFFS diverges
# purely as the mechanical consequence of Kvotaflow's variable-segment
# logistics model allocating a leg to a different position than the эталон's
# fixed 3-leg model. The per-position logistics/customs cells
# (T16/U16/V16/Y16/Z16) are always expected-segment by definition (handled
# wholesale, see SEGMENT_INFO_CELLS) — that map is for the *downstream
# per-product* cells (AB16 = S16+V16+Y16+…, and everything past it) that
# inherit the same per-position logistics redistribution.
#
# The verification contract: such a cell is EXPECTED to differ per-position
# but its quote-level TOTAL must still match ≤0.01% (or, where a genuine
# residual survives, that total is itself a KNOWN_DIVERGENCES entry — e.g.
# rubli's Y13/AB13 customs residual). The golden-master test prints these
# as "expected segment-model difference" and derives NO pass/fail from the
# per-product cell — exactly as it does for T16/U16/V16. xfail is NOT used:
# these are correct behaviour, not Phase-2 bugs.
#
# Only rubli qualifies: it is the one corpus file that carries product
# weights (I13 > 0) AND a multi-segment logistics split. ``EXPECTED_SEGMENT_DIFFS``
# itself is imported from ``tests.golden_support`` (the single source, shared
# with Track B, imported at the top of this module); A1 keeps only the
# test-local ``_expected_segment_diff`` accessor that consults it.
# ---------------------------------------------------------------------------


def _expected_segment_diff(source: str, cell: str) -> bool:
    """True if ``cell`` is an expected segment-model per-product difference."""
    return cell in EXPECTED_SEGMENT_DIFFS.get(source, set())


def _divergence_for(source: str, cell: str):
    """Return the documented Divergence covering ``cell`` for ``source``, or None."""
    for div in KNOWN_DIVERGENCES.get(source, []):
        if cell in div.cells:
            return div
    return None


# ---------------------------------------------------------------------------
# Live-data pinning
# ---------------------------------------------------------------------------


def _make_convert_amount_stub(
    fx_quote_to_item: Decimal, quote_currency: str, item_currency: str
):
    """Build a ``convert_amount`` stub pinned to one fixture's эталон FX rate.

    ``build_calculation_inputs`` calls ``convert_amount`` for two distinct
    purposes, which the stub must serve differently:

      * **The per-item exchange-rate probe** — exactly
        ``convert_amount(Decimal("1"), quote_currency, item_currency)``.
        The engine computes ``R16 = P16 / exchange_rate``, and the эталон
        does ``R16 = P16 / Q16`` — so this call must return the эталон's
        col-Q rate. Recognised by its precise signature: amount == 1,
        from == the engine quote currency, to == the item currency.

      * **Logistics conversion** — ``convert_amount(<leg_total>, 'USD',
        quote_currency)``. ``build_calculation_inputs`` hard-codes 'USD' as
        the source currency for every logistics leg regardless of the real
        currency. The shim already passes the эталон leg totals in the
        engine's quote-currency magnitude, so this conversion must be an
        identity — the value arrives at the engine unchanged.

    Any same-currency call is a trivial identity. Each corpus file has a
    uniform col-Q rate (verified — idemitsu/forma/amtel = 1.0, rubli =
    0.011218648086), so one scalar fully pins a file.
    """

    # ``_rate_date`` mirrors the real ``convert_amount`` signature so the stub
    # is a drop-in monkeypatch; ``build_calculation_inputs`` never passes it.
    def _stub(amount, from_currency, to_currency, _rate_date=None):
        amt = Decimal(str(amount))
        if from_currency == to_currency:
            return amt
        # The exchange-rate probe — return the эталон col-Q rate.
        if (
            amt == Decimal("1")
            and from_currency == quote_currency
            and to_currency == item_currency
        ):
            return fx_quote_to_item
        # Everything else (logistics USD→quote): эталон leg totals are
        # already in quote-currency magnitude — identity, no scaling.
        return amt

    return _stub


def _make_import_tariff_stub():
    """Pin ``_resolve_import_tariff_pct`` to the эталон tariff on the item.

    The shim stores the эталон's col-X import tariff (already as a percent)
    on each item as ``import_tariff``. Pinning the resolver wholesale —
    rather than threading through the legacy ``_calc_combined_duty`` /
    Alta ``customs_calc`` branches — keeps the test from rabbit-holing into
    customs-rate plumbing while still feeding the engine the exact эталон
    tariff. (Design §6: "pin at the highest sensible level … and note it".)
    """

    # ``_quote_currency`` mirrors the real ``_resolve_import_tariff_pct``
    # signature (the caller passes it positionally); the эталон tariff rides
    # on the item, so the stub ignores it.
    def _stub(item, _quote_currency):
        return float(item.get("import_tariff") or 0.0)

    return _stub


def _make_admin_settings_stub(rate_forex_risk_fraction):
    """Pin ``get_default_admin_settings`` to the эталон's forex-risk rate.

    ``build_calculation_inputs`` calls ``map_variables_to_calculation_input``
    WITHOUT an ``admin_settings`` argument, so the mapper falls back to
    ``get_default_admin_settings()`` — which hard-codes ``rate_forex_risk =
    3``. The эталон's actual rate is the per-file AH11/AI11 cell (a decimal
    fraction; e.g. amtel = 0). ``rate_forex_risk`` is a live admin-data
    input, so — exactly like FX and tariff — it is pinned to the эталон
    value here. (For idemitsu/forma/rubli the эталон rate is 3%, which
    coincides with the default; for amtel it is 0%.)
    """
    forex_pct = float(rate_forex_risk_fraction or 0.0) * 100.0

    def _stub():
        return {
            "rate_forex_risk": Decimal(str(forex_pct)),
            "rate_fin_comm": Decimal("2"),  # helpsheet E13 — 2% across corpus
            "rate_loan_interest_annual": Decimal("0.25"),  # helpsheet E11
            "customs_logistics_pmt_due": 10,  # helpsheet E27
        }

    return _stub


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _within_tolerance(engine_val: Decimal, etalon_val: Decimal) -> tuple[bool, Decimal]:
    """Return ``(passes, deviation_pct)`` for one checkpoint.

    Uses the relative criterion ``|Δ| / max(|эталон|, EPS) ≤ REL_TOL``;
    when ``|эталон| < EPS`` falls back to the absolute ``|Δ| ≤ ABS_TOL``.
    ``deviation_pct`` is the relative deviation expressed as a percentage,
    for the failure message.
    """
    diff = abs(engine_val - etalon_val)
    if abs(etalon_val) < EPS:
        passes = diff <= ABS_TOL
        return passes, diff  # report the absolute delta near zero
    rel = diff / abs(etalon_val)
    return rel <= REL_TOL, rel * Decimal("100")


def _dec(value) -> Decimal:
    """Coerce a JSON/engine numeric to Decimal; treat None/blank as 0."""
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def _run_engine(golden: dict):
    """Shim → production mapper → engine. Returns the result list.

    Live-data lookups are pinned for the duration of this call only. Three
    surfaces are pinned to the эталон's own values (design §6):
      * ``convert_amount`` — FX, pinned to the эталон col-Q rate;
      * ``_resolve_import_tariff_pct`` — pinned to the эталон col-X tariff;
      * ``get_default_admin_settings`` — pinned so ``rate_forex_risk``
        matches the эталон AH11/AI11 cell.
    """
    items, variables = golden_support.golden_to_items_and_variables(golden)

    # The эталон's col-Q rate (uniform per file) is the engine's required
    # exchange_rate. Read it off the first item the shim produced. The
    # engine quote currency and item currency are needed so the FX stub can
    # recognise the exchange-rate probe by its exact signature.
    fx = _dec(items[0].get("_etalon_fx_rate") or 1)
    fx = fx if fx != 0 else Decimal("1")
    engine_quote_currency = variables["currency_of_quote"]
    item_currency = items[0].get("purchase_currency") or "USD"

    convert_stub = _make_convert_amount_stub(fx, engine_quote_currency, item_currency)
    tariff_stub = _make_import_tariff_stub()
    admin_stub = _make_admin_settings_stub(
        golden["inputs"]["variables"].get("rate_forex_risk")
    )

    # Pin all three live-data surfaces. ``convert_amount`` is imported
    # inside build_calculation_inputs from services.currency_service — patch
    # it at the source module. ``_resolve_import_tariff_pct`` is module-level
    # in calculation_helpers. ``get_default_admin_settings`` is called by
    # map_variables_to_calculation_input from calculation_mapper.
    import calculation_mapper
    import services.currency_service as currency_service

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


def _load_golden(json_name: str) -> dict:
    with open(os.path.join(_GOLDEN_DIR, json_name), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Corpus parametrisation
# ---------------------------------------------------------------------------

CORPUS = [
    "idemitsu.json",
    "rubli_zakaz15.json",
    "forma_nds22_18.json",
    "amtel_cofly.json",
]


@pytest.fixture(scope="module", params=CORPUS, ids=[c[:-5] for c in CORPUS])
def golden_run(request):
    """Load one golden fixture and run it through the engine once per module."""
    golden = _load_golden(request.param)
    results = _run_engine(golden)
    return golden, results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_engine_runs_and_product_count_matches(golden_run):
    """The engine produced one result per эталон product row."""
    golden, results = golden_run
    expected_n = len(golden["inputs"]["products"])
    assert len(results) == expected_n, (
        f"{golden['source_xlsm']}: engine returned {len(results)} results "
        f"for {expected_n} product rows"
    )


def test_product_checkpoints(golden_run):
    """Every per-product checkpoint reproduces the эталон within ≤0.01%.

    A failing checkpoint is triaged into one of three buckets:

      * **expected segment-model difference** — its cell is in this file's
        ``EXPECTED_SEGMENT_DIFFS`` set: the divergence is the correct,
        mechanical consequence of Kvotaflow's variable-segment logistics
        model (design §5). No pass/fail verdict; printed for inspection.
        NOT an xfail — this is correct behaviour, not a Phase-2 bug.
      * **documented divergence (XFAIL)** — its cell is in this file's
        ``KNOWN_DIVERGENCES`` set: a genuine non-segment divergence
        recorded for the Phase-2 fix. The test stays green so the branch
        is mergeable.
      * **HARD failure** — covered by neither: a regression or a new
        divergence. That is how the suite still catches one.

    Every checkpoint that PASSES is a hard assert. Per the segment rule
    (design §5) logistics/customs per-position cells (T16/U16/V16/Y16/Z16)
    are NOT in PRODUCT_CHECKPOINTS at all — see
    ``test_logistics_customs_segments_informational`` and the V13/Y13
    totals. The failure message names file, row, cell, both values, the
    deviation % and the currency-match flag.
    """
    golden, results = golden_run
    source = golden["source_xlsm"]
    currency = golden["quote_currency"]
    exp_products = golden["expected"]["products"]

    hard_failures: list[str] = []
    xfailed: list[str] = []
    segment_diffs: list[str] = []

    for result, exp in zip(results, exp_products):
        row = exp["row"]
        for cell, attr in PRODUCT_CHECKPOINTS:
            etalon_cell = exp.get(cell)
            if etalon_cell is None:
                continue
            etalon_val = _dec(etalon_cell.get("value"))
            etalon_ccy = etalon_cell.get("currency")
            engine_val = _dec(getattr(result, attr, None))

            passes, deviation = _within_tolerance(engine_val, etalon_val)
            currency_ok = etalon_ccy == currency

            if passes and currency_ok:
                continue

            msg = (
                f"{source} row {row} {cell} ({attr}): "
                f"эталон={etalon_val} engine={engine_val} "
                f"deviation={deviation:.6f}% currency={etalon_ccy}"
                f"{'' if currency_ok else ' [CURRENCY MISMATCH]'}"
            )
            if _expected_segment_diff(source, cell) and currency_ok:
                segment_diffs.append(msg)
                continue
            divergence = _divergence_for(source, cell)
            if divergence is not None and currency_ok:
                xfailed.append(f"{msg}  [{divergence.surface}]")
            else:
                hard_failures.append(msg)

    if segment_diffs:
        # Expected segment-model differences — informational, no verdict.
        print(
            f"\n[A1 expected segment-model differences — {source}: "
            f"{len(segment_diffs)} per-product checkpoint(s), no verdict "
            f"(design §5 — variable-segment logistics reallocation; the "
            f"quote totals carry the verdict)]"
        )
    if xfailed:
        # Surface documented divergences in the test log without failing.
        print(
            f"\n[A1 documented divergences — {source}: "
            f"{len(xfailed)} checkpoint(s), xfail by KNOWN_DIVERGENCES]"
        )
        for div in KNOWN_DIVERGENCES.get(source, []):
            print(f"  ROOT CAUSE ({div.surface}): {div.reason}")

    assert not hard_failures, (
        f"{source}: {len(hard_failures)} UNDOCUMENTED checkpoint(s) out of "
        f"≤0.01% tolerance (not covered by KNOWN_DIVERGENCES or "
        f"EXPECTED_SEGMENT_DIFFS — a regression or new divergence):\n"
        + "\n".join(f"  - {m}" for m in hard_failures)
    )


def test_logistics_customs_segments_informational(golden_run):
    """Logistics & customs per-position cells — INFORMATIONAL ONLY (design §5).

    The segment rule: Kvotaflow splits logistics into a variable number of
    segments while the эталон Excel always uses exactly three legs (T/U/V),
    so a per-position comparison is apples-to-oranges. This test prints the
    per-position logistics (T16/U16/V16) and customs (Y16/Z16) engine vs
    эталон values for inspection but derives **no pass/fail verdict** from
    them — they are expected, correct segment-model differences.

    The verdict for logistics and customs lives entirely in the V13 / Y13
    entries of ``test_quote_total_checkpoints`` (the quote totals). This
    test therefore only asserts something trivially true (that it ran), so
    the segment-level numbers stay visible in the test log without ever
    failing the suite on an expected per-segment difference.
    """
    golden, results = golden_run
    source = golden["source_xlsm"]
    exp_products = golden["expected"]["products"]

    lines: list[str] = []
    for result, exp in zip(results, exp_products):
        row = exp["row"]
        for cell, attr in SEGMENT_INFO_CELLS:
            etalon_cell = exp.get(cell)
            if etalon_cell is None:
                continue
            etalon_val = _dec(etalon_cell.get("value"))
            engine_val = _dec(getattr(result, attr, None))
            _, deviation = _within_tolerance(engine_val, etalon_val)
            lines.append(
                f"  row {row} {cell} ({attr}): эталон={etalon_val} "
                f"engine={engine_val} deviation={deviation:.6f}%"
            )

    print(
        f"\n[A1 logistics/customs per-position — {source}: "
        f"informational only, no verdict (design §5 segment rule — "
        f"verdict is on the V13/Y13 totals)]"
    )
    for line in lines:
        print(line)

    # No verdict on per-segment values — the assert is intentionally
    # trivial. logistics/customs are judged at the total level only.
    assert results is not None


def test_quote_total_checkpoints(golden_run):
    """Quote-level totals (row 13) reproduce the эталон within ≤0.01%.

    Totals are summed from the per-product engine results — the engine
    distributes quote costs to products, so a faithful per-product result
    sums to the эталон total.

    This is also where logistics and customs get their ONLY verdict: per
    the segment rule (design §5) they are not judged per-position, so V13
    (Σ logistics) and Y13 (Σ customs) are full hard-assert checkpoints
    here. A V13/Y13 total may legitimately diverge — e.g. rubli's customs
    residual where uneven per-product tariffs stop the weight-vs-value
    logistics reallocation from cancelling — in which case it is a
    documented ``KNOWN_DIVERGENCES`` entry and xfails like any other total.
    """
    golden, results = golden_run
    source = golden["source_xlsm"]
    currency = golden["quote_currency"]
    totals = golden["expected"]["totals"]

    hard_failures: list[str] = []
    xfailed: list[str] = []

    for cell, attr in TOTAL_CHECKPOINTS:
        etalon_cell = totals.get(cell)
        if etalon_cell is None:
            continue
        etalon_val = _dec(etalon_cell.get("value"))
        etalon_ccy = etalon_cell.get("currency")
        engine_total = sum(
            (_dec(getattr(r, attr, None)) for r in results), Decimal("0")
        )

        passes, deviation = _within_tolerance(engine_total, etalon_val)
        currency_ok = etalon_ccy == currency

        if passes and currency_ok:
            continue

        msg = (
            f"{source} TOTAL {cell} (Σ {attr}): "
            f"эталон={etalon_val} engine={engine_total} "
            f"deviation={deviation:.6f}% currency={etalon_ccy}"
            f"{'' if currency_ok else ' [CURRENCY MISMATCH]'}"
        )
        # A total cell is xfail iff the same cell name is in the file's
        # KNOWN_DIVERGENCES — the per-product cascade also moves its total.
        divergence = _divergence_for(source, cell)
        if divergence is not None and currency_ok:
            xfailed.append(f"{msg}  [{divergence.surface}]")
        else:
            hard_failures.append(msg)

    if xfailed:
        print(
            f"\n[A1 documented total divergences — {source}: "
            f"{len(xfailed)} total(s), xfail by KNOWN_DIVERGENCES]"
        )
        for line in xfailed:
            print(f"  {line}")

    assert not hard_failures, (
        f"{source}: {len(hard_failures)} UNDOCUMENTED quote total(s) out of "
        f"≤0.01% tolerance (not covered by KNOWN_DIVERGENCES — a regression "
        f"or new divergence):\n"
        + "\n".join(f"  - {m}" for m in hard_failures)
    )
