"""
TDD Tests for Сводка (Summary) tab redesign — 6-block layout.

TASK: [86afdkux7] — Сводка tab 6-block layout redesign

The current _render_summary_tab() has 6 cards but with different content/layout:
  - Card 1: Основная информация (customer, seller, contact)
  - Card 2: Доставка
  - Card 3: Дополнительная информация (tender, creator, KP number, notes)
  - Card 4: Порядок расчетов
  - Card 5: Итого (3-column: total, profit, count)
  - Card 6: Информация для печати

The REDESIGN reorganizes into a 2-column layout (LEFT 3 + RIGHT 3):
  LEFT:
    Block I:   ОСНОВНАЯ ИНФОРМАЦИЯ (customer/seller name+INN, contact+phone)
    Block II:  ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ (5 people FIOs + corresponding dates)
    Block III: ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ (KP/SP dates and validity)
  RIGHT:
    Block IV:  ПОРЯДОК РАСЧЕТОВ (exchange rate placeholders "—", payment terms)
    Block V:   ДОСТАВКА (method, terms, country, city, address)
    Block VI:  ИТОГО (total, profit, item count, margin %)

Key changes:
  - Block II now shows 5 user FIOs from user_profiles (creator, quote_controller,
    spec_controller, customs, logistics) with corresponding completion dates
  - Block VI adds margin percentage calculation
  - Exchange rates show "—" placeholders (CBR API deferred to Session 5)
  - All FK lookups must use safe null pattern: (obj.get("fk") or {}).get("col", default)

Tests are written BEFORE implementation (TDD) and MUST FAIL.
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


def _extract_function_source(func_name, source=None):
    """Extract a function's source from main.py."""
    if source is None:
        source = _read_main_source()
    pattern = re.compile(
        rf'^(def {re.escape(func_name)}\(.*?)(?=\ndef |\n@rt\(|\nclass |\Z)',
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(source)
    assert match, f"Function '{func_name}' not found in main.py"
    return match.group(1)


def _extract_route_handler(route_pattern, source=None):
    """Extract a route handler block starting with @rt(route_pattern) def get/post."""
    if source is None:
        source = _read_main_source()
    escaped = re.escape(route_pattern)
    pattern = re.compile(
        rf'(@rt\({escaped}\)\s*def \w+\(.*?)(?=\n@rt\(|\nclass |\Z)',
        re.DOTALL,
    )
    match = pattern.search(source)
    assert match, f"Route handler for {route_pattern} not found in main.py"
    return match.group(1)


# ==============================================================================
# Test: Function exists and returns content
# ==============================================================================

class TestSvodkaTabFunctionExists:
    """The _render_summary_tab function must exist in main.py."""

    def test_render_summary_tab_exists(self):
        """_render_summary_tab function should exist and be callable."""
        source = _read_main_source()
        assert "def _render_summary_tab(" in source, (
            "_render_summary_tab function not found in main.py"
        )

    def test_render_summary_tab_returns_div(self):
        """_render_summary_tab should return a Div (contains return Div(...))."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "return Div(" in func_source, (
            "_render_summary_tab must return a Div element"
        )


# ==============================================================================
# Block I: ОСНОВНАЯ ИНФОРМАЦИЯ — customer/seller name+INN, contact+phone
# ==============================================================================

class TestBlockIMainInfo:
    """Block I should contain customer name, customer INN, seller name, seller INN,
    contact person, and contact phone/mobile number."""

    def test_block_i_has_customer_name_field(self):
        """Block I must have a 'Клиент' field for customer name."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Клиент" in func_source, (
            "Block I must contain a 'Клиент' label for customer name"
        )

    def test_block_i_has_customer_inn_field(self):
        """Block I must have a 'ИНН клиента' or 'ИНН Клиента' field."""
        func_source = _extract_function_source("_render_summary_tab")
        has_inn = "ИНН клиента" in func_source or "ИНН Клиента" in func_source
        assert has_inn, (
            "Block I must contain customer INN field ('ИНН клиента')"
        )

    def test_block_i_has_seller_name_field(self):
        """Block I must have a seller company name field."""
        func_source = _extract_function_source("_render_summary_tab")
        has_seller = ("Продавец" in func_source or
                      "Организация продавец" in func_source)
        assert has_seller, (
            "Block I must contain a seller company name field "
            "('Продавец' or 'Организация продавец')"
        )

    def test_block_i_has_seller_inn_field(self):
        """Block I must have a 'ИНН продавца' or 'ИНН Продавца' field."""
        func_source = _extract_function_source("_render_summary_tab")
        has_seller_inn = "ИНН продавца" in func_source or "ИНН Продавца" in func_source
        assert has_seller_inn, (
            "Block I must contain seller INN field ('ИНН продавца')"
        )

    def test_block_i_has_contact_person_field(self):
        """Block I must have a 'Контактное лицо' field."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Контактное лицо" in func_source, (
            "Block I must contain 'Контактное лицо' field"
        )

    def test_block_i_has_contact_phone_field(self):
        """Block I must have a visible label for contact phone number.
        The TZ spec requires 'Номер продавца + mobile' rendered as a field in Block I."""
        func_source = _extract_function_source("_render_summary_tab")
        # Find Block I area (ОСНОВНАЯ ИНФОРМАЦИЯ)
        block_i_start = func_source.find("ОСНОВНАЯ ИНФОРМАЦИЯ")
        assert block_i_start != -1, "Block I header not found"
        # Look for the next card boundary (next _card_header call or next card variable)
        block_i_area = func_source[block_i_start:block_i_start + 800]
        # Must have a visible phone/mobile label rendered as a _field()
        has_phone_label = (
            "Телефон" in block_i_area or
            "Номер продавца" in block_i_area or
            "Мобильный" in block_i_area or
            "_field(\"Телефон" in block_i_area or
            "_field(\"Номер" in block_i_area
        )
        assert has_phone_label, (
            "Block I must contain a visible phone/mobile field label "
            "(e.g., 'Телефон', 'Номер продавца', 'Мобильный'). "
            "The TZ spec requires 'Номер продавца + mobile' in Block I."
        )


# ==============================================================================
# Block II: ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ — 5 people FIOs + dates
# ==============================================================================

class TestBlockIIAdditionalInfo:
    """Block II must show 5 workflow actors with FIOs and corresponding dates:
    1. Создатель (creator) — Дата создания
    2. Контролер КП — Дата проверки КП
    3. Контролер СП — Дата проверки СП
    4. Таможенный менеджер — Дата таможни
    5. Логистический менеджер — Дата логистики
    """

    def test_block_ii_header_exists(self):
        """Block II must have 'ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ' header."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ" in func_source, (
            "Block II must have 'ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ' header"
        )

    def test_block_ii_has_creator_label(self):
        """Block II must have a 'Создатель' label for creator FIO."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Создатель" in func_source, (
            "Block II must contain 'Создатель' label"
        )

    def test_block_ii_has_quote_controller_label(self):
        """Block II must have a 'Контролер КП' label for quote controller FIO."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Контролер КП" in func_source, (
            "Block II must contain 'Контролер КП' label. "
            "The redesign requires showing quote_controller_id FIO from user_profiles."
        )

    def test_block_ii_has_spec_controller_label(self):
        """Block II must have a 'Контролер СП' label for spec controller FIO."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Контролер СП" in func_source, (
            "Block II must contain 'Контролер СП' label. "
            "The redesign requires showing spec_controller_id FIO from user_profiles."
        )

    def test_block_ii_has_customs_manager_label(self):
        """Block II must have a 'Таможенный менеджер' label."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Таможенный менеджер" in func_source, (
            "Block II must contain 'Таможенный менеджер' label. "
            "The redesign requires showing assigned_customs_user FIO from user_profiles."
        )

    def test_block_ii_has_logistics_manager_label(self):
        """Block II must have a 'Логистический менеджер' label."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Логистический менеджер" in func_source, (
            "Block II must contain 'Логистический менеджер' label. "
            "The redesign requires showing assigned_logistics_user FIO from user_profiles."
        )

    def test_block_ii_has_quote_control_date(self):
        """Block II must reference quote_control_completed_at for the KP control date."""
        func_source = _extract_function_source("_render_summary_tab")
        has_date = "quote_control_completed_at" in func_source or "Дата проверки КП" in func_source
        assert has_date, (
            "Block II must show 'Дата проверки КП' from quote_control_completed_at column."
        )

    def test_block_ii_has_spec_control_date(self):
        """Block II must reference spec_control_completed_at for the SP control date."""
        func_source = _extract_function_source("_render_summary_tab")
        has_date = "spec_control_completed_at" in func_source or "Дата проверки СП" in func_source
        assert has_date, (
            "Block II must show 'Дата проверки СП' from spec_control_completed_at column."
        )

    def test_block_ii_has_customs_date(self):
        """Block II must reference customs_completed_at or 'Дата таможни'."""
        func_source = _extract_function_source("_render_summary_tab")
        has_date = "customs_completed_at" in func_source or "Дата таможни" in func_source
        assert has_date, (
            "Block II must show customs completion date from customs_completed_at."
        )

    def test_block_ii_has_logistics_date(self):
        """Block II must reference logistics_completed_at or 'Дата логистики'."""
        func_source = _extract_function_source("_render_summary_tab")
        has_date = "logistics_completed_at" in func_source or "Дата логистики" in func_source
        assert has_date, (
            "Block II must show logistics completion date from logistics_completed_at."
        )


# ==============================================================================
# Block III: ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ — KP/SP dates and validity
# ==============================================================================

class TestBlockIIIPrintInfo:
    """Block III should contain KP issue date, validity days, and SP dates."""

    def test_block_iii_header_exists(self):
        """Block III must have 'ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ' header."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ" in func_source, (
            "Block III must have 'ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ' header"
        )

    def test_block_iii_has_kp_issue_date(self):
        """Block III must have 'Дата выставления КП' field."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Дата выставления КП" in func_source, (
            "Block III must contain 'Дата выставления КП' field"
        )

    def test_block_iii_has_validity_days(self):
        """Block III must have validity days field."""
        func_source = _extract_function_source("_render_summary_tab")
        has_validity = "Срок действия" in func_source or "validity_days" in func_source
        assert has_validity, (
            "Block III must contain validity days field ('Срок действия')"
        )


# ==============================================================================
# Block IV: ПОРЯДОК РАСЧЕТОВ — exchange rates + payment terms
# ==============================================================================

class TestBlockIVPaymentTerms:
    """Block IV should have exchange rate placeholders and payment terms."""

    def test_block_iv_header_exists(self):
        """Block IV must have 'ПОРЯДОК РАСЧЕТОВ' header."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "ПОРЯДОК РАСЧЕТОВ" in func_source, (
            "Block IV must have 'ПОРЯДОК РАСЧЕТОВ' header"
        )

    def test_block_iv_has_exchange_rate_kp_placeholder(self):
        """Block IV must have 'Курс USD/RUB на дату КП' with '—' placeholder."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Курс USD/RUB на дату КП" in func_source, (
            "Block IV must contain 'Курс USD/RUB на дату КП' field. "
            "Should show '—' placeholder (CBR API integration deferred to Session 5)."
        )

    def test_block_iv_has_exchange_rate_sp_placeholder(self):
        """Block IV must have 'Курс USD/RUB на дату СП' with '—' placeholder."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Курс USD/RUB на дату СП" in func_source, (
            "Block IV must contain 'Курс USD/RUB на дату СП' field. "
            "Should show '—' placeholder."
        )

    def test_block_iv_has_exchange_rate_upd_placeholder(self):
        """Block IV must have 'Курс USD/RUB на дату УПД' with '—' placeholder."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Курс USD/RUB на дату УПД" in func_source, (
            "Block IV must contain 'Курс USD/RUB на дату УПД' field. "
            "Should show '—' placeholder."
        )

    def test_block_iv_has_payment_terms(self):
        """Block IV must have payment terms field."""
        func_source = _extract_function_source("_render_summary_tab")
        has_terms = ("Условия расчетов" in func_source or
                     "payment_terms" in func_source)
        assert has_terms, (
            "Block IV must contain payment terms field ('Условия расчетов')"
        )

    def test_block_iv_has_advance_percent(self):
        """Block IV must have 'Частичная предоплата' and 'Размер аванса' fields."""
        func_source = _extract_function_source("_render_summary_tab")
        has_partial = "Частичная предоплата" in func_source
        has_amount = "Размер аванса" in func_source
        assert has_partial and has_amount, (
            "Block IV must contain both 'Частичная предоплата' (yes/no) "
            "and 'Размер аванса' (percentage) fields per the TZ spec."
        )


# ==============================================================================
# Block V: ДОСТАВКА — method, terms, country, city, address
# ==============================================================================

class TestBlockVDelivery:
    """Block V should contain delivery method, terms, country, city, and address."""

    def test_block_v_header_exists(self):
        """Block V must have 'ДОСТАВКА' header."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "ДОСТАВКА" in func_source, (
            "Block V must have 'ДОСТАВКА' header"
        )

    def test_block_v_has_delivery_method(self):
        """Block V must have delivery method field (Тип доставки or Тип сделки)."""
        func_source = _extract_function_source("_render_summary_tab")
        has_method = "Тип доставки" in func_source or "Тип сделки" in func_source
        assert has_method, (
            "Block V must contain delivery method field"
        )

    def test_block_v_has_delivery_country(self):
        """Block V must have 'Страна поставки' field."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Страна поставки" in func_source, (
            "Block V must contain 'Страна поставки' field"
        )

    def test_block_v_has_delivery_city(self):
        """Block V must have delivery city field."""
        func_source = _extract_function_source("_render_summary_tab")
        has_city = "Город доставки" in func_source or "Город поставки" in func_source
        assert has_city, (
            "Block V must contain delivery city field ('Город доставки' or 'Город поставки')"
        )

    def test_block_v_has_delivery_terms(self):
        """Block V must have 'Базис поставки' field for delivery terms."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Базис поставки" in func_source, (
            "Block V must contain 'Базис поставки' field"
        )


# ==============================================================================
# Block VI: ИТОГО — total, profit, item count, margin %
# ==============================================================================

class TestBlockVITotals:
    """Block VI should have total amount, profit, item count, and margin percentage."""

    def test_block_vi_header_exists(self):
        """Block VI must have 'ИТОГО' header."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "ИТОГО" in func_source, (
            "Block VI must have 'ИТОГО' header"
        )

    def test_block_vi_has_total_amount(self):
        """Block VI must have 'Общая сумма' field."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Общая сумма" in func_source, (
            "Block VI must contain 'Общая сумма' field"
        )

    def test_block_vi_has_total_profit(self):
        """Block VI must have 'Общий профит' field."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Общий профит" in func_source, (
            "Block VI must contain 'Общий профит' field"
        )

    def test_block_vi_has_item_count(self):
        """Block VI must have 'Количество позиций' field."""
        func_source = _extract_function_source("_render_summary_tab")
        assert "Количество позиций" in func_source, (
            "Block VI must contain 'Количество позиций' field"
        )

    def test_block_vi_has_margin_percentage(self):
        """Block VI must have margin percentage label ('Маржа %' or 'Маржа').
        Formula: (profit / total_amount) * 100 if total_amount > 0, else 0."""
        func_source = _extract_function_source("_render_summary_tab")
        # Search specifically in the ИТОГО block area, not the entire function
        # (to avoid matching CSS margin properties)
        totals_start = func_source.find("ИТОГО")
        assert totals_start != -1, "ИТОГО header not found"
        totals_area = func_source[totals_start:totals_start + 1200]
        has_margin = ("Маржа" in totals_area or "маржа" in totals_area)
        assert has_margin, (
            "Block VI (ИТОГО) must contain margin percentage field ('Маржа %'). "
            "Formula: (profit / total_amount) * 100 if total_amount > 0. "
            "Currently the ИТОГО block only shows total, profit, and item count."
        )

    def test_block_vi_margin_calculation_logic(self):
        """Margin % must be calculated as profit/total*100."""
        func_source = _extract_function_source("_render_summary_tab")
        # Should have division: profit / total or total_profit / total_amount
        has_division = re.search(
            r'(profit|total_profit)\s*/\s*(total|total_amount)',
            func_source
        )
        has_multiply_100 = re.search(
            r'\*\s*100',
            func_source
        )
        assert has_division and has_multiply_100, (
            "Block VI must calculate margin as (profit / total_amount) * 100. "
            "The function should contain profit/total division and *100 multiplication."
        )


# ==============================================================================
# Layout: 2-column structure (LEFT 3 blocks + RIGHT 3 blocks)
# ==============================================================================

class TestLayoutStructure:
    """The tab must use a 2-column layout with LEFT column (3 blocks) and
    RIGHT column (3 blocks), arranged in 3 rows of 2 cards each."""

    def test_layout_has_two_column_rows(self):
        """Layout must have 2-column rows (flex or grid with 2 children per row)."""
        func_source = _extract_function_source("_render_summary_tab")
        # Current code uses: Div(card_X, card_Y, style="display: flex; gap: ...")
        flex_rows = re.findall(r'display:\s*flex', func_source)
        grid_cols = re.findall(r'grid-template-columns', func_source)
        # Need at least 3 rows of 2-column layout
        total_layout_markers = len(flex_rows) + len(grid_cols)
        assert total_layout_markers >= 3, (
            f"Layout must have at least 3 two-column rows. "
            f"Found {total_layout_markers} flex/grid layout markers. "
            "Expected 3 rows: [Block I + Block IV], [Block II + Block V], [Block III + Block VI]"
        )

    def test_layout_left_column_order(self):
        """Left column must have blocks in order: Основная, Дополнительная, Печать."""
        func_source = _extract_function_source("_render_summary_tab")
        # Find positions of headers to verify order
        pos_main = func_source.find("ОСНОВНАЯ ИНФОРМАЦИЯ")
        pos_additional = func_source.find("ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ")
        pos_print = func_source.find("ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ")

        assert pos_main != -1 and pos_additional != -1 and pos_print != -1, (
            "All three left-column headers must exist: "
            "'ОСНОВНАЯ ИНФОРМАЦИЯ', 'ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ', 'ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ'"
        )
        assert pos_main < pos_additional < pos_print, (
            "Left column block order must be: "
            "ОСНОВНАЯ ИНФОРМАЦИЯ → ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ → ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ. "
            f"Current positions: main={pos_main}, additional={pos_additional}, print={pos_print}"
        )

    def test_layout_right_column_order(self):
        """Right column must have blocks in order: Расчеты, Доставка, Итого."""
        func_source = _extract_function_source("_render_summary_tab")
        pos_payment = func_source.find("ПОРЯДОК РАСЧЕТОВ")
        pos_delivery = func_source.find("ДОСТАВКА")
        pos_totals = func_source.find("ИТОГО")

        assert pos_payment != -1 and pos_delivery != -1 and pos_totals != -1, (
            "All three right-column headers must exist"
        )
        assert pos_payment < pos_delivery < pos_totals, (
            "Right column block order must be: "
            "ПОРЯДОК РАСЧЕТОВ → ДОСТАВКА → ИТОГО. "
            f"Current positions: payment={pos_payment}, delivery={pos_delivery}, totals={pos_totals}"
        )

    def test_layout_pairs_main_and_payment(self):
        """Row 1 must pair Block I (Основная) with Block IV (Расчеты).
        In the source, they should appear in the same Div() row constructor."""
        func_source = _extract_function_source("_render_summary_tab")
        # Find the first row Div that contains both card references
        # After redesign, card_1 (Основная) and card_4 (Расчеты) should be in same row
        # Pattern: Div(card_1, card_4, ...) or Div(left_card_1, right_card_1, ...)
        # Current code has: Div(card_1, card_2, ...) — wrong pairing
        #
        # We check that in the layout section, ОСНОВНАЯ ИНФОРМАЦИЯ and ПОРЯДОК РАСЧЕТОВ
        # are NOT paired with ДОСТАВКА
        layout_section = func_source[func_source.rfind("return Div("):]
        # The first row should reference both the main-info card and the payment card
        first_row_match = re.search(r'Div\((card_\w+),\s*(card_\w+)', layout_section)
        if first_row_match:
            pair = (first_row_match.group(1), first_row_match.group(2))
            # After redesign, first row should be (card_1, card_4) not (card_1, card_2)
            assert pair != ("card_1", "card_2"), (
                f"Row 1 currently pairs {pair[0]} and {pair[1]}. "
                "After redesign, Row 1 must pair Block I (ОСНОВНАЯ) with Block IV (РАСЧЕТЫ), "
                "not Block I with Block II (ДОСТАВКА)."
            )


# ==============================================================================
# FK Null Safety — all FK lookups must use safe pattern
# ==============================================================================

class TestFKNullSafety:
    """All FK lookups in _render_summary_tab must use the safe null pattern:
    (obj.get("fk") or {}).get("col", default) — NOT .get("fk", {}).get(...)"""

    def test_no_unsafe_fk_pattern_in_summary_tab(self):
        """No .get("key", {}).get() patterns — must use (x.get("key") or {}).get()."""
        func_source = _extract_function_source("_render_summary_tab")
        # Unsafe pattern: .get("something", {}).get(
        unsafe_matches = re.findall(
            r'\.get\(["\'][a-z_]+["\'],\s*\{\}\)\.get\(',
            func_source
        )
        assert len(unsafe_matches) == 0, (
            f"Found {len(unsafe_matches)} unsafe FK access pattern(s) in _render_summary_tab: "
            f"{unsafe_matches}. "
            "Use (obj.get('fk') or {{}}).get('col', default) instead of "
            "obj.get('fk', {{}}).get('col', default) — the latter fails when FK value is None."
        )

    def test_customer_fk_uses_safe_pattern(self):
        """Customer FK lookup must use safe null pattern."""
        func_source = _extract_function_source("_render_summary_tab")
        if "customers" in func_source and ".get(" in func_source:
            # If customer FK is accessed, it must use the safe pattern
            safe_pattern = re.search(
                r'\(.*?\.get\(["\']customers["\']\)\s*or\s*\{\}\)\.get\(',
                func_source
            )
            unsafe_pattern = re.search(
                r'\.get\(["\']customers["\'],\s*\{\}\)\.get\(',
                func_source
            )
            assert unsafe_pattern is None, (
                "Customer FK uses unsafe .get('customers', {}).get() pattern. "
                "Must use (obj.get('customers') or {}).get() for null safety."
            )


# ==============================================================================
# User Profile FIO queries — must fetch from user_profiles table
# ==============================================================================

class TestUserProfileQueries:
    """The quote detail route must fetch user profiles for all workflow actors
    (creator, quote_controller, spec_controller, customs, logistics)."""

    def test_quote_detail_fetches_quote_controller_profile(self):
        """Route handler must query user_profiles for quote_controller_id."""
        source = _read_main_source()
        # Find the GET handler for /quotes/{quote_id}
        handler = _extract_route_handler('"/quotes/{quote_id}"', source)
        has_query = ("quote_controller_id" in handler and "user_profiles" in handler)
        assert has_query, (
            "Quote detail handler must fetch user_profiles for quote_controller_id. "
            "Currently only creator FIO is fetched (created_by → user_profiles). "
            "The redesign needs FIOs for all 5 workflow actors."
        )

    def test_quote_detail_fetches_spec_controller_profile(self):
        """Route handler must query user_profiles for spec_controller_id."""
        source = _read_main_source()
        handler = _extract_route_handler('"/quotes/{quote_id}"', source)
        has_query = ("spec_controller_id" in handler and "user_profiles" in handler)
        assert has_query, (
            "Quote detail handler must fetch user_profiles for spec_controller_id."
        )

    def test_quote_detail_fetches_customs_user_profile(self):
        """Route handler must query user_profiles for assigned_customs_user."""
        source = _read_main_source()
        handler = _extract_route_handler('"/quotes/{quote_id}"', source)
        has_query = ("assigned_customs_user" in handler and "user_profiles" in handler)
        assert has_query, (
            "Quote detail handler must fetch user_profiles for assigned_customs_user."
        )

    def test_quote_detail_fetches_logistics_user_profile(self):
        """Route handler must query user_profiles for assigned_logistics_user."""
        source = _read_main_source()
        handler = _extract_route_handler('"/quotes/{quote_id}"', source)
        has_query = ("assigned_logistics_user" in handler and "user_profiles" in handler)
        assert has_query, (
            "Quote detail handler must fetch user_profiles for assigned_logistics_user."
        )

    def test_existing_creator_profile_query(self):
        """Verify the existing creator FIO query works (baseline — should pass now)."""
        source = _read_main_source()
        handler = _extract_route_handler('"/quotes/{quote_id}"', source)
        assert "created_by" in handler and "user_profiles" in handler, (
            "Quote detail handler must already fetch creator profile from user_profiles."
        )

    def test_render_summary_tab_accepts_profile_params(self):
        """_render_summary_tab must accept user profile data for all workflow actors.
        The function signature should include parameters for controller/manager FIOs."""
        func_source = _extract_function_source("_render_summary_tab")
        # The function signature (first line) should reference controller/manager data
        sig_match = re.search(r'def _render_summary_tab\((.*?)\):', func_source, re.DOTALL)
        assert sig_match, "_render_summary_tab function definition not found"
        signature = sig_match.group(1)
        # Must have params for user profiles (e.g., user_profiles dict, or individual name params)
        has_profile_param = (
            "controller" in signature.lower() or
            "profile" in signature.lower() or
            "customs" in signature.lower() or
            "logistics" in signature.lower() or
            "user_names" in signature.lower()
        )
        assert has_profile_param, (
            f"_render_summary_tab signature must include parameters for workflow actor profiles. "
            f"Current signature: ({signature}). "
            "Needs controller/manager FIO data to display in Block II."
        )


# ==============================================================================
# Content removed from old layout (negative tests)
# ==============================================================================

class TestRemovedContent:
    """Content that should be removed or relocated in the redesign."""

    def test_tender_field_removed_from_block_ii(self):
        """Block II should NOT have 'Тендер ФЗ' in the redesigned version.
        The old Block II (Дополнительная информация) had tender info, notes, and KP number.
        The new Block II replaces that with 5 workflow actors + dates."""
        func_source = _extract_function_source("_render_summary_tab")
        # In the redesigned version, "Тендер ФЗ" should not be inside Block II content
        # (it may be moved elsewhere or removed entirely)
        block_ii_start = func_source.find("ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ")
        if block_ii_start == -1:
            pytest.skip("Block II header not found")
        # Check the next ~500 chars after Block II header for tender
        block_ii_area = func_source[block_ii_start:block_ii_start + 600]
        assert "Тендер ФЗ" not in block_ii_area, (
            "Block II (ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ) should not contain 'Тендер ФЗ' "
            "in the redesigned version. Block II is now for workflow actors + dates."
        )

    def test_notes_field_removed_from_block_ii(self):
        """Block II should NOT have 'Дополнительно' (notes) in redesigned version."""
        func_source = _extract_function_source("_render_summary_tab")
        block_ii_start = func_source.find("ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ")
        if block_ii_start == -1:
            pytest.skip("Block II header not found")
        block_ii_area = func_source[block_ii_start:block_ii_start + 600]
        assert "Дополнительно" not in block_ii_area, (
            "Block II should not contain 'Дополнительно' (notes) field. "
            "The redesigned Block II is for 5 workflow actors + dates."
        )

    def test_totals_block_uses_2col_not_3col(self):
        """Block VI (ИТОГО) must use 2-column grid (4 fields), not 3-column.
        Old version had 3-column: total, profit, count.
        New version has 2x2 grid: total|count, profit|margin%."""
        func_source = _extract_function_source("_render_summary_tab")
        # Find the ИТОГО section
        totals_start = func_source.find("ИТОГО")
        if totals_start == -1:
            pytest.skip("ИТОГО header not found")
        # Use 1200 chars to ensure we capture the grid-template-columns style
        totals_area = func_source[totals_start:totals_start + 1200]
        # Old code uses "grid-template-columns: 1fr 1fr 1fr" (3 columns)
        has_3col = "1fr 1fr 1fr" in totals_area
        assert not has_3col, (
            "Block VI (ИТОГО) still uses 3-column grid (1fr 1fr 1fr). "
            "The redesign requires 2-column grid with 4 fields: "
            "Общая сумма | Количество позиций / Общий профит | Маржа %."
        )
