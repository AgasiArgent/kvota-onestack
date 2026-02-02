# Code Inspection Report

**Date**: 2026-02-02 15:50
**Scope**: Procurement Price Save Workflow - Bug Analysis
**Inspector**: code-inspector agent
**Previous Reports Reviewed**: `code-inspection-2026-02-01-seller-company-validation.md`

## Executive Summary

The procurement price save workflow has **3 interconnected bugs** that form a data loss chain: (1) Python's `or ''` operator converts price `0` to empty string when rendering, (2) JavaScript's truthy check treats empty string and `0` as falsy and sends `null`, (3) Backend validation rejects prices ≤0 as "missing". Additionally, the customs page is missing the critical `hot.deselectCell()` fix that procurement has, risking the same "uncommitted cell edit" data loss issue.

## Critical Findings (Immediate Attention)

### Finding 1: Python `or ''` Converts Valid Zero Price to Empty String

**Severity**: Critical
**Location**: `main.py:14015`
**Pattern**: Incorrect Falsy Handling

**Current Code**:
```python
'price': item.get('purchase_price_original') or '',
```

**Problem**:
- If `purchase_price_original = 0` (valid zero price), Python evaluates `0 or ''` → `''` (empty string)
- If `purchase_price_original = None`, result is also `''`
- Both cases become indistinguishable in the frontend

**Data Flow**:
```
DB: purchase_price_original = 0
  ↓
Python: item.get('purchase_price_original') or ''
  → 0 or '' → '' (WRONG!)
  ↓
JSON: 'price': ''
  ↓
Handsontable renders empty cell
```

**Proposed Solution**:
```python
# Option A: Explicit None check
'price': item.get('purchase_price_original') if item.get('purchase_price_original') is not None else '',

# Option B: Convert to string directly (preserves 0)
'price': str(item.get('purchase_price_original')) if item.get('purchase_price_original') is not None else '',

# Option C: More defensive
'price': item.get('purchase_price_original', '') if item.get('purchase_price_original') not in [None, ''] else '',
```

**Risk Assessment**: HIGH - Zero prices cannot be displayed correctly, users cannot see/edit them
**Effort Estimate**: Small (1 line change)

---

### Finding 2: JavaScript Truthy Check Converts Valid Prices to Null

**Severity**: Critical
**Location**: `main.py:14738` (embedded JS)
**Pattern**: Incorrect Falsy Handling

**Current Code**:
```javascript
purchase_price_original: row.price ? parseFloat(row.price) : null,
```

**Problem**:
- `row.price = 0` → `0 ? parseFloat(0) : null` → `null` (WRONG!)
- `row.price = "0"` → `"0" ? parseFloat("0") : null` → `0` (correct, truthy string)
- `row.price = ""` → `"" ? parseFloat("") : null` → `null` (correct)
- `row.price = "123"` → `123` (correct)

The issue is numeric `0` from the data object is falsy in JavaScript.

**Proposed Solution**:
```javascript
// Option A: Check for explicit empty/undefined/null
purchase_price_original: (row.price !== '' && row.price !== null && row.price !== undefined)
    ? parseFloat(row.price)
    : null,

// Option B: Check type and value separately
purchase_price_original: (typeof row.price === 'number' || (typeof row.price === 'string' && row.price.trim() !== ''))
    ? parseFloat(row.price)
    : null,

// Option C: Simple explicit check for meaningful value
purchase_price_original: row.price !== '' && row.price != null ? parseFloat(row.price) : null,
```

**Risk Assessment**: HIGH - Valid zero prices are converted to null and not saved
**Effort Estimate**: Small (1 line change)

---

### Finding 3: Validation Rejects Zero Price as Invalid

**Severity**: High
**Location**: `main.py:15225`
**Pattern**: Incorrect Business Logic

**Current Code**:
```python
has_price = item.get("purchase_price_original") and float(item.get("purchase_price_original", 0)) > 0
```

**Problem**:
- `purchase_price_original = 0` → `0 and float(0) > 0` → `0 and False` → `False` (falsy short-circuit)
- `purchase_price_original = 0.01` → `0.01 and True` → `True` (correct)
- `purchase_price_original = None` → `None and ...` → `None` → `False` (correct)

This validation explicitly requires price > 0, which may or may not be intentional business logic.

**Business Question**: Can items have a valid price of $0 (free samples, promotional items)?

**If Zero Price Should Be Valid**:
```python
has_price = item.get("purchase_price_original") is not None and float(item.get("purchase_price_original", 0)) >= 0
```

**If Zero Price Is Intentionally Invalid** (current behavior):
- Document this in the codebase
- Add user-facing message explaining why 0 is not accepted

**Risk Assessment**: Medium - Depends on business requirements
**Effort Estimate**: Small

---

### Finding 4: Customs Page Missing `deselectCell()` - Data Loss Risk

**Severity**: High
**Location**: `main.py:17725-17756`
**Pattern**: Inconsistent Pattern Application

**Procurement Page (CORRECT)**:
```javascript
// Line 14727-14729
window.saveAllChanges = function(showAlert) {
    if (!hot) return Promise.resolve({ success: true });
    // IMPORTANT: Finish any active cell edit before reading data
    // Without this, typing a value and clicking Save/Complete won't include the current edit
    hot.deselectCell();  // ← PRESENT
    var sourceData = hot.getSourceData();
```

**Customs Page (MISSING)**:
```javascript
// Line 17725-17728
window.saveCustomsItems = function() {
    if (!hot) return Promise.resolve({ success: true });
    // ← MISSING hot.deselectCell()
    var sourceData = hot.getSourceData();
```

**Quote Items Page (ALSO MISSING)**:
```javascript
// Line 7768-7769
function saveAllItems() {
    var sourceData = hot.getSourceData();  // ← MISSING hot.deselectCell()
```

**Problem**: Without `deselectCell()`, if user is actively editing a cell and clicks Save/Submit:
1. Cell editor still has focus
2. Typed value is in the editor, NOT in the source data
3. `getSourceData()` returns the OLD value
4. New value is lost

**User Experience**: "I typed a value, clicked Save, but my value wasn't saved!"

**Proposed Solution** - Add to customs page:
```javascript
window.saveCustomsItems = function() {
    if (!hot) return Promise.resolve({ success: true });
    hot.deselectCell();  // ADD THIS LINE
    var sourceData = hot.getSourceData();
```

**Proposed Solution** - Add to quote items page:
```javascript
function saveAllItems() {
    hot.deselectCell();  // ADD THIS LINE
    var sourceData = hot.getSourceData();
```

**Risk Assessment**: HIGH - Active data loss bug affecting customs and quote items pages
**Effort Estimate**: Small (2 lines total)

---

## Moderate Findings (Plan to Address)

### Finding 5: N+1 Query Pattern in Bulk Update

**Severity**: Medium
**Location**: `main.py:15432-15456`
**Pattern**: Performance Anti-Pattern

**Current Code**:
```python
for item in items:
    # ... validation ...
    if update_data:
        supabase.table("quote_items") \
            .update(update_data) \
            .eq("id", item_id) \
            .execute()  # ← One query per item
        updated += 1
```

**Problem**: For N items, makes N database queries instead of 1 batch query.

**Impact**:
- 50 items = 50 queries (~500ms+ latency)
- Acceptable for small datasets but will degrade with scale

**Proposed Solution** (future optimization):
```python
# Batch approach using Supabase RPC or transaction
# For now, acceptable for typical item counts < 20
```

**Risk Assessment**: Low (performance, not correctness)
**Effort Estimate**: Medium

---

### Finding 6: Inconsistent `production_time` Handling

**Severity**: Low
**Location**: `main.py:14016, 14739`
**Pattern**: Same Issue as Price

**Current Code** (Python):
```python
'production_time': item.get('production_time_days') or '',  # Same 0→'' bug
```

**Current Code** (JavaScript):
```javascript
production_time_days: row.production_time ? parseInt(row.production_time) : null,  // Same 0→null bug
```

**Problem**: If production time is 0 days (immediate delivery), same bugs apply.

**Effort Estimate**: Small (apply same fixes as price)

---

## Positive Patterns Observed

1. **Procurement page has `deselectCell()`** - Someone already identified and fixed this issue for procurement. The fix just needs to be propagated.

2. **Clear comments in code** - Line 14727-14728 has excellent comments explaining why `deselectCell()` is needed.

3. **Promise chaining for sequential operations** - `completeInvoice()` properly waits for `saveAllChanges()` before proceeding.

4. **Consistent API patterns** - All bulk update endpoints follow similar structure.

---

## Comparison with Previous Inspections

**2026-02-01 Seller Company Validation Report**:
- Found pattern: Database values don't match expected code values
- Solution pattern: Normalization mapping in main.py

**This Report**:
- Similar root cause: Implicit type coercion causing data mismatches
- Similar solution: Explicit value checks instead of truthy/falsy shortcuts

**Trend**: Codebase has multiple instances of relying on JavaScript/Python falsy semantics where explicit null/zero checks are needed.

---

## Recommended Action Plan

### Immediate (Fix Today)

1. **Add `deselectCell()` to customs page** (Line 17727)
   - Risk: HIGH (active data loss)
   - Effort: 1 line

2. **Add `deselectCell()` to quote items page** (Line 7769)
   - Risk: HIGH (active data loss)
   - Effort: 1 line

3. **Fix Python `or ''` for price** (Line 14015)
   - Risk: HIGH (zero prices lost)
   - Effort: 1 line

4. **Fix JavaScript truthy check for price** (Line 14738)
   - Risk: HIGH (zero prices become null)
   - Effort: 1 line

### Short-term (This Week)

5. **Fix same patterns for production_time** (Lines 14016, 14739)
6. **Clarify business rule for zero prices** (Line 15225)
   - Is `price > 0` intentional or should it be `price >= 0`?

### Later (When Nearby)

7. **Consider batch update optimization** (Lines 15432-15456)
8. **Audit other Handsontable instances** for similar patterns

---

## Files Inspected

- `main.py:14005-14022` - Items data preparation for Handsontable
- `main.py:14725-14761` - `saveAllChanges()` JavaScript function
- `main.py:15210-15250` - Invoice completion validation
- `main.py:15425-15461` - Bulk update API endpoint
- `main.py:17722-17760` - Customs page `saveCustomsItems()` function
- `main.py:7765-7800` - Quote items page `saveAllItems()` function

---

## Bug Chain Visualization

```
USER ENTERS PRICE "0"
        ↓
[BUG 1] Python: 0 or '' → ''
        ↓
JSON sent to browser: {price: ''}
        ↓
USER EDITS CELL, TYPES "150", CLICKS SAVE
        ↓
[BUG 4] Missing deselectCell() - value might not commit
        ↓
[BUG 2] JS: row.price ? parseFloat : null
         If row.price is '' or 0 → sends null
        ↓
API receives: {purchase_price_original: null}
        ↓
[Line 15439] null is not None → FALSE → not updated
        ↓
DATABASE STILL HAS NULL (or old value)
        ↓
User clicks "Complete Invoice"
        ↓
[BUG 3] Validation: price > 0 → FALSE
        ↓
ERROR: "Не все позиции оценены"
```

**Fix all 4 points to break the bug chain.**
