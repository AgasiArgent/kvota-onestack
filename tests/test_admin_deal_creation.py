"""
TDD Tests for Admin Deal Creation Bug Fix.

BUG: When admin changes spec status to "signed" via admin_change_status action
in POST /spec-control/{spec_id}, it only updates the status field -- it does NOT
create a deal. The proper deal creation flow is at /spec-control/{spec_id}/confirm-signature.

The admin override at main.py (action == "admin_change_status") needs to also create
a deal when new_status == "signed".

Additionally, the static label "Сделка создана" at the spec detail GET page
(status == "signed") is shown unconditionally when status is signed, even when
no deal actually exists. It should check the deals table first.

These tests are written BEFORE the fix (TDD).
All tests should FAIL until the bug is fixed.

Tests cover:
1. admin_change_status to "signed" must create a deal record
2. Idempotent: skip deal creation if deal already exists for the spec
3. Quote workflow_status must be updated to "deal_signed"
4. Static "Сделка создана" label must only show when deal actually exists
5. Non-"signed" admin status changes must NOT create a deal
6. Deal data must match expected shape (number, amount, currency, etc.)
"""

import pytest
import re
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock


# Path constants (relative to project root via os.path)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY) as f:
        return f.read()


def _extract_post_spec_control_handler():
    """
    Extract the POST /spec-control/{spec_id} handler source.
    This is the second 'def post(session, spec_id' after @rt("/spec-control/{spec_id}").
    """
    content = _read_main_source()
    # Find the admin_change_status block specifically
    # The POST handler starts at the second @rt("/spec-control/{spec_id}") def post(
    matches = list(re.finditer(
        r'@rt\("/spec-control/\{spec_id\}"\)\s*\ndef post\(',
        content
    ))
    if len(matches) < 1:
        pytest.fail("Could not find POST /spec-control/{spec_id} handler in main.py")

    # Get the POST handler body (from the match to the next @rt)
    start = matches[-1].start()  # Use the last match (POST handler)
    # Find the next top-level @rt decorator
    next_rt = re.search(r'\n@rt\(', content[start + 10:])
    if next_rt:
        end = start + 10 + next_rt.start()
    else:
        end = len(content)

    return content[start:end]


def _extract_admin_change_status_block():
    """
    Extract just the admin_change_status action block from the POST handler.
    """
    handler_source = _extract_post_spec_control_handler()
    match = re.search(
        r'if action == "admin_change_status":(.*?)(?=\n    # Check if editable|\n    # Determine new status|\n    # Helper for safe)',
        handler_source,
        re.DOTALL
    )
    if not match:
        pytest.fail("Could not find admin_change_status block in POST handler")
    return match.group(0)


def _extract_get_spec_control_handler():
    """
    Extract the GET /spec-control/{spec_id} handler source.
    """
    content = _read_main_source()
    matches = list(re.finditer(
        r'@rt\("/spec-control/\{spec_id\}"\)\s*\ndef get\(',
        content
    ))
    if not matches:
        pytest.fail("Could not find GET /spec-control/{spec_id} handler in main.py")

    start = matches[0].start()
    # Find the next top-level @rt or def
    next_rt = re.search(r'\n@rt\(', content[start + 10:])
    if next_rt:
        end = start + 10 + next_rt.start()
    else:
        end = len(content)

    return content[start:end]


def _make_uuid():
    return str(uuid.uuid4())


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def spec_id():
    return _make_uuid()


@pytest.fixture
def quote_id():
    return _make_uuid()


@pytest.fixture
def org_id():
    return _make_uuid()


@pytest.fixture
def user_id():
    return _make_uuid()


# ==============================================================================
# 1. Admin Change Status to "signed" MUST create a deal
# ==============================================================================

class TestAdminChangeStatusCreatesDeal:
    """
    When admin uses admin_change_status action with new_status="signed",
    the handler must also create a deal record (same logic as confirm-signature).
    """

    def test_admin_change_status_block_references_deals_table(self):
        """
        The admin_change_status block must interact with the deals table
        to create a deal when new_status is 'signed'.
        """
        block = _extract_admin_change_status_block()

        assert '"deals"' in block or "'deals'" in block, (
            "admin_change_status block must reference the 'deals' table "
            "to create a deal when changing status to 'signed'. "
            "Currently it only updates the specifications table status."
        )

    def test_admin_change_status_block_inserts_deal_when_signed(self):
        """
        The admin_change_status block must insert a deal record when
        new_status == 'signed'.
        """
        block = _extract_admin_change_status_block()

        # Must have an insert operation for deal creation
        has_insert = ".insert(" in block
        has_signed_check = 'new_status == "signed"' in block or "new_status == 'signed'" in block

        assert has_insert and has_signed_check, (
            "admin_change_status block must check if new_status == 'signed' and "
            "insert a deal record. Currently it only updates status without "
            "creating a deal."
        )

    def test_admin_change_status_generates_deal_number(self):
        """
        When creating a deal via admin_change_status, the handler must
        generate a deal number (e.g., 'DEAL-2026-0001').
        """
        block = _extract_admin_change_status_block()

        has_deal_number = "deal_number" in block or "generate_deal_number" in block
        assert has_deal_number, (
            "admin_change_status block must generate a deal_number when "
            "creating a deal for signed status. The deal_number follows "
            "the pattern 'DEAL-YYYY-NNNN'."
        )

    def test_admin_change_status_fetches_quote_data_for_deal(self):
        """
        Creating a deal requires quote data (total_amount, customer info).
        The admin_change_status block must fetch quote data when signing.
        """
        block = _extract_admin_change_status_block()

        # Must fetch quote data (the spec has a quote_id)
        has_quote_fetch = '"quotes"' in block or "'quotes'" in block
        assert has_quote_fetch, (
            "admin_change_status block must fetch quote data (total_amount, customer) "
            "from the quotes table when creating a deal for signed status."
        )


# ==============================================================================
# 2. Idempotent: No duplicate deal creation
# ==============================================================================

class TestAdminChangeStatusIdempotent:
    """
    If a deal already exists for the specification, the admin_change_status
    handler must NOT create a duplicate deal.
    """

    def test_admin_change_status_checks_existing_deal(self):
        """
        Before creating a deal, the handler must check if a deal already
        exists for this specification (idempotency check).
        """
        block = _extract_admin_change_status_block()

        # Must query deals table to check for existing deal
        has_existing_check = (
            "existing_deal" in block
            or "deal_exists" in block
            or ('specification_id' in block and '"deals"' in block)
        )
        assert has_existing_check, (
            "admin_change_status block must check for an existing deal "
            "before creating a new one (idempotency). If a deal already "
            "exists for this spec, it should skip deal creation."
        )

    def test_admin_change_status_skips_insert_when_deal_exists(self):
        """
        When a deal already exists, the admin_change_status block must
        skip the insert operation and just update the status.
        """
        block = _extract_admin_change_status_block()

        # Must have conditional logic: if deal exists, skip insert
        has_conditional = (
            ("not existing_deal" in block or "not deal_exists" in block or
             "if not existing" in block or "if not deal_result" in block)
        )
        assert has_conditional, (
            "admin_change_status block must conditionally skip deal creation "
            "when a deal already exists for this specification."
        )


# ==============================================================================
# 3. Quote workflow_status must be updated to "deal_signed"
# ==============================================================================

class TestAdminChangeStatusUpdatesQuoteWorkflow:
    """
    After creating a deal, the admin_change_status handler must update
    the quote's workflow_status to 'deal_signed'.
    """

    def test_admin_change_status_updates_quote_workflow(self):
        """
        The admin_change_status block must update the quote's workflow_status
        to 'deal_signed' after creating a deal (same as confirm-signature).
        """
        block = _extract_admin_change_status_block()

        has_workflow_update = (
            "deal_signed" in block
            or "workflow_status" in block
            or "transition_quote_status" in block
        )
        assert has_workflow_update, (
            "admin_change_status block must update quote workflow_status to "
            "'deal_signed' after creating a deal. Currently missing."
        )

    def test_admin_change_status_references_workflow_service(self):
        """
        The deal_signed workflow transition should use the workflow service
        (transition_quote_status) or direct update to quotes table.
        """
        block = _extract_admin_change_status_block()

        has_quote_update = (
            "transition_quote_status" in block
            or ('quotes' in block and 'workflow_status' in block)
            or ('quotes' in block and 'deal_signed' in block)
        )
        assert has_quote_update, (
            "admin_change_status block must use either transition_quote_status() "
            "or direct quotes table update to set workflow_status='deal_signed'."
        )


# ==============================================================================
# 4. Static "Сделка создана" label fix
# ==============================================================================

class TestStaticDealCreatedLabel:
    """
    The GET /spec-control/{spec_id} page shows 'Спецификация подписана. Сделка создана.'
    unconditionally when status == 'signed'. This is incorrect because
    admin_change_status can set status to 'signed' WITHOUT creating a deal.
    The label must check the deals table first.
    """

    def test_get_handler_queries_deals_for_signed_spec(self):
        """
        The GET handler must query the deals table when status is 'signed'
        to determine whether to show 'Сделка создана' or not.
        """
        handler = _extract_get_spec_control_handler()

        # The handler must reference 'deals' table in the context of the detail page
        has_deals_query = '"deals"' in handler or "'deals'" in handler
        assert has_deals_query, (
            "GET /spec-control/{spec_id} must query the deals table to check "
            "whether a deal exists for this signed specification. Currently "
            "it shows 'Сделка создана' unconditionally when status=='signed'."
        )

    def test_deal_created_label_is_conditional_on_deal_existence(self):
        """
        The 'Сделка создана' text must only appear when a deal actually exists,
        not just when status == 'signed'.
        """
        handler = _extract_get_spec_control_handler()

        # Find the area around "Сделка создана" text
        label_area_match = re.search(
            r'Сделка создана.*?\) if (.*?) else None',
            handler,
            re.DOTALL
        )
        if not label_area_match:
            pytest.fail(
                "Could not find the conditional rendering of 'Сделка создана' label"
            )

        condition = label_area_match.group(1).strip()

        # The condition must reference deal existence, not just status
        is_just_status_check = condition == 'status == "signed"' or condition == "status == 'signed'"
        assert not is_just_status_check, (
            f"The 'Сделка создана' label condition is currently: `{condition}`. "
            "It must check deal existence (e.g., has_deal, existing_deal, deal_exists), "
            "not just rely on status == 'signed'."
        )

    def test_signed_spec_without_deal_shows_different_message(self):
        """
        When a spec is signed but no deal exists (e.g., admin set status
        directly without deal creation), the page should show a different
        message or no 'Сделка создана' message at all.
        """
        handler = _extract_get_spec_control_handler()

        # After the fix, there should be handling for "signed without deal"
        # either a different message or the absence of "Сделка создана"
        # when there's no deal.
        has_no_deal_case = (
            "Сделка не создана" in handler
            or "сделка не найдена" in handler.lower()
            or "deal_exists" in handler
            or "has_deal" in handler
            or "existing_deal" in handler
        )
        assert has_no_deal_case, (
            "GET handler must handle the case where spec is signed but no deal exists. "
            "Currently it unconditionally shows 'Сделка создана' for signed specs."
        )


# ==============================================================================
# 5. Non-"signed" admin status changes must NOT create a deal
# ==============================================================================

class TestAdminChangeStatusNonSignedNoDeal:
    """
    When admin changes status to anything other than 'signed' (draft,
    pending_review, approved), no deal should be created.
    """

    def test_deal_creation_only_for_signed_status(self):
        """
        The deal creation logic in admin_change_status must be guarded
        by a check for new_status == 'signed'. Status changes to draft,
        pending_review, or approved must not trigger deal creation.
        """
        block = _extract_admin_change_status_block()

        # The block must have conditional: only create deal when new_status == "signed"
        has_signed_guard = (
            'new_status == "signed"' in block
            or "new_status == 'signed'" in block
            or 'new_status == "signed"' in block.replace(" ", "")
        )
        assert has_signed_guard, (
            "admin_change_status block must guard deal creation with "
            'new_status == "signed" check. Deal creation should only happen '
            "when the status is being changed to 'signed', not for draft/pending/approved."
        )

    def test_status_update_always_happens(self):
        """
        Regardless of whether a deal is created, the status update itself
        must always execute for all valid statuses.
        """
        block = _extract_admin_change_status_block()

        # Must have the specifications table update (existing behavior)
        has_spec_update = (
            '"specifications"' in block or "'specifications'" in block
        ) and ".update(" in block
        assert has_spec_update, (
            "admin_change_status block must always update the specifications "
            "table status (existing behavior must be preserved)."
        )


# ==============================================================================
# 6. Deal data shape validation
# ==============================================================================

class TestAdminDealDataShape:
    """
    The deal created by admin_change_status must have the same data shape
    as the one created by confirm-signature:
    - specification_id
    - quote_id
    - organization_id
    - deal_number (DEAL-YYYY-NNNN format)
    - signed_at (date)
    - total_amount (from quote)
    - currency (from spec)
    - status = "active"
    - created_by (admin user_id)
    """

    def test_deal_insert_includes_specification_id(self):
        """Deal record must include specification_id."""
        block = _extract_admin_change_status_block()
        assert "specification_id" in block, (
            "Deal insert must include specification_id field."
        )

    def test_deal_insert_includes_quote_id(self):
        """Deal record must include quote_id."""
        block = _extract_admin_change_status_block()
        assert "quote_id" in block, (
            "Deal insert must include quote_id field."
        )

    def test_deal_insert_includes_organization_id(self):
        """Deal record must include organization_id."""
        block = _extract_admin_change_status_block()
        # org_id is the variable name used in the handler
        has_org = "organization_id" in block or "org_id" in block
        assert has_org, (
            "Deal insert must include organization_id field."
        )

    def test_deal_insert_includes_created_by(self):
        """Deal record must include created_by (the admin user)."""
        block = _extract_admin_change_status_block()
        has_created_by = "created_by" in block or "user_id" in block
        assert has_created_by, (
            "Deal insert must include created_by field (the admin's user_id)."
        )

    def test_deal_insert_sets_active_status(self):
        """Deal record must be created with status='active'."""
        block = _extract_admin_change_status_block()
        # The deal status should be set to 'active'
        has_active = '"active"' in block or "'active'" in block
        assert has_active, (
            "Deal insert must set status='active' for the new deal."
        )

    def test_deal_uses_spec_currency(self):
        """Deal must use the specification_currency from the spec."""
        block = _extract_admin_change_status_block()
        has_currency = (
            "specification_currency" in block
            or "currency" in block
        )
        assert has_currency, (
            "Deal must use the specification_currency or currency from the spec/quote."
        )


# ==============================================================================
# 7. Full POST handler structure: admin override creates deal on sign
# ==============================================================================

class TestFullHandlerStructure:
    """
    Integration-level tests verifying the overall structure of the
    POST handler after the fix is applied.
    """

    def test_admin_change_status_to_signed_is_different_from_other_statuses(self):
        """
        The admin_change_status block must have different behavior for
        new_status=='signed' vs other statuses. For 'signed', it must
        create a deal. For others, it must only update status.
        """
        block = _extract_admin_change_status_block()

        # Count the number of .execute() calls -- with deal creation there should be more
        execute_count = block.count(".execute()")

        # Currently: just 1 execute (update status). After fix: at least 3
        # (check existing deal, insert deal, update status, maybe update quote)
        assert execute_count >= 3, (
            f"admin_change_status block has only {execute_count} .execute() calls. "
            "After the fix, it should have at least 3: update status, check existing deal, "
            "and insert deal record (when new_status=='signed')."
        )

    def test_admin_change_status_does_not_require_signed_scan(self):
        """
        Unlike confirm-signature, admin_change_status should NOT require
        a signed scan upload. Admins can override without a scan.
        The block must NOT check for signed_scan_url as a prerequisite.
        """
        block = _extract_admin_change_status_block()

        # Admin override should NOT block on missing signed_scan_url
        blocks_on_scan = (
            "signed_scan_url" in block
            and "return" in block.split("signed_scan_url")[1][:100]
        )
        assert not blocks_on_scan, (
            "admin_change_status should NOT require signed_scan_url. "
            "Admins should be able to override status to 'signed' even "
            "without a signed scan (this is the point of admin override)."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
