"""
Tests for Plan-Fact Auto-Generation Service

Tests the generate_plan_fact_from_deal() function and related auto-generation
functionality from services/plan_fact_service.py.

Feature: DEAL-002 - Plan-fact auto-generation
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

# Import the service functions and classes
from services.plan_fact_service import (
    # Data classes
    PlanFactCategory,
    PlanFactItem,
    GeneratePlanFactResult,
    # Category functions
    get_all_categories,
    get_category,
    get_category_by_code,
    get_income_categories,
    get_expense_categories,
    # Create operations
    create_plan_fact_item,
    create_plan_fact_item_with_category_code,
    bulk_create_plan_fact_items,
    # Read operations
    get_plan_fact_item,
    get_plan_fact_items_for_deal,
    count_items_for_deal,
    get_unpaid_items_for_deal,
    get_paid_items_for_deal,
    get_overdue_items_for_deal,
    # Update operations
    update_plan_fact_item,
    record_actual_payment,
    clear_actual_payment,
    update_planned_payment,
    # Delete operations
    delete_plan_fact_item,
    delete_all_items_for_deal,
    # Summary functions
    get_deal_plan_fact_summary,
    get_items_grouped_by_category,
    get_upcoming_payments,
    get_payments_for_period,
    # Validation
    validate_item_for_payment,
    validate_deal_plan_fact,
    # Auto-generation (DEAL-002)
    generate_plan_fact_from_deal,
    regenerate_plan_fact_for_deal,
    get_plan_fact_generation_preview,
)


# ============================================================================
# Test Data Classes
# ============================================================================

class TestPlanFactCategory:
    """Tests for PlanFactCategory dataclass."""

    def test_from_dict_basic(self):
        """Test creating category from dict."""
        data = {
            'id': 'cat-123',
            'code': 'client_payment',
            'name': 'Client Payment',
            'is_income': True,
            'sort_order': 1,
            'created_at': '2025-01-15T10:00:00+00:00'
        }

        category = PlanFactCategory.from_dict(data)

        assert category.id == 'cat-123'
        assert category.code == 'client_payment'
        assert category.name == 'Client Payment'
        assert category.is_income is True
        assert category.sort_order == 1

    def test_from_dict_defaults(self):
        """Test category with default values."""
        data = {
            'id': 'cat-456',
            'code': 'supplier_payment',
            'name': 'Supplier Payment',
            'created_at': '2025-01-15T10:00:00+00:00'
        }

        category = PlanFactCategory.from_dict(data)

        assert category.is_income is False  # Default
        assert category.sort_order == 0  # Default


class TestPlanFactItem:
    """Tests for PlanFactItem dataclass."""

    def test_from_dict_basic(self):
        """Test creating item from dict."""
        data = {
            'id': 'item-123',
            'deal_id': 'deal-456',
            'category_id': 'cat-789',
            'description': 'Test payment',
            'planned_amount': '50000.00',
            'planned_currency': 'RUB',
            'planned_date': '2025-02-15',
            'actual_amount': None,
            'actual_currency': None,
            'actual_date': None,
            'actual_exchange_rate': None,
            'variance_amount': None,
            'payment_document': None,
            'notes': None,
            'created_by': 'user-111',
            'created_at': '2025-01-15T10:00:00+00:00',
            'updated_at': None
        }

        item = PlanFactItem.from_dict(data)

        assert item.id == 'item-123'
        assert item.deal_id == 'deal-456'
        assert item.category_id == 'cat-789'
        assert item.description == 'Test payment'
        assert item.planned_amount == Decimal('50000.00')
        assert item.planned_currency == 'RUB'
        assert item.planned_date == date(2025, 2, 15)
        assert item.actual_amount is None
        assert item.is_paid is False

    def test_from_dict_with_actual_payment(self):
        """Test item with recorded actual payment."""
        data = {
            'id': 'item-123',
            'deal_id': 'deal-456',
            'category_id': 'cat-789',
            'description': 'Paid item',
            'planned_amount': '50000.00',
            'planned_currency': 'RUB',
            'planned_date': '2025-02-15',
            'actual_amount': '49500.00',
            'actual_currency': 'RUB',
            'actual_date': '2025-02-14',
            'actual_exchange_rate': None,
            'variance_amount': '-500.00',
            'payment_document': 'PP-2025-001',
            'notes': 'Paid on time',
            'created_by': 'user-111',
            'created_at': '2025-01-15T10:00:00+00:00',
            'updated_at': '2025-02-14T12:00:00+00:00'
        }

        item = PlanFactItem.from_dict(data)

        assert item.actual_amount == Decimal('49500.00')
        assert item.actual_date == date(2025, 2, 14)
        assert item.variance_amount == Decimal('-500.00')
        assert item.is_paid is True

    def test_to_dict(self):
        """Test converting item to dict."""
        data = {
            'id': 'item-123',
            'deal_id': 'deal-456',
            'category_id': 'cat-789',
            'description': 'Test',
            'planned_amount': '50000.00',
            'planned_currency': 'RUB',
            'planned_date': '2025-02-15',
            'actual_amount': None,
            'actual_currency': None,
            'actual_date': None,
            'actual_exchange_rate': None,
            'variance_amount': None,
            'payment_document': None,
            'notes': None,
            'created_by': None,
            'created_at': '2025-01-15T10:00:00+00:00',
            'updated_at': None
        }

        item = PlanFactItem.from_dict(data)
        result = item.to_dict()

        assert result['id'] == 'item-123'
        assert result['deal_id'] == 'deal-456'
        assert result['planned_amount'] == 50000.0
        assert result['planned_date'] == '2025-02-15'


class TestGeneratePlanFactResult:
    """Tests for GeneratePlanFactResult dataclass."""

    def test_success_result(self):
        """Test successful generation result."""
        result = GeneratePlanFactResult(
            success=True,
            items_created=[],
            items_count=5,
            error=None,
            source_data={'deal': {'id': 'deal-123'}}
        )

        assert result.success is True
        assert result.items_count == 5
        assert result.error is None

    def test_failure_result(self):
        """Test failed generation result."""
        result = GeneratePlanFactResult(
            success=False,
            items_created=[],
            items_count=0,
            error="Deal not found",
            source_data={}
        )

        assert result.success is False
        assert result.error == "Deal not found"


# ============================================================================
# Test Category Functions
# ============================================================================

class TestCategoryFunctions:
    """Tests for category lookup functions."""

    def test_get_category_by_code_import(self):
        """Test that get_category_by_code is importable."""
        assert callable(get_category_by_code)

    def test_get_income_categories_import(self):
        """Test that get_income_categories is importable."""
        assert callable(get_income_categories)

    def test_get_expense_categories_import(self):
        """Test that get_expense_categories is importable."""
        assert callable(get_expense_categories)


# ============================================================================
# Test Auto-Generation Functions (DEAL-002)
# ============================================================================

class TestGeneratePlanFactFromDeal:
    """Tests for the main plan-fact auto-generation function."""

    def test_function_exists(self):
        """Verify generate_plan_fact_from_deal function exists and is callable."""
        assert callable(generate_plan_fact_from_deal)

    def test_function_signature(self):
        """Verify function has correct parameters."""
        import inspect
        sig = inspect.signature(generate_plan_fact_from_deal)
        params = list(sig.parameters.keys())

        assert 'deal_id' in params
        assert 'created_by' in params
        assert 'replace_existing' in params

    def test_return_type_is_dataclass(self):
        """Verify function returns GeneratePlanFactResult."""
        # Check the function's return type annotation
        import inspect
        sig = inspect.signature(generate_plan_fact_from_deal)

        # The return annotation should be GeneratePlanFactResult
        assert sig.return_annotation == GeneratePlanFactResult


class TestRegeneratePlanFactForDeal:
    """Tests for the regeneration wrapper function."""

    def test_function_exists(self):
        """Verify regenerate_plan_fact_for_deal function exists."""
        assert callable(regenerate_plan_fact_for_deal)

    def test_function_signature(self):
        """Verify function has correct parameters."""
        import inspect
        sig = inspect.signature(regenerate_plan_fact_for_deal)
        params = list(sig.parameters.keys())

        assert 'deal_id' in params
        assert 'created_by' in params


class TestGetPlanFactGenerationPreview:
    """Tests for the preview function."""

    def test_function_exists(self):
        """Verify get_plan_fact_generation_preview function exists."""
        assert callable(get_plan_fact_generation_preview)

    def test_function_signature(self):
        """Verify function has correct parameters."""
        import inspect
        sig = inspect.signature(get_plan_fact_generation_preview)
        params = list(sig.parameters.keys())

        assert 'deal_id' in params


# ============================================================================
# Test CRUD Operations
# ============================================================================

class TestCreateOperations:
    """Tests for create operations."""

    def test_create_plan_fact_item_import(self):
        """Test that create_plan_fact_item is importable."""
        assert callable(create_plan_fact_item)

    def test_create_plan_fact_item_with_category_code_import(self):
        """Test that create_plan_fact_item_with_category_code is importable."""
        assert callable(create_plan_fact_item_with_category_code)

    def test_bulk_create_plan_fact_items_import(self):
        """Test that bulk_create_plan_fact_items is importable."""
        assert callable(bulk_create_plan_fact_items)


class TestReadOperations:
    """Tests for read operations."""

    def test_get_plan_fact_item_import(self):
        """Test that get_plan_fact_item is importable."""
        assert callable(get_plan_fact_item)

    def test_get_plan_fact_items_for_deal_import(self):
        """Test that get_plan_fact_items_for_deal is importable."""
        assert callable(get_plan_fact_items_for_deal)

    def test_count_items_for_deal_import(self):
        """Test that count_items_for_deal is importable."""
        assert callable(count_items_for_deal)

    def test_get_unpaid_items_import(self):
        """Test that get_unpaid_items_for_deal is importable."""
        assert callable(get_unpaid_items_for_deal)

    def test_get_paid_items_import(self):
        """Test that get_paid_items_for_deal is importable."""
        assert callable(get_paid_items_for_deal)

    def test_get_overdue_items_import(self):
        """Test that get_overdue_items_for_deal is importable."""
        assert callable(get_overdue_items_for_deal)


class TestUpdateOperations:
    """Tests for update operations."""

    def test_update_plan_fact_item_import(self):
        """Test that update_plan_fact_item is importable."""
        assert callable(update_plan_fact_item)

    def test_record_actual_payment_import(self):
        """Test that record_actual_payment is importable."""
        assert callable(record_actual_payment)

    def test_clear_actual_payment_import(self):
        """Test that clear_actual_payment is importable."""
        assert callable(clear_actual_payment)

    def test_update_planned_payment_import(self):
        """Test that update_planned_payment is importable."""
        assert callable(update_planned_payment)


class TestDeleteOperations:
    """Tests for delete operations."""

    def test_delete_plan_fact_item_import(self):
        """Test that delete_plan_fact_item is importable."""
        assert callable(delete_plan_fact_item)

    def test_delete_all_items_for_deal_import(self):
        """Test that delete_all_items_for_deal is importable."""
        assert callable(delete_all_items_for_deal)


# ============================================================================
# Test Summary and Statistics Functions
# ============================================================================

class TestSummaryFunctions:
    """Tests for summary and statistics functions."""

    def test_get_deal_plan_fact_summary_import(self):
        """Test that get_deal_plan_fact_summary is importable."""
        assert callable(get_deal_plan_fact_summary)

    def test_get_items_grouped_by_category_import(self):
        """Test that get_items_grouped_by_category is importable."""
        assert callable(get_items_grouped_by_category)

    def test_get_upcoming_payments_import(self):
        """Test that get_upcoming_payments is importable."""
        assert callable(get_upcoming_payments)

    def test_get_payments_for_period_import(self):
        """Test that get_payments_for_period is importable."""
        assert callable(get_payments_for_period)


# ============================================================================
# Test Validation Functions
# ============================================================================

class TestValidationFunctions:
    """Tests for validation functions."""

    def test_validate_item_for_payment_import(self):
        """Test that validate_item_for_payment is importable."""
        assert callable(validate_item_for_payment)

    def test_validate_deal_plan_fact_import(self):
        """Test that validate_deal_plan_fact is importable."""
        assert callable(validate_deal_plan_fact)


# ============================================================================
# Test Service Integration from __init__.py
# ============================================================================

class TestServiceExports:
    """Test that all functions are properly exported from services package."""

    def test_import_from_services_package(self):
        """Test importing from services package."""
        from services import (
            generate_plan_fact_from_deal,
            regenerate_plan_fact_for_deal,
            get_plan_fact_generation_preview,
            GeneratePlanFactResult,
        )

        assert callable(generate_plan_fact_from_deal)
        assert callable(regenerate_plan_fact_for_deal)
        assert callable(get_plan_fact_generation_preview)

    def test_dataclass_export(self):
        """Test that GeneratePlanFactResult is exported."""
        from services import GeneratePlanFactResult

        # Should be able to create instances
        result = GeneratePlanFactResult(
            success=True,
            items_created=[],
            items_count=0,
            error=None,
            source_data={}
        )
        assert result.success is True


# ============================================================================
# Test Business Logic
# ============================================================================

class TestBusinessLogic:
    """Tests for business logic in plan-fact generation."""

    def test_is_paid_property(self):
        """Test the is_paid property on PlanFactItem."""
        # Unpaid item
        unpaid_data = {
            'id': 'item-1',
            'deal_id': 'deal-1',
            'category_id': 'cat-1',
            'planned_amount': '50000',
            'planned_currency': 'RUB',
            'planned_date': '2025-02-15',
            'actual_amount': None,
            'actual_date': None,
            'created_at': '2025-01-15T10:00:00+00:00',
        }
        unpaid_item = PlanFactItem.from_dict(unpaid_data)
        assert unpaid_item.is_paid is False

        # Paid item
        paid_data = {
            'id': 'item-2',
            'deal_id': 'deal-1',
            'category_id': 'cat-1',
            'planned_amount': '50000',
            'planned_currency': 'RUB',
            'planned_date': '2025-02-15',
            'actual_amount': '50000',
            'actual_date': '2025-02-14',
            'created_at': '2025-01-15T10:00:00+00:00',
        }
        paid_item = PlanFactItem.from_dict(paid_data)
        assert paid_item.is_paid is True

    def test_variance_calculation_concept(self):
        """Test that variance concept is understood."""
        # Variance = actual - planned
        # Positive variance = paid more than planned (unfavorable for expenses, favorable for income)
        # Negative variance = paid less than planned (favorable for expenses, unfavorable for income)

        data = {
            'id': 'item-1',
            'deal_id': 'deal-1',
            'category_id': 'cat-1',
            'planned_amount': '50000',
            'planned_currency': 'RUB',
            'planned_date': '2025-02-15',
            'actual_amount': '48000',
            'actual_date': '2025-02-14',
            'variance_amount': '-2000',  # Paid 2000 less than planned
            'created_at': '2025-01-15T10:00:00+00:00',
        }
        item = PlanFactItem.from_dict(data)

        assert item.planned_amount == Decimal('50000')
        assert item.actual_amount == Decimal('48000')
        assert item.variance_amount == Decimal('-2000')


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_values_handling(self):
        """Test handling of empty/None values."""
        data = {
            'id': 'item-1',
            'deal_id': 'deal-1',
            'category_id': 'cat-1',
            'description': None,
            'planned_amount': '0',
            'planned_currency': 'RUB',
            'planned_date': None,
            'actual_amount': None,
            'actual_currency': None,
            'actual_date': None,
            'actual_exchange_rate': None,
            'variance_amount': None,
            'payment_document': None,
            'notes': None,
            'created_by': None,
            'created_at': '2025-01-15T10:00:00+00:00',
            'updated_at': None
        }

        item = PlanFactItem.from_dict(data)

        assert item.description is None
        assert item.planned_amount == Decimal('0')
        assert item.planned_date is None
        assert item.actual_amount is None

    def test_decimal_conversion(self):
        """Test that decimal amounts are properly converted."""
        data = {
            'id': 'item-1',
            'deal_id': 'deal-1',
            'category_id': 'cat-1',
            'planned_amount': '123456.78',
            'planned_currency': 'RUB',
            'planned_date': '2025-02-15',
            'created_at': '2025-01-15T10:00:00+00:00',
        }

        item = PlanFactItem.from_dict(data)

        # Should be exact Decimal, not float
        assert item.planned_amount == Decimal('123456.78')
        assert isinstance(item.planned_amount, Decimal)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
