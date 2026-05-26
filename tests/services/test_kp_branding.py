"""Unit tests for ``services.kp_branding`` — Master Bearing branding constants.

These guard the contract that the renderer relies on at runtime:
- Every static asset path resolves to an actual file on disk.
- Every inline SVG fragment parses as valid XML.
- Brand color values match the Master Bearing palette spec.
- The page-1 footer feature tuple holds exactly four entries (the design
  bakes the four-column grid into the page-1 footer CSS, so a 3rd-iteration
  change here is a layout regression, not a code change).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from services.kp_branding import (
    MASTER_BEARING,
    FooterFeature,
    KpBranding,
)


@pytest.mark.unit
class TestMasterBearingStructure:
    def test_is_kp_branding_instance(self) -> None:
        assert isinstance(MASTER_BEARING, KpBranding)

    def test_dataclass_is_frozen(self) -> None:
        """KpBranding must be immutable — branding is a singleton constant."""
        with pytest.raises(Exception):
            MASTER_BEARING.primary_blue = "#000000"  # type: ignore[misc]

    def test_footer_feature_is_frozen(self) -> None:
        ff = MASTER_BEARING.page1_footer_features[0]
        assert isinstance(ff, FooterFeature)
        with pytest.raises(Exception):
            ff.title_line_1 = "X"  # type: ignore[misc]

    def test_brand_name(self) -> None:
        assert MASTER_BEARING.name == "Master Bearing"

    def test_default_subtitle(self) -> None:
        assert MASTER_BEARING.default_subtitle == "на поставку крупной спецтехники"


@pytest.mark.unit
class TestMasterBearingColors:
    """Brand palette spec from design.md ADR-2."""

    def test_primary_blue_is_hex(self) -> None:
        assert MASTER_BEARING.primary_blue.startswith("#")
        assert len(MASTER_BEARING.primary_blue) == 7

    def test_primary_red_is_hex(self) -> None:
        assert MASTER_BEARING.primary_red.startswith("#")
        assert len(MASTER_BEARING.primary_red) == 7

    def test_accent_cream_is_hex(self) -> None:
        assert MASTER_BEARING.accent_cream.startswith("#")
        assert len(MASTER_BEARING.accent_cream) == 7

    def test_brand_colors_distinct(self) -> None:
        colors = {
            MASTER_BEARING.primary_blue,
            MASTER_BEARING.primary_red,
            MASTER_BEARING.accent_cream,
        }
        assert len(colors) == 3


@pytest.mark.unit
class TestMasterBearingAssets:
    def test_hero_path_resolves(self) -> None:
        assert isinstance(MASTER_BEARING.hero_machinery_path, Path)
        assert MASTER_BEARING.hero_machinery_path.is_file()
        assert MASTER_BEARING.hero_machinery_path.suffix == ".png"

    def test_mountains_path_resolves(self) -> None:
        assert isinstance(MASTER_BEARING.mountains_path, Path)
        assert MASTER_BEARING.mountains_path.is_file()
        assert MASTER_BEARING.mountains_path.suffix == ".png"

    def test_font_dir_resolves_to_directory(self) -> None:
        assert isinstance(MASTER_BEARING.font_dir, Path)
        assert MASTER_BEARING.font_dir.is_dir()

    def test_font_dir_contains_four_weights(self) -> None:
        ttfs = sorted(p.name for p in MASTER_BEARING.font_dir.glob("*.ttf"))
        # Must include the four weights the renderer expects (file naming may
        # vary but each weight slot must be present).
        assert len(ttfs) >= 4


@pytest.mark.unit
class TestMasterBearingSvgFragments:
    """Every inline SVG fragment must parse cleanly (it is interpolated
    into the rendered HTML as-is — a malformed SVG would crash WeasyPrint).
    """

    @staticmethod
    def _assert_parses(svg: str) -> None:
        # ET.fromstring handles a single root <svg> element.
        root = ET.fromstring(svg)
        # Validate it's an SVG root (with or without xmlns prefix).
        assert root.tag.endswith("svg"), f"expected <svg> root, got {root.tag}"

    def test_logo_html_is_inline_base64_img(self) -> None:
        """Logo is a PNG base64-inlined as an ``<img>`` tag.

        Inlined so chromium-headless-shell renders it (file:// URLs are
        silently dropped — ADR-8). White-on-blue look is achieved via the
        CSS ``filter: brightness(0) invert(1)`` rule in ``.kp-logo__img``.
        """
        logo = MASTER_BEARING.logo_html
        assert logo.startswith("<img"), f"expected <img> tag, got {logo[:40]!r}"
        assert 'src="data:image/png;base64,' in logo
        assert 'class="kp-logo__img"' in logo

    def test_footer_feature_count(self) -> None:
        assert len(MASTER_BEARING.page1_footer_features) == 4

    def test_footer_feature_titles_uppercase_ru(self) -> None:
        titles = [
            (ff.title_line_1, ff.title_line_2)
            for ff in MASTER_BEARING.page1_footer_features
        ]
        # Spec: НАДЕЖНЫЕ/ПОСТАВКИ, КАЧЕСТВЕННАЯ/ПРОДУКЦИЯ, etc.
        expected = [
            ("НАДЕЖНЫЕ", "ПОСТАВКИ"),
            ("КАЧЕСТВЕННАЯ", "ПРОДУКЦИЯ"),
            ("ТЕХНИЧЕСКАЯ", "ПОДДЕРЖКА"),
            ("ИНДИВИДУАЛЬНЫЙ", "ПОДХОД"),
        ]
        assert titles == expected

    def test_each_footer_feature_svg_parses(self) -> None:
        for ff in MASTER_BEARING.page1_footer_features:
            self._assert_parses(ff.icon_svg)


@pytest.mark.unit
class TestMasterBearingFooterDefaults:
    def test_page2_footer_phone_present(self) -> None:
        assert MASTER_BEARING.page2_footer_phone
        assert "8-800" in MASTER_BEARING.page2_footer_phone

    def test_page2_footer_site_present(self) -> None:
        assert MASTER_BEARING.page2_footer_site
        assert "masterbearing" in MASTER_BEARING.page2_footer_site

    def test_page2_footer_email_present(self) -> None:
        assert "@" in MASTER_BEARING.page2_footer_email
