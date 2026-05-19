"""TDD guard for Track B — the offline comparison-computation logic.

Track B of the Calculation Engine verification (see
``docs/plans/2026-05-18-calc-engine-verification-design.md`` §8). Track B
turns the engine-vs-эталон comparison into a human-readable .xlsx artifact
for non-coding reviewers.

This module tests the *computation* layer that feeds that .xlsx — the
deviation %, the PASS/FAIL/segment verdict, and the segment-rule
classification (design §5) — all of which live in
``tests.golden_support`` so Track A1 and Track B share one definition.

The .xlsx writing itself (``scripts/generate_calc_comparison.py``) is
verified by generating the files and sanity-checking them, not here.

Tolerance and segment rule (design §5)
--------------------------------------
* A cell PASSES iff ``|engine − эталон| / max(|эталон|, EPS) ≤ 1e-4``
  (≤0.01%), or — near zero — ``|engine − эталон| ≤ ABS_TOL``.
* Logistics/customs **per-position** cells (T16/U16/V16/Y16/Z16) and the
  downstream per-product cells they reallocate carry NO pass/fail verdict
  — they are an expected consequence of Kvotaflow's variable-segment
  logistics model. Their verdict lives only at the quote-total level
  (V13/Y13).
"""

from __future__ import annotations

from decimal import Decimal

from tests import golden_support


# ---------------------------------------------------------------------------
# Tolerance constants — must equal Track A1's (design §5).
# ---------------------------------------------------------------------------


def test_tolerance_constants_match_a1():
    """The comparison module pins the same ≤0.01% tolerance as A1."""
    assert golden_support.REL_TOL == Decimal("1e-4")
    assert golden_support.EPS == Decimal("1e-6")
    assert golden_support.ABS_TOL == Decimal("0.01")


# ---------------------------------------------------------------------------
# deviation / within-tolerance
# ---------------------------------------------------------------------------


def test_within_tolerance_exact_match_passes():
    passes, dev = golden_support.within_tolerance(Decimal("100"), Decimal("100"))
    assert passes is True
    assert dev == Decimal("0")


def test_within_tolerance_hairline_under_001pct_passes():
    # 100.005 vs 100 → 0.005% < 0.01%
    passes, dev = golden_support.within_tolerance(Decimal("100.005"), Decimal("100"))
    assert passes is True
    assert dev < Decimal("0.01")


def test_within_tolerance_over_001pct_fails():
    # 100.02 vs 100 → 0.02% > 0.01%
    passes, dev = golden_support.within_tolerance(Decimal("100.02"), Decimal("100"))
    assert passes is False
    assert dev > Decimal("0.01")


def test_within_tolerance_near_zero_uses_absolute_criterion():
    # эталон below EPS → absolute criterion |Δ| ≤ ABS_TOL.
    passes, dev = golden_support.within_tolerance(Decimal("0.005"), Decimal("0"))
    assert passes is True  # 0.005 ≤ 0.01
    assert dev == Decimal("0.005")  # reports the absolute delta near zero

    fails, _ = golden_support.within_tolerance(Decimal("0.5"), Decimal("0"))
    assert fails is False  # 0.5 > 0.01


def test_within_tolerance_deviation_is_a_percentage():
    # 110 vs 100 → exactly 10%.
    _, dev = golden_support.within_tolerance(Decimal("110"), Decimal("100"))
    assert dev == Decimal("10")


# ---------------------------------------------------------------------------
# coerce_decimal — None / blank tolerant
# ---------------------------------------------------------------------------


def test_coerce_decimal_handles_none_and_blank():
    assert golden_support.coerce_decimal(None) == Decimal("0")
    assert golden_support.coerce_decimal("") == Decimal("0")
    assert golden_support.coerce_decimal(12.5) == Decimal("12.5")
    assert golden_support.coerce_decimal("3.25") == Decimal("3.25")


# ---------------------------------------------------------------------------
# Segment-rule classification (design §5)
# ---------------------------------------------------------------------------


def test_per_position_logistics_customs_cells_are_segment_informational():
    """T16/U16/V16/Y16/Z16 are always informational, for every corpus file."""
    for cell in ("T16", "U16", "V16", "Y16", "Z16"):
        assert golden_support.is_segment_informational("idemitsu.xlsm", cell)
        assert golden_support.is_segment_informational("rubli_zakaz15.xlsm", cell)
        assert golden_support.is_segment_informational("forma_nds22_18.xlsm", cell)


def test_downstream_per_product_cells_are_segment_informational_only_for_rubli():
    """Downstream per-product cells are segment-informational only for rubli.

    rubli is the one corpus file with product weights AND a multi-segment
    logistics split, so its weight-based per-leg distribution reallocates
    logistics across positions. idemitsu/forma split logistics
    value-based on both sides — their per-product divergences are genuine.
    """
    # rubli: AB16 (COGS per product) inherits the logistics reallocation.
    assert golden_support.is_segment_informational("rubli_zakaz15.xlsm", "AB16")
    # idemitsu: AB16 is NOT segment-informational — a real divergence there
    # is genuine and must keep its verdict.
    assert not golden_support.is_segment_informational("idemitsu.xlsm", "AB16")
    assert not golden_support.is_segment_informational("forma_nds22_18.xlsm", "AB16")


def test_purchase_cells_never_segment_informational():
    """Purchase-price cells (N16/P16/S16) carry a verdict for every file."""
    for cell in ("N16", "P16", "R16", "S16"):
        for src in ("idemitsu.xlsm", "rubli_zakaz15.xlsm", "forma_nds22_18.xlsm"):
            assert not golden_support.is_segment_informational(src, cell)


# ---------------------------------------------------------------------------
# classify_cell — the per-cell verdict the .xlsx colour-codes on
# ---------------------------------------------------------------------------


def test_classify_cell_pass_when_within_tolerance():
    row = golden_support.classify_cell(
        source="idemitsu.xlsm",
        cell="S16",
        field="purchase_price_total_quote_currency",
        engine_val=Decimal("75200"),
        etalon_val=Decimal("75200"),
        is_total=False,
    )
    assert row.verdict == golden_support.VERDICT_PASS
    assert row.deviation_pct == Decimal("0")
    assert row.abs_delta == Decimal("0")


def test_classify_cell_fail_when_out_of_tolerance_and_verdict_bearing():
    # idemitsu S16 is verdict-bearing — a 5% gap is a FAIL.
    row = golden_support.classify_cell(
        source="idemitsu.xlsm",
        cell="S16",
        field="purchase_price_total_quote_currency",
        engine_val=Decimal("79000"),
        etalon_val=Decimal("75200"),
        is_total=False,
    )
    assert row.verdict == golden_support.VERDICT_FAIL
    assert row.deviation_pct > Decimal("0.01")


def test_classify_cell_segment_difference_not_fail_for_per_position_cell():
    """A diverging per-position logistics cell → segment verdict, never FAIL."""
    row = golden_support.classify_cell(
        source="rubli_zakaz15.xlsm",
        cell="V16",
        field="logistics_total",
        engine_val=Decimal("1000"),
        etalon_val=Decimal("1270"),  # ~27% gap — expected per segment rule
        is_total=False,
    )
    assert row.verdict == golden_support.VERDICT_SEGMENT
    # The deviation is still reported (informational).
    assert row.deviation_pct > Decimal("0.01")


def test_classify_cell_segment_difference_for_rubli_downstream_cell():
    """rubli's downstream per-product cell diverging → segment, not FAIL."""
    row = golden_support.classify_cell(
        source="rubli_zakaz15.xlsm",
        cell="AB16",
        field="cogs_per_product",
        engine_val=Decimal("1000"),
        etalon_val=Decimal("1100"),
        is_total=False,
    )
    assert row.verdict == golden_support.VERDICT_SEGMENT


def test_classify_cell_total_logistics_is_verdict_bearing():
    """V13 (logistics TOTAL) carries a real PASS/FAIL — segment rule §5."""
    fail_row = golden_support.classify_cell(
        source="rubli_zakaz15.xlsm",
        cell="V13",
        field="logistics_total",
        engine_val=Decimal("1000"),
        etalon_val=Decimal("1100"),
        is_total=True,
    )
    assert fail_row.verdict == golden_support.VERDICT_FAIL

    pass_row = golden_support.classify_cell(
        source="rubli_zakaz15.xlsm",
        cell="V13",
        field="logistics_total",
        engine_val=Decimal("1100"),
        etalon_val=Decimal("1100"),
        is_total=True,
    )
    assert pass_row.verdict == golden_support.VERDICT_PASS


def test_classify_cell_currency_mismatch_is_fail():
    """A currency mismatch is always a FAIL, even if the magnitude matches."""
    row = golden_support.classify_cell(
        source="idemitsu.xlsm",
        cell="S16",
        field="purchase_price_total_quote_currency",
        engine_val=Decimal("75200"),
        etalon_val=Decimal("75200"),
        is_total=False,
        engine_currency="USD",
        etalon_currency="EUR",
    )
    assert row.verdict == golden_support.VERDICT_FAIL
    assert row.currency_mismatch is True


# ---------------------------------------------------------------------------
# Verdict banner aggregation
# ---------------------------------------------------------------------------


def _row(verdict, dev):
    """Build a minimal ComparisonRow for banner tests."""
    return golden_support.ComparisonRow(
        position="поз. 1",
        cell="X16",
        field="field",
        engine_val=Decimal("0"),
        etalon_val=Decimal("0"),
        abs_delta=Decimal("0"),
        deviation_pct=Decimal(str(dev)),
        verdict=verdict,
        currency_mismatch=False,
    )


def test_verdict_banner_all_pass():
    rows = [
        _row(golden_support.VERDICT_PASS, "0.001"),
        _row(golden_support.VERDICT_PASS, "0.003"),
    ]
    banner = golden_support.build_verdict_banner(rows)
    assert "ВСЁ СХОДИТСЯ" in banner
    assert "0.003" in banner


def test_verdict_banner_with_failures():
    rows = [
        _row(golden_support.VERDICT_PASS, "0.001"),
        _row(golden_support.VERDICT_FAIL, "1.38"),
        _row(golden_support.VERDICT_FAIL, "0.5"),
    ]
    banner = golden_support.build_verdict_banner(rows)
    assert "РАСХОЖДЕНИЕ" in banner
    assert "2" in banner  # 2 failing cells
    assert "1.38" in banner  # max deviation among failures


def test_verdict_banner_segment_rows_excluded_from_failure_count():
    """Segment-informational rows never count toward the failure verdict."""
    rows = [
        _row(golden_support.VERDICT_PASS, "0.002"),
        _row(golden_support.VERDICT_SEGMENT, "27.0"),  # huge but expected
    ]
    banner = golden_support.build_verdict_banner(rows)
    assert "ВСЁ СХОДИТСЯ" in banner
    # The 27% segment deviation must NOT appear as the max — only verdict-
    # bearing rows drive the banner's max.
    assert "27" not in banner


def test_verdict_banner_segment_max_excluded_even_with_failures():
    rows = [
        _row(golden_support.VERDICT_FAIL, "1.5"),
        _row(golden_support.VERDICT_SEGMENT, "30.0"),
    ]
    banner = golden_support.build_verdict_banner(rows)
    assert "РАСХОЖДЕНИЕ" in banner
    assert "1.5" in banner
    assert "30" not in banner


# ---------------------------------------------------------------------------
# build_comparison_rows — end-to-end on the real corpus
# ---------------------------------------------------------------------------


def test_build_comparison_rows_idemitsu_produces_rows():
    """The whole comparison runs end-to-end on idemitsu and yields rows."""
    result = golden_support.build_comparison("idemitsu.json")
    assert result.source_xlsm == "idemitsu.xlsm"
    assert result.quote_currency == "EUR"
    assert len(result.rows) > 0
    assert len(result.input_rows) == 1  # idemitsu has one product
    # Every row carries a verdict.
    for row in result.rows:
        assert row.verdict in (
            golden_support.VERDICT_PASS,
            golden_support.VERDICT_FAIL,
            golden_support.VERDICT_SEGMENT,
        )
    # The banner is a non-empty string.
    assert isinstance(result.banner, str) and result.banner


def test_build_comparison_rows_segment_rule_applied_for_rubli():
    """rubli's per-position logistics rows never FAIL — segment rule §5.

    A per-position logistics/customs cell is verdict-free: when it diverges
    it is ``VERDICT_SEGMENT``, when it happens to match (e.g. rubli's Z16
    excise = 0 on both sides) it is ``VERDICT_PASS``. The forbidden outcome
    is ``VERDICT_FAIL`` — these cells are an EXPECTED segment-model effect.
    """
    result = golden_support.build_comparison("rubli_zakaz15.json")
    per_position_logistics = [
        r for r in result.rows if r.cell in ("T16", "U16", "V16", "Y16", "Z16")
    ]
    assert per_position_logistics, "expected per-position logistics rows"
    for row in per_position_logistics:
        assert row.verdict != golden_support.VERDICT_FAIL, (
            f"{row.cell} is a per-position logistics/customs cell — it must "
            f"never FAIL (segment rule §5), got {row.verdict}"
        )
    # At least one per-position cell genuinely diverges (rubli's weight-based
    # logistics split) — confirm the segment verdict actually fires.
    assert any(
        r.verdict == golden_support.VERDICT_SEGMENT for r in per_position_logistics
    ), "expected at least one VERDICT_SEGMENT among rubli's logistics legs"
    # The logistics/customs TOTAL rows DO carry a verdict.
    total_rows = [r for r in result.rows if r.cell in ("V13", "Y13")]
    assert total_rows, "expected V13/Y13 total rows"
    for row in total_rows:
        assert row.verdict in (golden_support.VERDICT_PASS, golden_support.VERDICT_FAIL)


def test_build_comparison_input_rows_expose_visible_inputs():
    """The input layer exposes qty / price / currency / country per position."""
    result = golden_support.build_comparison("rubli_zakaz15.json")
    assert len(result.input_rows) == 13  # rubli has 13 products
    first = result.input_rows[0]
    assert first.quantity is not None
    assert first.currency
    assert first.country
