"""Track A1 — autonomous golden-master regression for the Calculation Engine.

Design: ``docs/plans/2026-05-18-calc-engine-verification-design.md`` §6 (A1).

For each of the three эталон ".xlsm" files (extracted into JSON golden
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
A1 may legitimately surface a difference between engine/mapping and the
эталон — that is the single most valuable output of this work. A
verdict-bearing checkpoint that genuinely differs by >0.01% is triaged
into one of two categories:

  * ``KNOWN_DIVERGENCES`` — a still-unfixed engine/mapping BUG. The
    offending cell is recorded as XFAIL so the branch stays mergeable
    until the bug is fixed; then the entry is removed. After the Phase-2
    closeout (2026-05-19) this dict is EMPTY: the two targeted Phase-2
    bugs (idemitsu input-mapping, forma %-DM-fee) were fixed, and the two
    residual differences (idemitsu Y16/Y13 rounding residual, forma
    blank-seller financing) were reviewed and ACCEPTED by the user — moved
    to ``ACCEPTED_DIFFERENCES`` below.
  * ``ACCEPTED_DIFFERENCES`` — a CORRECT, PERMANENT difference (an
    intentional engine design choice, e.g. rubli's value-based logistics
    distribution, or a known incomplete эталон file). Logged as accepted,
    never hard-failed; permanent, no future fix removes it.

Passing checkpoints remain hard asserts. A failing checkpoint covered by
NEITHER category is a HARD failure — a regression or a new divergence.
Harness bugs (orders-of-magnitude / wrong-sign / all-zero) are never
xfailed — they are fixed.

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
differences, not bugs, and appear in neither ``KNOWN_DIVERGENCES`` nor
``ACCEPTED_DIFFERENCES``. A logistics or customs *total* (V13/Y13) may
still genuinely differ — that IS a verdict-bearing checkpoint and remains
a hard assert (or, for an accepted methodological difference like rubli's
customs residual, an ``ACCEPTED_DIFFERENCES`` entry).
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
# Two divergence categories — KNOWN_DIVERGENCES vs ACCEPTED_DIFFERENCES.
#
# A1 runs against the production input mapper + the locked engine with all
# live data pinned to the эталон's own values. A checkpoint that genuinely
# differs from the эталон by >0.01% (and is NOT a per-segment logistics/
# customs cell — see the segment rule below) falls into one of two
# categories, with deliberately different intent:
#
#   * KNOWN_DIVERGENCES — a PENDING BUG. A real engine/mapping defect that
#     a future fix must close. The golden-master test records its cell as
#     XFAIL so the branch stays mergeable while the bug is tracked; when
#     the bug is fixed the cell starts passing and its entry is removed.
#     The two targeted Phase-2 bugs (idemitsu input-mapping, forma
#     %-DM-fee) were fixed 2026-05-18. After the Phase-2 closeout
#     (2026-05-19) this dict is EMPTY: the two residual differences
#     (idemitsu AX16 rounding, forma blank-seller financing) were reviewed
#     and ACCEPTED by the user — they are now ACCEPTED_DIFFERENCES entries.
#
#   * ACCEPTED_DIFFERENCES — CORRECT & PERMANENT, not a bug. An accepted
#     difference between the engine and the эталон: either an intentional
#     engine design choice (the engine's behaviour is the chosen design
#     and will NOT change) or a known incomplete эталон file (the engine
#     is correct, the эталон .xlsm is the imperfect side). The test still
#     must not hard-fail on these cells, but they are logged as "accepted
#     methodological difference", never as a pending xfail. An
#     ACCEPTED_DIFFERENCES entry is permanent — there is no future fix to
#     remove it.
#
# Both dicts map source_xlsm → list of entries; each entry lists every
# verdict-bearing checkpoint cell it covers (a PRODUCT_CHECKPOINTS per-
# product cell, or a TOTAL_CHECKPOINTS quote total — including V13/Y13). A
# failing checkpoint covered by NEITHER dict is a HARD failure — that is
# how the suite still catches a regression or a new divergence. Every
# checkpoint that PASSES remains a hard assert.
#
# Segment rule (design §5) — what is NEITHER a divergence NOR an accepted
# difference:
#   Per-position logistics (T16/U16/V16) and customs (Y16/Z16) are NOT
#   verdict-bearing and NEVER appear in either dict: a per-segment
#   difference is the EXPECTED, correct consequence of Kvotaflow's
#   variable-segment logistics model vs the эталон's fixed 3-leg model.
#   Only the logistics/customs TOTALS (V13/Y13) carry a verdict.
# ---------------------------------------------------------------------------


class Divergence:
    """One documented engine/mapping-vs-эталон divergence — a PENDING bug.

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


class AcceptedDifference:
    """One accepted methodological difference — CORRECT & PERMANENT.

    Distinct from ``Divergence``: this is NOT an engine/mapping bug and
    there is no future fix. The engine is correct here; the difference from
    the эталон is a known, accepted consequence of either an intentional
    engine design choice (e.g. rubli's value-based logistics distribution)
    or a known incomplete эталон file (e.g. forma's blank-seller .xlsm,
    where the эталон cell omits RU VAT). The golden-master test does not
    hard-fail on these cells and logs them as "accepted methodological
    difference".

    Attributes:
        surface: the verification surface — "engine" for an accepted engine
            design choice, "эталон" when the эталон file itself is the
            incomplete side and the engine is confirmed correct.
        reason: human-readable explanation of why the difference is
            accepted and permanent.
        cells: set of checkpoint cell names this difference covers.
    """

    def __init__(self, surface: str, reason: str, cells: set[str]):
        self.surface = surface
        self.reason = reason
        self.cells = cells


# source_xlsm → list of PENDING-bug divergences for that file.
#
# EMPTY after the Phase-2 closeout (2026-05-19).
#
# Phase 2 fixed two real bugs: the idemitsu EU-cross-border input-mapping
# bug (services/calculation_helpers.py — resolve_vat_zone now resolves the
# EU-cross-border zone → internal markup 0.04 not 0.02) and the forma
# percentage-DM-fee engine bug (calculation_engine.py phase11 — AG16 now
# computes BD16·pct·AB13). Phase 2c (2026-05-19, user-authorized) aligned
# the engine's rounding policy to the эталон: the 6 money cells the эталон
# rounds to 2dp (Y16, AB16, AJ16, AL16, AM16, AX16) now round to 2dp in
# the engine. Two residual differences remain. The user reviewed both and
# ACCEPTED both — they are NOT pending bugs:
#   * idemitsu Y16/Y13 (~0.039%) — after the rounding alignment AX16 → 2dp
#     matched the эталон's AY16 cell and collapsed the former 13-cell
#     downstream cascade; one residual is left at Y13 because the эталон's
#     Y16 formula uses an INLINE UNROUNDED S16·(1+AW16) rather than its
#     rounded AY16 cell. Same rounding-granularity mismatch, now on Y13,
#     accepted as negligible. → ACCEPTED_DIFFERENCES.
#   * forma financing block (~1.086%) — NOT an engine bug: the forma эталон
#     .xlsm has a blank seller company, so its revenue-estimate BH2 omits
#     the 22% RU VAT and the shortfall cascades through financing/COGS.
#     The engine is correct (engine BH2 = эталон BH2 × 1.22 exactly); the
#     эталон FILE is incomplete. → ACCEPTED_DIFFERENCES.
#
# KNOWN_DIVERGENCES is therefore empty. A new entry would be added here only
# if a future change surfaces a genuine, still-unfixed engine/mapping bug.
KNOWN_DIVERGENCES: dict[str, list[Divergence]] = {}

# source_xlsm → list of ACCEPTED, permanent methodological differences.
ACCEPTED_DIFFERENCES: dict[str, list[AcceptedDifference]] = {
    # RUBLI_ZAKAZ15 — value-based logistics distribution (ACCEPTED, not a
    # bug). The эталон uses TWO distribution bases: a weight-based
    # BD16 = I16/I13 for the logistics legs T16/U16, and a value-based
    # BE16 = S16/S13 for everything else. The engine deliberately uses a
    # SINGLE value-based BD16 for both — weight is not always available in
    # Kvotaflow, so value-based distribution is the chosen, permanent
    # design. This is an accepted methodological difference: the engine's
    # value-based logistics distribution stays.
    #
    # Under the segment rule (design §5) the per-position T16/U16/V16
    # divergence (~27%) is EXPECTED and not judged — and the logistics
    # TOTAL V13 fully dissolves (0.000000%: Σ BD16 = 1 for both bases, so
    # Σ T16 = V11, Σ U16 = W11). What does NOT dissolve is customs: the
    # эталон's Y16 = X16·(S16·(1+AX16) + T16) carries a +T16 term that is
    # weight-redistributed, and because the per-product import tariff X16
    # differs (0/7/8/15%) the redistributed T16 does not cancel in the sum
    # — Σ X16·T16(weight) ≠ Σ X16·T16(value). The customs TOTAL Y13 is
    # therefore ~1.38% short (engine 186157.24 vs эталон 188766.73), and
    # that residual cascades ~0.11% into the COGS / profit / sale-price
    # totals (AB16 = S16+V16+Y16+…). Both the ~1.38% customs residual and
    # the ~0.11% cascade are ACCEPTED, permanent consequences of the
    # value-based-distribution design — not pending bugs.
    "rubli_zakaz15.xlsm": [
        AcceptedDifference(
            surface="engine",
            reason=(
                "Engine distributes logistics by a single value-based "
                "BD16 = S16/S13 (the эталон uses a weight-based BD16 = "
                "I16/I13 for the legs). Value-based distribution is the "
                "chosen, permanent design — product weight is not always "
                "available. The logistics TOTAL V13 dissolves (Σ BD16 = 1 "
                "either way). The customs total does NOT dissolve: "
                "Y16 = X16·(AY16 + T16) carries a weight-redistributed "
                "+T16, and uneven per-product tariffs X16 (0/7/8/15%) "
                "prevent cancellation — Y13 is ~1.38% short and cascades "
                "~0.11% into AB13/AF13/AK13/AL13. Both the customs residual "
                "and the cascade are ACCEPTED, not bugs."
            ),
            cells={
                "Y13", "AB13", "AF13", "AK13", "AL13",
            },
        ),
    ],
    # IDEMITSU — Y16-cascade residual after the эталон rounding alignment
    # (ACCEPTED, not a bug). Phase 2 fixed the idemitsu input-mapping bug
    # (supplier country "ЕС (закупка между странами ЕС)" → wrong "Прочие"
    # zone → internal markup 0.02): resolve_vat_zone now resolves the
    # EU-cross-border zone and the engine uses internal markup 0.04.
    # Phase 2c (2026-05-19, user-authorized) then aligned the engine's
    # rounding policy to the эталон: the 6 money cells the эталон rounds to
    # 2dp (Y16, AB16, AJ16, AL16, AM16, AX16) now round to 2dp in the
    # engine too. AX16 = ROUND(S16·(1+AW16)/E16, 2) = 9.78 (was 9.7760),
    # so AY16 = 78240 — matching the эталон's AY16 cell exactly. That
    # collapsed 9 of the former 13 downstream cells (AY16/AJ16/AK16/AL16/
    # AN16/AO16/AP16/BB16/AK13/AL13 — all GREEN now). FOUR residual cells
    # remain — AD16, AE16, AH16, Y13 — all the SAME root cause: the
    # эталон's Y16 formula = ROUND(X16·(S16·(1+AW16) + T16), 2) recomputes
    # S16·(1+AW16) INLINE and UNROUNDED (78208); it does NOT reference the
    # эталон's rounded AY16 cell. The engine's phase4_duties Y16 consumes
    # the single internal AY16 value, now rounded (78240). So engine Y16
    # is 0.05·(78240−78208) = 1.60 above the эталон → Y13 (Σ Y16) = 4076.34
    # vs 4074.74 (~0.039%), and the +1.60 flows through AB16 = S16+V16+
    # Y16+Z16+… into the sale price AD16/AE16 and the forex reserve AH16
    # (~0.035%). The эталон is internally inconsistent — it rounds AX16
    # for its AY16 cell but uses the unrounded product inside Y16.
    # Removing this residual would require a Y16 formula change (a
    # separate unrounded S16·(1+AW16) input) — out of scope for a
    # precision-only alignment. ~0.039%, negligible — not a logic bug.
    # Permanent.
    "idemitsu.xlsm": [
        AcceptedDifference(
            surface="engine",
            reason=(
                "Y16-каскад после выравнивания округления к эталону: "
                "эталон Y16 = ROUND(X16·(S16·(1+AW16)+T16), 2) считает "
                "S16·(1+AW16) внутри формулы НЕокруглённым (78208), не "
                "берёт округлённую ячейку AY16; движок Y16 потребляет "
                "единое AY16 = 78240 (округлённое). Тот же рассинхрон "
                "гранулярности AX16, +1.60 в Y16 → Y13 ~0.039% и через "
                "AB16 в AD16/AE16/AH16 ~0.035%; принято как "
                "несущественное (пользователь 2026-05-19)."
            ),
            cells={"AD16", "AE16", "AH16", "Y13"},
        ),
    ],
    # FORMA_NDS22_18 — blank-seller эталон file (ACCEPTED, not an engine
    # bug). Phase 2 fixed the percentage-DM-fee engine bug: phase11 now
    # computes AG16 = BD16·pct·AB13 (the эталон "комиссия %" formula). What
    # remains is a ~1.086% financing-block difference that is NOT an engine
    # bug — root cause traced: the forma эталон .xlsm has a BLANK seller
    # company. With no seller the эталон's revenue-estimate BH2 omits the
    # 22% RU VAT a RU seller would carry, and that shortfall cascades
    # through the financing block (BA16/BB16 come out ~half the эталон) into
    # AB16 = S16+V16+Y16+Z16+BA16+BB16 and on into every forma COGS /
    # profit / sale-price / VAT cell, ~1.086% short; AG16 inherits the same
    # ~1.086% via its quote-level base AB13 = Σ AB16. The engine is correct
    # — it applies RU VAT for a RU seller, and engine BH2 = эталон BH2 ×
    # 1.22 exactly. The эталон FILE is incomplete, not the engine. The user
    # reviewed this (2026-05-19) and ACCEPTED it. Permanent; the difference
    # would only disappear if the эталон file were re-saved with a seller.
    "forma_nds22_18.xlsm": [
        AcceptedDifference(
            surface="эталон",
            reason=(
                "forma: эталонный файл с НЕзаполненным продавцом → BH2 без "
                "НДС РФ → каскад в финансирование/COGS/ниже. Движок "
                "корректен; расхождение из-за неполного эталонного файла, "
                "не баг движка (пользователь 2026-05-19)."
            ),
            cells={
                "AA16", "AB16", "AD16", "AE16", "AF16", "AG16", "AH16",
                "AJ16", "AK16", "AL16", "AN16", "AP16", "BA16", "BB16",
                "AB13", "AF13", "AK13", "AL13",
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
# residual survives, that total is itself an ACCEPTED_DIFFERENCES entry —
# e.g. rubli's Y13/AB13 customs residual, an accepted permanent consequence
# of the engine's value-based logistics distribution). The golden-master
# test prints these as "expected segment-model difference" and derives NO
# pass/fail from the per-product cell — exactly as it does for T16/U16/V16.
# xfail is NOT used: these are correct behaviour, not bugs.
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


def _accepted_difference_for(source: str, cell: str):
    """Return the AcceptedDifference covering ``cell`` for ``source``, or None.

    An accepted difference (``ACCEPTED_DIFFERENCES``) is a correct, permanent
    methodological difference between the engine and the эталон — not a bug.
    A checkpoint it covers is logged as accepted and never hard-fails.
    """
    for acc in ACCEPTED_DIFFERENCES.get(source, []):
        if cell in acc.cells:
            return acc
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
    uniform col-Q rate (verified — idemitsu/forma = 1.0, rubli =
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
    fraction). ``rate_forex_risk`` is a live admin-data input, so — exactly
    like FX and tariff — it is pinned to the эталон value here. (For all
    three corpus files the эталон rate is 3%, which coincides with the
    default; the per-file pin keeps the harness correct should the corpus
    grow a file with a different rate.)
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

    A failing checkpoint is triaged into one of four buckets:

      * **expected segment-model difference** — its cell is in this file's
        ``EXPECTED_SEGMENT_DIFFS`` set: the divergence is the correct,
        mechanical consequence of Kvotaflow's variable-segment logistics
        model (design §5). No pass/fail verdict; printed for inspection.
        NOT an xfail — this is correct behaviour, not a bug.
      * **accepted methodological difference** — its cell is in this
        file's ``ACCEPTED_DIFFERENCES`` set: a correct, permanent
        difference between the engine and the эталон (an intentional
        engine design choice). No hard failure; logged as accepted. NOT
        an xfail — there is no pending fix.
      * **documented divergence (XFAIL)** — its cell is in this file's
        ``KNOWN_DIVERGENCES`` set: a genuine, still-unfixed engine/mapping
        bug. The test stays green so the branch is mergeable until the
        bug is fixed.
      * **HARD failure** — covered by none of the above: a regression or
        a new divergence. That is how the suite still catches one.

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
    accepted: list[str] = []
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
            accepted_diff = _accepted_difference_for(source, cell)
            if accepted_diff is not None and currency_ok:
                accepted.append(f"{msg}  [{accepted_diff.surface}]")
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
    if accepted:
        # Accepted methodological differences — correct & permanent, not bugs.
        print(
            f"\n[A1 accepted methodological differences — {source}: "
            f"{len(accepted)} checkpoint(s), correct & permanent "
            f"(ACCEPTED_DIFFERENCES — not a pending fix)]"
        )
        for acc in ACCEPTED_DIFFERENCES.get(source, []):
            print(f"  ACCEPTED ({acc.surface}): {acc.reason}")
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
        f"≤0.01% tolerance (not covered by KNOWN_DIVERGENCES, "
        f"ACCEPTED_DIFFERENCES or EXPECTED_SEGMENT_DIFFS — a regression or "
        f"new divergence):\n"
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
    here. A V13/Y13 total may legitimately differ from the эталон — e.g.
    rubli's customs residual, where the engine's accepted value-based
    logistics distribution leaves Y13 ~1.38% short — in which case it is
    an ``ACCEPTED_DIFFERENCES`` entry (correct & permanent, not a bug) and
    is logged as accepted instead of hard-failing. A still-unfixed bug
    would instead be a ``KNOWN_DIVERGENCES`` entry and xfail.
    """
    golden, results = golden_run
    source = golden["source_xlsm"]
    currency = golden["quote_currency"]
    totals = golden["expected"]["totals"]

    hard_failures: list[str] = []
    xfailed: list[str] = []
    accepted: list[str] = []

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
        # A total cell is an accepted difference (correct & permanent) iff
        # its cell name is in ACCEPTED_DIFFERENCES; a still-unfixed bug iff
        # in KNOWN_DIVERGENCES — the per-product cascade also moves its total.
        accepted_diff = _accepted_difference_for(source, cell)
        if accepted_diff is not None and currency_ok:
            accepted.append(f"{msg}  [{accepted_diff.surface}]")
            continue
        divergence = _divergence_for(source, cell)
        if divergence is not None and currency_ok:
            xfailed.append(f"{msg}  [{divergence.surface}]")
        else:
            hard_failures.append(msg)

    if accepted:
        print(
            f"\n[A1 accepted methodological total differences — {source}: "
            f"{len(accepted)} total(s), correct & permanent "
            f"(ACCEPTED_DIFFERENCES — not a pending fix)]"
        )
        for line in accepted:
            print(f"  {line}")
    if xfailed:
        print(
            f"\n[A1 documented total divergences — {source}: "
            f"{len(xfailed)} total(s), xfail by KNOWN_DIVERGENCES]"
        )
        for line in xfailed:
            print(f"  {line}")

    assert not hard_failures, (
        f"{source}: {len(hard_failures)} UNDOCUMENTED quote total(s) out of "
        f"≤0.01% tolerance (not covered by KNOWN_DIVERGENCES or "
        f"ACCEPTED_DIFFERENCES — a regression or new divergence):\n"
        + "\n".join(f"  - {m}" for m in hard_failures)
    )
