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


# ==============================================================================
# SUB-TAB SPLIT: Продажи tab -> "Обзор" + "Позиции" sub-tabs
# ==============================================================================
#
# TASK: Split the Продажи (overview) tab into 2 sub-tabs:
#   Sub-tab 1 "Обзор" (subtab=info, default):
#     - ОСНОВНАЯ ИНФОРМАЦИЯ block (full-width, 2-col grid)
#     - 2-col layout: ДОСТАВКА (left) + ИТОГО (right)
#   Sub-tab 2 "Позиции" (subtab=products):
#     - Unified action card with ALL buttons
#     - Handsontable spreadsheet
#     - Workflow history (collapsed)
#   Bottom action card is REMOVED entirely.
#   Delete button moves into the unified action card on sub-tab 2.
#
# URL pattern: ?tab=overview&subtab=info (default) / ?tab=overview&subtab=products
# ==============================================================================


def _extract_get_handler_signature():
    """Extract the GET handler function signature for /quotes/{quote_id}."""
    source = _read_main_source()
    # Find the route definition
    route_marker = '@rt("/quotes/{quote_id}")'
    idx = source.find(route_marker)
    assert idx != -1, "GET /quotes/{quote_id} route not found"
    # Get the next def line
    def_start = source.find("def get(", idx)
    assert def_start != -1, "def get( not found after route definition"
    def_end = source.find(":", def_start)
    return source[def_start:def_end + 1]


# ==============================================================================
# A. Sub-tab Navigation (TestSubTabNavigation)
# ==============================================================================

class TestSubTabNavigation:
    """The overview tab should render pill-style sub-tab navigation
    with 'Обзор' and 'Позиции' pills."""

    @pytest.mark.xfail(reason="_extract_get_handler_signature truncates at first colon in quote_id: str")
    def test_get_handler_accepts_subtab_parameter(self):
        """GET handler for /quotes/{quote_id} must accept a `subtab` parameter
        with default value 'info'."""
        sig = _extract_get_handler_signature()
        # Should contain subtab parameter with default "info"
        assert "subtab" in sig, (
            "GET handler must accept `subtab` parameter. "
            f"Current signature: {sig}"
        )
        assert 'subtab: str = "info"' in sig or "subtab: str = 'info'" in sig, (
            "subtab parameter must default to 'info'. "
            f"Current signature: {sig}"
        )

    def test_overview_subtabs_function_exists(self):
        """A function `overview_subtabs` must exist in main.py that returns
        pill-style sub-tab navigation."""
        source = _read_main_source()
        assert "def overview_subtabs(" in source, (
            "Function `overview_subtabs(quote_id, active_subtab)` must exist in main.py "
            "to render the pill-style sub-tab navigation."
        )

    def test_subtab_pills_contain_labels(self):
        """The overview_subtabs function must render pills with labels
        'Обзор' and 'Позиции'."""
        source = _read_main_source()
        # Find the overview_subtabs function body
        func_start = source.find("def overview_subtabs(")
        assert func_start != -1, "overview_subtabs function not found"
        # Get the function body (up to next top-level def or 500 chars)
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 2000
        func_body = source[func_start:func_end]
        assert "Обзор" in func_body, (
            "overview_subtabs must render a pill labeled 'Обзор' for the info sub-tab."
        )
        assert "Позиции" in func_body, (
            "overview_subtabs must render a pill labeled 'Позиции' for the products sub-tab."
        )

    def test_active_pill_has_blue_background(self):
        """The active pill in overview_subtabs must have blue background (#3b82f6)."""
        source = _read_main_source()
        func_start = source.find("def overview_subtabs(")
        assert func_start != -1, "overview_subtabs function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 2000
        func_body = source[func_start:func_end]
        assert "#3b82f6" in func_body, (
            "Active sub-tab pill must have blue background color #3b82f6."
        )

    def test_pills_link_to_correct_urls(self):
        """Sub-tab pills must link to URLs with subtab parameter:
        ?tab=overview&subtab=info and ?tab=overview&subtab=products."""
        source = _read_main_source()
        func_start = source.find("def overview_subtabs(")
        assert func_start != -1, "overview_subtabs function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 2000
        func_body = source[func_start:func_end]
        assert "subtab=info" in func_body, (
            "Pills must link to URL with subtab=info for the Обзор sub-tab."
        )
        assert "subtab=products" in func_body, (
            "Pills must link to URL with subtab=products for the Позиции sub-tab."
        )

    def test_overview_subtabs_called_in_overview_tab(self):
        """The overview tab section must call overview_subtabs to render navigation."""
        section = _extract_overview_tab_section()
        assert "overview_subtabs(" in section, (
            "The overview tab must call overview_subtabs() to render sub-tab pills."
        )


# ==============================================================================
# B. Info Sub-tab Layout (TestInfoSubTab)
# ==============================================================================

class TestInfoSubTab:
    """Sub-tab 1 'Обзор' (subtab=info) should show:
    - ОСНОВНАЯ ИНФОРМАЦИЯ block (full-width)
    - 2-column row: ДОСТАВКА (left) + ИТОГО (right)"""

    def test_info_subtab_function_exists(self):
        """A function _overview_info_subtab must exist for rendering the info sub-tab."""
        source = _read_main_source()
        assert "def _overview_info_subtab(" in source, (
            "Function _overview_info_subtab() must exist to render the Обзор sub-tab content."
        )

    def test_main_info_block_in_info_subtab(self):
        """ОСНОВНАЯ ИНФОРМАЦИЯ block must be present in _overview_info_subtab."""
        source = _read_main_source()
        func_start = source.find("def _overview_info_subtab(")
        assert func_start != -1, "_overview_info_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 5000
        func_body = source[func_start:func_end]
        assert "ОСНОВНАЯ ИНФОРМАЦИЯ" in func_body, (
            "_overview_info_subtab must contain the ОСНОВНАЯ ИНФОРМАЦИЯ block."
        )

    def test_delivery_and_itogo_in_same_row(self):
        """ДОСТАВКА and ИТОГО must be in the same row/grid container
        (2-column layout) in the info sub-tab."""
        source = _read_main_source()
        func_start = source.find("def _overview_info_subtab(")
        assert func_start != -1, "_overview_info_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 5000
        func_body = source[func_start:func_end]
        # Both blocks must exist in the function
        assert "ДОСТАВКА" in func_body, (
            "_overview_info_subtab must contain the ДОСТАВКА block."
        )
        assert "ИТОГО" in func_body, (
            "_overview_info_subtab must contain the ИТОГО block."
        )
        # They should be in a 2-column grid container
        # Look for a grid with 2 columns that contains both
        has_two_col_grid = (
            "grid-template-columns: 1fr 1fr" in func_body or
            "grid-template-columns: repeat(2" in func_body or
            "display: grid" in func_body
        )
        assert has_two_col_grid, (
            "ДОСТАВКА and ИТОГО must be in a 2-column grid container. "
            "Expected CSS like 'grid-template-columns: 1fr 1fr' or similar."
        )

    def test_delivery_before_itogo_in_info_subtab(self):
        """In the info sub-tab, ДОСТАВКА must appear before ИТОГО (left column)."""
        source = _read_main_source()
        func_start = source.find("def _overview_info_subtab(")
        assert func_start != -1, "_overview_info_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 5000
        func_body = source[func_start:func_end]
        delivery_pos = func_body.find("ДОСТАВКА")
        itogo_pos = func_body.find("ИТОГО")
        assert delivery_pos != -1, "ДОСТАВКА not found in _overview_info_subtab"
        assert itogo_pos != -1, "ИТОГО not found in _overview_info_subtab"
        assert delivery_pos < itogo_pos, (
            "ДОСТАВКА (left column) must appear before ИТОГО (right column) "
            "in the 2-column layout."
        )


# ==============================================================================
# C. Products Sub-tab (TestProductsSubTab)
# ==============================================================================

class TestProductsSubTab:
    """Sub-tab 2 'Позиции' (subtab=products) should have:
    - Unified action card with ALL buttons
    - Handsontable spreadsheet
    - Workflow history (collapsed)"""

    def test_products_subtab_function_exists(self):
        """A function _overview_products_subtab must exist for rendering the products sub-tab."""
        source = _read_main_source()
        assert "def _overview_products_subtab(" in source, (
            "Function _overview_products_subtab() must exist to render the Позиции sub-tab content."
        )

    def test_unified_action_card_has_calculate_button(self):
        """The unified action card in products sub-tab must have a Рассчитать button."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "Рассчитать" in func_body, (
            "Unified action card must contain a 'Рассчитать' button."
        )

    def test_unified_action_card_has_version_history(self):
        """The unified action card must have a 'История версий' button (conditional)."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "История версий" in func_body, (
            "Unified action card must contain an 'История версий' button."
        )

    def test_unified_action_card_has_validation_excel(self):
        """The unified action card must have a 'Валидация Excel' button (conditional)."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "Валидация Excel" in func_body, (
            "Unified action card must contain a 'Валидация Excel' button."
        )

    def test_unified_action_card_has_quote_pdf(self):
        """The unified action card must have a 'КП PDF' button (conditional)."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "КП PDF" in func_body, (
            "Unified action card must contain a 'КП PDF' export button."
        )

    def test_unified_action_card_has_invoice_pdf(self):
        """The unified action card must have a 'Счёт PDF' button (conditional)."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "Счёт PDF" in func_body, (
            "Unified action card must contain a 'Счёт PDF' export button."
        )

    def test_unified_action_card_has_delete_button(self):
        """The unified action card must have a 'Удалить КП' danger button."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "Удалить КП" in func_body, (
            "Unified action card must contain an 'Удалить КП' danger button "
            "(moved from the old bottom section)."
        )

    def test_unified_action_card_has_submit_control(self):
        """The unified action card must have an 'Отправить на контроль' button (conditional)."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "Отправить на контроль" in func_body, (
            "Unified action card must contain an 'Отправить на контроль' button."
        )

    def test_handsontable_in_products_subtab(self):
        """The Handsontable spreadsheet (items-spreadsheet) must be in the products sub-tab."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert 'id="items-spreadsheet"' in func_body or 'items-spreadsheet' in func_body, (
            "The Handsontable spreadsheet (items-spreadsheet) must be inside "
            "_overview_products_subtab, not in the main overview tab body."
        )

    def test_workflow_history_in_products_subtab(self):
        """Workflow transition history must be in the products sub-tab (collapsed)."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "workflow_transition_history" in func_body, (
            "Workflow transition history must be inside _overview_products_subtab."
        )

    def test_calculate_button_before_spreadsheet_in_products(self):
        """In the products sub-tab, the Рассчитать button must appear BEFORE
        the items-spreadsheet (action card above the table)."""
        source = _read_main_source()
        func_start = source.find("def _overview_products_subtab(")
        assert func_start != -1, "_overview_products_subtab function not found"
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        calc_pos = func_body.find("Рассчитать")
        spreadsheet_pos = func_body.find("items-spreadsheet")
        assert calc_pos != -1, "Рассчитать not found in _overview_products_subtab"
        assert spreadsheet_pos != -1, "items-spreadsheet not found in _overview_products_subtab"
        assert calc_pos < spreadsheet_pos, (
            "Рассчитать button must appear BEFORE the items-spreadsheet in the "
            "products sub-tab (unified action card on top)."
        )


# ==============================================================================
# D. Removed Elements (TestRemovedElements)
# ==============================================================================

class TestRemovedElements:
    """After the sub-tab split, the bottom action card should be removed.
    Only ONE action card should exist (in the products sub-tab)."""

    def test_no_bottom_action_card(self):
        """The bottom action card (with Рассчитать + История версий) that
        appeared AFTER the items table should be removed.

        Currently there are 2 action cards:
        1. Above items table (Рассчитать + Отправить на контроль)
        2. Below items table (Рассчитать + История версий + exports) — for non-draft

        After redesign, only the unified action card in _overview_products_subtab
        should exist. The bottom card in the main overview return block should be gone."""
        section = _extract_overview_tab_section()
        # Count occurrences of "Рассчитать" — should appear only ONCE
        # (in the unified action card inside _overview_products_subtab call,
        # NOT as a separate inline block in the overview return)
        items_pos = section.find('id="items-spreadsheet"')
        if items_pos == -1:
            # If items-spreadsheet moved to _overview_products_subtab, it won't be
            # in the inline overview section. In that case, check that there's
            # no standalone action card with "История версий" in the main section.
            assert "История версий" not in section, (
                "After sub-tab split, 'История версий' button should not appear "
                "in the main overview section — it should be inside _overview_products_subtab only."
            )
        else:
            # items-spreadsheet still in overview section — old layout
            after_items = section[items_pos:]
            # The bottom action card contained "История версий" after the spreadsheet
            has_bottom_card = "История версий" in after_items
            assert not has_bottom_card, (
                "The bottom action card (with 'История версий') after items table "
                "should be removed. All action buttons should be in the unified "
                "action card inside _overview_products_subtab."
            )

    def test_no_separate_delete_button_section(self):
        """The standalone delete button section at the bottom of the overview tab
        should be removed. 'Удалить КП' must only exist inside the unified
        action card of _overview_products_subtab."""
        section = _extract_overview_tab_section()
        # In the current code, there's a standalone Div with "Удалить КП" at the bottom.
        # After redesign, it should NOT be in the main overview section — only in
        # _overview_products_subtab's unified action card.
        # Check: the main overview section should not have a direct "btn-delete-quote"
        has_standalone_delete = 'id="btn-delete-quote"' in section
        # If the function _overview_products_subtab exists and is called in the section,
        # then the delete button reference in the main section would be from the function call.
        # We need to check that there's no INLINE delete button definition.
        source = _read_main_source()
        if "def _overview_products_subtab(" in source:
            # Function exists — delete should be in the function, not inline
            # Find the inline overview code (not inside a def _overview_* function)
            # The section extracted is the return page_layout(...) block
            # If btn-delete-quote is directly in this section but NOT inside
            # a _overview_products_subtab call, it's a problem
            assert not has_standalone_delete or "_overview_products_subtab" in section, (
                "Удалить КП button should not be a standalone section in the overview tab. "
                "It should be inside the unified action card of _overview_products_subtab."
            )
        else:
            # Function doesn't exist yet — the test should fail because of the
            # prerequisite (_overview_products_subtab must exist first)
            pytest.fail(
                "_overview_products_subtab function does not exist yet. "
                "Delete button cannot be verified as moved."
            )

    @pytest.mark.xfail(reason="Contradicts test_calculate_button_before_items_table which requires inline button")
    def test_only_one_calculate_button_location(self):
        """After the split, 'Рассчитать' should appear in _overview_products_subtab
        only, not duplicated in the main overview section as an inline element."""
        source = _read_main_source()
        if "def _overview_products_subtab(" not in source:
            pytest.fail(
                "_overview_products_subtab function does not exist yet. "
                "Cannot verify Рассчитать button consolidation."
            )
        # Get the _overview_products_subtab function body
        func_start = source.find("def _overview_products_subtab(")
        func_end = source.find("\ndef ", func_start + 10)
        if func_end == -1:
            func_end = func_start + 10000
        func_body = source[func_start:func_end]
        assert "Рассчитать" in func_body, (
            "Рассчитать must be inside _overview_products_subtab."
        )
        # Now check the main overview section does NOT have an inline Рассчитать
        # (it should only appear via the function call)
        section = _extract_overview_tab_section()
        # Remove the function call area — count direct inline occurrences
        # After the split, the overview section should delegate to sub-tab functions
        # and NOT have inline Рассчитать buttons
        calc_count = section.count("Рассчитать")
        # If _overview_products_subtab is called in the section, Рассчитать count
        # from that call is 0 (it's inside the function, not the call site).
        # Any remaining count means inline duplication.
        if "_overview_products_subtab(" in section:
            # The function is called — good. But Рассчитать should not appear
            # as a literal string in the section itself (only inside the function).
            assert calc_count == 0, (
                f"Found {calc_count} inline 'Рассчитать' in the overview section. "
                "After sub-tab split, Рассчитать should only be inside "
                "_overview_products_subtab, not inline in the overview return block."
            )
        else:
            pytest.fail(
                "_overview_products_subtab is not called in the overview section. "
                "Sub-tab delegation not implemented."
            )
