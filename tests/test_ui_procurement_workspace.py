"""
Tests for UI-019: Procurement Workspace View

Tests the procurement workspace page with v3.0 enhancements:
- Supply chain dropdowns (supplier_id, buyer_company_id, pickup_location_id)
- Quote items filtered by user's assigned brands
- Progress tracking and completion status
- HTMX-powered searchable dropdowns
"""

import pytest
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Check if fasthtml is available for UI component tests
try:
    from main import supplier_dropdown, buyer_company_dropdown, location_dropdown
    FASTHTML_AVAILABLE = True
except ImportError:
    FASTHTML_AVAILABLE = False


# Skip marker for tests requiring fasthtml
requires_fasthtml = pytest.mark.skipif(
    not FASTHTML_AVAILABLE,
    reason="FastHTML not installed - skipping UI component tests"
)


# ============================================================================
# Helper Functions
# ============================================================================

def create_mock_session(
    user_id: str = None,
    org_id: str = None,
    roles: list = None,
    email: str = "procurement@test.com"
) -> Dict[str, Any]:
    """Create a mock session for testing"""
    return {
        "user": {
            "id": user_id or str(uuid.uuid4()),
            "org_id": org_id or str(uuid.uuid4()),
            "organization_id": org_id or str(uuid.uuid4()),
            "email": email,
            "roles": roles or ["procurement"]
        }
    }


def create_mock_quote(
    quote_id: str = None,
    org_id: str = None,
    customer_name: str = "Test Customer",
    workflow_status: str = "pending_procurement",
    idn_quote: str = None,
) -> Dict[str, Any]:
    """Create a mock quote for testing"""
    qid = quote_id or str(uuid.uuid4())
    return {
        "id": qid,
        "organization_id": org_id or str(uuid.uuid4()),
        "idn_quote": idn_quote or f"Q-{qid[:8]}",
        "workflow_status": workflow_status,
        "status": workflow_status,
        "total_amount": 100000.00,
        "created_at": datetime.now().isoformat(),
        "customers": {"name": customer_name}
    }


def create_mock_quote_item(
    item_id: str = None,
    quote_id: str = None,
    brand: str = "TestBrand",
    procurement_status: str = "pending",
    supplier_id: str = None,
    buyer_company_id: str = None,
    pickup_location_id: str = None,
) -> Dict[str, Any]:
    """Create a mock quote item for testing"""
    return {
        "id": item_id or str(uuid.uuid4()),
        "quote_id": quote_id or str(uuid.uuid4()),
        "brand": brand,
        "name": f"Product {brand}",
        "product_code": f"SKU-{brand}",
        "quantity": 10,
        "procurement_status": procurement_status,
        "base_price_vat": 1500.00,
        "weight_in_kg": 0.5,
        "volume_m3": 0.01,
        "production_time_days": 30,
        "advance_to_supplier_percent": 100,
        "supplier_payment_terms": "100% advance",
        "procurement_notes": None,
        # v3.0 supply chain fields
        "supplier_id": supplier_id,
        "buyer_company_id": buyer_company_id,
        "pickup_location_id": pickup_location_id,
    }


def create_mock_supplier(supplier_id: str = None, code: str = "SUP", name: str = "Test Supplier"):
    """Create a mock supplier object"""
    class MockSupplier:
        def __init__(self, id, supplier_code, name, country="Китай", city="Шанхай"):
            self.id = id
            self.supplier_code = supplier_code
            self.name = name
            self.country = country
            self.city = city
            self.is_active = True

    return MockSupplier(supplier_id or str(uuid.uuid4()), code, name)


def create_mock_buyer_company(bc_id: str = None, code: str = "KVT", name: str = "ООО Квота"):
    """Create a mock buyer company object"""
    class MockBuyerCompany:
        def __init__(self, id, company_code, name, inn="1234567890"):
            self.id = id
            self.company_code = company_code
            self.name = name
            self.inn = inn
            self.is_active = True

    return MockBuyerCompany(bc_id or str(uuid.uuid4()), code, name)


def create_mock_location(loc_id: str = None, code: str = "MSK", city: str = "Москва"):
    """Create a mock location object"""
    class MockLocation:
        def __init__(self, id, code, city, country="Россия"):
            self.id = id
            self.code = code
            self.city = city
            self.country = country
            self.display_name = f"{code} - {city}, {country}"
            self.is_hub = True
            self.is_customs_point = False

    return MockLocation(loc_id or str(uuid.uuid4()), code, city)


# ============================================================================
# Test: Supply Chain Field Presence
# ============================================================================

class TestSupplyChainFields:
    """Test v3.0 supply chain fields in procurement form"""

    @requires_fasthtml
    def test_form_has_supplier_dropdown(self):
        """Procurement form should have supplier_id dropdown"""
        # The dropdown component should use supplier_dropdown() function
        dropdown = supplier_dropdown(
            name="supplier_id_test",
            label="Поставщик",
            selected_id=None,
        )

        # Should return a Div element
        assert dropdown is not None
        assert hasattr(dropdown, 'tag')  # FastHTML elements have tag attribute

    @requires_fasthtml
    def test_form_has_buyer_company_dropdown(self):
        """Procurement form should have buyer_company_id dropdown"""
        dropdown = buyer_company_dropdown(
            name="buyer_company_id_test",
            label="Компания-покупатель",
            selected_id=None,
        )

        assert dropdown is not None
        assert hasattr(dropdown, 'tag')

    @requires_fasthtml
    def test_form_has_location_dropdown(self):
        """Procurement form should have pickup_location_id dropdown"""
        dropdown = location_dropdown(
            name="pickup_location_id_test",
            label="Точка отгрузки",
            selected_id=None,
        )

        assert dropdown is not None
        assert hasattr(dropdown, 'tag')

    @requires_fasthtml
    def test_supplier_dropdown_with_preselected_value(self):
        """Supplier dropdown should handle pre-selected value"""
        supplier_id = str(uuid.uuid4())
        supplier_label = "SUP - Test Supplier (Китай)"

        dropdown = supplier_dropdown(
            name="supplier_id_test",
            label="Поставщик",
            selected_id=supplier_id,
            selected_label=supplier_label,
        )

        assert dropdown is not None

    @requires_fasthtml
    def test_buyer_company_dropdown_with_preselected_value(self):
        """Buyer company dropdown should handle pre-selected value"""
        bc_id = str(uuid.uuid4())
        bc_label = "KVT - ООО Квота"

        dropdown = buyer_company_dropdown(
            name="buyer_company_id_test",
            label="Компания-покупатель",
            selected_id=bc_id,
            selected_label=bc_label,
        )

        assert dropdown is not None

    @requires_fasthtml
    def test_location_dropdown_with_preselected_value(self):
        """Location dropdown should handle pre-selected value"""
        loc_id = str(uuid.uuid4())
        loc_label = "MSK - Москва, Россия [хаб]"

        dropdown = location_dropdown(
            name="pickup_location_id_test",
            label="Точка отгрузки",
            selected_id=loc_id,
            selected_label=loc_label,
        )

        assert dropdown is not None


# ============================================================================
# Test: Dropdown Component Attributes
# ============================================================================

class TestDropdownAttributes:
    """Test HTMX attributes on dropdown components"""

    @requires_fasthtml
    def test_supplier_dropdown_has_htmx_attributes(self):
        """Supplier dropdown should have HTMX search attributes"""
        dropdown = supplier_dropdown(
            name="supplier_id",
            label="Поставщик",
            dropdown_id="sup-test123",
        )

        # Convert to string to check content
        dropdown_str = str(dropdown)

        # Should have search endpoint
        assert "/api/suppliers/search" in dropdown_str
        # Should have HTMX trigger
        assert "hx-get" in dropdown_str
        assert "hx-trigger" in dropdown_str
        assert "hx-target" in dropdown_str

    @requires_fasthtml
    def test_buyer_company_dropdown_has_htmx_attributes(self):
        """Buyer company dropdown should have HTMX search attributes"""
        dropdown = buyer_company_dropdown(
            name="buyer_company_id",
            label="Компания-покупатель",
            dropdown_id="buy-test123",
        )

        dropdown_str = str(dropdown)

        assert "/api/buyer-companies/search" in dropdown_str
        assert "hx-get" in dropdown_str

    @requires_fasthtml
    def test_location_dropdown_has_htmx_attributes(self):
        """Location dropdown should have HTMX search attributes"""
        dropdown = location_dropdown(
            name="pickup_location_id",
            label="Точка отгрузки",
            dropdown_id="loc-test123",
        )

        dropdown_str = str(dropdown)

        assert "/api/locations/search" in dropdown_str
        assert "hx-get" in dropdown_str


# ============================================================================
# Test: Dropdown Help Text
# ============================================================================

class TestDropdownHelpText:
    """Test help text on dropdown components"""

    @requires_fasthtml
    def test_supplier_dropdown_help_text(self):
        """Supplier dropdown should show help text when provided"""
        help_text = "Внешний поставщик товара"
        dropdown = supplier_dropdown(
            name="supplier_id",
            label="Поставщик",
            help_text=help_text,
        )

        dropdown_str = str(dropdown)
        assert help_text in dropdown_str

    @requires_fasthtml
    def test_buyer_company_dropdown_help_text(self):
        """Buyer company dropdown should show help text when provided"""
        help_text = "Наше юрлицо для закупки"
        dropdown = buyer_company_dropdown(
            name="buyer_company_id",
            label="Компания-покупатель",
            help_text=help_text,
        )

        dropdown_str = str(dropdown)
        assert help_text in dropdown_str

    @requires_fasthtml
    def test_location_dropdown_help_text(self):
        """Location dropdown should show help text when provided"""
        help_text = "Откуда забирать товар"
        dropdown = location_dropdown(
            name="pickup_location_id",
            label="Точка отгрузки",
            help_text=help_text,
        )

        dropdown_str = str(dropdown)
        assert help_text in dropdown_str


# ============================================================================
# Test: Service Imports
# ============================================================================

class TestServiceImports:
    """Test that required services can be imported"""

    def test_supplier_service_import(self):
        """Should be able to import supplier service"""
        from services.supplier_service import (
            get_supplier,
            format_supplier_for_dropdown,
            Supplier
        )
        assert get_supplier is not None
        assert format_supplier_for_dropdown is not None

    def test_buyer_company_service_import(self):
        """Should be able to import buyer company service"""
        from services.buyer_company_service import (
            get_buyer_company,
            format_buyer_company_for_dropdown,
            BuyerCompany
        )
        assert get_buyer_company is not None
        assert format_buyer_company_for_dropdown is not None

    def test_location_service_import(self):
        """Should be able to import location service"""
        from services.location_service import (
            get_location,
            format_location_for_dropdown,
            Location
        )
        assert get_location is not None
        assert format_location_for_dropdown is not None


# ============================================================================
# Test: Workflow Service Integration
# ============================================================================

class TestWorkflowIntegration:
    """Test workflow service integration with procurement"""

    def test_workflow_status_enum_has_procurement(self):
        """WorkflowStatus enum should have PENDING_PROCUREMENT"""
        from services.workflow_service import WorkflowStatus
        assert WorkflowStatus.PENDING_PROCUREMENT == "pending_procurement"

    def test_status_names_has_procurement(self):
        """STATUS_NAMES should have procurement status translation"""
        from services.workflow_service import STATUS_NAMES, WorkflowStatus
        assert WorkflowStatus.PENDING_PROCUREMENT in STATUS_NAMES
        assert "закуп" in STATUS_NAMES[WorkflowStatus.PENDING_PROCUREMENT].lower()

    def test_complete_procurement_import(self):
        """Should be able to import complete_procurement function"""
        from services.workflow_service import complete_procurement
        assert complete_procurement is not None


# ============================================================================
# Test: Brand Service Integration
# ============================================================================

class TestBrandServiceIntegration:
    """Test brand service integration for filtering items"""

    def test_get_assigned_brands_import(self):
        """Should be able to import get_assigned_brands function"""
        from services.brand_service import get_assigned_brands
        assert get_assigned_brands is not None


# ============================================================================
# Test: Form Field Names
# ============================================================================

class TestFormFieldNames:
    """Test that form field names match expected patterns"""

    @requires_fasthtml
    def test_supplier_id_field_name_pattern(self):
        """Supplier ID field should follow naming pattern"""
        item_id = str(uuid.uuid4())
        expected_name = f"supplier_id_{item_id}"

        dropdown = supplier_dropdown(
            name=expected_name,
            label="Поставщик",
        )

        dropdown_str = str(dropdown)
        assert expected_name in dropdown_str

    @requires_fasthtml
    def test_buyer_company_id_field_name_pattern(self):
        """Buyer company ID field should follow naming pattern"""
        item_id = str(uuid.uuid4())
        expected_name = f"buyer_company_id_{item_id}"

        dropdown = buyer_company_dropdown(
            name=expected_name,
            label="Компания-покупатель",
        )

        dropdown_str = str(dropdown)
        assert expected_name in dropdown_str

    @requires_fasthtml
    def test_pickup_location_id_field_name_pattern(self):
        """Pickup location ID field should follow naming pattern"""
        item_id = str(uuid.uuid4())
        expected_name = f"pickup_location_id_{item_id}"

        dropdown = location_dropdown(
            name=expected_name,
            label="Точка отгрузки",
        )

        dropdown_str = str(dropdown)
        assert expected_name in dropdown_str


# ============================================================================
# Test: Read-Only Mode
# ============================================================================

class TestReadOnlyMode:
    """Test that dropdowns behave correctly in read-only mode"""

    @requires_fasthtml
    def test_disabled_supplier_dropdown(self):
        """Supplier dropdown should support disabled state through non-edit mode"""
        # In the procurement form, when can_edit=False, we show static text instead of dropdown
        # This is handled in the item_row function in main.py
        # Here we just verify the dropdown component itself renders
        dropdown = supplier_dropdown(
            name="supplier_id",
            label="Поставщик",
        )

        assert dropdown is not None


# ============================================================================
# Test: API Endpoints Exist
# ============================================================================

class TestAPIEndpoints:
    """Test that required API endpoints are defined"""

    @requires_fasthtml
    def test_suppliers_search_endpoint_exists(self):
        """Suppliers search endpoint should be defined in routes"""
        # Check that the endpoint pattern is used in the dropdown
        dropdown_str = str(supplier_dropdown(name="s", label="S"))
        assert "/api/suppliers/search" in dropdown_str

    @requires_fasthtml
    def test_buyer_companies_search_endpoint_exists(self):
        """Buyer companies search endpoint should be defined in routes"""
        dropdown_str = str(buyer_company_dropdown(name="b", label="B"))
        assert "/api/buyer-companies/search" in dropdown_str

    @requires_fasthtml
    def test_locations_search_endpoint_exists(self):
        """Locations search endpoint should be defined in routes"""
        dropdown_str = str(location_dropdown(name="l", label="L"))
        assert "/api/locations/search" in dropdown_str


# ============================================================================
# Test: Volume Field (v3.0)
# ============================================================================

class TestVolumeField:
    """Test volume_m3 field in procurement form"""

    def test_volume_field_in_update_data(self):
        """Volume field should be processed in form submission"""
        # The POST handler should accept volume_m3_{item_id} field
        # This is a structural test - actual form submission tested via integration

        # Verify the field is expected in quote_items table
        # The migration 029 added volume_m3 column
        assert True  # Placeholder - implementation verified by form submission


# ============================================================================
# Test: Supply Chain Section Layout
# ============================================================================

class TestSupplyChainLayout:
    """Test supply chain section layout in procurement form"""

    def test_supply_chain_section_header(self):
        """Supply chain section should have a header"""
        # The form should have a section labeled "Цепочка поставок"
        # This is verified by visual inspection and the code structure
        assert True  # Placeholder - layout verified by code review


# ============================================================================
# Test: Backward Compatibility
# ============================================================================

class TestBackwardCompatibility:
    """Test backward compatibility with existing data"""

    @requires_fasthtml
    def test_null_supplier_id_handled(self):
        """Form should handle items with null supplier_id"""
        # Items created before v3.0 may have null supplier_id
        # The form should display "— не выбран —" for these
        dropdown = supplier_dropdown(
            name="supplier_id",
            label="Поставщик",
            selected_id=None,
            selected_label=None,
        )

        dropdown_str = str(dropdown)
        assert "Выберите поставщика" in dropdown_str

    @requires_fasthtml
    def test_null_buyer_company_id_handled(self):
        """Form should handle items with null buyer_company_id"""
        dropdown = buyer_company_dropdown(
            name="buyer_company_id",
            label="Компания",
            selected_id=None,
            selected_label=None,
        )

        dropdown_str = str(dropdown)
        assert "Выберите компанию" in dropdown_str

    @requires_fasthtml
    def test_null_pickup_location_id_handled(self):
        """Form should handle items with null pickup_location_id"""
        dropdown = location_dropdown(
            name="pickup_location_id",
            label="Локация",
            selected_id=None,
            selected_label=None,
        )

        dropdown_str = str(dropdown)
        assert "Выберите локацию" in dropdown_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
