# Code Inspection Report

**Date**: 2026-02-01
**Scope**: SellerCompany Validation Error Analysis
**Inspector**: code-inspector agent
**Previous Reports Reviewed**: None (first inspection in this scope)

## Executive Summary

The SellerCompany validation fails because of a fundamental architecture mismatch: the calculation engine uses a hardcoded Pydantic enum (`SellerCompany`) expecting exact company name strings, but the database stores company names dynamically with different formatting. This is a **design decision from the original calculation engine** that was never adapted to work with a database-driven seller companies list.

## Critical Findings (Immediate Attention)

### Finding 1: Hardcoded Enum vs Dynamic Database Values

**Severity**: Critical
**Location**: `calculation_models.py:44-51`, `calculation_mapper.py:400-402`
**Pattern**: Design Inconsistency / Hardcoded Values

**Current Code in `calculation_models.py`:**
```python
class SellerCompany(str, Enum):
    """Seller company names (auto-derives seller_region)"""
    MASTER_BEARING_RU = "МАСТЕР БЭРИНГ ООО"
    CMTO1_RU = "ЦМТО1 ООО"
    RAD_RESURS_RU = "РАД РЕСУРС ООО"
    TEXCEL_TR = "TEXCEL OTOMOTİV TİCARET LİMİTED ŞİRKETİ"
    GESTUS_TR = "GESTUS DIŞ TİCARET LİMİTED ŞİRKETİ"
    UPDOOR_CN = "UPDOOR Limited"
```

**Validation in `calculation_mapper.py`:**
```python
seller_company_value = variables.get('seller_company') or 'МАСТЕР БЭРИНГ ООО'
company = CompanySettings(
    seller_company=SellerCompany(seller_company_value),  # <- FAILS if name doesn't match enum exactly
    offer_sale_type=OfferSaleType(variables.get('offer_sale_type', 'поставка'))
)
```

**Problem**:
- Database stores: `"ООО Мастер Бэринг"` (natural Russian order: legal form + name)
- Enum expects: `"МАСТЕР БЭРИНГ ООО"` (name + legal form, uppercase)
- The validation `SellerCompany(seller_company_value)` raises ValueError when names don't match exactly

**Data Flow Traced**:
```
1. User selects seller company in quote creation form
2. quote.seller_company_id → UUID stored in quotes table
3. main.py:9668 → get_seller_company(quote["seller_company_id"])
4. Returns SellerCompany object with .name from database
5. main.py:9672 → seller_company_name = seller_company.name
6. main.py:9791 → Hidden input: name="seller_company" value=seller_company_name
7. POST handler → variables['seller_company'] = form data
8. build_calculation_inputs() → passes variables to mapper
9. calculation_mapper.py:400-402 → SellerCompany(value) FAILS
```

**Risk Assessment**:
- **HIGH** - Prevents ALL calculation previews and final calculations for quotes with mismatched company names
- Users see cryptic error: `'ООО Мастер Бэринг' is not a valid SellerCompany`
- Business impact: Cannot generate quotes for any seller company not matching enum exactly

**Effort Estimate**: Small (database rename) or Medium (add normalization mapping)

---

### Finding 2: Missing Company Name Normalization (Like SupplierCountry)

**Severity**: High
**Location**: `calculation_mapper.py:78-167` (SupplierCountry has normalization, SellerCompany doesn't)
**Pattern**: Inconsistent Pattern Application

**Current Code** - SupplierCountry HAS normalization:
```python
# Map database values to enum values (handles variations in country names)
SUPPLIER_COUNTRY_MAPPING = {
    "ЕС (закупка между странами ЕС)": "ЕС (между странами ЕС)",
    "Turkey": "Турция",
    "Germany": "ЕС (между странами ЕС)",
    # ... many variations handled
}

def normalize_supplier_country(value: str) -> str:
    """Normalize supplier country value to match SupplierCountry enum."""
    if value in SUPPLIER_COUNTRY_MAPPING:
        return SUPPLIER_COUNTRY_MAPPING[value]
    return value
```

**SellerCompany has NO such normalization** - it's passed directly to enum constructor:
```python
seller_company_value = variables.get('seller_company') or 'МАСТЕР БЭРИНГ ООО'
company = CompanySettings(
    seller_company=SellerCompany(seller_company_value),  # No normalization!
```

**Problem**: The codebase has an established pattern for handling database/enum mismatches (SUPPLIER_COUNTRY_MAPPING), but this pattern was NOT applied to SellerCompany.

**Proposed Solution A** - Add similar mapping:
```python
SELLER_COMPANY_MAPPING = {
    # Database format → Enum format
    "ООО Мастер Бэринг": "МАСТЕР БЭРИНГ ООО",
    "ООО МАСТЕР БЭРИНГ": "МАСТЕР БЭРИНГ ООО",
    "Мастер Бэринг ООО": "МАСТЕР БЭРИНГ ООО",
    "ООО ЦМТО1": "ЦМТО1 ООО",
    "ООО РадРесурс": "РАД РЕСУРС ООО",
    # ... etc
}

def normalize_seller_company(value: str) -> str:
    """Normalize seller company value to match SellerCompany enum."""
    if not value:
        return "МАСТЕР БЭРИНГ ООО"  # Default
    if value in SELLER_COMPANY_MAPPING:
        return SELLER_COMPANY_MAPPING[value]
    # Try case-insensitive lookup
    for db_name, enum_name in SELLER_COMPANY_MAPPING.items():
        if db_name.lower() == value.lower():
            return enum_name
    return value  # Return as-is for clear error
```

**Proposed Solution B** (simpler) - Rename database values to match enum exactly:
```sql
UPDATE kvota.seller_companies
SET name = 'МАСТЕР БЭРИНГ ООО'
WHERE name ILIKE '%мастер%бэринг%';
```

**Risk Assessment**: Medium - affects all quotes using non-enum-matching company names
**Effort Estimate**: Small

---

### Finding 3: CLAUDE.md Prohibits Calculation Engine Modifications

**Severity**: Medium (constraint, not bug)
**Location**: `CLAUDE.md:8-21`
**Pattern**: Architecture Constraint

**Current Documentation**:
```markdown
## ⚠️ CRITICAL RULE - DO NOT MODIFY CALCULATION ENGINE

**Files to NEVER modify:**
- `calculation_engine.py`
- `calculation_models.py`
- `calculation_mapper.py`

**If data schema changes:** Adapt data in `build_calculation_inputs()` (main.py)
to match calculation engine expectations.
```

**Problem**: The recommended solution in CLAUDE.md is to adapt data before passing to the engine. However, adding a normalization function to `calculation_mapper.py` would technically violate this rule.

**Implication**:
- Cannot add `normalize_seller_company()` to `calculation_mapper.py`
- Must either: (a) rename database values, OR (b) add normalization in `build_calculation_inputs()` in `main.py`

**User's Prior Decision** (from conversation history):
> "last time we had this error we agreed to rename all the companies to match expectations of the calc engine"

This confirms the intended solution is **database rename**, not code modification.

---

## Moderate Findings (Plan to Address)

### Finding 4: Dual Class Definition for SellerCompany

**Severity**: Medium
**Location**: `calculation_models.py:44-51` (Enum) vs `seller_company_service.py:43-77` (Dataclass)
**Pattern**: Naming Collision / Potential Confusion

Two completely different classes named `SellerCompany`:

1. **Enum** in `calculation_models.py`:
```python
class SellerCompany(str, Enum):
    """Seller company names (auto-derives seller_region)"""
    MASTER_BEARING_RU = "МАСТЕР БЭРИНГ ООО"
```

2. **Dataclass** in `seller_company_service.py`:
```python
@dataclass
class SellerCompany:
    """Represents a seller company record."""
    id: str
    organization_id: str
    name: str
    supplier_code: str
```

**Problem**: Different files use different classes with same name. Import confusion is possible.

**Risk Assessment**: Low - currently working because imports are explicit, but could cause bugs if imports change.

**Effort Estimate**: Low (rename one class to avoid collision)

---

## Positive Patterns Observed

1. **Consistent normalization pattern** for SupplierCountry - can be replicated for SellerCompany
2. **Clear CLAUDE.md documentation** about not modifying calculation engine
3. **Two-tier variable resolution** (`get_value()` function) is well-designed
4. **Service layer separation** (`seller_company_service.py`) keeps database logic isolated

---

## Recommended Action Plan

Based on user's prior decision and CLAUDE.md constraints:

### Option A: Database Rename (Recommended)

**Rationale**: User previously agreed to this approach. Simplest, no code changes needed.

1. **Identify mismatched names** in database:
```sql
SELECT DISTINCT name FROM kvota.seller_companies
WHERE name NOT IN (
    'МАСТЕР БЭРИНГ ООО',
    'ЦМТО1 ООО',
    'РАД РЕСУРС ООО',
    'TEXCEL OTOMOTİV TİCARET LİMİTED ŞİRKETİ',
    'GESTUS DIŞ TİCARET LİMİTED ŞİRKETİ',
    'UPDOOR Limited'
);
```

2. **Create migration** to rename companies:
```sql
-- Migration: Rename seller companies to match calculation engine enum
UPDATE kvota.seller_companies
SET name = 'МАСТЕР БЭРИНГ ООО'
WHERE name ILIKE '%мастер%бэринг%' AND name != 'МАСТЕР БЭРИНГ ООО';

-- Repeat for other companies as needed
```

3. **Verify** calculation preview works after migration

### Option B: Add Normalization in main.py

**If database rename is not desired**, add normalization in `build_calculation_inputs()`:

```python
# In main.py, before calling map_variables_to_calculation_input
SELLER_COMPANY_NORM = {
    "ООО Мастер Бэринг": "МАСТЕР БЭРИНГ ООО",
    # ... other mappings
}

def normalize_seller_company_for_calc(name: str) -> str:
    return SELLER_COMPANY_NORM.get(name, name)

# In build_calculation_inputs or before passing to mapper:
calc_variables['seller_company'] = normalize_seller_company_for_calc(
    calc_variables.get('seller_company', 'МАСТЕР БЭРИНГ ООО')
)
```

This follows CLAUDE.md guidance (adapt data in main.py, don't modify calculation engine files).

---

## Files Inspected

- `calculation_models.py` - SellerCompany enum definition (lines 44-51)
- `calculation_mapper.py` - Validation point (lines 400-402), SupplierCountry normalization pattern (lines 78-167)
- `seller_company_service.py` - Database service with SellerCompany dataclass
- `main.py` - build_calculation_inputs() function (lines 9268-9407), seller company data flow (lines 9663-9791)
- `CLAUDE.md` - Calculation engine modification prohibition

---

## Summary

**Root Cause**: Hardcoded SellerCompany enum expects exact string matches, but database stores company names with different formatting.

**Immediate Fix**: Rename database values to match enum expectations (user's preferred approach from prior discussion).

**Long-term Consideration**: If more companies are added frequently, consider adding normalization mapping in main.py following the established pattern from SupplierCountry.
