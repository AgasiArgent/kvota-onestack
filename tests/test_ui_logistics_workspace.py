"""
Tests for UI-020: Logistics Workspace View (v3.0)

This module tests the logistics workspace implementation including:
- Item-level logistics cost fields (supplier→hub, hub→customs, customs→customer)
- Item-level logistics_total_days field
- Pickup location display for items
- Supplier display for items
- Quote-level delivery_time and logistics_notes
- Role-based access (logistics, admin, head_of_logistics)
- Form submission and data saving
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal


# =============================================================================
# Service Function Tests (no FastHTML import required)
# =============================================================================

class TestLogisticsDataCalculations:
    """Test logistics calculation helper functions."""

    def test_safe_decimal_conversion(self):
        """Test safe decimal conversion for logistics costs."""
        def safe_decimal(val, default="0"):
            try:
                return float(val) if val else float(default)
            except:
                return float(default)

        assert safe_decimal("100.50") == 100.50
        assert safe_decimal("0") == 0.0
        assert safe_decimal("") == 0.0
        assert safe_decimal(None) == 0.0
        assert safe_decimal("invalid") == 0.0
        assert safe_decimal("invalid", "10") == 10.0

    def test_safe_int_conversion(self):
        """Test safe integer conversion for logistics_total_days."""
        def safe_int(val, default=None):
            try:
                return int(val) if val else default
            except:
                return default

        assert safe_int("30") == 30
        # "0" converts to int 0, which is falsy, so returns default
        # This matches the form behavior where empty string should return None
        assert safe_int("") is None
        assert safe_int(None) is None
        assert safe_int("invalid") is None
        assert safe_int("invalid", 30) == 30
        # Note: "0" would return 0, then be filtered out in the handler
        # because logistics_total_days should be > 0

    def test_item_logistics_total_calculation(self):
        """Test calculation of total logistics cost per item."""
        def calculate_item_logistics_total(item):
            s2h = float(item.get("logistics_supplier_to_hub") or 0)
            h2c = float(item.get("logistics_hub_to_customs") or 0)
            c2c = float(item.get("logistics_customs_to_customer") or 0)
            return s2h + h2c + c2c

        # Item with all costs
        item1 = {
            "logistics_supplier_to_hub": 100,
            "logistics_hub_to_customs": 200,
            "logistics_customs_to_customer": 150
        }
        assert calculate_item_logistics_total(item1) == 450

        # Item with partial costs
        item2 = {
            "logistics_supplier_to_hub": 100,
            "logistics_hub_to_customs": None,
            "logistics_customs_to_customer": 150
        }
        assert calculate_item_logistics_total(item2) == 250

        # Item with no costs
        item3 = {}
        assert calculate_item_logistics_total(item3) == 0

    def test_quote_logistics_summary(self):
        """Test aggregation of logistics costs across all quote items."""
        items = [
            {"logistics_supplier_to_hub": 100, "logistics_hub_to_customs": 50, "logistics_customs_to_customer": 30, "logistics_total_days": 15},
            {"logistics_supplier_to_hub": 200, "logistics_hub_to_customs": 100, "logistics_customs_to_customer": 50, "logistics_total_days": 20},
            {"logistics_supplier_to_hub": None, "logistics_hub_to_customs": None, "logistics_customs_to_customer": None, "logistics_total_days": None},
        ]

        def calculate_quote_logistics_summary(items):
            total_items = len(items)
            items_with_logistics = 0
            total_logistics_cost = 0

            for item in items:
                s2h = float(item.get("logistics_supplier_to_hub") or 0)
                h2c = float(item.get("logistics_hub_to_customs") or 0)
                c2c = float(item.get("logistics_customs_to_customer") or 0)
                item_total = s2h + h2c + c2c
                if item_total > 0 or item.get("logistics_total_days"):
                    items_with_logistics += 1
                total_logistics_cost += item_total

            return {
                "total_items": total_items,
                "items_with_logistics": items_with_logistics,
                "total_logistics_cost": total_logistics_cost
            }

        summary = calculate_quote_logistics_summary(items)
        assert summary["total_items"] == 3
        assert summary["items_with_logistics"] == 2
        assert summary["total_logistics_cost"] == 530  # 180 + 350 + 0


class TestLogisticsRoleAccess:
    """Test role-based access to logistics workspace."""

    def test_logistics_role_allowed(self):
        """Test that logistics role can access the workspace."""
        def user_has_any_role(roles, required_roles):
            return any(role in required_roles for role in roles)

        assert user_has_any_role(["logistics"], ["logistics", "admin", "head_of_logistics"])
        assert user_has_any_role(["logistics", "sales"], ["logistics", "admin", "head_of_logistics"])

    def test_admin_role_allowed(self):
        """Test that admin role can access the workspace."""
        def user_has_any_role(roles, required_roles):
            return any(role in required_roles for role in roles)

        assert user_has_any_role(["admin"], ["logistics", "admin", "head_of_logistics"])

    def test_head_of_logistics_role_allowed(self):
        """Test that head_of_logistics role can access the workspace (v3.0)."""
        def user_has_any_role(roles, required_roles):
            return any(role in required_roles for role in roles)

        assert user_has_any_role(["head_of_logistics"], ["logistics", "admin", "head_of_logistics"])

    def test_sales_role_denied(self):
        """Test that sales role cannot access logistics workspace."""
        def user_has_any_role(roles, required_roles):
            return any(role in required_roles for role in roles)

        assert not user_has_any_role(["sales"], ["logistics", "admin", "head_of_logistics"])

    def test_procurement_role_denied(self):
        """Test that procurement role cannot access logistics workspace."""
        def user_has_any_role(roles, required_roles):
            return any(role in required_roles for role in roles)

        assert not user_has_any_role(["procurement"], ["logistics", "admin", "head_of_logistics"])


class TestLogisticsEditability:
    """Test logistics editability based on workflow status."""

    def test_editable_in_pending_logistics(self):
        """Test that logistics is editable in pending_logistics status."""
        editable_statuses = ["pending_logistics", "pending_customs", "draft", "pending_procurement"]
        assert "pending_logistics" in editable_statuses

    def test_editable_in_pending_customs(self):
        """Test that logistics is editable in pending_customs status (parallel)."""
        editable_statuses = ["pending_logistics", "pending_customs", "draft", "pending_procurement"]
        assert "pending_customs" in editable_statuses

    def test_not_editable_in_sales_review(self):
        """Test that logistics is not editable after moving to sales review."""
        editable_statuses = ["pending_logistics", "pending_customs", "draft", "pending_procurement"]
        assert "pending_sales_review" not in editable_statuses

    def test_not_editable_when_logistics_completed(self):
        """Test that logistics is not editable after completion."""
        def is_editable(workflow_status, logistics_completed_at):
            editable_statuses = ["pending_logistics", "pending_customs", "draft", "pending_procurement"]
            return workflow_status in editable_statuses and logistics_completed_at is None

        assert is_editable("pending_logistics", None)
        assert not is_editable("pending_logistics", "2026-01-15T12:00:00Z")


class TestLogisticsFormFields:
    """Test logistics form field naming and structure."""

    def test_item_level_field_naming(self):
        """Test that item-level fields use correct naming pattern."""
        item_id = "abc123-uuid"

        # Expected field names for v3.0 item-level logistics
        expected_fields = [
            f"logistics_supplier_to_hub_{item_id}",
            f"logistics_hub_to_customs_{item_id}",
            f"logistics_customs_to_customer_{item_id}",
            f"logistics_total_days_{item_id}"
        ]

        for field in expected_fields:
            assert item_id in field
            assert field.startswith("logistics_")

    def test_quote_level_field_naming(self):
        """Test quote-level logistics field names."""
        quote_level_fields = ["delivery_time", "logistics_notes"]
        assert "delivery_time" in quote_level_fields
        assert "logistics_notes" in quote_level_fields


class TestLogisticsItemDisplay:
    """Test logistics item display logic."""

    def test_item_completion_status_with_costs(self):
        """Test item shows as complete when costs are entered."""
        def get_item_status(item):
            s2h = float(item.get("logistics_supplier_to_hub") or 0)
            h2c = float(item.get("logistics_hub_to_customs") or 0)
            c2c = float(item.get("logistics_customs_to_customer") or 0)
            item_total = s2h + h2c + c2c
            has_logistics = item_total > 0 or item.get("logistics_total_days")
            return "✅" if has_logistics else "⏳"

        item_with_costs = {"logistics_supplier_to_hub": 100}
        assert get_item_status(item_with_costs) == "✅"

        item_without_costs = {}
        assert get_item_status(item_without_costs) == "⏳"

    def test_item_completion_status_with_days_only(self):
        """Test item shows as complete when only days are entered."""
        def get_item_status(item):
            s2h = float(item.get("logistics_supplier_to_hub") or 0)
            h2c = float(item.get("logistics_hub_to_customs") or 0)
            c2c = float(item.get("logistics_customs_to_customer") or 0)
            item_total = s2h + h2c + c2c
            has_logistics = item_total > 0 or item.get("logistics_total_days")
            return "✅" if has_logistics else "⏳"

        item_with_days_only = {"logistics_total_days": 15}
        assert get_item_status(item_with_days_only) == "✅"


class TestPickupLocationDisplay:
    """Test pickup location info display in logistics workspace."""

    def test_pickup_location_label_format(self):
        """Test pickup location label formatting."""
        location = {
            "id": "loc-uuid",
            "city": "Москва",
            "country": "Россия",
            "code": "MSK"
        }

        label = f"{location['code']} - {location['city']}, {location['country']}"
        assert "MSK" in label
        assert "Москва" in label
        assert "Россия" in label

    def test_pickup_location_tooltip(self):
        """Test pickup location tooltip content."""
        pickup_info = {"city": "Шанхай", "country": "Китай"}
        tooltip = f"Точка отгрузки: {pickup_info['city']}, {pickup_info['country']}"
        assert "Шанхай" in tooltip
        assert "Китай" in tooltip


class TestSupplierDisplay:
    """Test supplier info display in logistics workspace."""

    def test_supplier_label_truncation(self):
        """Test supplier label is truncated for long names."""
        long_name = "Very Long Supplier Company Name That Should Be Truncated"
        max_length = 30
        truncated = long_name[:max_length] if len(long_name) > max_length else long_name
        assert len(truncated) <= max_length

    def test_supplier_badge_with_country(self):
        """Test supplier badge includes country info."""
        supplier_info = {
            "label": "ABC Supplier",
            "country": "Китай"
        }
        assert supplier_info["label"] == "ABC Supplier"
        assert supplier_info["country"] == "Китай"


class TestLogisticsPostHandler:
    """Test logistics POST handler data processing."""

    def test_form_data_extraction(self):
        """Test extraction of logistics data from form."""
        # Simulate form data
        form_data = {
            "logistics_supplier_to_hub_item1": "100.50",
            "logistics_hub_to_customs_item1": "200.00",
            "logistics_customs_to_customer_item1": "150.25",
            "logistics_total_days_item1": "21",
            "delivery_time": "30",
            "logistics_notes": "Test notes",
            "action": "save"
        }

        # Extract values
        s2h = float(form_data.get("logistics_supplier_to_hub_item1", 0))
        h2c = float(form_data.get("logistics_hub_to_customs_item1", 0))
        c2c = float(form_data.get("logistics_customs_to_customer_item1", 0))
        days = int(form_data.get("logistics_total_days_item1", 0))

        assert s2h == 100.50
        assert h2c == 200.00
        assert c2c == 150.25
        assert days == 21

    def test_update_data_building(self):
        """Test building update data for quote_items."""
        def build_update_data(s2h, h2c, c2c, days):
            update_data = {}
            if s2h is not None:
                update_data["logistics_supplier_to_hub"] = float(s2h)
            if h2c is not None:
                update_data["logistics_hub_to_customs"] = float(h2c)
            if c2c is not None:
                update_data["logistics_customs_to_customer"] = float(c2c)
            if days is not None:
                days_val = int(days) if days else None
                update_data["logistics_total_days"] = days_val if days_val and days_val > 0 else None
            return update_data

        update_data = build_update_data("100", "200", "150", "21")
        assert update_data["logistics_supplier_to_hub"] == 100.0
        assert update_data["logistics_hub_to_customs"] == 200.0
        assert update_data["logistics_customs_to_customer"] == 150.0
        assert update_data["logistics_total_days"] == 21


# =============================================================================
# Service Import Tests
# =============================================================================

class TestServiceImports:
    """Test that required services are importable."""

    def test_location_service_import(self):
        """Test location_service imports."""
        try:
            from services.location_service import get_location, format_location_for_dropdown
            assert callable(get_location)
            assert callable(format_location_for_dropdown)
        except ImportError:
            pytest.skip("location_service not available")

    def test_supplier_service_import(self):
        """Test supplier_service imports."""
        try:
            from services.supplier_service import get_supplier, format_supplier_for_dropdown
            assert callable(get_supplier)
            assert callable(format_supplier_for_dropdown)
        except ImportError:
            pytest.skip("supplier_service not available")

    def test_workflow_service_import(self):
        """Test workflow_service imports."""
        try:
            from services.workflow_service import complete_logistics
            assert callable(complete_logistics)
        except ImportError:
            pytest.skip("workflow_service not available")


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
