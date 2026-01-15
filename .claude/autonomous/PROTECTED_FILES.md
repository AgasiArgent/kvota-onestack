# Protected Files - DO NOT MODIFY

## Overview

These files contain critical business logic that has been verified against external reference data (Excel). Modifying them without explicit user approval could break validated calculations.

## Protected Files

### 1. `calculation_engine.py`

**Purpose:** Core calculation engine implementing 13-phase quotation calculation logic

**Why Protected:**
- Contains complex financial formulas validated against Excel reference
- Any change could cascade into incorrect pricing for clients
- Has been tested with `test_calculation.py` achieving ~67% match rate
- The remaining discrepancies are known and documented

**What it does:**
- Converts currencies using exchange rates
- Calculates purchase prices with discounts
- Computes logistics costs per leg
- Applies customs duties and taxes
- Calculates financing costs (advance payments, credit)
- Generates final pricing with VAT

**If bug appears related to this file:**
1. Check if issue is in `calculation_mapper.py` (CAN be modified)
2. Check if issue is in calling code (main.py routes)
3. If truly in calculation_engine.py, mark bug as "stuck - requires calc engine review"

---

### 2. `calculation_models.py`

**Purpose:** Data models (dataclasses) for calculation engine inputs and outputs

**Why Protected:**
- Defines the contract between calculation engine and rest of app
- Changing fields could break calculation engine
- Enums define business-critical values (currencies, incoterms, etc.)

**Key models:**
- `QuoteCalculationInput` - All inputs for calculation
- `ProductCalculationResult` - Output per product
- `QuoteCalculationResult` - Output for entire quote
- `Currency`, `SupplierCountry`, `Incoterms`, `DMFeeType` - Enums

---

## Files That CAN Be Modified

### `calculation_mapper.py`

**Purpose:** Maps UI/database data to calculation engine inputs

**Why NOT protected:**
- This is the "glue" between app and calculation engine
- Bugs here are typically mapping issues, not calculation logic
- Safe to modify as long as calculation_models contracts are respected

**Common fixes:**
- Wrong field mapping from quote_items
- Missing currency conversions before calling engine
- Incorrect default values

---

## Testing the Calculation Engine

The calculation engine has its own test files:

- `test_calculation.py` - Main test comparing against Excel reference
- `test_excel_comparison.py` - Additional Excel validation

**Current Status (as of init):**
- 66.7% pass rate (16/24 comparisons)
- Known discrepancies in logistics and VAT calculations
- These are NOT bugs to fix - they may represent differences from Excel reference

---

## How This Affects Testing Loop

When the testing loop encounters a failure:

1. **Check file location** - Is it in a protected file?
2. **If protected** - Mark as "stuck" with reason "protected file - calc engine"
3. **If NOT protected** - Attempt fix normally

The testing loop configuration in `testing-loop.json` includes:

```json
{
  "protected_files": [
    "calculation_engine.py",
    "calculation_models.py"
  ],
  "protected_files_note": "NEVER modify these files..."
}
```

---

## When to Unprotect

These files should only be modified when:

1. User explicitly requests calculation engine changes
2. New Excel reference data is provided for validation
3. Business requirements change (new fee types, currencies, etc.)
4. A session is dedicated specifically to calculation engine work

In such cases, the user should:
1. Remove files from `protected_files` list in testing-loop.json
2. Run calculation tests after each change
3. Re-add to protected list when work is complete
