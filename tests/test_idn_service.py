"""
Tests for IDN Service

Feature #IDN-001: Quote IDN generation
Feature #IDN-002: Item IDN generation

Tests cover:
- Parsing quote and item IDNs
- Validation functions
- Utility functions
"""

import pytest
from services.idn_service import (
    # Data classes
    ParsedQuoteIDN,
    ParsedItemIDN,
    # Parsing functions
    parse_quote_idn,
    parse_item_idn,
    # Validation functions
    is_valid_quote_idn,
    is_valid_item_idn,
    validate_seller_code,
    validate_inn,
    # Utility functions
    extract_quote_idn_from_item_idn,
    format_item_position,
    get_year_from_idn,
    get_customer_inn_from_idn,
    get_seller_code_from_idn,
)


# =============================================================================
# TESTS: Quote IDN Parsing
# =============================================================================

class TestParseQuoteIDN:
    """Tests for parse_quote_idn function"""

    def test_parse_valid_quote_idn(self):
        """Test parsing a valid quote IDN"""
        result = parse_quote_idn("CMT-1234567890-2025-1")

        assert result is not None
        assert result.seller_code == "CMT"
        assert result.customer_inn == "1234567890"
        assert result.year == 2025
        assert result.sequence == 1

    def test_parse_quote_idn_with_12_digit_inn(self):
        """Test parsing with 12-digit INN (individual entrepreneur)"""
        result = parse_quote_idn("RAR-123456789012-2024-42")

        assert result is not None
        assert result.seller_code == "RAR"
        assert result.customer_inn == "123456789012"
        assert result.year == 2024
        assert result.sequence == 42

    def test_parse_quote_idn_various_seller_codes(self):
        """Test various seller code lengths (2-5 chars)"""
        # 2-char code
        result = parse_quote_idn("AB-1234567890-2025-1")
        assert result is not None
        assert result.seller_code == "AB"

        # 3-char code
        result = parse_quote_idn("MBR-1234567890-2025-1")
        assert result is not None
        assert result.seller_code == "MBR"

        # 5-char code
        result = parse_quote_idn("TEXIM-1234567890-2025-1")
        assert result is not None
        assert result.seller_code == "TEXIM"

    def test_parse_quote_idn_high_sequence(self):
        """Test parsing with high sequence number"""
        result = parse_quote_idn("CMT-1234567890-2025-9999")

        assert result is not None
        assert result.sequence == 9999

    def test_parse_invalid_quote_idn_none(self):
        """Test parsing None input"""
        assert parse_quote_idn(None) is None

    def test_parse_invalid_quote_idn_empty(self):
        """Test parsing empty string"""
        assert parse_quote_idn("") is None

    def test_parse_invalid_quote_idn_wrong_format(self):
        """Test parsing wrong format strings"""
        # Missing parts
        assert parse_quote_idn("CMT-1234567890-2025") is None
        assert parse_quote_idn("CMT-1234567890") is None

        # Wrong separator
        assert parse_quote_idn("CMT_1234567890_2025_1") is None

        # Lowercase seller code
        assert parse_quote_idn("cmt-1234567890-2025-1") is None

        # Non-numeric INN
        assert parse_quote_idn("CMT-ABCDEFGHIJ-2025-1") is None

        # Invalid INN length
        assert parse_quote_idn("CMT-123456789-2025-1") is None  # 9 digits
        assert parse_quote_idn("CMT-1234567890123-2025-1") is None  # 13 digits

    def test_parsed_quote_idn_full_idn_property(self):
        """Test that full_idn property reconstructs correctly"""
        result = parse_quote_idn("CMT-1234567890-2025-42")

        assert result is not None
        assert result.full_idn == "CMT-1234567890-2025-42"


# =============================================================================
# TESTS: Item IDN Parsing
# =============================================================================

class TestParseItemIDN:
    """Tests for parse_item_idn function"""

    def test_parse_valid_item_idn(self):
        """Test parsing a valid item IDN"""
        result = parse_item_idn("CMT-1234567890-2025-1-001")

        assert result is not None
        assert result.quote_idn.seller_code == "CMT"
        assert result.quote_idn.customer_inn == "1234567890"
        assert result.quote_idn.year == 2025
        assert result.quote_idn.sequence == 1
        assert result.position == 1

    def test_parse_item_idn_various_positions(self):
        """Test parsing with various positions"""
        # Position 1
        result = parse_item_idn("CMT-1234567890-2025-1-001")
        assert result.position == 1

        # Position 42
        result = parse_item_idn("CMT-1234567890-2025-1-042")
        assert result.position == 42

        # Position 999
        result = parse_item_idn("CMT-1234567890-2025-1-999")
        assert result.position == 999

    def test_parse_invalid_item_idn_none(self):
        """Test parsing None input"""
        assert parse_item_idn(None) is None

    def test_parse_invalid_item_idn_empty(self):
        """Test parsing empty string"""
        assert parse_item_idn("") is None

    def test_parse_invalid_item_idn_wrong_position_format(self):
        """Test parsing with wrong position format"""
        # Non-padded position
        assert parse_item_idn("CMT-1234567890-2025-1-1") is None

        # 2-digit position
        assert parse_item_idn("CMT-1234567890-2025-1-01") is None

        # 4-digit position
        assert parse_item_idn("CMT-1234567890-2025-1-0001") is None

    def test_parsed_item_idn_full_idn_property(self):
        """Test that full_idn property reconstructs correctly"""
        result = parse_item_idn("CMT-1234567890-2025-1-007")

        assert result is not None
        assert result.full_idn == "CMT-1234567890-2025-1-007"


# =============================================================================
# TESTS: Validation Functions
# =============================================================================

class TestValidation:
    """Tests for validation functions"""

    def test_is_valid_quote_idn(self):
        """Test quote IDN validation"""
        assert is_valid_quote_idn("CMT-1234567890-2025-1") is True
        assert is_valid_quote_idn("MBR-123456789012-2024-999") is True
        assert is_valid_quote_idn("invalid") is False
        assert is_valid_quote_idn("") is False
        assert is_valid_quote_idn(None) is False

    def test_is_valid_item_idn(self):
        """Test item IDN validation"""
        assert is_valid_item_idn("CMT-1234567890-2025-1-001") is True
        assert is_valid_item_idn("MBR-123456789012-2024-999-042") is True
        assert is_valid_item_idn("invalid") is False
        assert is_valid_item_idn("CMT-1234567890-2025-1") is False  # Quote IDN, not item
        assert is_valid_item_idn("") is False
        assert is_valid_item_idn(None) is False

    def test_validate_seller_code(self):
        """Test seller code validation"""
        # Valid codes
        assert validate_seller_code("AB") is True
        assert validate_seller_code("CMT") is True
        assert validate_seller_code("ABCDE") is True

        # Invalid codes
        assert validate_seller_code("A") is False  # Too short
        assert validate_seller_code("ABCDEF") is False  # Too long
        assert validate_seller_code("cmt") is False  # Lowercase
        assert validate_seller_code("CM1") is False  # Contains number
        assert validate_seller_code("") is False
        assert validate_seller_code(None) is False

    def test_validate_inn(self):
        """Test INN validation"""
        # Valid INNs
        assert validate_inn("1234567890") is True  # 10 digits (legal entity)
        assert validate_inn("123456789012") is True  # 12 digits (individual)

        # Invalid INNs
        assert validate_inn("123456789") is False  # 9 digits
        assert validate_inn("12345678901") is False  # 11 digits
        assert validate_inn("1234567890123") is False  # 13 digits
        assert validate_inn("ABCDEFGHIJ") is False  # Non-numeric
        assert validate_inn("") is False
        assert validate_inn(None) is False


# =============================================================================
# TESTS: Utility Functions
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions"""

    def test_extract_quote_idn_from_item_idn(self):
        """Test extracting quote IDN from item IDN"""
        assert extract_quote_idn_from_item_idn("CMT-1234567890-2025-1-001") == "CMT-1234567890-2025-1"
        assert extract_quote_idn_from_item_idn("RAR-123456789012-2024-42-999") == "RAR-123456789012-2024-42"
        assert extract_quote_idn_from_item_idn("invalid") is None
        assert extract_quote_idn_from_item_idn("") is None
        assert extract_quote_idn_from_item_idn(None) is None

    def test_format_item_position(self):
        """Test position formatting"""
        assert format_item_position(1) == "001"
        assert format_item_position(42) == "042"
        assert format_item_position(999) == "999"
        assert format_item_position(0) == "000"

    def test_get_year_from_idn(self):
        """Test extracting year from IDN"""
        # From quote IDN
        assert get_year_from_idn("CMT-1234567890-2025-1") == 2025
        assert get_year_from_idn("MBR-1234567890-2024-42") == 2024

        # From item IDN
        assert get_year_from_idn("CMT-1234567890-2025-1-001") == 2025

        # Invalid
        assert get_year_from_idn("invalid") is None

    def test_get_customer_inn_from_idn(self):
        """Test extracting customer INN from IDN"""
        # From quote IDN
        assert get_customer_inn_from_idn("CMT-1234567890-2025-1") == "1234567890"
        assert get_customer_inn_from_idn("MBR-123456789012-2024-42") == "123456789012"

        # From item IDN
        assert get_customer_inn_from_idn("CMT-1234567890-2025-1-001") == "1234567890"

        # Invalid
        assert get_customer_inn_from_idn("invalid") is None

    def test_get_seller_code_from_idn(self):
        """Test extracting seller code from IDN"""
        # From quote IDN
        assert get_seller_code_from_idn("CMT-1234567890-2025-1") == "CMT"
        assert get_seller_code_from_idn("MBR-1234567890-2024-42") == "MBR"

        # From item IDN
        assert get_seller_code_from_idn("CMT-1234567890-2025-1-001") == "CMT"

        # Invalid
        assert get_seller_code_from_idn("invalid") is None


# =============================================================================
# TESTS: Data Class Properties
# =============================================================================

class TestDataClasses:
    """Tests for data class properties and methods"""

    def test_parsed_quote_idn_dataclass(self):
        """Test ParsedQuoteIDN dataclass"""
        idn = ParsedQuoteIDN(
            seller_code="CMT",
            customer_inn="1234567890",
            year=2025,
            sequence=1
        )

        assert idn.seller_code == "CMT"
        assert idn.customer_inn == "1234567890"
        assert idn.year == 2025
        assert idn.sequence == 1
        assert idn.full_idn == "CMT-1234567890-2025-1"

    def test_parsed_item_idn_dataclass(self):
        """Test ParsedItemIDN dataclass"""
        quote_idn = ParsedQuoteIDN(
            seller_code="CMT",
            customer_inn="1234567890",
            year=2025,
            sequence=1
        )

        item_idn = ParsedItemIDN(
            quote_idn=quote_idn,
            position=42
        )

        assert item_idn.quote_idn == quote_idn
        assert item_idn.position == 42
        # Item IDN format: QUOTE_IDN-POSITION (3-digit padded)
        assert item_idn.full_idn == "CMT-1234567890-2025-1-042"

    def test_parsed_item_idn_position_padding(self):
        """Test that item IDN position is correctly padded"""
        quote_idn = ParsedQuoteIDN(
            seller_code="CMT",
            customer_inn="1234567890",
            year=2025,
            sequence=1
        )

        # Single digit position should be padded to 3 digits
        item_idn = ParsedItemIDN(quote_idn=quote_idn, position=1)
        assert item_idn.full_idn == "CMT-1234567890-2025-1-001"

        # Position 7 should be padded to 007
        item_idn_with_position_7 = ParsedItemIDN(quote_idn=quote_idn, position=7)
        assert item_idn_with_position_7.full_idn == "CMT-1234567890-2025-1-007"

        # Position 42 should be padded to 042
        item_idn_with_position_42 = ParsedItemIDN(quote_idn=quote_idn, position=42)
        assert item_idn_with_position_42.full_idn == "CMT-1234567890-2025-1-042"

        # Position 999 should not be padded (already 3 digits)
        item_idn_with_position_999 = ParsedItemIDN(quote_idn=quote_idn, position=999)
        assert item_idn_with_position_999.full_idn == "CMT-1234567890-2025-1-999"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
