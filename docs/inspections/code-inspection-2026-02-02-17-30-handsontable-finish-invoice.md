# Code Inspection Report

**Date**: 2026-02-02 17:30
**Scope**: Handsontable Finish Invoice Bug - Prices Not Saving
**Inspector**: code-inspector agent
**Previous Reports Reviewed**: `code-inspection-2026-02-02-15-50-procurement-price-save.md`

## Executive Summary

The user reports that when clicking "Finish Invoice" on the procurement page, **only the invoice number saves**, but product prices and other data from Handsontable are lost. After analyzing the complete data flow, I've identified the **root cause**: the invoice edit modal uses a **separate form submission** that only saves invoice-level fields (invoice_number, currency, weight, volume) - it does **NOT call `saveAllChanges()`** to save item-level Handsontable data.

## Critical Findings (Immediate Attention)

### Finding 1: Invoice Edit Form Does Not Save Handsontable Data

**Severity**: Critical
**Location**: `main.py:15062-15118` (backend) and the edit invoice modal form
**Pattern**: Workflow Gap / Missing Save Step

**The Bug**:

When user:
1. Enters prices in Handsontable (price, production_time, etc.)
2. Opens invoice edit modal and changes invoice_number
3. Clicks "Сохранить" (Save) in the modal

**What happens**:
- Modal form POSTs to `/api/procurement/{quote_id}/invoices/update`
- This endpoint ONLY saves invoice fields: `invoice_number`, `currency`, `total_weight_kg`, `total_volume_m3`
- **Item prices from Handsontable are NOT saved** because `saveAllChanges()` is never called

**Evidence from code**:

**Backend endpoint (lines 15062-15118)**:
```python
@rt("/api/procurement/{quote_id}/invoices/update", methods=["PATCH"])
async def api_update_invoice(quote_id: str, session, request):
    # ...
    update_data = {}
    invoice_number = form.get("invoice_number")
    if invoice_number:
        update_data["invoice_number"] = invoice_number.strip()
    # ... only updates invoice table, NOT quote_items!
```

**The modal form** calls `submitEditInvoiceForm()` which does NOT include `saveAllChanges()`.

**Compare with "Complete Invoice" button** (lines 14816-14847):
```javascript
window.completeInvoice = function(invoiceId) {{
    // First save all changes  <-- THIS CORRECTLY SAVES HANDSONTABLE
    window.saveAllChanges(false)
        .then(function(saveResult) {{
            // Then complete the invoice
            return fetch('/api/procurement/' + quoteId + '/invoices/' + invoiceId + '/complete', ...)
        }})
```

**The "Complete Invoice" workflow correctly calls `saveAllChanges()` first**, but the invoice edit form submission does NOT.

---

### Finding 2: "Сохранить" Button Below Table vs Modal "Сохранить" - User Confusion

**Severity**: High
**Pattern**: UX Confusion

**Problem**: There are TWO "Сохранить" buttons:

1. **Main page "Сохранить"** button (below Handsontable) - calls `saveAllChanges()` → saves item prices to `quote_items`
2. **Invoice edit modal "Сохранить"** button - submits form → saves only invoice fields to `invoices`

**User likely expects** that editing the invoice and clicking Save in the modal will save BOTH:
- Invoice-level changes (number, currency, weight)
- Item-level changes (prices, production times)

**But only invoice-level changes are saved.**

---

### Finding 3: HTMX Form Bypasses JavaScript - Root Cause Confirmed

**Severity**: Critical
**Location**: `main.py:14555-14559`
**Pattern**: HTMX Direct Submission Bypasses JS Save

**The actual code**:
```python
id="edit-invoice-form",
hx_patch=f"/api/procurement/{quote_id}/invoices/update",
hx_target="#invoices-list",
hx_swap="innerHTML",
hx_on="htmx:afterRequest: if(event.detail.successful && event.detail.requestConfig.verb === 'patch') closeEditInvoiceModal();"
```

**Problem**: The form uses **HTMX `hx_patch`** to submit directly to the backend. HTMX submissions **bypass any JavaScript onclick handlers**. There is NO mechanism to call `saveAllChanges()` before the HTMX request.

**Fix Options**:

**Option A (Recommended): Use `hx_on` to call `saveAllChanges()` before request**:
```python
hx_on="""htmx:beforeRequest:
    // Save Handsontable data first
    if (window.hot) window.hot.deselectCell();
    // Note: HTMX doesn't wait for async - need different approach
"""
```

**Option B: Replace HTMX with JavaScript form handler**:
```python
# Remove hx_patch, use onclick instead
btn("Сохранить", variant="primary", type="button", onclick="submitEditInvoiceWithSave()"),
```

Then add JavaScript:
```javascript
window.submitEditInvoiceWithSave = function() {
    saveAllChanges(false).then(function(result) {
        if (!result.success) {
            alert('Ошибка сохранения');
            return;
        }
        // Now submit the form via fetch
        var form = document.getElementById('edit-invoice-form');
        var formData = new FormData(form);
        fetch('/api/procurement/' + quoteId + '/invoices/update', {
            method: 'PATCH',
            body: formData
        }).then(r => r.json()).then(data => {
            if (data.success) {
                closeEditInvoiceModal();
                location.reload();
            }
        });
    });
};
```

**Option C: Save on modal open (defensive)**:
```javascript
window.openEditInvoiceModal = function(invoiceId) {
    // Save first, then open modal
    saveAllChanges(false).then(function() {
        // ... existing modal open code
    });
};
```

---

## The Complete Workflow (Expected vs Actual)

### Expected Workflow
```
USER ENTERS PRICES IN HANDSONTABLE
        ↓
USER CLICKS INVOICE → EDIT MODAL OPENS
        ↓
USER UPDATES INVOICE NUMBER
        ↓
USER CLICKS "СОХРАНИТЬ" IN MODAL
        ↓
[EXPECTED] Both saved:
  - Invoice fields → /api/procurement/{quote_id}/invoices/update
  - Item prices → /api/procurement/{quote_id}/items/bulk
        ↓
DATA PERSISTED CORRECTLY
```

### Actual Workflow (BUG)
```
USER ENTERS PRICES IN HANDSONTABLE
        ↓
USER CLICKS INVOICE → EDIT MODAL OPENS
        ↓
USER UPDATES INVOICE NUMBER
        ↓
USER CLICKS "СОХРАНИТЬ" IN MODAL
        ↓
[ACTUAL] Only invoice fields saved:
  - Invoice fields → /api/procurement/{quote_id}/invoices/update ✓
  - Item prices → NEVER CALLED ✗
        ↓
PAGE RELOADS → HANDSONTABLE DATA LOST!
```

---

## Recommended Fix

### Option A: Call `saveAllChanges()` Before Invoice Update (Recommended)

Modify the invoice edit form submission to first save Handsontable data:

```javascript
window.submitEditInvoiceForm = function() {
    // First save Handsontable changes
    window.saveAllChanges(false)
        .then(function(saveResult) {
            if (!saveResult.success) {
                alert('Ошибка сохранения позиций: ' + (saveResult.error || 'Неизвестная ошибка'));
                return;
            }
            // Then submit the invoice form
            var form = document.getElementById('edit-invoice-form');
            // ... existing form submission code
        });
};
```

### Option B: Auto-Save Handsontable on Page Unload/Modal Open

Add `beforeunload` or modal open hook to save changes:

```javascript
window.openEditInvoiceModal = function(invoiceId) {
    // Save changes before opening modal
    window.saveAllChanges(false).then(function() {
        // ... existing modal open code
    });
};
```

### Option C: Disable Invoice Edit Until Items Saved

Show a warning if there are unsaved Handsontable changes when user tries to open modal.

---

## Testing Checklist

After fix, verify:

1. [ ] Enter price in Handsontable cell
2. [ ] Open invoice edit modal
3. [ ] Change invoice number
4. [ ] Click Save in modal
5. [ ] Reload page
6. [ ] **Verify**: Both invoice number AND prices are saved

---

## Files to Modify

1. **`main.py`** - Find the `submitEditInvoiceForm` function or modal form handler
   - Add `saveAllChanges()` call before submitting invoice update

2. **Consider also modifying `openEditInvoiceModal`** to save changes proactively

---

## Positive Patterns Observed

1. **`completeInvoice()` is correct** - It properly chains `saveAllChanges()` before completing
2. **`completeProcurement()` is correct** - Same pattern
3. **`saveAllChanges()` has `deselectCell()`** - Fix from previous inspection is in place

---

## Files Inspected

- `main.py:14570-14763` - JavaScript functions for procurement workspace
- `main.py:14816-14867` - `completeInvoice()` and `reopenInvoice()` functions
- `main.py:15062-15118` - `api_update_invoice()` endpoint
- `main.py:14880-14950` - Handsontable initialization

---

## Summary

**Root Cause**: The invoice edit modal saves only invoice-level fields. It does NOT call `saveAllChanges()` to persist Handsontable item data before submitting/reloading.

**Impact**: User loses all price/production_time edits when saving invoice changes.

**Fix**: Add `saveAllChanges()` call to the invoice edit form submission flow.
