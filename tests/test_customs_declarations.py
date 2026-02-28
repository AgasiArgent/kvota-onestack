"""
TDD Tests for Customs Declaration (GTD) XML Import — Parser Unit Tests.

Feature: [86aftzmne] Загрузка таможенных деклараций (ДТ) из XML + учёт пошлин в план-факте

Tests cover:
- parse_gtd_xml() function from services/customs_declaration_service.py
- Header fields: regnum, date, currency, exchange_rate, sender, receiver, internal_ref
- Item parsing: single TOVG and multiple TOVGs
- Payment distribution: proportional by INVOICCOST across TOVGs within a BLOCK
- Total payments: fee (1010), duty (2010), VAT (5010) from B_1/B_2/B_3
- Encoding: windows-1251 handling
- Error handling: invalid XML, non-AltaGTD XML, empty blocks, zero INVOICCOST

Fixtures:
- tests/fixtures/gtd_sample_3313.xml — 1 BLOCK, 1 TOVG (2 units MANITOU), EUR, 3 payments
- tests/fixtures/gtd_sample_3328.xml — 1 BLOCK, 2 TOVGs (POM TANGSHAN K90-A and K270-1), USD, 3 payments

TDD: These tests are written BEFORE implementation.
The customs_declaration_service.py module does not exist yet — tests should fail with ImportError.
"""

import pytest
from decimal import Decimal
import os
import sys
import tempfile

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fixture paths (CI-portable, no absolute paths)
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_3313 = os.path.join(FIXTURES_DIR, "gtd_sample_3313.xml")
SAMPLE_3328 = os.path.join(FIXTURES_DIR, "gtd_sample_3328.xml")


# =============================================================================
# IMPORT TESTS — verify module and public API exist
# =============================================================================

class TestImports:
    """Verify that the module and its public API are importable."""

    def test_module_importable(self):
        """customs_declaration_service module should be importable."""
        from services.customs_declaration_service import parse_gtd_xml

    def test_gtd_parse_result_importable(self):
        """GTDParseResult dataclass should be importable."""
        from services.customs_declaration_service import GTDParseResult

    def test_gtd_item_importable(self):
        """GTDItem dataclass should be importable."""
        from services.customs_declaration_service import GTDItem


# =============================================================================
# HEADER PARSING — sample 3313 (EUR, Turkey sender)
# =============================================================================

class TestParseHeader3313:
    """Parse header fields from sample 3313 (EUR, 1 BLOCK, 1 TOVG)."""

    @pytest.fixture
    def result(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3313)

    def test_parse_returns_result_object(self, result):
        """parse_gtd_xml should return a GTDParseResult, not None."""
        from services.customs_declaration_service import GTDParseResult
        assert result is not None
        assert isinstance(result, GTDParseResult)

    def test_no_errors(self, result):
        """Parsing a valid file should produce no errors."""
        assert result.errors == [] or result.errors is None or len(result.errors) == 0

    def test_regnum(self, result):
        """REGNUM should be '10009100/261125/5177437'."""
        assert result.regnum == "10009100/261125/5177437"

    def test_declaration_date(self, result):
        """REG_DATE should be '2025-11-27' (as string or date object)."""
        date_val = str(result.declaration_date)
        assert "2025-11-27" in date_val

    def test_currency(self, result):
        """G_22_3 currency should be 'EUR'."""
        assert result.currency == "EUR"

    def test_exchange_rate(self, result):
        """G_23_1 exchange rate should be 90.9698."""
        assert Decimal(str(result.exchange_rate)) == Decimal("90.9698")

    def test_sender_name(self, result):
        """Sender name from G_2_NAM should be present."""
        assert "HORIZON GLOBAL MAKINA" in result.sender_name

    def test_sender_country(self, result):
        """G_2_7 sender country should be 'TR'."""
        assert result.sender_country == "TR"

    def test_receiver_name(self, result):
        """G_8_NAM receiver name should contain the company name."""
        # The XML has windows-1251 encoded Cyrillic: ООО "МАСТЕР БЭРИНГ"
        assert result.receiver_name is not None
        assert len(result.receiver_name) > 0

    def test_receiver_inn(self, result):
        """G_8_6 receiver INN should be '0242013464/772101001'."""
        assert result.receiver_inn == "0242013464/772101001"

    def test_internal_ref(self, result):
        """Comment attribute on AltaGTD root should give internal_ref='3313'."""
        assert result.internal_ref == "3313"

    def test_total_customs_value_rub(self, result):
        """G_12_0 total customs value should be 14204319.31."""
        assert Decimal(str(result.total_customs_value_rub)) == Decimal("14204319.31")


# =============================================================================
# HEADER PARSING — sample 3328 (USD, China sender)
# =============================================================================

class TestParseHeader3328:
    """Parse header fields from sample 3328 (USD, 1 BLOCK, 2 TOVGs)."""

    @pytest.fixture
    def result(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3328)

    def test_regnum(self, result):
        """REGNUM should be '10702070/261125/5415785'."""
        assert result.regnum == "10702070/261125/5415785"

    def test_declaration_date(self, result):
        """REG_DATE should be '2025-11-28'."""
        date_val = str(result.declaration_date)
        assert "2025-11-28" in date_val

    def test_currency(self, result):
        """G_22_3 currency should be 'USD'."""
        assert result.currency == "USD"

    def test_exchange_rate(self, result):
        """G_23_1 exchange rate should be 78.9615."""
        assert Decimal(str(result.exchange_rate)) == Decimal("78.9615")

    def test_sender_country(self, result):
        """G_2_7 sender country should be 'CN'."""
        assert result.sender_country == "CN"

    def test_sender_name(self, result):
        """G_2_NAM sender should be NINGBO CHEMBULL."""
        assert "NINGBO CHEMBULL" in result.sender_name

    def test_internal_ref(self, result):
        """Comment attribute should give internal_ref='3328'."""
        assert result.internal_ref == "3328"

    def test_total_customs_value_rub(self, result):
        """G_12_0 total customs value should be 1894317.97."""
        assert Decimal(str(result.total_customs_value_rub)) == Decimal("1894317.97")


# =============================================================================
# ITEM PARSING — single TOVG (sample 3313)
# =============================================================================

class TestParseSingleTovg:
    """Sample 3313 has 1 BLOCK with 1 TOVG (MANITOU, qty=2)."""

    @pytest.fixture
    def result(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3313)

    def test_items_count(self, result):
        """Should parse exactly 1 item (1 TOVG)."""
        assert len(result.items) == 1

    def test_item_sku(self, result):
        """G31_15 SKU should be 'MLT-X 735 T LSU'."""
        assert result.items[0].sku == "MLT-X 735 T LSU"

    def test_item_description(self, result):
        """G31_1 description should contain product info."""
        desc = result.items[0].description
        assert desc is not None
        assert len(desc) > 10

    def test_item_manufacturer(self, result):
        """G31_11 manufacturer should be 'MANITOU BF SA'."""
        assert result.items[0].manufacturer == "MANITOU BF SA"

    def test_item_brand(self, result):
        """G31_14 brand should be 'MANITOU'."""
        assert result.items[0].brand == "MANITOU"

    def test_item_quantity(self, result):
        """KOLVO should be 2."""
        assert result.items[0].quantity == 2

    def test_item_unit(self, result):
        """NAME_EDI should be present."""
        assert result.items[0].unit is not None

    def test_item_gross_weight(self, result):
        """G31_35 gross weight should be 15674."""
        assert Decimal(str(result.items[0].gross_weight)) == Decimal("15674")

    def test_item_net_weight(self, result):
        """G31_38 net weight should be 15674."""
        assert Decimal(str(result.items[0].net_weight)) == Decimal("15674")

    def test_item_invoice_cost(self, result):
        """INVOICCOST should be 156143.24 (in header currency EUR)."""
        assert Decimal(str(result.items[0].invoice_cost)) == Decimal("156143.24")

    def test_item_hs_code(self, result):
        """G_33_1 HS code from BLOCK should be '8427201909'."""
        assert result.items[0].hs_code == "8427201909"

    def test_item_customs_value_rub(self, result):
        """G_45_0 customs value (RUB) from BLOCK should be 14204319.31."""
        assert Decimal(str(result.items[0].customs_value_rub)) == Decimal("14204319.31")


# =============================================================================
# ITEM PARSING — multiple TOVGs (sample 3328)
# =============================================================================

class TestParseMultipleTovgs:
    """Sample 3328 has 1 BLOCK with 2 TOVGs (POM TANGSHAN K90-A and K270-1)."""

    @pytest.fixture
    def result(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3328)

    def test_items_count(self, result):
        """Should parse exactly 2 items (2 TOVGs)."""
        assert len(result.items) == 2

    def test_item0_sku(self, result):
        """First TOVG: G31_15 should be 'POM TANGSHAN K90-A'."""
        assert result.items[0].sku == "POM TANGSHAN K90-A"

    def test_item0_invoice_cost(self, result):
        """First TOVG: INVOICCOST should be 11995.2."""
        assert Decimal(str(result.items[0].invoice_cost)) == Decimal("11995.2")

    def test_item0_quantity(self, result):
        """First TOVG: KOLVO should be 10."""
        assert result.items[0].quantity == 10

    def test_item0_manufacturer(self, result):
        """First TOVG: G31_11 manufacturer."""
        assert result.items[0].manufacturer == "TANGSHAN ZHONGHAO CHEMICAL CO., LTD"

    def test_item0_hs_code(self, result):
        """First TOVG: HS code from BLOCK should be '3907100000'."""
        assert result.items[0].hs_code == "3907100000"

    def test_item1_sku(self, result):
        """Second TOVG: G31_15 should be 'POM TANGSHAN K270-1'."""
        assert result.items[1].sku == "POM TANGSHAN K270-1"

    def test_item1_invoice_cost(self, result):
        """Second TOVG: INVOICCOST should be 11995.2."""
        assert Decimal(str(result.items[1].invoice_cost)) == Decimal("11995.2")

    def test_item1_quantity(self, result):
        """Second TOVG: KOLVO should be 10."""
        assert result.items[1].quantity == 10

    def test_items_have_different_skus(self, result):
        """Two TOVGs should have distinct SKUs."""
        assert result.items[0].sku != result.items[1].sku


# =============================================================================
# PAYMENT DISTRIBUTION — single item gets 100% of block payments
# =============================================================================

class TestPaymentDistributionSingleItem:
    """Sample 3313: 1 TOVG in block gets 100% of block payments."""

    @pytest.fixture
    def result(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3313)

    def test_item_fee_rub(self, result):
        """Single TOVG gets 100% of customs fee (1010): 30000.00 RUB."""
        assert Decimal(str(result.items[0].fee_rub)) == Decimal("30000.00")

    def test_item_duty_rub(self, result):
        """Single TOVG gets 100% of import duty (2010): 710215.97 RUB."""
        assert Decimal(str(result.items[0].duty_rub)) == Decimal("710215.97")

    def test_item_vat_rub(self, result):
        """Single TOVG gets 100% of VAT (5010): 2982907.06 RUB."""
        assert Decimal(str(result.items[0].vat_rub)) == Decimal("2982907.06")


# =============================================================================
# PAYMENT DISTRIBUTION — proportional by INVOICCOST
# =============================================================================

class TestPaymentDistributionProportional:
    """Sample 3328: 2 TOVGs with equal INVOICCOST (11995.2 each) -> 50/50 split."""

    @pytest.fixture
    def result(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3328)

    def test_equal_invoiccost_means_equal_split(self, result):
        """Both TOVGs have INVOICCOST=11995.2, so each gets 50%."""
        item0 = result.items[0]
        item1 = result.items[1]
        # Verify the costs are equal
        assert Decimal(str(item0.invoice_cost)) == Decimal(str(item1.invoice_cost))

    def test_item0_fee_rub(self, result):
        """First TOVG gets 50% of fee (1010): 11746.00 / 2 = 5873.00."""
        assert Decimal(str(result.items[0].fee_rub)) == Decimal("5873.00")

    def test_item1_fee_rub(self, result):
        """Second TOVG gets 50% of fee (1010): 11746.00 / 2 = 5873.00."""
        assert Decimal(str(result.items[1].fee_rub)) == Decimal("5873.00")

    def test_item0_duty_rub(self, result):
        """First TOVG gets 50% of duty (2010): 75772.72 / 2 = 37886.36."""
        assert Decimal(str(result.items[0].duty_rub)) == Decimal("37886.36")

    def test_item1_duty_rub(self, result):
        """Second TOVG gets 50% of duty (2010): 75772.72 / 2 = 37886.36."""
        assert Decimal(str(result.items[1].duty_rub)) == Decimal("37886.36")

    def test_item0_vat_rub(self, result):
        """First TOVG gets 50% of VAT (5010): 394018.14 / 2 = 197009.07."""
        assert Decimal(str(result.items[0].vat_rub)) == Decimal("197009.07")

    def test_item1_vat_rub(self, result):
        """Second TOVG gets 50% of VAT (5010): 394018.14 / 2 = 197009.07."""
        assert Decimal(str(result.items[1].vat_rub)) == Decimal("197009.07")

    def test_fee_sum_equals_block_total(self, result):
        """Sum of distributed fees should equal block total."""
        total = Decimal(str(result.items[0].fee_rub)) + Decimal(str(result.items[1].fee_rub))
        assert total == Decimal("11746.00")

    def test_duty_sum_equals_block_total(self, result):
        """Sum of distributed duties should equal block total."""
        total = Decimal(str(result.items[0].duty_rub)) + Decimal(str(result.items[1].duty_rub))
        assert total == Decimal("75772.72")

    def test_vat_sum_equals_block_total(self, result):
        """Sum of distributed VAT should equal block total."""
        total = Decimal(str(result.items[0].vat_rub)) + Decimal(str(result.items[1].vat_rub))
        assert total == Decimal("394018.14")


# =============================================================================
# TOTAL PAYMENTS — from B_1, B_2, B_3 elements
# =============================================================================

class TestTotalPayments3313:
    """Verify total_fee_rub, total_duty_rub, total_vat_rub from sample 3313."""

    @pytest.fixture
    def result(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3313)

    def test_total_fee_rub(self, result):
        """B_1 total fee (1010): 30000.00 RUB."""
        assert Decimal(str(result.total_fee_rub)) == Decimal("30000.00")

    def test_total_duty_rub(self, result):
        """B_2 total duty (2010): 710215.97 RUB."""
        assert Decimal(str(result.total_duty_rub)) == Decimal("710215.97")

    def test_total_vat_rub(self, result):
        """B_3 total VAT (5010): 2982907.06 RUB."""
        assert Decimal(str(result.total_vat_rub)) == Decimal("2982907.06")


class TestTotalPayments3328:
    """Verify total_fee_rub, total_duty_rub, total_vat_rub from sample 3328."""

    @pytest.fixture
    def result(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3328)

    def test_total_fee_rub(self, result):
        """B_1 total fee (1010): 11746.00 RUB."""
        assert Decimal(str(result.total_fee_rub)) == Decimal("11746.00")

    def test_total_duty_rub(self, result):
        """B_2 total duty (2010): 75772.72 RUB."""
        assert Decimal(str(result.total_duty_rub)) == Decimal("75772.72")

    def test_total_vat_rub(self, result):
        """B_3 total VAT (5010): 394018.14 RUB."""
        assert Decimal(str(result.total_vat_rub)) == Decimal("394018.14")


# =============================================================================
# ENCODING — windows-1251
# =============================================================================

class TestEncoding:
    """Verify windows-1251 encoded files parse correctly."""

    def test_encoding_windows_1251_opens_correctly(self):
        """Files with windows-1251 encoding should open without errors."""
        from services.customs_declaration_service import parse_gtd_xml
        result = parse_gtd_xml(SAMPLE_3313)
        # If we get here without UnicodeDecodeError, encoding is handled
        assert result is not None

    def test_cyrillic_receiver_name_decoded(self):
        """Receiver name (G_8_NAM) with Cyrillic should decode properly."""
        from services.customs_declaration_service import parse_gtd_xml
        result = parse_gtd_xml(SAMPLE_3313)
        # Should contain Cyrillic text, not mojibake
        # ООО "МАСТЕР БЭРИНГ" in the actual XML
        assert result.receiver_name is not None
        # At minimum, should have non-ASCII characters decoded correctly
        assert len(result.receiver_name) > 3

    def test_cyrillic_description_decoded(self):
        """Item description (G31_1) with Cyrillic should decode properly."""
        from services.customs_declaration_service import parse_gtd_xml
        result = parse_gtd_xml(SAMPLE_3313)
        desc = result.items[0].description
        assert desc is not None
        # Description starts with Cyrillic text about telescopic loader
        assert len(desc) > 20


# =============================================================================
# ERROR HANDLING — invalid/malformed input
# =============================================================================

class TestErrorHandling:
    """Verify graceful error handling for bad input."""

    def test_invalid_xml_garbage_bytes(self):
        """Garbage bytes should return errors, not crash."""
        from services.customs_declaration_service import parse_gtd_xml
        # Write garbage to a temp file
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="wb") as f:
            f.write(b"\x00\x01\x02\xff\xfe random garbage not xml at all")
            tmp_path = f.name
        try:
            result = parse_gtd_xml(tmp_path)
            # Should return a result with errors, not raise an exception
            assert result is not None
            assert len(result.errors) > 0
            assert len(result.items) == 0
        finally:
            os.unlink(tmp_path)

    def test_non_altagtd_xml(self):
        """Valid XML but not AltaGTD format should return error."""
        from services.customs_declaration_service import parse_gtd_xml
        with tempfile.NamedTemporaryFile(
            suffix=".xml", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write('<?xml version="1.0"?>\n<root><data>not a GTD</data></root>')
            tmp_path = f.name
        try:
            result = parse_gtd_xml(tmp_path)
            assert result is not None
            assert len(result.errors) > 0
        finally:
            os.unlink(tmp_path)

    def test_file_not_found(self):
        """Non-existent file should return errors or raise FileNotFoundError."""
        from services.customs_declaration_service import parse_gtd_xml
        try:
            result = parse_gtd_xml("/tmp/nonexistent_gtd_file_12345.xml")
            # If it returns a result, it should have errors
            assert result is not None
            assert len(result.errors) > 0
        except FileNotFoundError:
            # Also acceptable — explicit exception for missing file
            pass


# =============================================================================
# EDGE CASES — empty blocks, zero INVOICCOST
# =============================================================================

class TestEdgeCases:
    """Edge cases: empty blocks, zero cost, etc."""

    def test_empty_block_no_tovgs(self):
        """BLOCK without TOVG elements should be skipped gracefully."""
        from services.customs_declaration_service import parse_gtd_xml
        xml_content = '''<?xml version="1.0" encoding="utf-8"?>
<AltaGTD Comment="9999">
  <REGNUM>99999999/010125/0000001</REGNUM>
  <G_22_3>USD</G_22_3>
  <G_23_1>75.0000</G_23_1>
  <G_2_NAM>SENDER INC</G_2_NAM>
  <G_2_7>US</G_2_7>
  <G_8_NAM>RECEIVER LLC</G_8_NAM>
  <G_8_6>1234567890</G_8_6>
  <G_12_0>100000.00</G_12_0>
  <REG_DATE>2025-01-01</REG_DATE>
  <BLOCK>
    <G_33_1>1234567890</G_33_1>
    <G_45_0>100000.00</G_45_0>
    <G_47_1_1>1010</G_47_1_1>
    <G_47_1_4>5000.00</G_47_1_4>
  </BLOCK>
  <B_1>1010-5000.00-643-1234567890</B_1>
</AltaGTD>'''
        with tempfile.NamedTemporaryFile(
            suffix=".xml", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(xml_content)
            tmp_path = f.name
        try:
            result = parse_gtd_xml(tmp_path)
            assert result is not None
            # No TOVGs in BLOCK -> no items
            assert len(result.items) == 0
        finally:
            os.unlink(tmp_path)

    def test_zero_invoiccost_no_divide_by_zero(self):
        """TOVG with INVOICCOST=0 should not cause divide-by-zero."""
        from services.customs_declaration_service import parse_gtd_xml
        xml_content = '''<?xml version="1.0" encoding="utf-8"?>
<AltaGTD Comment="8888">
  <REGNUM>88888888/010125/0000002</REGNUM>
  <G_22_3>USD</G_22_3>
  <G_23_1>75.0000</G_23_1>
  <G_2_NAM>SENDER INC</G_2_NAM>
  <G_2_7>US</G_2_7>
  <G_8_NAM>RECEIVER LLC</G_8_NAM>
  <G_8_6>1234567890</G_8_6>
  <G_12_0>0.00</G_12_0>
  <REG_DATE>2025-01-01</REG_DATE>
  <BLOCK>
    <G_33_1>1234567890</G_33_1>
    <G_45_0>0.00</G_45_0>
    <G_47_1_1>1010</G_47_1_1>
    <G_47_1_4>5000.00</G_47_1_4>
    <TOVG>
      <G31_15>ZERO-COST-ITEM</G31_15>
      <G31_1>Item with zero cost</G31_1>
      <G31_11>MAKER</G31_11>
      <G31_14>BRAND</G31_14>
      <KOLVO>1</KOLVO>
      <NAME_EDI>PCS</NAME_EDI>
      <G31_35>100</G31_35>
      <G31_38>90</G31_38>
      <INVOICCOST>0</INVOICCOST>
    </TOVG>
  </BLOCK>
  <B_1>1010-5000.00-643-1234567890</B_1>
</AltaGTD>'''
        with tempfile.NamedTemporaryFile(
            suffix=".xml", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(xml_content)
            tmp_path = f.name
        try:
            result = parse_gtd_xml(tmp_path)
            # Should not crash with ZeroDivisionError
            assert result is not None
            assert len(result.items) == 1
            item = result.items[0]
            assert item.sku == "ZERO-COST-ITEM"
            assert Decimal(str(item.invoice_cost)) == Decimal("0")
        finally:
            os.unlink(tmp_path)


# =============================================================================
# G_47 FLAT PAYMENT PARSING — verify the flat element pattern
# =============================================================================

class TestG47FlatPaymentParsing:
    """
    CRITICAL: G_47 payments use FLAT elements, not nested.
    Pattern: G_47_{row}_{field} where field 1=type code, 4=amount.
    Example:
        <G_47_1_1>1010</G_47_1_1>
        <G_47_1_4>30000.00</G_47_1_4>
        <G_47_2_1>2010</G_47_2_1>
        <G_47_2_4>710215.97</G_47_2_4>
    """

    @pytest.fixture
    def result_3313(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3313)

    @pytest.fixture
    def result_3328(self):
        from services.customs_declaration_service import parse_gtd_xml
        return parse_gtd_xml(SAMPLE_3328)

    def test_3313_three_payment_types_parsed(self, result_3313):
        """Sample 3313 has 3 G_47 rows: 1010, 2010, 5010."""
        item = result_3313.items[0]
        # All three payment types should be non-zero
        assert Decimal(str(item.fee_rub)) > 0     # 1010
        assert Decimal(str(item.duty_rub)) > 0    # 2010
        assert Decimal(str(item.vat_rub)) > 0     # 5010

    def test_3313_fee_is_1010_amount(self, result_3313):
        """G_47_1_1=1010, G_47_1_4=30000.00 -> fee_rub=30000.00."""
        assert Decimal(str(result_3313.items[0].fee_rub)) == Decimal("30000.00")

    def test_3313_duty_is_2010_amount(self, result_3313):
        """G_47_2_1=2010, G_47_2_4=710215.97 -> duty_rub=710215.97."""
        assert Decimal(str(result_3313.items[0].duty_rub)) == Decimal("710215.97")

    def test_3313_vat_is_5010_amount(self, result_3313):
        """G_47_3_1=5010, G_47_3_4=2982907.06 -> vat_rub=2982907.06."""
        assert Decimal(str(result_3313.items[0].vat_rub)) == Decimal("2982907.06")

    def test_3328_fee_total_from_flat_elements(self, result_3328):
        """Sample 3328: G_47_1_1=1010, G_47_1_4=11746.00."""
        total_fee = sum(Decimal(str(item.fee_rub)) for item in result_3328.items)
        assert total_fee == Decimal("11746.00")

    def test_3328_duty_total_from_flat_elements(self, result_3328):
        """Sample 3328: G_47_2_1=2010, G_47_2_4=75772.72."""
        total_duty = sum(Decimal(str(item.duty_rub)) for item in result_3328.items)
        assert total_duty == Decimal("75772.72")

    def test_3328_vat_total_from_flat_elements(self, result_3328):
        """Sample 3328: G_47_3_1=5010, G_47_3_4=394018.14."""
        total_vat = sum(Decimal(str(item.vat_rub)) for item in result_3328.items)
        assert total_vat == Decimal("394018.14")


# =============================================================================
# DATACLASS STRUCTURE — verify expected fields exist on GTDItem and GTDParseResult
# =============================================================================

class TestDataclassFields:
    """Verify GTDItem and GTDParseResult have the expected fields."""

    def test_gtd_item_has_required_fields(self):
        """GTDItem should have all expected fields."""
        from services.customs_declaration_service import GTDItem
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(GTDItem)}
        expected = {
            "sku", "description", "manufacturer", "brand",
            "quantity", "unit", "gross_weight", "net_weight",
            "invoice_cost", "hs_code", "customs_value_rub",
            "fee_rub", "duty_rub", "vat_rub",
        }
        for field in expected:
            assert field in field_names, f"GTDItem missing field: {field}"

    def test_gtd_parse_result_has_required_fields(self):
        """GTDParseResult should have all expected fields."""
        from services.customs_declaration_service import GTDParseResult
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(GTDParseResult)}
        expected = {
            "regnum", "declaration_date", "currency", "exchange_rate",
            "sender_name", "sender_country", "receiver_name", "receiver_inn",
            "internal_ref", "total_customs_value_rub",
            "total_fee_rub", "total_duty_rub", "total_vat_rub",
            "items", "errors",
        }
        for field in expected:
            assert field in field_names, f"GTDParseResult missing field: {field}"
