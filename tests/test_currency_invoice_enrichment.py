"""
Tests for Currency Invoice Enrichment (TDD - tests first, implementation later)

New functions to be added to services/currency_invoice_service.py:
1. lookup_contract — find matching contract from currency_contracts table data
2. pick_bank_account — select bank account by entity + currency, prefer default
3. PAYMENT_TERMS_EURTR / PAYMENT_TERMS_TRRU / DELIVERY_TERMS_TRRU — constants
4. generate_currency_invoices — enhanced with contracts + bank_accounts params
"""

import pytest
from decimal import Decimal
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# CONTRACT LOOKUP TESTS
# ============================================================================

class TestLookupContract:
    """Tests for lookup_contract function."""

    def _import_lookup_contract(self):
        from services.currency_invoice_service import lookup_contract
        return lookup_contract

    def _make_contracts(self):
        """Sample currency_contracts data (as returned from DB)."""
        return [
            {
                "id": "contract-1",
                "contract_number": "EU-TR/2026-001",
                "contract_date": "2026-01-15",
                "seller_entity_type": "buyer_company",
                "seller_entity_id": "bc-eu-1",
                "buyer_entity_type": "intermediary",
                "buyer_entity_id": "int-tr-1",
                "currency": "EUR",
                "is_active": True,
            },
            {
                "id": "contract-2",
                "contract_number": "TR-RU/2026-001",
                "contract_date": "2026-02-01",
                "seller_entity_type": "intermediary",
                "seller_entity_id": "int-tr-1",
                "buyer_entity_type": "seller_company",
                "buyer_entity_id": "sc-ru-1",
                "currency": "USD",
                "is_active": True,
            },
            {
                "id": "contract-3",
                "contract_number": "OLD/2024-001",
                "contract_date": "2024-06-01",
                "seller_entity_type": "buyer_company",
                "seller_entity_id": "bc-eu-1",
                "buyer_entity_type": "intermediary",
                "buyer_entity_id": "int-tr-1",
                "currency": "EUR",
                "is_active": False,  # inactive
            },
        ]

    def test_returns_matching_contract(self):
        """Returns the contract dict when all 5 fields match."""
        lookup_contract = self._import_lookup_contract()
        contracts = self._make_contracts()
        result = lookup_contract(
            contracts=contracts,
            seller_entity_type="buyer_company",
            seller_entity_id="bc-eu-1",
            buyer_entity_type="intermediary",
            buyer_entity_id="int-tr-1",
            currency="EUR",
        )
        assert result is not None
        assert result["contract_number"] == "EU-TR/2026-001"
        assert result["id"] == "contract-1"

    def test_returns_none_when_no_match(self):
        """Returns None when no contract matches."""
        lookup_contract = self._import_lookup_contract()
        contracts = self._make_contracts()
        result = lookup_contract(
            contracts=contracts,
            seller_entity_type="buyer_company",
            seller_entity_id="nonexistent",
            buyer_entity_type="intermediary",
            buyer_entity_id="int-tr-1",
            currency="EUR",
        )
        assert result is None

    def test_skips_inactive_contracts(self):
        """Inactive contracts (is_active=False) are not returned."""
        lookup_contract = self._import_lookup_contract()
        # Only inactive contract matches these params
        contracts = [
            {
                "id": "contract-inactive",
                "contract_number": "OLD/2024-001",
                "contract_date": "2024-06-01",
                "seller_entity_type": "buyer_company",
                "seller_entity_id": "bc-eu-1",
                "buyer_entity_type": "intermediary",
                "buyer_entity_id": "int-tr-1",
                "currency": "EUR",
                "is_active": False,
            },
        ]
        result = lookup_contract(
            contracts=contracts,
            seller_entity_type="buyer_company",
            seller_entity_id="bc-eu-1",
            buyer_entity_type="intermediary",
            buyer_entity_id="int-tr-1",
            currency="EUR",
        )
        assert result is None

    def test_matches_on_all_five_fields(self):
        """Must match seller_type+id, buyer_type+id, AND currency."""
        lookup_contract = self._import_lookup_contract()
        contracts = self._make_contracts()

        # Wrong currency — should NOT match contract-1 (EUR)
        result = lookup_contract(
            contracts=contracts,
            seller_entity_type="buyer_company",
            seller_entity_id="bc-eu-1",
            buyer_entity_type="intermediary",
            buyer_entity_id="int-tr-1",
            currency="USD",  # contract-1 is EUR
        )
        assert result is None

    def test_empty_contracts_list(self):
        """Empty contracts list returns None."""
        lookup_contract = self._import_lookup_contract()
        result = lookup_contract(
            contracts=[],
            seller_entity_type="buyer_company",
            seller_entity_id="bc-eu-1",
            buyer_entity_type="intermediary",
            buyer_entity_id="int-tr-1",
            currency="EUR",
        )
        assert result is None

    def test_matches_trru_segment_contract(self):
        """Can find TR-RU segment contracts too."""
        lookup_contract = self._import_lookup_contract()
        contracts = self._make_contracts()
        result = lookup_contract(
            contracts=contracts,
            seller_entity_type="intermediary",
            seller_entity_id="int-tr-1",
            buyer_entity_type="seller_company",
            buyer_entity_id="sc-ru-1",
            currency="USD",
        )
        assert result is not None
        assert result["contract_number"] == "TR-RU/2026-001"


# ============================================================================
# BANK ACCOUNT SELECTION TESTS
# ============================================================================

class TestPickBankAccount:
    """Tests for pick_bank_account function."""

    def _import_pick_bank_account(self):
        from services.currency_invoice_service import pick_bank_account
        return pick_bank_account

    def _make_bank_accounts(self):
        """Sample bank accounts data."""
        return [
            {
                "id": "ba-1",
                "entity_type": "buyer_company",
                "entity_id": "bc-eu-1",
                "currency": "EUR",
                "bank_name": "Deutsche Bank",
                "iban": "DE89370400440532013000",
                "is_default": True,
            },
            {
                "id": "ba-2",
                "entity_type": "buyer_company",
                "entity_id": "bc-eu-1",
                "currency": "EUR",
                "bank_name": "Commerzbank",
                "iban": "DE44500400750135000000",
                "is_default": False,
            },
            {
                "id": "ba-3",
                "entity_type": "buyer_company",
                "entity_id": "bc-eu-1",
                "currency": "USD",
                "bank_name": "Deutsche Bank USD",
                "iban": "DE12345678901234567890",
                "is_default": True,
            },
            {
                "id": "ba-4",
                "entity_type": "intermediary",
                "entity_id": "int-tr-1",
                "currency": "USD",
                "bank_name": "Garanti BBVA",
                "iban": "TR330006100519786457841326",
                "is_default": True,
            },
        ]

    def test_returns_matching_account(self):
        """Returns bank account matching entity + currency."""
        pick_bank_account = self._import_pick_bank_account()
        accounts = self._make_bank_accounts()
        result = pick_bank_account(
            bank_accounts=accounts,
            entity_type="buyer_company",
            entity_id="bc-eu-1",
            currency="EUR",
        )
        assert result is not None
        assert result["currency"] == "EUR"
        assert result["entity_id"] == "bc-eu-1"

    def test_prefers_default_account(self):
        """When multiple accounts match, prefers is_default=True."""
        pick_bank_account = self._import_pick_bank_account()
        accounts = self._make_bank_accounts()
        result = pick_bank_account(
            bank_accounts=accounts,
            entity_type="buyer_company",
            entity_id="bc-eu-1",
            currency="EUR",
        )
        assert result is not None
        assert result["id"] == "ba-1"
        assert result["is_default"] is True

    def test_falls_back_to_non_default(self):
        """When no default account, returns any matching account."""
        pick_bank_account = self._import_pick_bank_account()
        # Only non-default accounts
        accounts = [
            {
                "id": "ba-only",
                "entity_type": "buyer_company",
                "entity_id": "bc-eu-1",
                "currency": "EUR",
                "bank_name": "Only Bank",
                "iban": "DE00000000000000000000",
                "is_default": False,
            },
        ]
        result = pick_bank_account(
            bank_accounts=accounts,
            entity_type="buyer_company",
            entity_id="bc-eu-1",
            currency="EUR",
        )
        assert result is not None
        assert result["id"] == "ba-only"

    def test_returns_none_when_no_match(self):
        """Returns None if no account matches entity + currency."""
        pick_bank_account = self._import_pick_bank_account()
        accounts = self._make_bank_accounts()
        result = pick_bank_account(
            bank_accounts=accounts,
            entity_type="buyer_company",
            entity_id="nonexistent",
            currency="EUR",
        )
        assert result is None

    def test_currency_mismatch_returns_none(self):
        """Account exists for entity but in wrong currency — returns None."""
        pick_bank_account = self._import_pick_bank_account()
        accounts = [
            {
                "id": "ba-eur-only",
                "entity_type": "buyer_company",
                "entity_id": "bc-eu-1",
                "currency": "EUR",
                "bank_name": "EUR Bank",
                "iban": "DE11111111111111111111",
                "is_default": True,
            },
        ]
        result = pick_bank_account(
            bank_accounts=accounts,
            entity_type="buyer_company",
            entity_id="bc-eu-1",
            currency="CNY",  # no CNY account
        )
        assert result is None

    def test_empty_accounts_list(self):
        """Empty bank accounts list returns None."""
        pick_bank_account = self._import_pick_bank_account()
        result = pick_bank_account(
            bank_accounts=[],
            entity_type="buyer_company",
            entity_id="bc-eu-1",
            currency="EUR",
        )
        assert result is None

    def test_matches_by_entity_type_and_id(self):
        """Different entity_type with same entity_id should NOT match."""
        pick_bank_account = self._import_pick_bank_account()
        accounts = self._make_bank_accounts()
        # ba-4 is intermediary/int-tr-1/USD — searching for buyer_company/int-tr-1 should NOT match
        result = pick_bank_account(
            bank_accounts=accounts,
            entity_type="buyer_company",
            entity_id="int-tr-1",
            currency="USD",
        )
        assert result is None


# ============================================================================
# PAYMENT & DELIVERY TERMS CONSTANTS TESTS
# ============================================================================

class TestPaymentDeliveryTermsConstants:
    """Tests for payment and delivery terms constants."""

    def test_eurtr_payment_terms_exists(self):
        """PAYMENT_TERMS_EURTR constant is a non-empty string."""
        from services.currency_invoice_service import PAYMENT_TERMS_EURTR
        assert isinstance(PAYMENT_TERMS_EURTR, str)
        assert len(PAYMENT_TERMS_EURTR) > 0

    def test_trru_payment_terms_exists(self):
        """PAYMENT_TERMS_TRRU constant is a non-empty string."""
        from services.currency_invoice_service import PAYMENT_TERMS_TRRU
        assert isinstance(PAYMENT_TERMS_TRRU, str)
        assert len(PAYMENT_TERMS_TRRU) > 0

    def test_trru_delivery_terms_exists(self):
        """DELIVERY_TERMS_TRRU constant is a non-empty string."""
        from services.currency_invoice_service import DELIVERY_TERMS_TRRU
        assert isinstance(DELIVERY_TERMS_TRRU, str)
        assert len(DELIVERY_TERMS_TRRU) > 0

    def test_eurtr_payment_terms_mentions_180_days(self):
        """EURTR payment terms should mention 180 days."""
        from services.currency_invoice_service import PAYMENT_TERMS_EURTR
        assert "180" in PAYMENT_TERMS_EURTR

    def test_trru_payment_terms_mentions_prepayment(self):
        """TRRU payment terms should mention prepayment."""
        from services.currency_invoice_service import PAYMENT_TERMS_TRRU
        assert "prepayment" in PAYMENT_TERMS_TRRU.lower() or "100%" in PAYMENT_TERMS_TRRU

    def test_trru_delivery_terms_mentions_dap(self):
        """TRRU delivery terms should mention DAP."""
        from services.currency_invoice_service import DELIVERY_TERMS_TRRU
        assert "DAP" in DELIVERY_TERMS_TRRU


# ============================================================================
# ENHANCED generate_currency_invoices TESTS
# ============================================================================

class TestGenerateCurrencyInvoicesEnriched:
    """Tests for generate_currency_invoices with new contracts & bank_accounts params."""

    def _make_seller_company(self):
        return {"id": "sc-ru-1", "name": "MB Rus", "entity_type": "seller_company"}

    def _make_buyer_companies(self):
        return {
            "bc-eu-1": {"id": "bc-eu-1", "name": "EuroInvest", "region": "EU"},
        }

    def _make_items(self):
        return [
            {
                "id": "item-1",
                "buyer_company_id": "bc-eu-1",
                "product_name": "Bearing",
                "sku": "BRG-001",
                "idn_sku": "IDN-001",
                "brand": "SKF",
                "quantity": Decimal("100"),
                "unit": "pcs",
                "hs_code": "8482.10",
                "purchase_price_original": Decimal("50.00"),
                "purchase_currency": "EUR",
            },
        ]

    def _make_contracts(self):
        return [
            {
                "id": "contract-eurtr",
                "contract_number": "EU-TR/2026-001",
                "contract_date": "2026-01-15",
                "seller_entity_type": "buyer_company",
                "seller_entity_id": "bc-eu-1",
                "buyer_entity_type": "seller_company",
                "buyer_entity_id": "sc-ru-1",
                "currency": "EUR",
                "is_active": True,
            },
            {
                "id": "contract-trru",
                "contract_number": "TR-RU/2026-001",
                "contract_date": "2026-02-01",
                "seller_entity_type": None,  # intermediary TBD
                "seller_entity_id": None,
                "buyer_entity_type": "seller_company",
                "buyer_entity_id": "sc-ru-1",
                "currency": "EUR",
                "is_active": True,
            },
        ]

    def _make_bank_accounts(self):
        return [
            {
                "id": "ba-eu-eur",
                "entity_type": "buyer_company",
                "entity_id": "bc-eu-1",
                "currency": "EUR",
                "bank_name": "Deutsche Bank",
                "iban": "DE89370400440532013000",
                "is_default": True,
            },
        ]

    def test_backward_compatible_without_new_params(self):
        """Existing code should still work without contracts/bank_accounts."""
        from services.currency_invoice_service import generate_currency_invoices

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
        )
        # Should still generate invoices as before
        assert len(result) >= 1

    def test_eurtr_invoice_has_contract_number_when_contracts_provided(self):
        """EURTR invoice should have contract_number from matched contract."""
        from services.currency_invoice_service import generate_currency_invoices

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=self._make_contracts(),
        )
        eurtr = [inv for inv in result if inv["segment"] == "EURTR"][0]
        assert "contract_number" in eurtr
        assert eurtr["contract_number"] == "EU-TR/2026-001"

    def test_eurtr_invoice_has_contract_date_when_contracts_provided(self):
        """EURTR invoice should have contract_date from matched contract."""
        from services.currency_invoice_service import generate_currency_invoices

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=self._make_contracts(),
        )
        eurtr = [inv for inv in result if inv["segment"] == "EURTR"][0]
        assert "contract_date" in eurtr
        assert eurtr["contract_date"] == "2026-01-15"

    def test_invoice_has_seller_bank_account_id_when_bank_accounts_provided(self):
        """Invoice should have seller_bank_account_id from matched bank account."""
        from services.currency_invoice_service import generate_currency_invoices

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            bank_accounts=self._make_bank_accounts(),
        )
        eurtr = [inv for inv in result if inv["segment"] == "EURTR"][0]
        assert "seller_bank_account_id" in eurtr
        assert eurtr["seller_bank_account_id"] == "ba-eu-eur"

    def test_eurtr_invoice_has_payment_terms(self):
        """EURTR invoice should have payment_terms from PAYMENT_TERMS_EURTR constant."""
        from services.currency_invoice_service import (
            generate_currency_invoices,
            PAYMENT_TERMS_EURTR,
        )

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=self._make_contracts(),
            bank_accounts=self._make_bank_accounts(),
        )
        eurtr = [inv for inv in result if inv["segment"] == "EURTR"][0]
        assert "payment_terms" in eurtr
        assert eurtr["payment_terms"] == PAYMENT_TERMS_EURTR

    def test_eurtr_invoice_has_no_delivery_terms(self):
        """EURTR invoice should NOT have delivery_terms (None)."""
        from services.currency_invoice_service import generate_currency_invoices

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=self._make_contracts(),
            bank_accounts=self._make_bank_accounts(),
        )
        eurtr = [inv for inv in result if inv["segment"] == "EURTR"][0]
        assert "delivery_terms" in eurtr
        assert eurtr["delivery_terms"] is None

    def test_trru_invoice_has_payment_terms(self):
        """TRRU invoice should have payment_terms from PAYMENT_TERMS_TRRU constant."""
        from services.currency_invoice_service import (
            generate_currency_invoices,
            PAYMENT_TERMS_TRRU,
        )

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=self._make_contracts(),
            bank_accounts=self._make_bank_accounts(),
        )
        trru = [inv for inv in result if inv["segment"] == "TRRU"][0]
        assert "payment_terms" in trru
        assert trru["payment_terms"] == PAYMENT_TERMS_TRRU

    def test_trru_invoice_has_delivery_terms(self):
        """TRRU invoice should have delivery_terms from DELIVERY_TERMS_TRRU constant."""
        from services.currency_invoice_service import (
            generate_currency_invoices,
            DELIVERY_TERMS_TRRU,
        )

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=self._make_contracts(),
            bank_accounts=self._make_bank_accounts(),
        )
        trru = [inv for inv in result if inv["segment"] == "TRRU"][0]
        assert "delivery_terms" in trru
        assert trru["delivery_terms"] == DELIVERY_TERMS_TRRU

    def test_no_contract_match_leaves_contract_fields_none(self):
        """When no contract matches, contract_number and contract_date should be None."""
        from services.currency_invoice_service import generate_currency_invoices

        # Empty contracts list — no match possible
        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=[],  # no contracts
            bank_accounts=self._make_bank_accounts(),
        )
        eurtr = [inv for inv in result if inv["segment"] == "EURTR"][0]
        assert eurtr.get("contract_number") is None
        assert eurtr.get("contract_date") is None

    def test_no_bank_account_match_leaves_bank_account_id_none(self):
        """When no bank account matches, seller_bank_account_id should be None."""
        from services.currency_invoice_service import generate_currency_invoices

        result = generate_currency_invoices(
            deal_id="deal-1",
            quote_idn="Q202601-0004",
            items=self._make_items(),
            buyer_companies=self._make_buyer_companies(),
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=self._make_contracts(),
            bank_accounts=[],  # no accounts
        )
        eurtr = [inv for inv in result if inv["segment"] == "EURTR"][0]
        assert eurtr.get("seller_bank_account_id") is None

    def test_tr_buyer_trru_invoice_enriched(self):
        """TR buyer -> TRRU invoice should also get enrichment fields."""
        from services.currency_invoice_service import generate_currency_invoices

        buyer_companies = {
            "bc-tr-1": {"id": "bc-tr-1", "name": "MB TR", "region": "TR"},
        }
        items = [
            {
                "id": "item-tr",
                "buyer_company_id": "bc-tr-1",
                "product_name": "Seal",
                "sku": "SL-001",
                "idn_sku": "IDN-002",
                "brand": "NOK",
                "quantity": Decimal("200"),
                "unit": "pcs",
                "hs_code": "4016.93",
                "purchase_price_original": Decimal("10.00"),
                "purchase_currency": "USD",
            },
        ]
        contracts = [
            {
                "id": "contract-trru-tr",
                "contract_number": "TR-RU/2026-002",
                "contract_date": "2026-03-01",
                "seller_entity_type": None,
                "seller_entity_id": None,
                "buyer_entity_type": "seller_company",
                "buyer_entity_id": "sc-ru-1",
                "currency": "USD",
                "is_active": True,
            },
        ]
        result = generate_currency_invoices(
            deal_id="deal-2",
            quote_idn="Q202601-0005",
            items=items,
            buyer_companies=buyer_companies,
            seller_company=self._make_seller_company(),
            organization_id="org-1",
            contracts=contracts,
            bank_accounts=[],
        )
        assert len(result) == 1
        trru = result[0]
        assert trru["segment"] == "TRRU"
        # Enrichment fields must be present
        assert "payment_terms" in trru
        assert "delivery_terms" in trru
        assert trru.get("delivery_terms") is not None
        assert "contract_number" in trru
        assert trru["contract_number"] == "TR-RU/2026-002"
