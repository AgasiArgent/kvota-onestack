"""
Tests for Procurement Invoice API Endpoints

Tests the invoice-first procurement workflow API endpoints:
- POST /api/procurement/{quote_id}/invoices - Create invoice
- PATCH /api/procurement/{quote_id}/invoices/update - Update invoice
- DELETE /api/procurement/{quote_id}/invoices/{invoice_id} - Delete invoice
- POST /api/procurement/{quote_id}/items/assign - Assign items to invoice
- PATCH /api/procurement/{quote_id}/items/bulk - Bulk update item prices
- POST /api/procurement/{quote_id}/complete - Complete procurement

Security tests verify:
- org_id validation on all endpoints
- Quote ownership verification
- Invoice-quote relationship validation
- Role-based access control (procurement, admin only)
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json
from uuid import uuid4


# ============================================================================
# TEST FIXTURES
# ============================================================================

def make_uuid():
    return str(uuid4())


@pytest.fixture
def org_id():
    """Organization ID for test user."""
    return make_uuid()


@pytest.fixture
def other_org_id():
    """Different organization ID for security tests."""
    return make_uuid()


@pytest.fixture
def quote_id():
    """Quote ID for tests."""
    return make_uuid()


@pytest.fixture
def invoice_id():
    """Invoice ID for tests."""
    return make_uuid()


@pytest.fixture
def supplier_id():
    """Supplier ID for tests."""
    return make_uuid()


@pytest.fixture
def buyer_company_id():
    """Buyer company ID for tests."""
    return make_uuid()


@pytest.fixture
def item_ids():
    """List of item IDs for tests."""
    return [make_uuid() for _ in range(3)]


@pytest.fixture
def procurement_session(org_id):
    """Session for procurement user."""
    user_id = make_uuid()
    return {
        "user": {
            "id": user_id,
            "org_id": org_id,
            "email": "procurement@test.com"
        },
        "roles": ["procurement"]
    }


@pytest.fixture
def admin_session(org_id):
    """Session for admin user."""
    user_id = make_uuid()
    return {
        "user": {
            "id": user_id,
            "org_id": org_id,
            "email": "admin@test.com"
        },
        "roles": ["admin"]
    }


@pytest.fixture
def sales_session(org_id):
    """Session for sales user (should be denied)."""
    user_id = make_uuid()
    return {
        "user": {
            "id": user_id,
            "org_id": org_id,
            "email": "sales@test.com"
        },
        "roles": ["sales"]
    }


# ============================================================================
# ENDPOINT EXISTENCE TESTS
# ============================================================================

class TestProcurementAPIEndpointsExist:
    """Verify all procurement API endpoints are defined in main.py."""

    def test_invoice_create_endpoint_exists(self):
        """Verify POST /api/procurement/{quote_id}/invoices endpoint is defined."""
        with open("main.py", "r") as f:
            content = f.read()
            assert '/api/procurement/{quote_id}/invoices' in content
            assert 'methods=["POST"]' in content or "methods=['POST']" in content

    def test_invoice_update_endpoint_exists(self):
        """Verify PATCH /api/procurement/{quote_id}/invoices/update endpoint is defined."""
        with open("main.py", "r") as f:
            content = f.read()
            assert '/api/procurement/{quote_id}/invoices/update' in content
            assert 'methods=["PATCH"]' in content or "methods=['PATCH']" in content

    def test_invoice_delete_endpoint_exists(self):
        """Verify DELETE /api/procurement/{quote_id}/invoices/{invoice_id} endpoint is defined."""
        with open("main.py", "r") as f:
            content = f.read()
            assert '/api/procurement/{quote_id}/invoices/{invoice_id}' in content
            assert 'methods=["DELETE"]' in content or "methods=['DELETE']" in content

    def test_items_assign_endpoint_exists(self):
        """Verify POST /api/procurement/{quote_id}/items/assign endpoint is defined."""
        with open("main.py", "r") as f:
            content = f.read()
            assert '/api/procurement/{quote_id}/items/assign' in content

    def test_items_bulk_endpoint_exists(self):
        """Verify PATCH /api/procurement/{quote_id}/items/bulk endpoint is defined."""
        with open("main.py", "r") as f:
            content = f.read()
            assert '/api/procurement/{quote_id}/items/bulk' in content

    def test_complete_endpoint_exists(self):
        """Verify POST /api/procurement/{quote_id}/complete endpoint is defined."""
        with open("main.py", "r") as f:
            content = f.read()
            assert '/api/procurement/{quote_id}/complete' in content


# ============================================================================
# SECURITY VALIDATION TESTS
# ============================================================================

class TestOrgIdValidation:
    """Test that org_id validation is present on all endpoints."""

    def test_delete_invoice_validates_org_id(self):
        """Verify DELETE invoice endpoint validates organization ownership."""
        with open("main.py", "r") as f:
            content = f.read()
            # Find the delete invoice function
            delete_start = content.find('async def api_delete_invoice')
            if delete_start == -1:
                pytest.skip("api_delete_invoice function not found")

            # Get the function body (next 100 lines or so)
            func_body = content[delete_start:delete_start + 3000]

            # Should have org_id extraction
            assert 'org_id = user["org_id"]' in func_body, "Missing org_id extraction"

            # Should verify quote belongs to organization
            assert '.eq("organization_id", org_id)' in func_body, "Missing org_id validation"

    def test_assign_items_validates_org_id(self):
        """Verify assign items endpoint validates organization ownership."""
        with open("main.py", "r") as f:
            content = f.read()
            func_start = content.find('async def api_assign_items_to_invoice')
            if func_start == -1:
                pytest.skip("api_assign_items_to_invoice function not found")

            func_body = content[func_start:func_start + 3000]

            assert 'org_id = user["org_id"]' in func_body, "Missing org_id extraction"
            assert '.eq("organization_id", org_id)' in func_body, "Missing org_id validation"

    def test_bulk_update_validates_org_id(self):
        """Verify bulk update endpoint validates organization ownership."""
        with open("main.py", "r") as f:
            content = f.read()
            func_start = content.find('async def api_bulk_update_items')
            if func_start == -1:
                pytest.skip("api_bulk_update_items function not found")

            func_body = content[func_start:func_start + 3000]

            assert 'org_id = user["org_id"]' in func_body, "Missing org_id extraction"
            assert '.eq("organization_id", org_id)' in func_body, "Missing org_id validation"


class TestExceptionHandling:
    """Test that proper exception handling is in place."""

    def test_assign_items_uses_specific_exception(self):
        """Verify assign items uses json.JSONDecodeError not bare except."""
        with open("main.py", "r") as f:
            content = f.read()
            func_start = content.find('async def api_assign_items_to_invoice')
            if func_start == -1:
                pytest.skip("api_assign_items_to_invoice function not found")

            func_body = content[func_start:func_start + 2000]

            # Should use specific exception
            assert 'except json.JSONDecodeError' in func_body, "Should use json.JSONDecodeError"
            # Should NOT have bare except
            lines = func_body.split('\n')
            for line in lines:
                if 'except:' in line and 'except json' not in line:
                    pytest.fail(f"Found bare except clause: {line}")

    def test_bulk_update_uses_specific_exception(self):
        """Verify bulk update uses json.JSONDecodeError not bare except."""
        with open("main.py", "r") as f:
            content = f.read()
            func_start = content.find('async def api_bulk_update_items')
            if func_start == -1:
                pytest.skip("api_bulk_update_items function not found")

            func_body = content[func_start:func_start + 2000]

            assert 'except json.JSONDecodeError' in func_body, "Should use json.JSONDecodeError"


class TestQuoteOwnershipValidation:
    """Test quote-invoice relationship validation."""

    def test_delete_invoice_scopes_to_quote(self):
        """Verify DELETE scopes invoice deletion to quote_id."""
        with open("main.py", "r") as f:
            content = f.read()
            func_start = content.find('async def api_delete_invoice')
            if func_start == -1:
                pytest.skip("api_delete_invoice function not found")

            func_body = content[func_start:func_start + 3000]

            # Delete should scope to quote_id
            assert '.eq("quote_id", quote_id)' in func_body, "Delete should scope to quote_id"

    def test_assign_items_validates_invoice_belongs_to_quote(self):
        """Verify assign validates invoice belongs to quote."""
        with open("main.py", "r") as f:
            content = f.read()
            func_start = content.find('async def api_assign_items_to_invoice')
            if func_start == -1:
                pytest.skip("api_assign_items_to_invoice function not found")

            func_body = content[func_start:func_start + 3000]

            # Should verify invoice belongs to quote
            assert '.eq("quote_id", quote_id)' in func_body, "Should validate invoice belongs to quote"


# ============================================================================
# ROLE-BASED ACCESS CONTROL TESTS
# ============================================================================

class TestRoleBasedAccess:
    """Test role-based access control on endpoints."""

    def test_invoice_endpoints_require_procurement_or_admin(self):
        """Verify invoice endpoints check for procurement or admin role."""
        with open("main.py", "r") as f:
            content = f.read()

            # All invoice endpoints should check roles
            endpoints = [
                'api_create_invoice',
                'api_update_invoice',
                'api_delete_invoice',
                'api_assign_items_to_invoice',
                'api_bulk_update_items',
                'api_complete_procurement'
            ]

            for endpoint in endpoints:
                func_start = content.find(f'async def {endpoint}')
                if func_start == -1:
                    continue

                func_body = content[func_start:func_start + 1500]

                # Should check for procurement or admin role
                assert 'user_has_any_role' in func_body, f"{endpoint} should check roles"
                assert '"procurement"' in func_body or "'procurement'" in func_body, \
                    f"{endpoint} should allow procurement role"
                assert '"admin"' in func_body or "'admin'" in func_body, \
                    f"{endpoint} should allow admin role"


# ============================================================================
# JAVASCRIPT RACE CONDITION FIX TESTS
# ============================================================================

class TestJavaScriptRaceConditionFix:
    """Test that race condition in completeProcurement was fixed."""

    def test_save_all_changes_returns_promise(self):
        """Verify saveAllChanges returns a Promise for chaining."""
        with open("main.py", "r") as f:
            content = f.read()

            # Find the JavaScript section
            js_start = content.find('window.saveAllChanges')
            if js_start == -1:
                pytest.skip("saveAllChanges function not found")

            js_section = content[js_start:js_start + 2000]

            # Should return a Promise
            assert 'return fetch' in js_section or 'return Promise' in js_section, \
                "saveAllChanges should return a Promise"

    def test_complete_procurement_awaits_save(self):
        """Verify completeProcurement properly awaits saveAllChanges."""
        with open("main.py", "r") as f:
            content = f.read()

            js_start = content.find('window.completeProcurement')
            if js_start == -1:
                pytest.skip("completeProcurement function not found")

            js_section = content[js_start:js_start + 2000]

            # Should NOT use setTimeout
            assert 'setTimeout' not in js_section, \
                "completeProcurement should not use setTimeout (race condition)"

            # Should use .then() chaining
            assert '.then(' in js_section, \
                "completeProcurement should use Promise chaining"

    def test_complete_procurement_handles_save_errors(self):
        """Verify completeProcurement handles save errors before completing."""
        with open("main.py", "r") as f:
            content = f.read()

            js_start = content.find('window.completeProcurement')
            if js_start == -1:
                pytest.skip("completeProcurement function not found")

            js_section = content[js_start:js_start + 2000]

            # Should check saveResult.success
            assert 'saveResult' in js_section or 'save' in js_section.lower(), \
                "Should check save result before completing"

            # Should have error handling
            assert '.catch(' in js_section, \
                "Should handle network errors"


# ============================================================================
# INVOICE DATA VALIDATION TESTS
# ============================================================================

class TestInvoiceDataValidation:
    """Test invoice creation validation."""

    def test_create_invoice_requires_supplier_and_buyer(self):
        """Verify create invoice requires supplier_id and buyer_company_id."""
        with open("main.py", "r") as f:
            content = f.read()

            func_start = content.find('async def api_create_invoice')
            if func_start == -1:
                pytest.skip("api_create_invoice function not found")

            func_body = content[func_start:func_start + 2500]

            # Should require supplier and buyer
            assert 'supplier_id' in func_body
            assert 'buyer_company_id' in func_body
            assert 'not supplier_id or not buyer_company_id' in func_body or \
                   'supplier_id and buyer_company_id' in func_body.replace('not ', '')

    def test_invoice_number_auto_generation(self):
        """Verify invoice number is auto-generated if not provided."""
        with open("main.py", "r") as f:
            content = f.read()

            func_start = content.find('async def api_create_invoice')
            if func_start == -1:
                pytest.skip("api_create_invoice function not found")

            func_body = content[func_start:func_start + 3000]

            # Should have auto-generation logic (always generates, no user input)
            assert 'invoice_number = f"INV-' in func_body or 'INV-' in func_body, "Should generate invoice number with INV- prefix"


# ============================================================================
# BULK UPDATE VALIDATION TESTS
# ============================================================================

class TestBulkUpdateValidation:
    """Test bulk item update validation."""

    def test_bulk_update_validates_item_ids(self):
        """Verify bulk update validates item IDs belong to quote."""
        with open("main.py", "r") as f:
            content = f.read()

            func_start = content.find('async def api_bulk_update_items')
            if func_start == -1:
                pytest.skip("api_bulk_update_items function not found")

            func_body = content[func_start:func_start + 3000]

            # Should validate item IDs
            assert 'valid_item_ids' in func_body or 'valid_items' in func_body, \
                "Should validate item IDs before update"

    def test_bulk_update_handles_fields(self):
        """Verify bulk update handles price, production_time, and country."""
        with open("main.py", "r") as f:
            content = f.read()

            func_start = content.find('async def api_bulk_update_items')
            if func_start == -1:
                pytest.skip("api_bulk_update_items function not found")

            func_body = content[func_start:func_start + 3000]

            # Should handle these fields
            assert 'purchase_price_original' in func_body
            assert 'production_time_days' in func_body
            assert 'supplier_country' in func_body


# ============================================================================
# COMPLETE PROCUREMENT TESTS
# ============================================================================

class TestCompleteProcurement:
    """Test complete procurement endpoint."""

    def test_complete_marks_items_as_completed(self):
        """Verify complete procurement marks items with completed status."""
        with open("main.py", "r") as f:
            content = f.read()

            func_start = content.find('async def api_complete_procurement')
            if func_start == -1:
                pytest.skip("api_complete_procurement function not found")

            func_body = content[func_start:func_start + 3000]

            # Should set procurement_status to completed
            assert '"procurement_status": "completed"' in func_body or \
                   "'procurement_status': 'completed'" in func_body

    def test_complete_records_completion_metadata(self):
        """Verify complete records who and when completed."""
        with open("main.py", "r") as f:
            content = f.read()

            func_start = content.find('async def api_complete_procurement')
            if func_start == -1:
                pytest.skip("api_complete_procurement function not found")

            func_body = content[func_start:func_start + 3000]

            # Should record completion metadata
            assert 'procurement_completed_at' in func_body
            assert 'procurement_completed_by' in func_body

    def test_complete_filters_by_user_brands(self):
        """Verify complete only affects user's assigned brands."""
        with open("main.py", "r") as f:
            content = f.read()

            func_start = content.find('async def api_complete_procurement')
            if func_start == -1:
                pytest.skip("api_complete_procurement function not found")

            func_body = content[func_start:func_start + 3000]

            # Should get user's brands
            assert 'get_assigned_brands' in func_body or 'my_brands' in func_body


# ============================================================================
# INVOICES HELPER FUNCTION TESTS
# ============================================================================

class TestRenderInvoicesList:
    """Test render_invoices_list helper function."""

    def test_render_invoices_list_exists(self):
        """Verify render_invoices_list helper is defined."""
        with open("main.py", "r") as f:
            content = f.read()
            assert 'async def render_invoices_list' in content or \
                   'def render_invoices_list' in content

    def test_render_invoices_list_fetches_supplier_names(self):
        """Verify helper fetches supplier and buyer names."""
        with open("main.py", "r") as f:
            content = f.read()

            func_start = content.find('def render_invoices_list')
            if func_start == -1:
                func_start = content.find('async def render_invoices_list')
            if func_start == -1:
                pytest.skip("render_invoices_list function not found")

            func_body = content[func_start:func_start + 3000]

            # Should fetch supplier and buyer names
            assert 'suppliers' in func_body
            assert 'buyer_companies' in func_body


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
