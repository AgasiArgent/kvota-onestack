"""
Tests for Plan-Fact Actual Payment Registration Service

Tests the register_payment_for_item() function and related payment registration
functionality from services/plan_fact_service.py.

Feature: DEAL-003 - Plan-fact actual payment registration
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

# Import the service functions and classes
from services.plan_fact_service import (
    # Data classes
    PlanFactItem,
    RegisterPaymentResult,
    # Constants
    SUPPORTED_PAYMENT_CURRENCIES,
    MIN_EXCHANGE_RATE,
    MAX_EXCHANGE_RATE,
    SIGNIFICANT_VARIANCE_THRESHOLD,
    MAX_OVERPAYMENT_RATIO,
    # Validation functions
    validate_payment_amount,
    validate_payment_date,
    validate_payment_currency,
    validate_payment_document,
    validate_payment_data,
    # Registration functions
    register_payment_for_item,
    register_partial_payment,
    bulk_register_payments,
    # Preview and summary
    get_payment_registration_preview,
    get_variance_summary,
)


# ============================================================================
# Test RegisterPaymentResult Dataclass
# ============================================================================

class TestRegisterPaymentResult:
    """Tests for RegisterPaymentResult dataclass."""

    def test_success_result(self):
        """Test successful payment result."""
        result = RegisterPaymentResult(
            success=True,
            item=None,
            error=None,
            warnings=['Payment is 2 day(s) late'],
            variance_amount=Decimal('-500'),
            variance_percent=Decimal('-1.0'),
            is_late=True,
            is_overpayment=False,
            is_underpayment=True
        )

        assert result.success is True
        assert result.error is None
        assert result.is_late is True
        assert result.is_underpayment is True
        assert result.variance_amount == Decimal('-500')

    def test_failure_result(self):
        """Test failed payment result."""
        result = RegisterPaymentResult(
            success=False,
            item=None,
            error='Payment amount is required',
            warnings=[],
            variance_amount=None,
            variance_percent=None,
            is_late=False,
            is_overpayment=False,
            is_underpayment=False
        )

        assert result.success is False
        assert result.error == 'Payment amount is required'

    def test_overpayment_detection(self):
        """Test overpayment flag."""
        result = RegisterPaymentResult(
            success=True,
            item=None,
            error=None,
            warnings=[],
            variance_amount=Decimal('5000'),
            variance_percent=Decimal('10.0'),
            is_late=False,
            is_overpayment=True,
            is_underpayment=False
        )

        assert result.is_overpayment is True
        assert result.is_underpayment is False
        assert result.variance_amount > 0


# ============================================================================
# Test Constants
# ============================================================================

class TestConstants:
    """Tests for payment registration constants."""

    def test_supported_currencies(self):
        """Test supported currencies list."""
        assert 'RUB' in SUPPORTED_PAYMENT_CURRENCIES
        assert 'USD' in SUPPORTED_PAYMENT_CURRENCIES
        assert 'EUR' in SUPPORTED_PAYMENT_CURRENCIES
        assert 'CNY' in SUPPORTED_PAYMENT_CURRENCIES
        assert 'TRY' in SUPPORTED_PAYMENT_CURRENCIES
        assert 'AED' in SUPPORTED_PAYMENT_CURRENCIES

    def test_exchange_rate_bounds(self):
        """Test exchange rate limits."""
        assert MIN_EXCHANGE_RATE > 0
        assert MAX_EXCHANGE_RATE > MIN_EXCHANGE_RATE
        assert MAX_EXCHANGE_RATE == Decimal('10000.0')

    def test_variance_threshold(self):
        """Test variance threshold is reasonable."""
        assert SIGNIFICANT_VARIANCE_THRESHOLD == Decimal('0.01')  # 1%

    def test_overpayment_ratio(self):
        """Test max overpayment ratio."""
        assert MAX_OVERPAYMENT_RATIO == Decimal('1.5')  # 50% over


# ============================================================================
# Test validate_payment_amount
# ============================================================================

class TestValidatePaymentAmount:
    """Tests for validate_payment_amount function."""

    def test_valid_amount(self):
        """Test valid payment amount."""
        result = validate_payment_amount(50000)
        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_zero_amount(self):
        """Test zero amount is invalid."""
        result = validate_payment_amount(0)
        assert result['valid'] is False
        assert 'Payment amount must be greater than 0' in result['errors']

    def test_negative_amount(self):
        """Test negative amount is invalid."""
        result = validate_payment_amount(-1000)
        assert result['valid'] is False
        assert 'Payment amount must be greater than 0' in result['errors']

    def test_none_amount(self):
        """Test None amount is invalid."""
        result = validate_payment_amount(None)
        assert result['valid'] is False
        assert 'Payment amount is required' in result['errors']

    def test_overpayment_warning(self):
        """Test overpayment generates warning."""
        # 80000 is more than 50% over 50000
        result = validate_payment_amount(80000, Decimal('50000'))
        assert result['valid'] is True  # Still valid
        assert len(result['warnings']) > 0
        assert any('exceeds planned amount' in w for w in result['warnings'])

    def test_underpayment_warning(self):
        """Test significant underpayment generates warning."""
        # 40000 is 20% less than 50000 (more than 1% threshold)
        result = validate_payment_amount(40000, Decimal('50000'))
        assert result['valid'] is True  # Still valid
        assert len(result['warnings']) > 0
        assert any('less than planned' in w for w in result['warnings'])

    def test_exact_payment_no_warnings(self):
        """Test exact payment has no variance warnings."""
        result = validate_payment_amount(50000, Decimal('50000'))
        assert result['valid'] is True
        # No underpayment or overpayment warnings
        assert not any('exceeds' in w or 'less than' in w for w in result['warnings'])


# ============================================================================
# Test validate_payment_date
# ============================================================================

class TestValidatePaymentDate:
    """Tests for validate_payment_date function."""

    def test_valid_date(self):
        """Test valid payment date."""
        result = validate_payment_date(date.today())
        assert result['valid'] is True
        assert result['is_late'] is False

    def test_none_date(self):
        """Test None date is invalid."""
        result = validate_payment_date(None)
        assert result['valid'] is False
        assert 'Payment date is required' in result['errors']

    def test_future_date_warning(self):
        """Test future date generates warning."""
        future = date.today() + timedelta(days=30)
        result = validate_payment_date(future)
        assert result['valid'] is True
        assert any('in the future' in w for w in result['warnings'])

    def test_late_payment_detection(self):
        """Test late payment is detected."""
        planned = date(2025, 1, 15)
        actual = date(2025, 1, 20)  # 5 days late
        result = validate_payment_date(actual, planned)
        assert result['valid'] is True
        assert result['is_late'] is True
        assert any('5 day(s) late' in w for w in result['warnings'])

    def test_early_payment_not_late(self):
        """Test early payment is not marked late."""
        planned = date(2025, 1, 20)
        actual = date(2025, 1, 15)  # 5 days early
        result = validate_payment_date(actual, planned)
        assert result['is_late'] is False

    def test_on_time_payment(self):
        """Test on-time payment."""
        planned = date(2025, 1, 15)
        actual = date(2025, 1, 15)
        result = validate_payment_date(actual, planned)
        assert result['is_late'] is False


# ============================================================================
# Test validate_payment_currency
# ============================================================================

class TestValidatePaymentCurrency:
    """Tests for validate_payment_currency function."""

    def test_valid_rub(self):
        """Test valid RUB currency."""
        result = validate_payment_currency('RUB')
        assert result['valid'] is True
        assert result['needs_exchange_rate'] is False

    def test_valid_usd(self):
        """Test valid USD currency."""
        result = validate_payment_currency('USD')
        assert result['valid'] is True
        assert result['needs_exchange_rate'] is True

    def test_valid_usd_with_rate(self):
        """Test USD with valid exchange rate."""
        result = validate_payment_currency('USD', exchange_rate=92.5)
        assert result['valid'] is True
        assert result['needs_exchange_rate'] is True
        # No error about missing rate

    def test_invalid_currency(self):
        """Test unsupported currency."""
        result = validate_payment_currency('GBP')
        assert result['valid'] is False
        assert any('Unsupported currency' in e for e in result['errors'])

    def test_empty_currency(self):
        """Test empty currency is invalid."""
        result = validate_payment_currency('')
        assert result['valid'] is False
        assert 'Currency is required' in result['errors']

    def test_currency_mismatch_warning(self):
        """Test currency mismatch generates warning."""
        result = validate_payment_currency('USD', planned_currency='EUR')
        assert result['valid'] is True
        assert any('differs from planned' in w for w in result['warnings'])

    def test_exchange_rate_out_of_range(self):
        """Test exchange rate out of valid range."""
        result = validate_payment_currency('USD', exchange_rate=20000)  # Too high
        assert result['valid'] is False
        assert any('out of valid range' in e for e in result['errors'])

    def test_exchange_rate_too_low(self):
        """Test exchange rate too low."""
        result = validate_payment_currency('USD', exchange_rate=0.0001)  # Too low
        assert result['valid'] is False

    def test_currency_case_insensitive(self):
        """Test currency is case-insensitive."""
        result = validate_payment_currency('usd')
        assert result['valid'] is True


# ============================================================================
# Test validate_payment_document
# ============================================================================

class TestValidatePaymentDocument:
    """Tests for validate_payment_document function."""

    def test_valid_document(self):
        """Test valid document reference."""
        result = validate_payment_document('PP-2025-001')
        assert result['valid'] is True

    def test_none_document_warning(self):
        """Test None document generates warning but is valid."""
        result = validate_payment_document(None)
        assert result['valid'] is True
        assert any('No payment document' in w for w in result['warnings'])

    def test_empty_document_warning(self):
        """Test empty document generates warning."""
        result = validate_payment_document('')
        assert result['valid'] is True
        # Empty string is falsy, so same as None

    def test_too_long_document(self):
        """Test document reference too long."""
        long_doc = 'A' * 101
        result = validate_payment_document(long_doc)
        assert result['valid'] is False
        assert any('too long' in e for e in result['errors'])

    def test_invalid_characters(self):
        """Test document with invalid characters."""
        result = validate_payment_document('<script>alert(1)</script>')
        assert result['valid'] is False
        assert any('invalid characters' in e for e in result['errors'])


# ============================================================================
# Test validate_payment_data (Comprehensive)
# ============================================================================

class TestValidatePaymentData:
    """Tests for comprehensive payment data validation."""

    def test_function_exists(self):
        """Verify validate_payment_data exists and is callable."""
        assert callable(validate_payment_data)

    def test_function_signature(self):
        """Verify function has correct parameters."""
        import inspect
        sig = inspect.signature(validate_payment_data)
        params = list(sig.parameters.keys())

        assert 'item_id' in params
        assert 'actual_amount' in params
        assert 'actual_date' in params
        assert 'actual_currency' in params
        assert 'actual_exchange_rate' in params
        assert 'payment_document' in params


# ============================================================================
# Test register_payment_for_item
# ============================================================================

class TestRegisterPaymentForItem:
    """Tests for the main payment registration function."""

    def test_function_exists(self):
        """Verify register_payment_for_item exists and is callable."""
        assert callable(register_payment_for_item)

    def test_function_signature(self):
        """Verify function has correct parameters."""
        import inspect
        sig = inspect.signature(register_payment_for_item)
        params = list(sig.parameters.keys())

        assert 'item_id' in params
        assert 'actual_amount' in params
        assert 'actual_date' in params
        assert 'actual_currency' in params
        assert 'actual_exchange_rate' in params
        assert 'payment_document' in params
        assert 'notes' in params
        assert 'skip_validation' in params

    def test_return_type_is_dataclass(self):
        """Verify function returns RegisterPaymentResult."""
        import inspect
        sig = inspect.signature(register_payment_for_item)

        # The return annotation should be RegisterPaymentResult
        assert sig.return_annotation == RegisterPaymentResult


# ============================================================================
# Test register_partial_payment
# ============================================================================

class TestRegisterPartialPayment:
    """Tests for partial payment registration."""

    def test_function_exists(self):
        """Verify register_partial_payment exists and is callable."""
        assert callable(register_partial_payment)

    def test_function_signature(self):
        """Verify function has correct parameters."""
        import inspect
        sig = inspect.signature(register_partial_payment)
        params = list(sig.parameters.keys())

        assert 'item_id' in params
        assert 'partial_amount' in params
        assert 'payment_date' in params
        assert 'currency' in params
        assert 'exchange_rate' in params
        assert 'payment_document' in params
        assert 'notes' in params


# ============================================================================
# Test bulk_register_payments
# ============================================================================

class TestBulkRegisterPayments:
    """Tests for bulk payment registration."""

    def test_function_exists(self):
        """Verify bulk_register_payments exists and is callable."""
        assert callable(bulk_register_payments)

    def test_empty_list(self):
        """Test bulk registration with empty list."""
        result = bulk_register_payments([])
        assert result['success_count'] == 0
        assert result['failure_count'] == 0
        assert result['total_amount'] == 0.0
        assert len(result['results']) == 0

    def test_missing_required_fields(self):
        """Test bulk registration with missing fields."""
        payments = [
            {'item_id': 'item-1'},  # Missing amount and date
            {'actual_amount': 1000},  # Missing item_id and date
        ]
        result = bulk_register_payments(payments)
        assert result['failure_count'] == 2
        assert result['success_count'] == 0


# ============================================================================
# Test get_payment_registration_preview
# ============================================================================

class TestGetPaymentRegistrationPreview:
    """Tests for payment registration preview."""

    def test_function_exists(self):
        """Verify get_payment_registration_preview exists and is callable."""
        assert callable(get_payment_registration_preview)

    def test_function_signature(self):
        """Verify function has correct parameters."""
        import inspect
        sig = inspect.signature(get_payment_registration_preview)
        params = list(sig.parameters.keys())

        assert 'item_id' in params


# ============================================================================
# Test get_variance_summary
# ============================================================================

class TestGetVarianceSummary:
    """Tests for variance summary function."""

    def test_function_exists(self):
        """Verify get_variance_summary exists and is callable."""
        assert callable(get_variance_summary)

    def test_function_signature(self):
        """Verify function has correct parameters."""
        import inspect
        sig = inspect.signature(get_variance_summary)
        params = list(sig.parameters.keys())

        assert 'item_id' in params


# ============================================================================
# Test Service Exports from __init__.py
# ============================================================================

class TestServiceExports:
    """Test that all functions are properly exported from services package."""

    def test_import_result_dataclass(self):
        """Test importing RegisterPaymentResult from services package."""
        from services import RegisterPaymentResult

        result = RegisterPaymentResult(
            success=True,
            item=None,
            error=None,
            warnings=[],
            variance_amount=Decimal('0'),
            variance_percent=Decimal('0'),
            is_late=False,
            is_overpayment=False,
            is_underpayment=False
        )
        assert result.success is True

    def test_import_constants(self):
        """Test importing constants from services package."""
        from services import SUPPORTED_PAYMENT_CURRENCIES
        assert 'RUB' in SUPPORTED_PAYMENT_CURRENCIES

    def test_import_validation_functions(self):
        """Test importing validation functions."""
        from services import (
            validate_payment_amount,
            validate_payment_date,
            validate_payment_currency,
            validate_payment_document,
            validate_payment_data,
        )
        assert callable(validate_payment_amount)
        assert callable(validate_payment_date)
        assert callable(validate_payment_currency)
        assert callable(validate_payment_document)
        assert callable(validate_payment_data)

    def test_import_registration_functions(self):
        """Test importing registration functions."""
        from services import (
            register_payment_for_item,
            register_partial_payment,
            bulk_register_payments,
        )
        assert callable(register_payment_for_item)
        assert callable(register_partial_payment)
        assert callable(bulk_register_payments)

    def test_import_preview_and_summary(self):
        """Test importing preview and summary functions."""
        from services import (
            get_payment_registration_preview,
            get_variance_summary,
        )
        assert callable(get_payment_registration_preview)
        assert callable(get_variance_summary)


# ============================================================================
# Test Business Logic
# ============================================================================

class TestBusinessLogic:
    """Tests for business logic in payment registration."""

    def test_variance_calculation_concept(self):
        """Test variance calculation: actual - planned."""
        # Variance = actual - planned
        # Positive variance = paid more (overpayment)
        # Negative variance = paid less (underpayment)

        planned = Decimal('50000')
        actual_under = Decimal('45000')
        actual_over = Decimal('55000')

        variance_under = actual_under - planned  # -5000
        variance_over = actual_over - planned  # +5000

        assert variance_under < 0  # Underpayment
        assert variance_over > 0  # Overpayment

    def test_variance_percent_calculation(self):
        """Test variance percentage calculation."""
        planned = Decimal('50000')
        actual = Decimal('48000')

        variance = actual - planned  # -2000
        variance_percent = (variance / planned) * 100  # -4%

        assert variance_percent == Decimal('-4.0')

    def test_late_payment_detection_logic(self):
        """Test late payment detection."""
        planned_date = date(2025, 1, 15)
        actual_date = date(2025, 1, 20)

        is_late = actual_date > planned_date
        days_late = (actual_date - planned_date).days

        assert is_late is True
        assert days_late == 5

    def test_overpayment_threshold(self):
        """Test overpayment threshold (50% over)."""
        planned = Decimal('50000')
        significant_over = planned * MAX_OVERPAYMENT_RATIO  # 75000

        # 80000 is over the threshold
        assert Decimal('80000') > significant_over

        # 60000 is under the threshold
        assert Decimal('60000') < significant_over


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_small_amount(self):
        """Test very small payment amount."""
        result = validate_payment_amount(0.01)
        assert result['valid'] is True

    def test_very_large_amount(self):
        """Test very large payment amount."""
        result = validate_payment_amount(1000000000)  # 1 billion
        assert result['valid'] is True

    def test_planned_zero_amount(self):
        """Test when planned amount is zero."""
        result = validate_payment_amount(1000, Decimal('0'))
        # Should still be valid - just no variance warnings
        assert result['valid'] is True

    def test_float_precision(self):
        """Test float precision handling."""
        result = validate_payment_amount(1234.56, Decimal('1234.56'))
        assert result['valid'] is True

    def test_unicode_in_document(self):
        """Test Unicode characters in document reference."""
        result = validate_payment_document('ПП-2025-001-Оплата')
        assert result['valid'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
