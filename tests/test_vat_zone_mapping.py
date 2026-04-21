"""
Tests for VAT Zone Mapping Layer.

Two-factor mapping: (country + price_includes_vat) → SupplierCountry enum value.

Functions under test:
  - normalize_country_to_iso(value) → ISO code
  - resolve_vat_zone(country_raw, price_includes_vat) → dict
  - build_vat_zone_info(items) → dict with aggregate status
"""

import pytest
import os


# ============================================================================
# Import helpers
# ============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _import_from_main(name):
    """Historic name — after Phase 6C-3 the helpers live in services.calculation_helpers."""
    os.environ.setdefault("TESTING", "true")
    os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("SUPABASE_KEY", "test-key")
    os.environ.setdefault("APP_SECRET", "test-secret")
    import importlib
    helpers_mod = importlib.import_module("services.calculation_helpers")
    return getattr(helpers_mod, name)


# ============================================================================
# 1. resolve_vat_zone — direct matches WITH VAT
# ============================================================================

class TestResolveVatZoneDirectMatchesWithVat:
    def test_turkey_with_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("TR", True)
        assert result["zone"] == "Турция"
        assert result["error"] is None

    def test_russia_with_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("RU", True)
        assert result["zone"] == "Россия"
        assert result["error"] is None

    def test_china_with_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("CN", True)
        assert result["zone"] == "Китай"
        assert result["error"] is None

    def test_china_without_vat(self):
        """China always maps to Китай regardless of VAT flag."""
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("CN", False)
        assert result["zone"] == "Китай"
        assert result["error"] is None

    def test_uae_with_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("AE", True)
        assert result["zone"] == "ОАЭ"
        assert result["error"] is None


# ============================================================================
# 2. resolve_vat_zone — direct matches WITHOUT VAT
# ============================================================================

class TestResolveVatZoneDirectMatchesWithoutVat:
    def test_turkey_without_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("TR", False)
        assert result["zone"] == "Прочие"
        assert result["warning"] is not None

    def test_russia_without_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("RU", False)
        assert result["zone"] == "Прочие"
        assert result["warning"] is not None


# ============================================================================
# 3. resolve_vat_zone — EU WITHOUT VAT → cross-border
# ============================================================================

class TestResolveVatZoneEuWithoutVat:
    def test_belgium_without_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("BE", False)
        assert result["zone"] == "ЕС (между странами ЕС)"
        assert result["warning"] is not None
        assert result["error"] is None

    def test_germany_without_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("DE", False)
        assert result["zone"] == "ЕС (между странами ЕС)"
        assert result["error"] is None

    def test_france_without_vat(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("FR", False)
        assert result["zone"] == "ЕС (между странами ЕС)"


# ============================================================================
# 4. resolve_vat_zone — EU WITH VAT (matching zone exists)
# ============================================================================

class TestResolveVatZoneEuWithVatMatching:
    def test_belgium_with_vat_21_maps_to_litva(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("BE", True)
        assert result["zone"] == "Литва"
        assert result["error"] is None
        assert "21%" in result["reason"]

    def test_france_with_vat_20_maps_to_bulgaria(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("FR", True)
        assert result["zone"] == "Болгария"
        assert result["error"] is None
        assert "20%" in result["reason"]

    def test_poland_with_vat_23_maps_to_poland(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("PL", True)
        assert result["zone"] == "Польша"
        assert result["error"] is None

    def test_portugal_with_vat_23_maps_to_poland(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("PT", True)
        assert result["zone"] == "Польша"
        assert result["error"] is None

    def test_latvia_with_vat_21_maps_to_latvia(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("LV", True)
        assert result["zone"] == "Латвия"
        assert result["error"] is None

    def test_austria_with_vat_20_maps_to_bulgaria(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("AT", True)
        assert result["zone"] == "Болгария"
        assert result["error"] is None


# ============================================================================
# 5. resolve_vat_zone — EU WITH VAT (no matching zone → error)
# ============================================================================

class TestResolveVatZoneEuWithVatNoMatch:
    def test_germany_with_vat_19_error(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("DE", True)
        assert result["zone"] is None
        assert result["error"] is not None
        assert "19%" in result["error"]

    def test_italy_with_vat_22_error(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("IT", True)
        assert result["zone"] is None
        assert result["error"] is not None

    def test_sweden_with_vat_25_error(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("SE", True)
        assert result["zone"] is None
        assert result["error"] is not None


# ============================================================================
# 6. resolve_vat_zone — normalization of various inputs
# ============================================================================

class TestResolveVatZoneNormalization:
    def test_russian_name_belgium(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("Бельгия", False)
        assert result["zone"] == "ЕС (между странами ЕС)"

    def test_russian_name_turkey(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("Турция", True)
        assert result["zone"] == "Турция"

    def test_english_name_turkey(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("Turkey", True)
        assert result["zone"] == "Турция"

    def test_empty_string(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("", False)
        assert result["zone"] == "Прочие"
        assert result["warning"] is not None

    def test_enum_value_litva(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("Литва", True)
        assert result["zone"] == "Литва"

    def test_unknown_country(self):
        resolve = _import_from_main("resolve_vat_zone")
        result = resolve("ZZ", False)
        assert result["zone"] == "Прочие"


# ============================================================================
# 7. normalize_country_to_iso
# ============================================================================

class TestNormalizeCountryToIso:
    def test_iso_code(self):
        normalize = _import_from_main("normalize_country_to_iso")
        assert normalize("BE") == "BE"
        assert normalize("de") == "DE"

    def test_russian_name(self):
        normalize = _import_from_main("normalize_country_to_iso")
        assert normalize("Бельгия") == "BE"
        assert normalize("Турция") == "TR"
        assert normalize("Китай") == "CN"

    def test_english_name(self):
        normalize = _import_from_main("normalize_country_to_iso")
        assert normalize("Belgium") == "BE"
        assert normalize("Turkey") == "TR"

    def test_enum_value(self):
        normalize = _import_from_main("normalize_country_to_iso")
        assert normalize("Литва") == "LT"
        assert normalize("Болгария") == "BG"

    def test_empty(self):
        normalize = _import_from_main("normalize_country_to_iso")
        assert normalize("") == ""
        assert normalize(None) == ""


# TestBuildVatZoneInfo removed in Phase 6C-2B Mega-B — `build_vat_zone_info`
# lived in main.py next to the other Janna checklist helpers and was archived
# to legacy-fasthtml/control_flow.py alongside its only caller
# /quote-control/{quote_id}. The live `normalize_country_to_iso` and
# `resolve_vat_zone` coverage above is unchanged.
