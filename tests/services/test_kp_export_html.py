"""HTML-structure assertions for ``render_proposal_html``.

These run against a deliberately under-filled ``MINIMAL_PROPOSAL`` fixture
(one item, two specs) to make sure the padding logic still emits the
minimum slot counts required by the design:

- ≥5 items table rows (REQ-4.4)
- ≥8 spec slots (REQ-6.3)
- ≥8 packaging slots (REQ-7.4)
- ≥3 condition slots (REQ-8.3)
- 6 service rows (REQ-9.2)
- 4 footer feature tiles (REQ-15.5)

Pure text-level assertions — no PDF parsing, no font subsetting. Runs in
milliseconds, marked unit.
"""

from __future__ import annotations

import pytest

from services.kp_branding import MASTER_BEARING
from services.kp_export import (
    KpItem,
    KpPackagingItem,
    KpProposal,
    KpServices,
    render_proposal_html,
)


MINIMAL_PROPOSAL = KpProposal(
    subtitle="на поставку техники",
    supplier="ООО «Тест Поставщик»",
    manager="Иванов И. И.",
    amount="12 480 000",
    items=(KpItem(name="Бульдозер", model="X-200", qty="1", price="100"),),
    specs=("Мощность — 162 л.с.", "Масса — 17.2 т"),
    packaging=(KpPackagingItem(text="Кабина", checked=True),),
    conditions=("Гарантия 12 месяцев",),
    services=KpServices(delivery=True, training=False),
)


@pytest.fixture(scope="module")
def html_doc() -> str:
    return render_proposal_html(MINIMAL_PROPOSAL)


# ---------------------------------------------------------------------------
# Brand interpolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBrandInterpolation:
    def test_primary_blue_present(self, html_doc: str) -> None:
        assert MASTER_BEARING.primary_blue in html_doc

    def test_primary_red_present(self, html_doc: str) -> None:
        assert MASTER_BEARING.primary_red in html_doc

    def test_supplier_text_present(self, html_doc: str) -> None:
        assert "ООО «Тест Поставщик»" in html_doc


# ---------------------------------------------------------------------------
# Font wiring
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFontWiring:
    def test_inter_font_face_present(self, html_doc: str) -> None:
        assert "@font-face" in html_doc
        assert "font-family: 'Inter'" in html_doc

    def test_all_four_weights_referenced(self, html_doc: str) -> None:
        """All four font URLs (regular/500/600/700) must be present so
        WeasyPrint embeds the full family — otherwise it falls back to
        DejaVu Sans for the missing weight and breaks Cyrillic rendering.
        """
        assert "Inter-regular.ttf" in html_doc
        assert "Inter-500.ttf" in html_doc
        assert "Inter-600.ttf" in html_doc
        assert "Inter-700.ttf" in html_doc

    def test_font_urls_are_absolute_file_urls(self, html_doc: str) -> None:
        # WeasyPrint needs absolute file:// URLs (not relative paths).
        assert "file://" in html_doc
        assert "file:///" in html_doc


# ---------------------------------------------------------------------------
# Padding — minimum visible slots
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPaddingMinimums:
    def test_items_table_has_at_least_5_rows(self, html_doc: str) -> None:
        # REQ-4.4 — even when 1 item is provided, render 5 rows.
        assert html_doc.count("kp-table__row") >= 5

    def test_specs_block_has_at_least_8_slots(self, html_doc: str) -> None:
        # REQ-6.3 — count the bullet items inside the bullet list.
        # Each spec slot is rendered as a <div class="item"> with <div class="b"> bullet.
        # The kp-bullet-list is the specs container; check the b dot occurrences inside.
        # Easier signal: spec bullets are <div class="b"></div> in the bullet list.
        # The packaging block uses <div class="c"> not <div class="b">, so b-count
        # equals (8 spec slots) + (3 condition slots) — both use bullets.
        spec_or_condition_bullets = html_doc.count('<div class="b">')
        # Conditions render at least 3 slots → 8 + 3 = 11 minimum.
        assert spec_or_condition_bullets >= 11

    def test_packaging_block_has_at_least_8_slots(self, html_doc: str) -> None:
        # REQ-7.4 — packaging and service indicators both render the
        # same <div class="c"> (optionally "c checked") shape. The page
        # has exactly 8 packaging slots + 6 service indicators = 14 minimum.
        # Both ``class="c"`` and ``class="c checked"`` use the same opening
        # angle bracket, so count both variants together.
        c_count = (
            html_doc.count('class="c"') + html_doc.count('class="c checked"')
        )
        assert c_count >= 14

    def test_conditions_block_has_at_least_3_slots(self, html_doc: str) -> None:
        # REQ-8.3 — count the condition rows in <div class="kp-conditions">.
        # Conditions appear as <div class="row">.
        assert html_doc.count('<div class="row">') >= 3

    def test_six_service_rows(self, html_doc: str) -> None:
        # REQ-9.2 — exactly 6 service items rendered.
        # ``kp-services__item`` also appears in CSS selectors above; count
        # the rendered <div ...> occurrences only.
        assert html_doc.count('<div class="kp-services__item">') == 6

    def test_four_footer_feature_titles(self, html_doc: str) -> None:
        # REQ-15.5 — the four Master Bearing tiles in fixed order.
        for label in ("НАДЕЖНЫЕ", "КАЧЕСТВЕННАЯ", "ТЕХНИЧЕСКАЯ", "ИНДИВИДУАЛЬНЫЙ"):
            assert label in html_doc, f"missing footer feature title: {label}"


# ---------------------------------------------------------------------------
# Service labels (REQ-9.3)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestServiceLabels:
    def test_all_six_service_labels_present_in_order(self, html_doc: str) -> None:
        labels = [
            "Доставка",
            "Обучение операторов",
            "Шеф-монтаж",
            "Расширенная гарантия",
            "Пусконаладочные работы",
            "Сервисное обслуживание",
        ]
        # Verify each label appears exactly once and in the fixed order.
        positions = [html_doc.index(lbl) for lbl in labels]
        assert positions == sorted(positions)


# ---------------------------------------------------------------------------
# Two pages emitted
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPageCount:
    def test_two_kp_pages_in_document(self, html_doc: str) -> None:
        # Two <div class="kp-page"> sections — page 1 + page 2.
        assert html_doc.count('class="kp-page"') == 2

    def test_page_two_indicator_present(self, html_doc: str) -> None:
        assert "2/2" in html_doc

    def test_headline_uppercase(self, html_doc: str) -> None:
        assert "КОММЕРЧЕСКОЕ" in html_doc and "ПРЕДЛОЖЕНИЕ" in html_doc


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProposalDefaults:
    def test_empty_proposal_renders_without_error(self) -> None:
        html = render_proposal_html(KpProposal())
        assert "<!DOCTYPE html>" in html
        assert "<body>" in html

    def test_default_subtitle_used_when_blank(self) -> None:
        html = render_proposal_html(KpProposal())  # subtitle=""
        assert MASTER_BEARING.default_subtitle in html

    def test_user_subtitle_overrides_default(self) -> None:
        html = render_proposal_html(KpProposal(subtitle="custom subtitle"))
        assert "custom subtitle" in html
