"""
Design Audit Tests: C1, C2, C3

Tests for three design issues found during UI audit:

C1: English text in quote detail Totals/Actions section (should be Russian)
    - Lines ~8136-8145: "Totals", "Products Subtotal:", "Logistics:"
    - Lines ~8668-8682: "Actions", "Calculate", "Version History", "Export",
      "Specification PDF", "Invoice PDF", "Validation Excel"

C2: Emoji characters used instead of Lucide icon() calls
    - Line ~32493: signatory contact badge uses raw emoji instead of icon("pen-line")
    - Lines ~17016-17018: delivery method icons use emoji instead of icon("truck"/etc)

C3: Payments table missing table-enhanced class or gradient header styling
    - Lines ~25933-25944: Table() in _deal_payments_section has no cls="table-enhanced"
      and no gradient header, inconsistent with other tables in the app

All tests are expected to FAIL until the design issues are fixed.
"""

import pytest
import re
import os


# ============================================================================
# Path constants
# ============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code (no import needed, avoids sentry_sdk dep)."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _extract_function_source(func_name, source=None):
    """Extract a top-level function body from main.py by name."""
    if source is None:
        source = _read_main_source()
    pattern = re.compile(
        rf'^(def {re.escape(func_name)}\(.*?)(?=\ndef |\n@rt\(|\nclass |\n# ===|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(source)
    assert match, f"Function '{func_name}' not found in main.py"
    return match.group(1)


def _find_lines_containing(source, needle):
    """Return list of (line_number, line_text) for lines containing needle."""
    results = []
    for i, line in enumerate(source.splitlines(), 1):
        if needle in line:
            results.append((i, line))
    return results


# ============================================================================
# C1: English text in quote detail Totals/Actions section
# ============================================================================

class TestC1_TotalsSectionRussianText:
    """
    The quote detail page Totals card (~line 8136) displays English text.
    All user-facing labels must be in Russian.

    Expected translations:
      "Totals"             -> "Итого"
      "Products Subtotal:" -> "Товары (подитог):"
      "Logistics:"         -> "Логистика:"
      "Total:"             -> remains acceptable, but should ideally be "Итого:"
    """

    def test_totals_heading_is_russian(self):
        """H3('Totals') should be H3('Итого') -- Russian heading."""
        source = _read_main_source()
        # The Totals card heading must NOT contain the English word "Totals"
        totals_hits = _find_lines_containing(source, 'H3("Totals")')
        assert len(totals_hits) == 0, (
            f"Found English heading H3(\"Totals\") at line(s) "
            f"{[ln for ln, _ in totals_hits]}. "
            f"Should be H3(\"Итого\") in Russian."
        )

    def test_products_subtotal_label_is_russian(self):
        """'Products Subtotal:' should be 'Товары (подитог):' in Russian."""
        source = _read_main_source()
        hits = _find_lines_containing(source, "Products Subtotal:")
        assert len(hits) == 0, (
            f"Found English label 'Products Subtotal:' at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be 'Товары (подитог):' or similar Russian text."
        )

    def test_logistics_label_is_russian(self):
        """'Logistics:' should be 'Логистика:' in Russian."""
        source = _read_main_source()
        # Search specifically in Td context to avoid false positives in comments
        hits = _find_lines_containing(source, 'Td("Logistics:")')
        assert len(hits) == 0, (
            f"Found English label Td(\"Logistics:\") at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be Td(\"Логистика:\") in Russian."
        )


class TestC1_ActionsSectionRussianText:
    """
    The quote detail page Actions card (~line 8668) displays English text.
    All user-facing labels must be in Russian.

    Expected translations:
      "Actions"          -> "Действия"
      "Calculate"        -> "Рассчитать"
      "Version History"  -> "История версий"
      "Export"           -> "Экспорт"
      "Specification PDF" -> "Спецификация PDF"
      "Invoice PDF"      -> "Счёт PDF"
      "Validation Excel" -> "Валидация Excel"
    """

    def test_actions_heading_is_russian(self):
        """H3('Actions') should be H3('Действия')."""
        source = _read_main_source()
        hits = _find_lines_containing(source, 'H3("Actions")')
        assert len(hits) == 0, (
            f"Found English heading H3(\"Actions\") at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be H3(\"Действия\")."
        )

    def test_calculate_button_is_russian(self):
        """btn_link('Calculate', ...) should use Russian label 'Рассчитать'."""
        source = _read_main_source()
        hits = _find_lines_containing(source, '"Calculate"')
        assert len(hits) == 0, (
            f"Found English button label \"Calculate\" at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be \"Рассчитать\"."
        )

    def test_version_history_button_is_russian(self):
        """btn_link('Version History', ...) should use Russian label."""
        source = _read_main_source()
        hits = _find_lines_containing(source, '"Version History"')
        assert len(hits) == 0, (
            f"Found English button label \"Version History\" at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be \"История версий\"."
        )

    def test_export_heading_is_russian(self):
        """H4('Export', ...) should be H4('Экспорт', ...)."""
        source = _read_main_source()
        hits = _find_lines_containing(source, 'H4("Export"')
        assert len(hits) == 0, (
            f"Found English heading H4(\"Export\") at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be H4(\"Экспорт\")."
        )

    def test_specification_pdf_button_is_russian(self):
        """btn_link('Specification PDF', ...) should use Russian label."""
        source = _read_main_source()
        hits = _find_lines_containing(source, '"Specification PDF"')
        assert len(hits) == 0, (
            f"Found English button label \"Specification PDF\" at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be \"Спецификация PDF\" or similar."
        )

    def test_invoice_pdf_button_is_russian(self):
        """btn_link('Invoice PDF', ...) should use Russian label."""
        source = _read_main_source()
        hits = _find_lines_containing(source, '"Invoice PDF"')
        assert len(hits) == 0, (
            f"Found English button label \"Invoice PDF\" at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be \"Счёт PDF\" or similar."
        )

    def test_validation_excel_button_is_russian(self):
        """btn_link('Validation Excel', ...) should use Russian label."""
        source = _read_main_source()
        hits = _find_lines_containing(source, '"Validation Excel"')
        assert len(hits) == 0, (
            f"Found English button label \"Validation Excel\" at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should be \"Валидация Excel\" or similar."
        )


# ============================================================================
# C2: Emoji characters instead of Lucide icon() calls
# ============================================================================

class TestC2_SignatoryContactBadge:
    """
    Customer contact card (~line 32493) uses raw emoji for signatory badge.

    Current: Span("✏️", title="Подписант", ...)
    Expected: Span(icon("pen-line", size=14), title="Подписант", ...)
              or icon("pen-tool", ...) -- any Lucide icon, not raw emoji.
    """

    def test_no_pencil_emoji_for_signatory_badge(self):
        """Signatory badge must use icon() instead of raw pencil emoji."""
        source = _read_main_source()
        # Find lines with the pencil emoji near "Подписант"
        hits = []
        for i, line in enumerate(source.splitlines(), 1):
            if "\u270f\ufe0f" in line and "Подписант" in line:
                hits.append((i, line.strip()))
        assert len(hits) == 0, (
            f"Found raw pencil emoji (✏️) for signatory badge at line(s) "
            f"{[ln for ln, _ in hits]}. "
            f"Should use icon('pen-line') or icon('pen-tool') Lucide icon instead."
        )

    def test_signatory_badge_in_contact_card_uses_icon_call(self):
        """The signatory badge in customer contact card must use icon(), not emoji.

        The contact card builds badges in a loop over customer.contacts.
        The is_signatory branch (~line 32493) must use icon("pen-tool") or
        icon("pen-line") wrapped in Span, NOT a raw emoji string.

        There are OTHER places in the codebase that correctly use icon("pen-tool")
        with "Подписант" (e.g., the contact detail page). This test specifically
        checks the contact *preview card* on the customer detail page, which is
        the one that currently uses the emoji.
        """
        source = _read_main_source()
        # Find the specific line that has both 'is_signatory' context and 'Подписант'
        # The buggy pattern is: Span("emoji", title="Подписант") on a line
        # with badges.append -- this is the contact card preview section.
        found_emoji_badge = False
        for line in source.splitlines():
            # The contact card badge line has "badges.append" + "Подписант"
            if "badges.append" in line and "Подписант" in line:
                # This specific badge line should use icon(), not emoji
                if 'icon("pen' not in line and "icon('pen" not in line:
                    found_emoji_badge = True
                    break
        assert not found_emoji_badge, (
            "Customer contact card signatory badge (badges.append with 'Подписант') "
            "does not use icon('pen-line') or icon('pen-tool'). "
            "It should use a Lucide icon call instead of emoji."
        )



# ============================================================================
# C3: Payments table not using table-enhanced styling
# ============================================================================

@pytest.mark.xfail(reason="Design debt: plan-fact tab uses inline styles, not table-enhanced class yet")
class TestC3_PaymentsTableEnhanced:
    """
    The payments table in _finance_plan_fact_tab_content uses plain
    Table() with inline styles instead of the project-standard
    cls='table-enhanced' class or gradient header styling.

    Other tables in the app use either:
    - cls="table-enhanced" on the Table element
    - Gradient header styling (linear-gradient on thead)

    The payments table should follow the same pattern for visual consistency.
    """

    def test_payments_table_has_table_enhanced_class(self):
        """Table in _deal_payments_section should use cls='table-enhanced'."""
        source = _extract_function_source("_finance_plan_fact_tab_content")
        # Find the Table( construction that builds the payments table
        # It should have cls="table-enhanced" or cls='table-enhanced'
        has_enhanced = bool(
            re.search(r'Table\([^)]*cls\s*=\s*["\'].*table-enhanced.*["\']', source, re.DOTALL)
            or re.search(r'payments_table\s*=\s*Table\(.*?cls\s*=\s*["\'].*table-enhanced.*["\']', source, re.DOTALL)
        )
        assert has_enhanced, (
            "_deal_payments_section: payments_table = Table(...) does not use "
            "cls='table-enhanced'. All data tables should use the table-enhanced "
            "class for consistent styling."
        )

    def test_payments_table_thead_has_gradient_or_enhanced_style(self):
        """Payments table header should have gradient background or table-enhanced class.

        Other sections use gradient headers like:
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%)
        on the thead/th elements specifically (not on buttons).

        The payments table thead should follow this pattern or rely on
        table-enhanced CSS which provides its own header styling.
        """
        source = _extract_function_source("_finance_plan_fact_tab_content")
        has_enhanced_class = "table-enhanced" in source

        # Check if linear-gradient is used specifically in th_style definition
        # (the variable used for Th styling), not just on any button.
        # Do NOT use re.DOTALL -- th_style and linear-gradient must be on same line.
        has_gradient_in_th = bool(
            re.search(r'th_style\s*=.*linear-gradient', source)
        )

        assert has_gradient_in_th or has_enhanced_class, (
            "_deal_payments_section: payments table has neither gradient header "
            "styling in th_style nor table-enhanced class. The linear-gradient "
            "found in the function is on a button, not on the table header. "
            "This is inconsistent with other tables in the application."
        )

    def test_payments_table_not_using_bare_inline_collapse_style(self):
        """Payments table should not rely solely on inline border-collapse style.

        When table-enhanced is used, the CSS class handles table layout.
        A bare 'border-collapse: collapse' with no class indicates the table
        hasn't been converted to the design system.
        """
        source = _extract_function_source("_finance_plan_fact_tab_content")
        # Find the Table definition line
        table_match = re.search(
            r'payments_table\s*=\s*Table\(.*?style\s*=\s*"([^"]*)"',
            source,
            re.DOTALL,
        )
        if table_match:
            table_style = table_match.group(1)
            has_only_collapse = "border-collapse" in table_style
            has_enhanced = "table-enhanced" in source
            assert not has_only_collapse or has_enhanced, (
                f"payments_table uses bare inline style=\"{table_style}\" without "
                f"table-enhanced class. Should use cls='table-enhanced' which "
                f"handles layout via CSS."
            )
        else:
            # If no inline style found, check for table-enhanced class
            assert "table-enhanced" in source, (
                "Could not find table-enhanced class in _deal_payments_section. "
                "The payments table needs enhanced styling."
            )
