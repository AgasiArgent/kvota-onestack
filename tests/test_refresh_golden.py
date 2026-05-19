"""TDD guard for scripts/refresh_golden.py — the эталон extractor.

These tests assert known cell values read directly from the three .xlsm
эталон files (verified manually 2026-05-18). They are the harness-bug
detector required by the A1 design: if the extractor reads the wrong
column or mangles a value, a known-value assertion here fails BEFORE the
golden-master test can produce a false divergence.

The three corpus files share one Excel template, but `rubli_zakaz15` is a
+1-column-shifted variant (an extra "Финансирование вознаграждения"
column at AH). The extractor resolves output columns by header label —
these tests confirm that resolution lands on the right cells for both
template shapes.
"""

import os
import sys

import pytest

# refresh_golden lives in scripts/ (not importable as a package) — add it.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_REPO_ROOT, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import refresh_golden  # noqa: E402

SOURCES = os.path.join(_REPO_ROOT, "tests", "golden", "sources")


def _src(name: str) -> str:
    return os.path.join(SOURCES, name)


# ---------------------------------------------------------------------------
# Corpus presence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fname",
    ["idemitsu.xlsm", "rubli_zakaz15.xlsm", "forma_nds22_18.xlsm"],
)
def test_corpus_file_exists(fname):
    assert os.path.exists(_src(fname)), f"missing эталон corpus file: {fname}"


# ---------------------------------------------------------------------------
# extract_golden — IDEMITSU (1 product, поставка/DDP/EUR, standard template)
# ---------------------------------------------------------------------------


def test_idemitsu_quote_level():
    g = refresh_golden.extract_golden(_src("idemitsu.xlsm"), "idemitsu.xlsm")
    assert g["source_xlsm"] == "idemitsu.xlsm"
    assert g["quote_currency"] == "EUR"
    v = g["inputs"]["variables"]
    assert v["seller_company"] == "МАСТЕР БЭРИНГ ООО (ИНН 0242013464)"
    assert v["offer_sale_type"] == "поставка"
    assert v["offer_incoterms"] == "DDP"
    assert v["delivery_time"] == 80
    # advance_from_client = J5 ≈ 0.5 (50%); advance_to_supplier = D11 = 1.0
    assert abs(v["advance_from_client"] - 0.5) < 1e-9
    assert v["advance_to_supplier"] == 1.0
    # rate_forex_risk = AH11 = 0.03 (standard template)
    assert abs(v["rate_forex_risk"] - 0.03) < 1e-12


def test_idemitsu_product_inputs():
    g = refresh_golden.extract_golden(_src("idemitsu.xlsm"), "idemitsu.xlsm")
    products = g["inputs"]["products"]
    assert len(products) == 1, "IDEMITSU эталон has exactly 1 product row"
    p = products[0]
    assert p["row"] == 16
    assert p["quantity"] == 8000
    assert p["currency_of_base_price"] == "EUR"
    # N16 = 9.4 (price without VAT — K16 blank, user typed N16 directly)
    assert abs(p["price_no_vat"] - 9.4) < 1e-9
    assert abs(p["fx_rate"] - 1.0) < 1e-12  # Q16
    # M16 = 0 → vat_rate 0
    assert abs(p["vat_rate"] - 0.0) < 1e-12
    # X16 = 0.05 import tariff
    assert abs(p["import_tariff"] - 0.05) < 1e-12
    # AC16 = 0.2112 markup
    assert abs(p["markup"] - 0.2112) < 1e-12


def test_idemitsu_expected_outputs():
    g = refresh_golden.extract_golden(_src("idemitsu.xlsm"), "idemitsu.xlsm")
    exp = g["expected"]["products"][0]
    # N16/P16/R16/S16 — purchase block
    assert abs(exp["N16"]["value"] - 9.4) < 1e-6
    assert abs(exp["S16"]["value"] - 75200) < 1e-3
    # logistics V16 = 5486.8
    assert abs(exp["V16"]["value"] - 5486.8) < 1e-3
    # customs Y16 = 4074.74
    assert abs(exp["Y16"]["value"] - 4074.74) < 1e-2
    # COGS AB16 = 85893.55
    assert abs(exp["AB16"]["value"] - 85893.55) < 1e-2
    # final sale with VAT AL16 = 132720
    assert abs(exp["AL16"]["value"] - 132720) < 1e-1
    # currency stamped
    assert exp["S16"]["currency"] == "EUR"


def test_idemitsu_totals():
    g = refresh_golden.extract_golden(_src("idemitsu.xlsm"), "idemitsu.xlsm")
    t = g["expected"]["totals"]
    assert abs(t["S13"]["value"] - 75200) < 1e-3
    assert abs(t["AB13"]["value"] - 85893.55) < 1e-2
    assert abs(t["AL13"]["value"] - 132720) < 1e-1


# ---------------------------------------------------------------------------
# extract_golden — RUBLI_ZAKAZ15 (13 products, +1-shifted template)
# ---------------------------------------------------------------------------


def test_rubli_is_shifted_template():
    g = refresh_golden.extract_golden(_src("rubli_zakaz15.xlsm"), "rubli_zakaz15.xlsm")
    # rubli has the extra "Финансирование вознаграждения" column → output
    # block shifted +1. The extractor must still find AY16 (internal sale
    # total) at the shifted column AZ.
    assert g["template_variant"] == "shifted"


def test_rubli_product_count_and_first_row():
    g = refresh_golden.extract_golden(_src("rubli_zakaz15.xlsm"), "rubli_zakaz15.xlsm")
    products = g["inputs"]["products"]
    assert len(products) == 13
    p = products[0]
    assert p["quantity"] == 40
    # N16 = 63.1086 (price without VAT)
    assert abs(p["price_no_vat"] - 63.1086) < 1e-6
    # Латвия → vat_rate 0.21
    assert abs(p["vat_rate"] - 0.21) < 1e-9
    # fx Q16 ≈ 0.011218648086 (EUR↔RUB multi-currency)
    assert abs(p["fx_rate"] - 0.011218648086) < 1e-12


def test_rubli_expected_outputs_shifted_columns():
    g = refresh_golden.extract_golden(_src("rubli_zakaz15.xlsm"), "rubli_zakaz15.xlsm")
    exp = g["expected"]["products"][0]
    # S16 = 225013.20... ; the resolver must read the SHIFTED financial cols
    assert abs(exp["S16"]["value"] - 225013.208423) < 1e-1
    assert abs(exp["V16"]["value"] - 15621.2952) < 1e-1
    # AF16 (profit) lands at AF in both templates
    assert abs(exp["AF16"]["value"] - 20793.8) < 1e-1
    # AY16 = engine's internal_sale_price_total ("Сумма валютной
    # спецификации"). In the shifted rubli template that label sits at
    # physical column AZ (value 234013.6) — NOT the per-unit "Цена за ед."
    # at AY. This is the exact cell the label-resolver must land on.
    assert abs(exp["AY16"]["value"] - 234013.6) < 1e-1
    # AL16 = "Итого Сумма Продажи с НДС" — at physical column AM in rubli.
    assert abs(exp["AL16"]["value"] - 360031.2) < 1e-1
    assert g["quote_currency"] == "EUR"


def test_rubli_totals():
    g = refresh_golden.extract_golden(_src("rubli_zakaz15.xlsm"), "rubli_zakaz15.xlsm")
    t = g["expected"]["totals"]
    assert abs(t["S13"]["value"] - 1979235.513) < 1e0
    assert abs(t["AB13"]["value"] - 2343485.02) < 1e-1
    # AK13 = sale total NO VAT ("Сумма продажи без НДС") — at AL in rubli.
    assert abs(t["AK13"]["value"] - 2659736.06) < 1e-1
    # AL13 = sale total WITH VAT ("Итого Сумма Продажи с НДС") — at AM in rubli.
    assert abs(t["AL13"]["value"] - 3244877.75) < 1e-1


# ---------------------------------------------------------------------------
# extract_golden — FORMA_NDS22_18 (8 products, no D-column names)
# ---------------------------------------------------------------------------


def test_forma_product_count():
    g = refresh_golden.extract_golden(_src("forma_nds22_18.xlsm"), "forma_nds22_18.xlsm")
    # forma rows have NO column-D names — products keyed off col C / col E
    assert len(g["inputs"]["products"]) == 8


def test_forma_first_product():
    g = refresh_golden.extract_golden(_src("forma_nds22_18.xlsm"), "forma_nds22_18.xlsm")
    p = g["inputs"]["products"][0]
    assert p["quantity"] == 1
    # N16 = 180 (Турция, M16=0.2)
    assert abs(p["price_no_vat"] - 180) < 1e-6
    assert abs(p["vat_rate"] - 0.2) < 1e-9
    assert abs(p["import_tariff"] - 0.1) < 1e-9
    assert g["template_variant"] == "standard"


def test_forma_expected_outputs():
    g = refresh_golden.extract_golden(_src("forma_nds22_18.xlsm"), "forma_nds22_18.xlsm")
    exp = g["expected"]["products"][0]
    assert abs(exp["S16"]["value"] - 180) < 1e-3
    assert abs(exp["AB16"]["value"] - 253.86) < 1e-2
    assert abs(exp["AL16"]["value"] - 421.36) < 1e-2


# ---------------------------------------------------------------------------
# Schema completeness — every product carries all checkpoint cells
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fname",
    ["idemitsu.xlsm", "rubli_zakaz15.xlsm", "forma_nds22_18.xlsm"],
)
def test_golden_schema_complete(fname):
    g = refresh_golden.extract_golden(_src(fname), fname)
    # Required top-level keys
    for key in ("source_xlsm", "quote_idn", "quote_currency", "inputs", "expected"):
        assert key in g, f"{fname}: missing top-level key {key}"
    # Every product's expected block carries each checkpoint cell with a value+currency
    for pexp in g["expected"]["products"]:
        for cell in refresh_golden.PRODUCT_CHECKPOINT_CELLS:
            assert cell in pexp, f"{fname}: product missing checkpoint cell {cell}"
            assert "value" in pexp[cell] and "currency" in pexp[cell]
    # Totals carry the quote-level checkpoints
    for cell in refresh_golden.TOTAL_CHECKPOINT_CELLS:
        assert cell in g["expected"]["totals"], f"{fname}: missing total {cell}"
