"""
TDD Tests for Продажи (Sales) tab redesign — 3-block layout with action buttons.

TASK: [86afdkuyb] — Продажи tab redesign on quote detail page

The current overview tab (/quotes/{quote_id}?tab=overview) has 4 cards:
  - Card 1: ОСНОВНАЯ ИНФОРМАЦИЯ (customer + seller dropdowns, contact person)
  - Card 2: ДОСТАВКА (city, country, method, priority, terms)
  - Card 3: ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ (created_at, creator)
  - Card 4: ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ (validity_days, expiry)
  Then: Handsontable items table, then action buttons (Рассчитать, exports)

The REDESIGN restructures into 3 blocks + relocated action buttons:
  Block I:   ОСНОВНАЯ ИНФОРМАЦИЯ (2-col grid)
             Col 1: Продавец, Клиент, Контактное лицо, Срок действия КП
             Col 2: Создатель, Дата создания, Дополнительная информация (NEW), Действительно до
  Block II:  ДОСТАВКА (clean row: Страна, Город, Адрес (dropdown), Способ, Условия)
  Block III: ИТОГО (Общая сумма, Общий профит, Количество позиций, Маржа %)

  Action buttons ABOVE items table: "Рассчитать" left, "Отправить на контроль" right

Key changes:
  - Col 2 of Block I: Создатель, Дата создания, Дополнительная информация textarea, Действительно до
  - New DB field: additional_info (TEXT) on quotes table
  - Customer address dropdown in ДОСТАВКА (populated from customer addresses)
  - ИТОГО block shows 4 metrics: total, profit, item count, margin %
  - Action buttons relocated from after items table to before it
  - additional_info supported in inline PATCH handler

Tests use SOURCE CODE ANALYSIS pattern (read main.py as text, no imports).
"""

import pytest
import os
import re

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source without importing it."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _read_main_lines():
    """Read main.py as a list of lines."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.readlines()


def _extract_overview_tab_section(source=None):
    """Extract the overview tab section from the quote detail GET handler.

    The overview tab is the default (last) branch in the GET /quotes/{quote_id} handler.
    It starts after 'if tab == "summary":' block and renders with quote_detail_tabs(quote_id, "overview"...).
    """
    if source is None:
        source = _read_main_source()
    # Find the overview tab rendering start — it's the return page_layout with "overview"
    marker = 'quote_detail_tabs(quote_id, "overview"'
    start = source.find(marker)
    assert start != -1, "Overview tab section not found in main.py"
    # Walk back to find the return statement
    return_start = source.rfind("return page_layout(", 0, start)
    assert return_start != -1, "Could not find return page_layout before overview tab"
    # Find the next @rt or top-level def to delimit the section
    next_route = source.find("\n@rt(", start)
    if next_route == -1:
        next_route = len(source)
    return source[return_start:next_route]


def _extract_inline_patch_handler(source=None):
    """Extract the inline PATCH handler for /quotes/{quote_id}/inline."""
    if source is None:
        source = _read_main_source()
    marker = '@rt("/quotes/{quote_id}/inline", methods=["PATCH"])'
    start = source.find(marker)
    assert start != -1, "Inline PATCH handler not found"
    next_route = source.find("\n@rt(", start + 10)
    if next_route == -1:
        next_route = len(source)
    return source[start:next_route]


# ==============================================================================
# EXISTING FUNCTIONALITY — these should PASS now
# ==============================================================================

class TestExistingOverviewTabStructure:
    """Verify existing functionality that should still work."""

    def test_overview_tab_exists(self):
        """The overview tab renders via quote_detail_tabs with 'overview' param."""
        source = _read_main_source()
        assert 'quote_detail_tabs(quote_id, "overview"' in source

    def test_main_info_card_exists(self):
        """ОСНОВНАЯ ИНФОРМАЦИЯ card exists in overview tab."""
        section = _extract_overview_tab_section()
        assert "ОСНОВНАЯ ИНФОРМАЦИЯ" in section

    def test_delivery_card_exists(self):
        """ДОСТАВКА card exists in overview tab."""
        section = _extract_overview_tab_section()
        assert "ДОСТАВКА" in section

    def test_customer_dropdown_exists(self):
        """Customer dropdown with inline-customer id exists."""
        section = _extract_overview_tab_section()
        assert 'id="inline-customer"' in section

    def test_seller_dropdown_exists(self):
        """Seller company dropdown with inline-seller id exists."""
        section = _extract_overview_tab_section()
        assert 'id="inline-seller"' in section

    def test_contact_person_dropdown_exists(self):
        """Contact person dropdown exists."""
        section = _extract_overview_tab_section()
        assert "contact_person_id" in section

    def test_delivery_city_input_exists(self):
        """Delivery city input exists."""
        section = _extract_overview_tab_section()
        assert "delivery_city" in section

    def test_delivery_country_input_exists(self):
        """Delivery country input exists."""
        section = _extract_overview_tab_section()
        assert "delivery_country" in section

    def test_delivery_method_dropdown_exists(self):
        """Delivery method dropdown exists."""
        section = _extract_overview_tab_section()
        assert "delivery_method" in section

    def test_handsontable_container_exists(self):
        """Handsontable spreadsheet container exists for items."""
        section = _extract_overview_tab_section()
        assert 'id="items-spreadsheet"' in section

    def test_inline_patch_handler_exists(self):
        """The inline PATCH handler for /quotes/{quote_id}/inline exists."""
        source = _read_main_source()
        assert '/quotes/{quote_id}/inline", methods=["PATCH"]' in source

    def test_calculate_button_exists(self):
        """A Рассчитать button/link exists somewhere in the overview tab area."""
        section = _extract_overview_tab_section()
        assert "Рассчитать" in section or "calculate" in section


# ==============================================================================
# Block I col 2: Создатель, Дата создания, Дополнительная информация, Действительно до
# ==============================================================================

class TestBlockIColumn2:
    """Block I (ОСНОВНАЯ ИНФОРМАЦИЯ) col 2 should have:
    Создатель, Дата создания, Дополнительная информация textarea, Действительно до.
    Currently creator/date are in a separate Card 3, and additional_info doesn't exist."""

    def test_creator_in_main_info_block(self):
        """Создатель (creator name) should be inside the ОСНОВНАЯ ИНФОРМАЦИЯ block,
        not in a separate card."""
        section = _extract_overview_tab_section()
        # Find the ОСНОВНАЯ ИНФОРМАЦИЯ block boundaries
        main_info_start = section.find("ОСНОВНАЯ ИНФОРМАЦИЯ")
        assert main_info_start != -1, "ОСНОВНАЯ ИНФОРМАЦИЯ not found"
        # Find the next card/block boundary (ДОСТАВКА)
        delivery_start = section.find("ДОСТАВКА", main_info_start)
        assert delivery_start != -1, "ДОСТАВКА block not found after ОСНОВНАЯ ИНФОРМАЦИЯ"
        main_info_block = section[main_info_start:delivery_start]
        assert "СОЗДАЛ" in main_info_block or "Создатель" in main_info_block or "creator_name" in main_info_block, (
            "Creator (Создатель) should be in ОСНОВНАЯ ИНФОРМАЦИЯ block col 2, "
            "not in a separate card."
        )

    def test_created_at_in_main_info_block(self):
        """Дата создания should be inside ОСНОВНАЯ ИНФОРМАЦИЯ block."""
        section = _extract_overview_tab_section()
        main_info_start = section.find("ОСНОВНАЯ ИНФОРМАЦИЯ")
        delivery_start = section.find("ДОСТАВКА", main_info_start)
        main_info_block = section[main_info_start:delivery_start]
        assert "ДАТА СОЗДАНИЯ" in main_info_block or "created_at" in main_info_block, (
            "Created date should be in ОСНОВНАЯ ИНФОРМАЦИЯ block col 2."
        )

    def test_additional_info_textarea_exists(self):
        """A Дополнительная информация textarea should exist in the overview tab."""
        section = _extract_overview_tab_section()
        has_textarea = ("additional_info" in section and
                        ("Textarea" in section or "textarea" in section.lower()))
        assert has_textarea, (
            "Block I col 2 must contain an 'additional_info' textarea field "
            "for Дополнительная информация (free-text notes)."
        )

    def test_expiry_in_main_info_block(self):
        """Действительно до (expiry date) should be inside ОСНОВНАЯ ИНФОРМАЦИЯ block."""
        section = _extract_overview_tab_section()
        main_info_start = section.find("ОСНОВНАЯ ИНФОРМАЦИЯ")
        delivery_start = section.find("ДОСТАВКА", main_info_start)
        main_info_block = section[main_info_start:delivery_start]
        assert "ДЕЙСТВИТЕЛЕН ДО" in main_info_block or "expiry" in main_info_block, (
            "Expiry date (Действительно до) should be in ОСНОВНАЯ ИНФОРМАЦИЯ block col 2."
        )

    def test_validity_days_in_main_info_block(self):
        """Срок действия КП (validity_days) should be inside ОСНОВНАЯ ИНФОРМАЦИЯ block."""
        section = _extract_overview_tab_section()
        main_info_start = section.find("ОСНОВНАЯ ИНФОРМАЦИЯ")
        delivery_start = section.find("ДОСТАВКА", main_info_start)
        main_info_block = section[main_info_start:delivery_start]
        assert "validity_days" in main_info_block, (
            "Validity days should be in ОСНОВНАЯ ИНФОРМАЦИЯ block col 2."
        )


# ==============================================================================
# Block structure: Only 3 blocks (no separate Card 3 and Card 4)
# ==============================================================================

class TestThreeBlockLayout:
    """After redesign, overview tab should have exactly 3 blocks:
    ОСНОВНАЯ ИНФОРМАЦИЯ, ДОСТАВКА, ИТОГО.
    Separate ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ and ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ cards are removed."""

    def test_no_separate_additional_info_card(self):
        """There should NOT be a separate ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ card/header
        in the overview tab. Its fields move into Block I col 2."""
        section = _extract_overview_tab_section()
        # After redesign, ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ should not be a card header
        # It might exist as a field label but not as a section header with icon
        has_separate_header = (
            'icon("clock"' in section and "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ" in section
        )
        assert not has_separate_header, (
            "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ should not be a separate card. "
            "Its fields (creator, date) move to ОСНОВНАЯ ИНФОРМАЦИЯ col 2."
        )

    def test_no_separate_print_info_card(self):
        """There should NOT be a separate ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ card in overview tab.
        Validity/expiry fields move into Block I col 2."""
        section = _extract_overview_tab_section()
        has_separate_header = (
            'icon("printer"' in section and "ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ" in section
        )
        assert not has_separate_header, (
            "ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ should not be a separate card. "
            "Validity/expiry fields move to ОСНОВНАЯ ИНФОРМАЦИЯ col 2."
        )

    def test_itogo_block_exists(self):
        """An ИТОГО block should exist in the overview tab."""
        section = _extract_overview_tab_section()
        assert "ИТОГО" in section, (
            "The overview tab must have an ИТОГО block showing totals."
        )


# ==============================================================================
# ИТОГО block: 4 fields (total, profit, count, margin)
# ==============================================================================

class TestItogoBlock:
    """Block III (ИТОГО) should display Общая сумма, Общий профит,
    Количество позиций, and Маржа %."""

    def test_itogo_has_total_amount(self):
        """ИТОГО block must show Общая сумма."""
        section = _extract_overview_tab_section()
        itogo_start = section.find("ИТОГО")
        assert itogo_start != -1, "ИТОГО not found"
        itogo_area = section[itogo_start:itogo_start + 1500]
        assert "Общая сумма" in itogo_area or "total_amount" in itogo_area

    def test_itogo_has_profit(self):
        """ИТОГО block must show Общий профит."""
        section = _extract_overview_tab_section()
        itogo_start = section.find("ИТОГО")
        assert itogo_start != -1
        itogo_area = section[itogo_start:itogo_start + 1500]
        assert "Общий профит" in itogo_area or "total_profit" in itogo_area

    def test_itogo_has_item_count(self):
        """ИТОГО block must show Количество позиций."""
        section = _extract_overview_tab_section()
        itogo_start = section.find("ИТОГО")
        assert itogo_start != -1
        itogo_area = section[itogo_start:itogo_start + 1500]
        assert "Количество позиций" in itogo_area or "items_count" in itogo_area

    def test_itogo_has_margin(self):
        """ИТОГО block must show Маржа %."""
        section = _extract_overview_tab_section()
        itogo_start = section.find("ИТОГО")
        assert itogo_start != -1
        itogo_area = section[itogo_start:itogo_start + 1500]
        assert "Маржа" in itogo_area or "margin" in itogo_area


# ==============================================================================
# Action buttons: ABOVE items table (Рассчитать left, Отправить на контроль right)
# ==============================================================================

class TestActionButtonPlacement:
    """Action buttons (Рассчитать, Отправить на контроль) should appear
    ABOVE the items table, not below it."""

    def test_calculate_button_before_items_table(self):
        """Рассчитать button/link must appear BEFORE the items-spreadsheet div in code order."""
        section = _extract_overview_tab_section()
        calc_pos = section.find("Рассчитать")
        items_pos = section.find('id="items-spreadsheet"')
        assert calc_pos != -1, "Рассчитать button not found"
        assert items_pos != -1, "items-spreadsheet not found"
        assert calc_pos < items_pos, (
            f"Рассчитать button (pos {calc_pos}) must appear BEFORE items table "
            f"(pos {items_pos}). Currently it is after the table."
        )

    def test_submit_control_button_above_items_table(self):
        """An 'Отправить на контроль' button should exist ABOVE the items table,
        in the same action bar as 'Рассчитать'."""
        section = _extract_overview_tab_section()
        items_pos = section.find('id="items-spreadsheet"')
        assert items_pos != -1, "items-spreadsheet not found"
        before_items = section[:items_pos]
        # The button should be in a dedicated action bar before items, not in the
        # conditional workflow section (pending_sales_review) that exists after items
        has_button = "Отправить на контроль" in before_items
        assert has_button, (
            "Overview tab must have an 'Отправить на контроль' button ABOVE the items table, "
            "in the same action bar as 'Рассчитать'. "
            "Layout: Рассчитать (left), Отправить на контроль (right)."
        )


# ==============================================================================
# Delivery address dropdown (from customer addresses)
# ==============================================================================

class TestDeliveryAddressDropdown:
    """ДОСТАВКА block should include an address dropdown populated
    from the customer's addresses."""

    def test_delivery_address_field_exists(self):
        """ДОСТАВКА block should have an address selection field."""
        section = _extract_overview_tab_section()
        delivery_start = section.find("ДОСТАВКА")
        assert delivery_start != -1
        # Look for address-related content after ДОСТАВКА header
        delivery_area = section[delivery_start:delivery_start + 3000]
        has_address = (
            "АДРЕС" in delivery_area or
            "delivery_address" in delivery_area or
            "Адрес поставки" in delivery_area
        )
        assert has_address, (
            "ДОСТАВКА block must include an address field (АДРЕС / Адрес поставки) "
            "with a dropdown populated from customer profile addresses."
        )


# ==============================================================================
# additional_info field in inline PATCH handler
# ==============================================================================

class TestAdditionalInfoInlineSupport:
    """The inline PATCH handler must support the additional_info field."""

    def test_additional_info_in_editable_fields(self):
        """The inline PATCH handler's editable_fields list must include 'additional_info'."""
        handler = _extract_inline_patch_handler()
        assert "'additional_info'" in handler or '"additional_info"' in handler, (
            "The inline PATCH handler's editable_fields list must include 'additional_info' "
            "to support inline saving of the Дополнительная информация textarea."
        )


# ==============================================================================
# FK null safety in overview tab section
# ==============================================================================

class TestFkNullSafety:
    """Overview tab code must not use unsafe FK patterns like
    .get("fk_field", {}).get("col") which crashes when fk_field is null."""

    def test_no_unsafe_fk_patterns_in_overview(self):
        """No .get("field", {}).get("subfield") patterns in the overview section.
        Must use (obj.get("field") or {}).get("subfield", default) instead."""
        section = _extract_overview_tab_section()
        # Pattern: .get("something", {}).get( — this is unsafe when key exists but value is None
        unsafe_pattern = re.compile(r'\.get\(["\'][^"\']+["\'],\s*\{\}\)\.get\(')
        matches = unsafe_pattern.findall(section)
        assert len(matches) == 0, (
            f"Found {len(matches)} unsafe FK null pattern(s) in overview tab: "
            f".get('field', {{}}).get('col'). "
            "Use (obj.get('field') or {{}}).get('col', default) instead."
        )


# ==============================================================================
# Migration: additional_info column
# ==============================================================================

class TestAdditionalInfoMigration:
    """A migration file should exist adding additional_info column to kvota.quotes."""

    def test_migration_file_exists(self):
        """A migration file adding additional_info to kvota.quotes should exist."""
        migrations_dir = os.path.join(_PROJECT_ROOT, "migrations")
        if not os.path.isdir(migrations_dir):
            pytest.skip("migrations directory not found")
        migration_files = os.listdir(migrations_dir)
        has_migration = any(
            "additional_info" in f.lower()
            for f in migration_files
        )
        assert has_migration, (
            "No migration file found for adding additional_info column. "
            "Expected a migration like XXX_add_additional_info.sql in migrations/."
        )
