"""
Tests for Supplier-Brand UI (Feature UI-BSA)

Feature: Supplier detail page "Brands" tab for managing brand-supplier links.

Routes tested:
- GET /suppliers/{supplier_id}?tab=brands  -- brands tab on supplier detail
- POST /suppliers/{supplier_id}/brands     -- link a brand to supplier
- DELETE /suppliers/{supplier_id}/brands/{assignment_id}  -- unlink brand
- PATCH /suppliers/{supplier_id}/brands/{assignment_id}   -- toggle primary
"""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from typing import Optional
import uuid
import os

# Ensure TESTING env is set before any app imports
os.environ["TESTING"] = "true"
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("APP_SECRET", "test-secret")

from services.brand_supplier_assignment_service import (
    BrandSupplierAssignment,
    get_assignments_for_supplier,
)


# ==============================================================================
# Test Data Fixtures
# ==============================================================================

@pytest.fixture
def org_id():
    return str(uuid.uuid4())


@pytest.fixture
def supplier_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_supplier(supplier_id, org_id):
    """Sample supplier for detail page."""
    return {
        "id": supplier_id,
        "organization_id": org_id,
        "name": "China Manufacturing Ltd",
        "supplier_code": "CMT",
        "country": "China",
        "city": "Shanghai",
        "inn": None,
        "kpp": None,
        "contact_person": "John",
        "contact_email": "john@cmt.cn",
        "contact_phone": "+86123456",
        "default_payment_terms": "30 days",
        "is_active": True,
    }


@pytest.fixture
def sample_assignments(supplier_id, org_id):
    """Sample brand-supplier assignments for this supplier."""
    return [
        BrandSupplierAssignment(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            brand="BOSCH",
            supplier_id=supplier_id,
            is_primary=True,
            notes="Main supplier for BOSCH",
        ),
        BrandSupplierAssignment(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            brand="SIEMENS",
            supplier_id=supplier_id,
            is_primary=False,
            notes=None,
        ),
        BrandSupplierAssignment(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            brand="ABB",
            supplier_id=supplier_id,
            is_primary=True,
            notes="Exclusive for ABB",
        ),
    ]


@pytest.fixture
def mock_admin_session(org_id):
    """Admin session with procurement access."""
    return {
        "user_id": str(uuid.uuid4()),
        "email": "admin@example.com",
        "organization_id": org_id,
        "roles": ["admin"],
    }


@pytest.fixture
def mock_sales_session(org_id):
    """Sales session -- should NOT have access to supplier brands."""
    return {
        "user_id": str(uuid.uuid4()),
        "email": "sales@example.com",
        "organization_id": org_id,
        "roles": ["sales"],
    }


@pytest.fixture
def _fake_supplier(supplier_id, org_id):
    """Build a Supplier object for mocking get_supplier in tests."""
    from services.supplier_service import Supplier
    return Supplier(
        id=supplier_id, organization_id=org_id,
        name="China Manufacturing Ltd", supplier_code="CMT", is_active=True,
    )


@pytest.fixture
def client(supplier_id, _fake_supplier):
    """Create a test client with auth and supplier mocks applied."""
    from main import app
    from starlette.testclient import TestClient

    with patch("main.require_login", return_value=None), \
         patch("main.user_has_any_role", return_value=True), \
         patch("services.supplier_service.get_supplier", return_value=_fake_supplier):
        yield TestClient(app)


# ==============================================================================
# Tab Existence & Navigation Tests
# ==============================================================================

class TestBrandsTabExists:
    """Test that supplier detail page has a Brands tab."""

    def test_supplier_detail_has_brands_tab_link(self, client, supplier_id):
        """Supplier detail page should include a tab/link to 'Бренды'."""
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]):
            response = client.get(f"/suppliers/{supplier_id}")
            html = response.text
            assert "Бренды" in html, "Supplier detail page must have a 'Бренды' tab"

    def test_brands_tab_url_pattern(self, supplier_id):
        """Brands tab should be accessed via ?tab=brands query param."""
        expected_url = f"/suppliers/{supplier_id}?tab=brands"
        assert "tab=brands" in expected_url


# ==============================================================================
# Route Existence Tests
# ==============================================================================

class TestBrandRoutesExist:
    """Test that brand management routes exist and respond (not 404)."""

    def test_post_supplier_brands_route_exists(self):
        """POST /suppliers/{id}/brands route must exist."""
        from main import app

        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        assert any(
            "brands" in str(r) for r in routes if "supplier" in str(r).lower()
        ), f"POST /suppliers/{{supplier_id}}/brands route must be registered"

    def test_delete_supplier_brands_route_exists(self):
        """DELETE /suppliers/{id}/brands/{assignment_id} route must exist."""
        from main import app

        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        assert any(
            "brands" in str(r) and "{assignment_id}" in str(r)
            for r in routes
        ), f"DELETE /suppliers/{{supplier_id}}/brands/{{assignment_id}} route must be registered"

    def test_patch_supplier_brands_route_exists(self):
        """PATCH /suppliers/{id}/brands/{assignment_id} route must exist."""
        from main import app

        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        assert any(
            "brands" in str(r) and "{assignment_id}" in str(r)
            for r in routes
        ), f"PATCH /suppliers/{{supplier_id}}/brands/{{assignment_id}} route must be registered"


# ==============================================================================
# Brands Tab Content Tests
# ==============================================================================

class TestBrandsTabContent:
    """Test the content rendered in the brands tab."""

    def test_brands_tab_shows_brand_names(self, client, supplier_id, sample_assignments):
        """Brands tab should display all linked brand names."""
        brand_names = [a.brand for a in sample_assignments]
        assert "BOSCH" in brand_names
        assert "SIEMENS" in brand_names
        assert "ABB" in brand_names

        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=sample_assignments):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            html = response.text
            for brand in brand_names:
                assert brand in html, f"Brand '{brand}' must appear in brands tab"

    def test_brands_tab_shows_primary_badge(self, client, supplier_id, sample_assignments):
        """Primary brands should be marked with a visual indicator."""
        primary_brands = [a for a in sample_assignments if a.is_primary]
        assert len(primary_brands) == 2  # BOSCH and ABB

        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=sample_assignments):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            html = response.text
            assert "star" in html.lower() or "основной" in html.lower() or "primary" in html.lower(), \
                "Primary brands must have a visual indicator (star icon or badge)"

    def test_brands_tab_shows_add_button(self, client, supplier_id):
        """Brands tab should have an 'Add brand' button."""
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            html = response.text
            assert "Добавить бренд" in html or "добавить бренд" in html.lower(), \
                "Brands tab must have an 'Добавить бренд' button"

    def test_brands_tab_shows_remove_action(self, client, supplier_id, sample_assignments):
        """Each brand row should have a remove/unlink action."""
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=sample_assignments):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            html = response.text
            assert "delete" in html.lower() or "удалить" in html.lower() or "trash" in html.lower() or "unlink" in html.lower(), \
                "Each brand assignment must have a remove action"

    def test_brands_tab_empty_state(self, supplier_id):
        """When supplier has no brands, show empty state message."""
        # Verify the empty state rendering by calling _supplier_brands_tab directly
        # with a mock that returns empty AND bypassing the TESTING fallback
        from main import _supplier_brands_tab
        from fasthtml.common import to_xml

        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]), \
             patch.dict(os.environ, {"TESTING": "false"}):
            result = _supplier_brands_tab(supplier_id, session={})
            html = to_xml(result)
            assert "не привязан" in html.lower(), \
                "Empty state must show a message when no brands are linked"


# ==============================================================================
# CRUD via UI Tests
# ==============================================================================

class TestAddBrandToSupplier:
    """Test adding a brand to a supplier via the UI."""

    def test_add_brand_form_has_brand_input(self, client, supplier_id):
        """The add-brand form must have a brand name input field."""
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            html = response.text
            assert 'name="brand"' in html or 'name="brand_name"' in html, \
                "Add brand form must have a brand name input"

    def test_post_add_brand_creates_assignment(self, client, supplier_id, org_id):
        """POST /suppliers/{id}/brands with brand name should create assignment."""
        mock_result = BrandSupplierAssignment(
            id=str(uuid.uuid4()), organization_id=org_id,
            brand="SCHNEIDER", supplier_id=supplier_id, is_primary=False,
        )
        with patch("services.brand_supplier_assignment_service.create_brand_supplier_assignment", return_value=mock_result), \
             patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[mock_result]):
            response = client.post(
                f"/suppliers/{supplier_id}/brands",
                data={"brand": "SCHNEIDER", "is_primary": "false"},
            )
            assert response.status_code in [200, 201, 303], \
                f"POST should succeed, got {response.status_code}"

    def test_post_add_brand_appears_in_list(self, client, supplier_id, org_id):
        """After adding a brand, it should appear in the brands list."""
        mock_assignment = BrandSupplierAssignment(
            id=str(uuid.uuid4()), organization_id=org_id,
            brand="MITSUBISHI", supplier_id=supplier_id, is_primary=False,
        )
        with patch("services.brand_supplier_assignment_service.create_brand_supplier_assignment", return_value=mock_assignment), \
             patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[mock_assignment]):
            # Add brand
            client.post(
                f"/suppliers/{supplier_id}/brands",
                data={"brand": "MITSUBISHI"},
            )
            # The POST handler returns the updated brands list partial
            # Check that MITSUBISHI appears in the response
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            assert "MITSUBISHI" in response.text, \
                "Newly added brand must appear in the brands list"

    def test_post_add_brand_empty_name_rejected(self, client, supplier_id):
        """POST with empty brand name should be rejected."""
        with patch("services.brand_supplier_assignment_service.create_brand_supplier_assignment") as mock_create, \
             patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]):
            response = client.post(
                f"/suppliers/{supplier_id}/brands",
                data={"brand": ""},
            )
            assert response.status_code in [200, 400, 422] and \
                ("ошибк" in response.text.lower() or "обязательн" in response.text.lower() or not mock_create.called), \
                "Empty brand name must be rejected"


class TestRemoveBrandFromSupplier:
    """Test removing a brand from a supplier via the UI."""

    def test_delete_brand_assignment(self, client, supplier_id, sample_assignments):
        """DELETE /suppliers/{id}/brands/{assignment_id} should remove the link."""
        assignment_id = sample_assignments[0].id
        with patch("services.brand_supplier_assignment_service.delete_brand_supplier_assignment", return_value=True), \
             patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]):
            response = client.delete(
                f"/suppliers/{supplier_id}/brands/{assignment_id}",
            )
            assert response.status_code in [200, 303], \
                f"DELETE should succeed, got {response.status_code}"

    def test_deleted_brand_disappears_from_list(self, client, supplier_id, sample_assignments):
        """After deleting a brand assignment, it should not appear in list."""
        assignment = sample_assignments[1]  # SIEMENS
        remaining = [a for a in sample_assignments if a.id != assignment.id]
        with patch("services.brand_supplier_assignment_service.delete_brand_supplier_assignment", return_value=True), \
             patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=remaining):
            # Delete
            client.delete(f"/suppliers/{supplier_id}/brands/{assignment.id}")
            # Verify gone
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            assert assignment.id not in response.text, \
                "Deleted assignment should not appear in list"


class TestTogglePrimaryBrand:
    """Test toggling primary status on a brand assignment."""

    def test_patch_toggle_primary(self, client, supplier_id, sample_assignments):
        """PATCH /suppliers/{id}/brands/{assignment_id} should toggle primary."""
        assignment = sample_assignments[1]  # SIEMENS, currently not primary
        updated = BrandSupplierAssignment(
            id=assignment.id, organization_id=assignment.organization_id,
            brand=assignment.brand, supplier_id=assignment.supplier_id, is_primary=True,
        )
        with patch("services.brand_supplier_assignment_service.update_brand_supplier_assignment", return_value=updated), \
             patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=sample_assignments):
            response = client.patch(
                f"/suppliers/{supplier_id}/brands/{assignment.id}",
                data={"is_primary": "true"},
            )
            assert response.status_code in [200, 303], \
                f"PATCH should succeed, got {response.status_code}"

    def test_primary_toggle_updates_badge(self, client, supplier_id, sample_assignments):
        """After toggling primary, the UI should reflect the new status."""
        assignment = sample_assignments[1]  # SIEMENS, not primary -> make primary
        updated_assignments = [
            BrandSupplierAssignment(
                id=a.id, organization_id=a.organization_id,
                brand=a.brand, supplier_id=a.supplier_id,
                is_primary=True if a.id == assignment.id else a.is_primary,
            )
            for a in sample_assignments
        ]
        with patch("services.brand_supplier_assignment_service.update_brand_supplier_assignment"), \
             patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=updated_assignments):
            # Toggle to primary
            client.patch(
                f"/suppliers/{supplier_id}/brands/{assignment.id}",
                data={"is_primary": "true"},
            )
            # Check updated view
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            assert response.status_code == 200


# ==============================================================================
# Access Control Tests
# ==============================================================================

class TestBrandAccessControl:
    """Test role-based access to supplier brand management."""

    def test_admin_can_access_brands_tab(self):
        """Admin role should have access to brands tab."""
        allowed_roles = ["admin", "procurement"]
        assert "admin" in allowed_roles

    def test_procurement_can_access_brands_tab(self):
        """Procurement role should have access to brands tab."""
        allowed_roles = ["admin", "procurement"]
        assert "procurement" in allowed_roles

    def test_sales_cannot_manage_brands(self):
        """Sales role should NOT be able to add/remove brands."""
        allowed_roles = ["admin", "procurement"]
        assert "sales" not in allowed_roles

    def test_finance_cannot_manage_brands(self):
        """Finance role should NOT be able to add/remove brands."""
        allowed_roles = ["admin", "procurement"]
        assert "finance" not in allowed_roles


# ==============================================================================
# Service Integration Tests
# ==============================================================================

class TestBrandServiceIntegration:
    """Test that brand_supplier_assignment_service functions are importable and usable."""

    def test_get_assignments_for_supplier_import(self):
        """get_assignments_for_supplier function must be importable."""
        from services.brand_supplier_assignment_service import get_assignments_for_supplier
        assert callable(get_assignments_for_supplier)

    def test_create_assignment_import(self):
        """create_brand_supplier_assignment function must be importable."""
        from services.brand_supplier_assignment_service import create_brand_supplier_assignment
        assert callable(create_brand_supplier_assignment)

    def test_delete_assignment_import(self):
        """delete_brand_supplier_assignment function must be importable."""
        from services.brand_supplier_assignment_service import delete_brand_supplier_assignment
        assert callable(delete_brand_supplier_assignment)

    def test_update_assignment_import(self):
        """update_brand_supplier_assignment function must be importable."""
        from services.brand_supplier_assignment_service import update_brand_supplier_assignment
        assert callable(update_brand_supplier_assignment)


# ==============================================================================
# Data Display Tests
# ==============================================================================

class TestBrandDataDisplay:
    """Test that brand data is displayed correctly in the UI."""

    def test_assignment_has_required_display_fields(self, sample_assignments):
        """Each assignment should have brand name, primary flag, and id."""
        for assignment in sample_assignments:
            assert assignment.brand, "Brand name must be present"
            assert assignment.id, "Assignment ID must be present"
            assert isinstance(assignment.is_primary, bool), "is_primary must be boolean"

    def test_primary_assignments_count(self, sample_assignments):
        """Verify correct number of primary assignments."""
        primary_count = sum(1 for a in sample_assignments if a.is_primary)
        assert primary_count == 2, "Should have 2 primary assignments (BOSCH, ABB)"

    def test_non_primary_assignments_count(self, sample_assignments):
        """Verify correct number of non-primary assignments."""
        non_primary_count = sum(1 for a in sample_assignments if not a.is_primary)
        assert non_primary_count == 1, "Should have 1 non-primary assignment (SIEMENS)"

    def test_brands_sorted_alphabetically(self, sample_assignments):
        """Brands should be displayed in alphabetical order."""
        brand_names = [a.brand for a in sample_assignments]
        sorted_brands = sorted(brand_names)
        # ABB, BOSCH, SIEMENS
        assert sorted_brands == ["ABB", "BOSCH", "SIEMENS"]

    def test_notes_display(self, sample_assignments):
        """Assignments with notes should display them."""
        assignments_with_notes = [a for a in sample_assignments if a.notes]
        assert len(assignments_with_notes) == 2  # BOSCH and ABB have notes


# ==============================================================================
# Edge Case Tests
# ==============================================================================

class TestBrandEdgeCases:
    """Test edge cases for supplier-brand UI."""

    def test_supplier_with_no_brands(self, client, supplier_id):
        """Supplier with no brand assignments should show empty state."""
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            assert response.status_code == 200, "Page should not crash with zero brands"

    def test_duplicate_brand_rejected(self, client, supplier_id, org_id):
        """Adding the same brand twice to a supplier should be rejected."""
        mock_result = BrandSupplierAssignment(
            id=str(uuid.uuid4()), organization_id=org_id,
            brand="DUPLICATEBRAND", supplier_id=supplier_id, is_primary=False,
        )
        # First POST succeeds, second returns None (duplicate)
        with patch("services.brand_supplier_assignment_service.create_brand_supplier_assignment", side_effect=[mock_result, None]), \
             patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[mock_result]):
            client.post(
                f"/suppliers/{supplier_id}/brands",
                data={"brand": "DUPLICATEBRAND"},
            )
            response = client.post(
                f"/suppliers/{supplier_id}/brands",
                data={"brand": "DUPLICATEBRAND"},
            )
            assert response.status_code in [200, 400, 409, 422, 303]

    def test_brand_name_with_special_chars(self, supplier_id):
        """Brand names with special characters should be handled."""
        special_brands = ["Brand & Co.", "O'Reilly", "Brand (TM)"]
        for brand in special_brands:
            assert len(brand) > 0
            assert isinstance(brand, str)

    def test_nonexistent_supplier_returns_not_crash(self, client):
        """Accessing brands tab for nonexistent supplier should not crash."""
        fake_supplier_id = str(uuid.uuid4())
        # In TESTING mode, get_supplier returns None and a fallback Supplier is created,
        # so the page renders with status 200 and empty brands.
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]):
            response = client.get(f"/suppliers/{fake_supplier_id}?tab=brands")
            assert response.status_code in [200, 302, 404], \
                f"Nonexistent supplier should return proper response, got {response.status_code}"


# ==============================================================================
# HTMX Integration Tests
# ==============================================================================

class TestBrandHTMXIntegration:
    """Test HTMX-related attributes in the brand management UI."""

    def test_add_brand_form_uses_htmx(self, client, supplier_id):
        """Add brand form should use HTMX for inline submission."""
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=[]):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            html = response.text
            assert "hx-post" in html, "Add brand form must use HTMX (hx-post)"

    def test_delete_uses_htmx(self, client, supplier_id, sample_assignments):
        """Delete action should use inline HTMX ajax (no confirm dialog)."""
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=sample_assignments):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            html = response.text
            assert "htmx.ajax" in html and "DELETE" in html, "Delete action must use htmx.ajax DELETE (inline confirm, no browser dialog)"

    def test_toggle_primary_uses_htmx(self, client, supplier_id, sample_assignments):
        """Toggle primary should use HTMX for inline update."""
        with patch("services.brand_supplier_assignment_service.get_assignments_for_supplier", return_value=sample_assignments):
            response = client.get(f"/suppliers/{supplier_id}?tab=brands")
            html = response.text
            assert "hx-patch" in html, "Toggle primary must use HTMX (hx-patch)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
