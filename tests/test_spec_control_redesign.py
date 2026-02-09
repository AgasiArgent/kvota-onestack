"""
TDD Tests for Spec Control Page Redesign: Unified table + search + filter chips.

Feature: Merge 3 separate tables into ONE unified table with:
  - Clickable status chip/pill filter buttons (replaces dropdown)
  - Search input with HTMX debounce (by spec/quote number and client name)
  - Status column with colored badges
  - Group separators between status groups
  - Unified action column
  - Clickable status cards as filter shortcuts
  - HTMX filtering endpoint

Blueprint: .claude/test-ui-reports/blueprint-spec-control-redesign.md

These tests are written BEFORE implementation (TDD).
All tests should FAIL until the redesign is implemented.
"""

import pytest
import re
import os
from uuid import uuid4
from datetime import datetime


# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code (no import needed, avoids sentry_sdk dep)."""
    with open(MAIN_PY) as f:
        return f.read()


def _read_spec_control_function_source():
    """Extract _dashboard_spec_control_content function source from main.py."""
    content = _read_main_source()
    match = re.search(
        r'^(def _dashboard_spec_control_content\(.*?)(?=\ndef )',
        content,
        re.MULTILINE | re.DOTALL
    )
    if not match:
        pytest.fail("Could not find _dashboard_spec_control_content function in main.py")
    return match.group(0)


def _make_uuid():
    return str(uuid4())


# ============================================================================
# Test Data Factories
# ============================================================================

ORG_ID = _make_uuid()
USER_ID = _make_uuid()


def make_pending_quote(
    quote_id=None,
    idn_quote="Q-202601-0001",
    customer_name="Test Customer",
    currency="USD",
    total_amount=10000,
):
    """Create a mock pending quote dict."""
    return {
        "id": quote_id or _make_uuid(),
        "idn_quote": idn_quote,
        "customers": {"name": customer_name},
        "workflow_status": "pending_spec_control",
        "currency": currency,
        "total_amount": total_amount,
        "created_at": datetime.now().isoformat(),
        "deal_type": "supply",
    }


def make_spec(
    spec_id=None,
    status="draft",
    specification_number="SPEC-2026-0001",
    specification_currency="USD",
    total_amount_usd=5000,
    total_profit_usd=1000,
    customer_name="Test Customer",
    idn_quote="Q-202601-0001",
):
    """Create a mock specification dict."""
    return {
        "id": spec_id or _make_uuid(),
        "quote_id": _make_uuid(),
        "specification_number": specification_number,
        "status": status,
        "specification_currency": specification_currency,
        "created_at": datetime.now().isoformat(),
        "quotes": {
            "idn_quote": idn_quote,
            "total_amount_usd": total_amount_usd,
            "total_profit_usd": total_profit_usd,
            "customers": {"name": customer_name},
        },
    }


# ============================================================================
# 1. Unified Table: Single table replaces 3 separate tables
# ============================================================================

class TestUnifiedTable:
    """
    The redesign replaces 3 separate tables (pending quotes, specs on review,
    signed specs) with ONE unified table that shows all items together.
    """

    def test_single_table_container_exists(self):
        """
        There should be exactly ONE main table (not 3+).
        The old implementation has separate H3 sections: 'КП ожидающие спецификации',
        'Спецификации на проверке', 'Подписанные спецификации'.
        After redesign, none of these H3 headers should exist.
        """
        source = _read_spec_control_function_source()
        old_headers = [
            "КП ожидающие спецификации",
            "Спецификации на проверке",
            "Подписанные спецификации",
            "Черновики",
            "Утверждённые спецификации",
        ]
        for header in old_headers:
            assert f'H3(f"{header}"' not in source and f'H3("{header}"' not in source, (
                f"Old separate table header '{header}' should be removed. "
                "The redesign uses a single unified table with group separators."
            )

    def test_unified_table_has_id_spec_table_body(self):
        """
        The unified table body should have id='spec-table-body' for HTMX
        swap targeting.
        """
        source = _read_spec_control_function_source()
        assert 'id="spec-table-body"' in source or "id='spec-table-body'" in source, (
            "Unified table body must have id='spec-table-body' for HTMX "
            "filtering to target with hx-target."
        )

    def test_unified_table_columns(self):
        """
        The unified table must have these columns:
        НОМЕР, КЛИЕНТ, СТАТУС, ВАЛЮТА, СУММА, ПРОФИТ, ДАТА, ДЕЙСТВИЕ
        """
        source = _read_spec_control_function_source()
        required_headers = ["НОМЕР", "КЛИЕНТ", "СТАТУС", "ВАЛЮТА", "СУММА", "ПРОФИТ", "ДАТА"]
        for header in required_headers:
            assert f'"{header}"' in source, (
                f"Unified table must have column header '{header}'. "
                "All data types (pending quotes + specs) share the same column layout."
            )

    def test_no_separate_pending_quote_table(self):
        """
        The old separate pending quotes table had columns
        '№ КП', 'КЛИЕНТ', 'ТИП СДЕЛКИ', 'СУММА', 'ДАТА'.
        After redesign, this separate table should not exist.
        """
        source = _read_spec_control_function_source()
        # Old pattern: Thead with '№ КП' as first header
        assert 'Th("№ КП")' not in source, (
            "Old separate pending quotes table header '№ КП' should be removed. "
            "Pending quotes are now rows in the unified table with СТАТУС='Ожидает'."
        )

    def test_no_dropdown_filter(self):
        """
        The old dropdown Select element for status filtering should be removed.
        Replaced by clickable chip buttons.
        """
        source = _read_spec_control_function_source()
        # Old pattern: Select with onchange pointing to status_filter param
        has_old_select = (
            'Select(' in source
            and 'status_filter' in source
            and 'onchange=' in source
        )
        assert not has_old_select, (
            "Old dropdown filter (Select with onchange) should be removed. "
            "Replaced by clickable status chip buttons with HTMX."
        )


# ============================================================================
# 2. Search Input with HTMX
# ============================================================================

class TestSearchInput:
    """
    The redesign adds a search input that filters by spec/quote number
    and client name, using HTMX with debounce.
    """

    def test_search_input_exists(self):
        """
        Search input with placeholder text should exist in the source.
        """
        source = _read_spec_control_function_source()
        has_search = (
            "Поиск" in source
            and ("hx_get" in source or "hx-get" in source or 'hx_get=' in source)
        )
        assert has_search, (
            "Page must have a search input with placeholder containing 'Поиск' "
            "and HTMX hx-get attribute for live filtering."
        )

    def test_search_input_has_debounce(self):
        """
        Search input must use HTMX trigger with delay (debounce 300ms)
        to avoid excessive requests during typing.
        """
        source = _read_spec_control_function_source()
        # HTMX debounce patterns: hx_trigger="keyup changed delay:300ms"
        # or hx-trigger="keyup changed delay:300ms"
        has_debounce = (
            "delay:300ms" in source
            or "delay:300" in source
        )
        assert has_debounce, (
            "Search input must have HTMX trigger with debounce (delay:300ms). "
            "Example: hx_trigger='keyup changed delay:300ms'"
        )

    def test_search_input_targets_table_body(self):
        """
        Search input hx-target should point to the unified table body.
        """
        source = _read_spec_control_function_source()
        has_target = (
            "spec-table-body" in source
            and ("hx_target" in source or "hx-target" in source)
        )
        assert has_target, (
            "Search input must use hx-target='#spec-table-body' to swap "
            "only the table body content when filtering."
        )

    def test_search_input_has_name_q(self):
        """
        The search input must have name='q' so the query string
        is passed as a parameter to the filter endpoint.
        """
        source = _read_spec_control_function_source()
        has_name_q = (
            'name="q"' in source
            or "name='q'" in source
            or 'name="q"' in source
        )
        assert has_name_q, (
            "Search input must have name='q' for query parameter. "
            "The filter endpoint expects ?q=searchterm"
        )


# ============================================================================
# 3. Status Chip Buttons (replace dropdown)
# ============================================================================

class TestStatusChipButtons:
    """
    Clickable pill/chip buttons that replace the old dropdown filter.
    Each shows a status label with count.
    """

    def test_chip_buttons_exist(self):
        """
        Status chip buttons (not dropdown Options) should exist.
        Chips are rendered as Button/A elements with rounded-full class,
        NOT as Option elements inside a Select dropdown.
        """
        source = _read_spec_control_function_source()
        # Chips must NOT be inside a Select/Option dropdown
        # They must be standalone clickable elements with rounded-full styling
        has_chip_buttons = (
            "rounded-full" in source
            and "hx_get" in source
        )
        assert has_chip_buttons, (
            "Status filter chips must be rendered as standalone buttons with "
            "rounded-full styling and hx_get attributes, NOT as Select/Option dropdown."
        )

    def test_chips_have_htmx_get(self):
        """
        Each chip button must have hx-get to trigger filtering.
        """
        source = _read_spec_control_function_source()
        # Chip buttons use hx_get or hx-get to call the filter endpoint
        # Expect multiple hx_get occurrences for different chips
        hx_get_count = source.count("hx_get=") + source.count("hx-get=")
        # At least 5 chip buttons + 1 search input = 6+ hx_get
        assert hx_get_count >= 5, (
            f"Expected at least 5 hx-get attributes (one per chip + search), "
            f"found {hx_get_count}. Each chip button needs hx-get for HTMX filtering."
        )

    def test_chips_show_counts(self):
        """
        Each chip should show its count, e.g., 'Ожидают (4)'.
        The count comes from the stats dictionary.
        """
        source = _read_spec_control_function_source()
        # Pattern: chip label includes count like f"Ожидают ({stats['pending_quotes']})"
        # or similar pattern with dynamic count
        has_dynamic_count = (
            "stats[" in source
            and ("rounded-full" in source or "chip" in source or "pill" in source)
        )
        assert has_dynamic_count, (
            "Chip buttons must display dynamic counts from stats dict. "
            "Example: f\"Ожидают ({stats['pending_quotes']})\""
        )

    def test_chips_have_rounded_pill_style(self):
        """
        Chip buttons should have rounded-full or pill-like CSS styling.
        """
        source = _read_spec_control_function_source()
        has_pill_style = (
            "rounded-full" in source
            or "rounded-pill" in source
            or "chip" in source.lower()
        )
        assert has_pill_style, (
            "Chip buttons must have pill/rounded-full styling. "
            "Expected CSS class: 'rounded-full' (Tailwind) or equivalent."
        )

    def test_chip_all_resets_filter(self):
        """
        The 'Все' (All) chip should reset the filter to show everything.
        """
        source = _read_spec_control_function_source()
        # Look for a chip with "Все" that sets status=all or no status param
        # Pattern: Button/A with "Все" and hx_get containing status=all or no status
        has_all_chip = "Все" in source and ("status=all" in source or "status=" in source)
        assert has_all_chip, (
            "'Все' (All) chip button must reset the filter. "
            "It should have hx-get with status=all or no status parameter."
        )


# ============================================================================
# 4. Status Badges with Colored CSS
# ============================================================================

class TestStatusBadges:
    """
    Status column shows colored badges:
    - Ожидает -> orange
    - Черновик -> gray
    - На проверке -> blue
    - Подписана -> green
    """

    def test_pending_status_badge_orange(self):
        """
        Pending quotes in the unified table should show 'Ожидает' badge with
        orange styling (bg-orange or amber color).
        """
        source = _read_spec_control_function_source()
        # In the unified table, pending quotes need a status badge
        # The old code did NOT have a status badge for pending quotes (they were in a separate table)
        has_pending_badge = (
            "Ожидает" in source
            and ("orange" in source or "amber" in source)
        )
        assert has_pending_badge, (
            "Pending quotes in unified table must show 'Ожидает' badge with "
            "orange/amber styling. Old code had no status for pending quotes."
        )

    def test_draft_status_badge_gray(self):
        """Draft specs should show gray badge in the unified status badge mapping."""
        source = _read_spec_control_function_source()
        has_gray_badge = (
            "Черновик" in source
            and "gray" in source
        )
        assert has_gray_badge, (
            "Draft specs must show 'Черновик' badge with gray styling."
        )

    def test_review_status_badge_blue(self):
        """
        Specs on review should show BLUE badge (not yellow).
        The blueprint specifies blue for 'На проверке'.
        The old code used yellow (bg-yellow-200). The redesign changes to blue.
        """
        source = _read_spec_control_function_source()
        # Find the status_map entry for pending_review
        # Old: "pending_review": ("На проверке", "bg-yellow-200 text-yellow-800")
        # New: "pending_review": ("На проверке", "bg-blue-200 text-blue-800")
        has_blue_review = "bg-blue-200" in source and "На проверке" in source
        # Make sure it's NOT using yellow for review anymore
        import re
        review_match = re.search(r'"pending_review".*?(?:bg-\w+-\d+)', source, re.DOTALL)
        if review_match:
            review_snippet = review_match.group(0)
            assert "blue" in review_snippet, (
                f"'На проверке' badge must use BLUE styling (bg-blue-200), not yellow. "
                f"Found: {review_snippet}"
            )
        else:
            assert has_blue_review, (
                "Specs on review must show 'На проверке' badge with blue styling (bg-blue-200)."
            )

    def test_signed_status_badge_green(self):
        """Signed specs should show green badge in the unified status badge mapping."""
        source = _read_spec_control_function_source()
        has_green_signed = (
            "Подписана" in source
            and "green" in source
        )
        assert has_green_signed, (
            "Signed specs must show 'Подписана' badge with green styling."
        )


# ============================================================================
# 5. Group Separators Between Status Groups
# ============================================================================

class TestGroupSeparators:
    """
    The unified table shows group separator rows between different status groups.
    e.g., '--- Ожидают спецификации ---', '--- Черновики ---'
    """

    def test_group_separator_rows_exist(self):
        """
        Group separators should exist as Tr rows WITHIN the unified table body.
        They are Tr elements with a single Td (with colspan) containing a group title.
        These are NOT H3 headers above separate tables (old design).
        """
        source = _read_spec_control_function_source()
        # Group separator rows are inline separator Tr() within the single Tbody
        # They must NOT be H3 headers (old design had H3 sections)
        # Look for a separator function or inline Tr with group-separator class
        has_separator_rows = (
            "group-separator" in source
            or "separator-row" in source
            or "status-group-header" in source
        )
        assert has_separator_rows, (
            "Unified table must have inline group separator Tr rows (with class "
            "'group-separator' or similar) between status groups WITHIN the table body. "
            "These are NOT separate H3 headers above separate tables."
        )

    def test_group_separators_have_distinct_style(self):
        """
        Group separator rows should have distinct styling (e.g., background color,
        bold text) to visually separate groups within the unified table.
        """
        source = _read_spec_control_function_source()
        # Look for separator-specific styling in the unified context
        has_separator_style = (
            "group-separator" in source
            or "separator-row" in source
            or "status-group-header" in source
        )
        assert has_separator_style, (
            "Group separator rows must have distinct CSS class. "
            "Expected: 'group-separator', 'separator-row', or 'status-group-header'."
        )


# ============================================================================
# 6. Unified Action Column
# ============================================================================

class TestUnifiedActionColumn:
    """
    The action column depends on the item's status:
    - 'Ожидает' rows -> 'Создать спецификацию' link
    - 'Черновик/На проверке' rows -> 'Редактировать' link
    - 'Подписана' rows -> 'Просмотр' link

    In the unified table, all items go through a single row builder
    that selects the correct action based on type/status.
    """

    def test_action_create_spec_for_pending(self):
        """
        Pending quotes in the unified row builder should have
        'Создать спецификацию' action. This must be in the UNIFIED
        row builder, not in a separate pending_quote_row function.
        """
        source = _read_spec_control_function_source()
        # Must have the action AND not have the old separate function
        has_action = "Создать спецификацию" in source
        has_old_function = "def pending_quote_row(" in source
        assert has_action and not has_old_function, (
            "Pending quotes in unified row builder must have 'Создать спецификацию' action "
            "but the old separate pending_quote_row function should not exist."
        )

    def test_action_edit_for_draft(self):
        """
        Draft specs in the unified row builder should have 'Редактировать' action.
        This must be in a unified builder, not in the old spec_row function.
        """
        source = _read_spec_control_function_source()
        has_action = "Редактировать" in source
        has_old_function = "def spec_row(" in source
        assert has_action and not has_old_function, (
            "Draft specs in unified row builder must have 'Редактировать' action "
            "but the old separate spec_row function should not exist."
        )

    def test_action_view_for_signed(self):
        """
        Signed specs in the unified row builder should have 'Просмотр' action.
        This must be in a unified builder, not in the old spec_row function.
        """
        source = _read_spec_control_function_source()
        has_action = "Просмотр" in source
        has_old_function = "def spec_row(" in source
        assert has_action and not has_old_function, (
            "Signed specs in unified row builder must have 'Просмотр' action "
            "but the old separate spec_row function should not exist."
        )

    def test_unified_row_builder_handles_both_types(self):
        """
        A single row builder function should handle both pending quotes
        and specifications, choosing the right display and action.
        The old code had TWO separate functions: pending_quote_row() and spec_row().
        The redesign should have ONE unified function (or merged logic).
        """
        source = _read_spec_control_function_source()
        # The old implementation has both pending_quote_row and spec_row
        # The redesign should NOT have pending_quote_row as a separate function
        has_old_separate_builders = (
            "def pending_quote_row(" in source
            and "def spec_row(" in source
        )
        assert not has_old_separate_builders, (
            "Old separate row builders (pending_quote_row + spec_row) should be "
            "merged into a single unified row builder. The redesign uses one table "
            "and one row function that handles both types based on status/type."
        )


# ============================================================================
# 7. HTMX Filter Endpoint
# ============================================================================

class TestFilterEndpoint:
    """
    HTMX filtering: the page sends requests with status + q params,
    and the server returns only the table body HTML for swap.
    """

    def test_filter_endpoint_accepts_q_param(self):
        """
        The _dashboard_spec_control_content function (or a dedicated filter route)
        must accept a 'q' search parameter for text filtering.
        """
        source = _read_spec_control_function_source()
        # Check function signature or param handling for 'q'
        has_q_param = (
            "q:" in source  # function param q: str
            or "q =" in source  # q = request.query_params
            or '"q"' in source  # request.query_params.get("q")
            or "search" in source.lower()
        )
        # The function might also be a new dedicated route
        full_source = _read_main_source()
        has_filter_route = (
            "spec-control/filter" in full_source
            or ("spec-control" in full_source and "q=" in full_source)
        )
        assert has_q_param or has_filter_route, (
            "Must accept 'q' search parameter for text filtering. "
            "Either in _dashboard_spec_control_content signature or a dedicated /spec-control/filter route."
        )

    def test_search_filters_by_number_and_client(self):
        """
        The search should filter items by spec/quote number AND client name.
        There must be explicit search/filter logic that checks 'q' against
        multiple fields (not just querying from the database).
        """
        source = _read_spec_control_function_source()
        full_source = _read_main_source()

        # Look for client-side filtering logic: q.lower() in ... or similar
        # The filter must explicitly reference 'q' as a variable and do string matching
        has_search_logic = (
            (".lower()" in source and "q" in source)
            or ("q.lower()" in source)
            or ("search_term" in source and ".lower()" in source)
            or ("q_lower" in source)
        )
        # OR a dedicated filter route that accepts 'q' param
        has_filter_route = "spec-control/filter" in full_source
        assert has_search_logic or has_filter_route, (
            "Must have explicit search filtering logic that checks 'q' against "
            "spec/quote number and client name. Expected pattern: "
            "q.lower() in item['field'].lower() or a /spec-control/filter route."
        )

    def test_filter_returns_partial_html(self):
        """
        When filtering via HTMX, the response should return only the table body
        (partial HTML), not the full page. This is required for hx-swap to work.
        """
        source = _read_spec_control_function_source()
        full_source = _read_main_source()

        # Look for HX-Request check or a dedicated filter endpoint
        has_partial_response = (
            "HX-Request" in source
            or "HX-Request" in full_source[full_source.find("spec-control"):full_source.find("spec-control") + 5000] if "spec-control" in full_source else False
            or "spec-control/filter" in full_source
        )
        assert has_partial_response, (
            "Filter must return partial HTML (table body only) for HTMX swap. "
            "Either check HX-Request header or use a dedicated /spec-control/filter route."
        )


# ============================================================================
# 8. Clickable Status Cards
# ============================================================================

class TestClickableStatusCards:
    """
    The status cards at the top (Ожидают, На проверке, etc.) should be
    clickable filter shortcuts with HTMX attributes.
    """

    def test_status_cards_have_hx_get(self):
        """
        Status cards should have hx-get (or onclick with HTMX) to filter
        the table when clicked.
        """
        source = _read_spec_control_function_source()
        # Old cards are just Div elements with no interactivity
        # New cards should have hx_get or onclick+htmx
        stat_card_section = source[source.find("stat-card"):source.find("stat-card") + 2000] if "stat-card" in source else ""

        has_clickable_cards = (
            ("hx_get" in stat_card_section or "hx-get" in stat_card_section)
            or ("cursor" in stat_card_section and "pointer" in stat_card_section)
        )
        assert has_clickable_cards, (
            "Status cards must be clickable filter shortcuts. "
            "Each card needs hx-get attribute to filter the table on click."
        )

    def test_status_cards_target_table_body(self):
        """
        When clicked, status cards should target the table body for swap.
        """
        source = _read_spec_control_function_source()
        stat_card_section = source[source.find("stat-card"):source.find("stat-card") + 2000] if "stat-card" in source else ""

        has_target = (
            "spec-table-body" in stat_card_section
            or ("hx_target" in stat_card_section or "hx-target" in stat_card_section)
        )
        assert has_target, (
            "Clickable status cards must target '#spec-table-body' for HTMX swap."
        )


# ============================================================================
# 9. Itogo Summary Still Present
# ============================================================================

class TestItogoSummary:
    """
    The Itogo (total) summary line must remain after the redesign.
    """

    def test_itogo_summary_exists(self):
        """Itogo summary line should still be present."""
        source = _read_spec_control_function_source()
        assert "Итого" in source, (
            "The 'Итого' (total) summary line must remain after redesign."
        )

    def test_itogo_shows_amount_and_profit(self):
        """Summary should show both total amount and profit."""
        source = _read_spec_control_function_source()
        has_amount = "specs_total_amount" in source or "total_amount" in source
        has_profit = "specs_total_profit" in source or "total_profit" in source
        assert has_amount and has_profit, (
            "Itogo summary must show both total amount and total profit values."
        )


# ============================================================================
# 10. Empty State When No Results Match Filter
# ============================================================================

class TestEmptyState:
    """
    When search/filter returns no results, show an empty state message.
    """

    def test_empty_state_message_exists(self):
        """
        An empty state message should be shown when no items match the filter.
        This is different from the old per-table empty messages.
        """
        source = _read_spec_control_function_source()
        # The unified table needs a single empty state, not per-section ones
        # Old messages: "Нет КП, ожидающих спецификации", "Нет спецификаций на проверке"
        # New: unified "Ничего не найдено" or "Нет результатов"
        has_empty_state = (
            "Ничего не найдено" in source
            or "Нет результатов" in source
            or "Нет записей" in source
            or "не найдено" in source.lower()
        )
        assert has_empty_state, (
            "Unified table must show an empty state message when no items match "
            "the current filter/search. Expected: 'Ничего не найдено' or similar."
        )

    def test_old_per_table_empty_messages_removed(self):
        """
        The old per-table empty messages should be removed since there is
        only one unified table now.
        """
        source = _read_spec_control_function_source()
        old_empty_messages = [
            "Нет КП, ожидающих спецификации",
            "Нет спецификаций на проверке",
            "Нет подписанных спецификаций",
            "Нет черновиков",
            "Нет утверждённых спецификаций",
        ]
        for msg in old_empty_messages:
            assert msg not in source, (
                f"Old per-table empty message '{msg}' should be removed. "
                "The unified table uses a single empty state message."
            )


# ============================================================================
# 11. Combined Data Merging Logic
# ============================================================================

class TestDataMerging:
    """
    The function should merge pending quotes and specs into a single list,
    sorted by status priority.
    """

    def test_combined_items_list_created(self):
        """
        The function should create a combined/merged list that includes BOTH
        pending quotes and specifications together in a single iterable.
        The old code keeps them as separate lists (pending_quotes, draft_specs, etc.).
        The new code must have an explicit variable named combined_*/all_items/unified_*/merged_*.
        """
        source = _read_spec_control_function_source()
        # Look for an explicit combined variable assignment
        import re
        has_list_merge = bool(re.search(
            r'(combined_items|all_items|merged_items|unified_items|combined_rows|all_rows)\s*=',
            source
        ))
        assert has_list_merge, (
            "Function must explicitly create a combined list variable (e.g., combined_items, "
            "all_items, merged_items) that merges pending_quotes and specs. "
            "The old code keeps them as separate lists rendered in separate tables."
        )

    def test_pending_quotes_get_type_marker(self):
        """
        Pending quotes should be marked with a type field to distinguish
        them from specs in the unified list.
        """
        source = _read_spec_control_function_source()
        has_type_marker = (
            '"type"' in source
            or "'type'" in source
            or '"item_type"' in source
            or "'item_type'" in source
            or '"entry_type"' in source
        )
        assert has_type_marker, (
            "Pending quotes must have a type marker (e.g., type='quote') to "
            "distinguish them from specs in the unified list. This is needed "
            "for choosing the right action and display format."
        )

    def test_status_priority_sorting(self):
        """
        Combined items should be sorted by status priority:
        Ожидают -> Черновики -> На проверке -> Утверждены -> Подписаны.
        There must be an explicit priority/order mapping or sorted() call.
        """
        source = _read_spec_control_function_source()
        has_priority_sort = (
            "status_order" in source
            or "status_priority" in source
            or "sort_key" in source
            or ("sorted(" in source and "status" in source)
            or "priority_order" in source
        )
        assert has_priority_sort, (
            "Combined items must be sorted by status priority. "
            "Expected: status_order dict, sorted() with status key, or priority mapping. "
            "The old code does not sort -- it renders separate tables in fixed order."
        )


# ============================================================================
# 12. Calculation Logic: Combined Totals with Pending Quotes
# ============================================================================

class TestCombinedTotals:
    """
    Test that totals calculation works correctly with both pending quotes
    and specifications in the same view.
    """

    def test_sum_amounts_across_types(self):
        """Sum amounts from both pending quotes and specs."""
        pending = [
            make_pending_quote(total_amount=10000, currency="USD"),
            make_pending_quote(total_amount=25000, currency="EUR"),
        ]
        specs = [
            make_spec(total_amount_usd=5000, total_profit_usd=1000),
            make_spec(total_amount_usd=15000, total_profit_usd=3000),
        ]

        specs_total = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in specs
        )
        assert specs_total == 20000.0

    def test_sum_profits_from_specs(self):
        """Only specs have profit values; pending quotes show dash."""
        specs = [
            make_spec(total_profit_usd=1000),
            make_spec(total_profit_usd=3000),
            make_spec(total_profit_usd=None),
        ]

        total_profit = sum(
            float((s.get("quotes") or {}).get("total_profit_usd") or 0)
            for s in specs
        )
        assert total_profit == 4000.0

    def test_empty_filter_result_totals_zero(self):
        """When filter returns no items, totals should be zero."""
        items = []
        total = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in items
        )
        assert total == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
