"""TDD guard for tests/golden_support.py — the golden-JSON → items shim.

Confirms the shim emits the exact ``items`` / ``variables`` shape the
production ``build_calculation_inputs`` consumes, and that its mechanical
remaps (fraction→percent, base-price VAT reconstruction, seller-name and
customs-code normalisation) are correct.
"""

import json
import os

import pytest

from tests import golden_support

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GOLDEN = os.path.join(_REPO_ROOT, "tests", "golden")


def _load(name: str) -> dict:
    with open(os.path.join(_GOLDEN, name), encoding="utf-8") as fh:
        return json.load(fh)


CORPUS = ["idemitsu.json", "rubli_zakaz15.json", "forma_nds22_18.json", "amtel_cofly.json"]


@pytest.mark.parametrize("name", CORPUS)
def test_golden_json_exists(name):
    assert os.path.exists(os.path.join(_GOLDEN, name)), (
        f"missing golden fixture {name} — run scripts/refresh_golden.py"
    )


@pytest.mark.parametrize("name", CORPUS)
def test_shim_returns_items_and_variables(name):
    items, variables = golden_support.golden_to_items_and_variables(_load(name))
    assert isinstance(items, list) and items, "items must be a non-empty list"
    assert isinstance(variables, dict)
    # Each item is a dict in get_composed_items shape.
    for it in items:
        assert isinstance(it, dict)
        assert "purchase_price_original" in it
        assert "quantity" in it
        assert "supplier_country" in it


def test_shim_idemitsu_variables():
    items, variables = golden_support.golden_to_items_and_variables(_load("idemitsu.json"))
    # idemitsu col Q == 1 → engine quote currency stays the item currency.
    assert variables["currency_of_quote"] == "EUR"
    assert variables["offer_sale_type"] == "поставка"
    assert variables["offer_incoterms"] == "DDP"
    # advance_from_client: эталон fraction 0.5 → 50 percent
    assert abs(variables["advance_from_client"] - 50.0) < 1e-6
    assert abs(variables["advance_to_supplier"] - 100.0) < 1e-6
    # First leg = эталон V11 MINUS the insurance line (36.8): the engine
    # re-adds insurance itself in Phase 3, so the shim feeds 3286.8 − 36.8.
    assert abs(variables["logistics_supplier_hub"] - 3250.0) < 1e-3
    assert abs(variables["logistics_customs_client"] - 2200.0) < 1e-3


def test_shim_rubli_uses_distinct_engine_currency():
    """rubli's col Q ≠ 1 → engine quote currency must differ from item EUR."""
    _, variables = golden_support.golden_to_items_and_variables(_load("rubli_zakaz15.json"))
    assert variables["currency_of_quote"] != "EUR"
    assert variables["currency_of_quote"] == "RUB"


def test_shim_idemitsu_item_base_price():
    items, _ = golden_support.golden_to_items_and_variables(_load("idemitsu.json"))
    assert len(items) == 1
    it = items[0]
    assert it["quantity"] == 8000
    # IDEMITSU country = "ЕС (закупка между странами ЕС)" → zone "ЕС (между
    # странами ЕС)" → zone VAT 0% → reconstructed base price == эталон N16.
    assert abs(it["purchase_price_original"] - 9.4) < 1e-9
    # markup: эталон fraction 0.2112 → 21.12 percent.
    assert abs(it["markup"] - 21.12) < 1e-6
    assert it["price_includes_vat"] is True


def test_shim_rubli_base_price_vat_reconstruction():
    """Латвия zone has 21% VAT — base price must gross up N16 by ×1.21."""
    items, _ = golden_support.golden_to_items_and_variables(_load("rubli_zakaz15.json"))
    it = items[0]
    # эталон N16 = 63.1086, zone VAT 0.21 → with-VAT = 63.1086 × 1.21.
    assert abs(it["purchase_price_original"] - 63.1086 * 1.21) < 1e-6
    assert len(items) == 13


def test_shim_amtel_seller_company_normalised():
    items, variables = golden_support.golden_to_items_and_variables(_load("amtel_cofly.json"))
    # эталон D5 = "TEXCEL OTOMOTİV TİCARET LİMİTED ŞİRKETİ (Турция)"
    # → bare legal name (the parenthetical suffix stripped).
    assert variables["seller_company"] == "TEXCEL OTOMOTİV TİCARET LİMİTED ŞİRKETİ"
    assert variables["offer_sale_type"] == "транзит"
    assert len(items) == 103


def test_shim_forma_seller_company_default():
    """forma_nds22_18 has a blank D5 — shim must default to a valid enum."""
    _, variables = golden_support.golden_to_items_and_variables(_load("forma_nds22_18.json"))
    assert variables["seller_company"] == "МАСТЕР БЭРИНГ ООО"


def test_shim_customs_code_normalised():
    """A spaced/short customs code collapses to the 10-digit placeholder."""
    items, _ = golden_support.golden_to_items_and_variables(_load("rubli_zakaz15.json"))
    for it in items:
        code = it["customs_code"]
        assert len(code) == 10 and code.isdigit()
