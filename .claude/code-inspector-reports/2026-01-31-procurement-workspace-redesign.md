# Code Inspection Report: Procurement Workspace Redesign

**Date:** 2026-01-31
**Feature:** Invoice-First Procurement Workflow
**Files Analyzed:** `main.py` (lines 11722-12937)
**Scope:** Single-page procurement design with Handsontable, invoice CRUD APIs

---

## Executive Summary

The procurement workspace redesign successfully implements the planned invoice-first UX pattern. The code is functional but has several opportunities for improvement in error handling, security, and maintainability.

**Overall Quality:** 🟡 Good with improvements needed

| Category | Rating | Notes |
|----------|--------|-------|
| Functionality | ✅ Good | All planned features implemented |
| Security | 🟡 Needs Work | Missing org_id validation on some endpoints |
| Error Handling | 🟡 Needs Work | Bare except clauses, inconsistent error responses |
| Maintainability | 🟡 Needs Work | Large inline JavaScript, some duplication |
| Performance | 🟡 Acceptable | N+1 potential in bulk update loop |

---

## Critical Issues (Fix Immediately)

### 1. Missing Organization Validation on Invoice Deletion

**Location:** `main.py:12646-12673`

```python
@rt("/api/procurement/{quote_id}/invoices/{invoice_id}", methods=["DELETE"])
async def api_delete_invoice(quote_id: str, invoice_id: str, session):
    # ...
    # PROBLEM: Deletes invoice without verifying it belongs to user's org
    supabase.table("invoices").delete().eq("id", invoice_id).execute()
```

**Risk:** Any authenticated procurement user could delete invoices from other organizations.

**Fix:**
```python
# Verify invoice belongs to quote in user's org
quote_result = supabase.table("quotes") \
    .select("id") \
    .eq("id", quote_id) \
    .eq("organization_id", org_id) \
    .single() \
    .execute()

if not quote_result.data:
    return JSONResponse({"success": False, "error": "Quote not found"}, status_code=404)

# Then delete
supabase.table("invoices").delete().eq("id", invoice_id).eq("quote_id", quote_id).execute()
```

### 2. Missing Organization Validation on Item Assignment

**Location:** `main.py:12676-12720`

```python
@rt("/api/procurement/{quote_id}/items/assign", methods=["POST"])
async def api_assign_items_to_invoice(quote_id: str, session, request):
    # PROBLEM: No org_id check - could assign items across orgs
    supabase.table("quote_items") \
        .update({"invoice_id": invoice_id, "purchase_currency": currency}) \
        .in_("id", item_ids) \
        .eq("quote_id", quote_id)  # Only checks quote_id, not org
        .execute()
```

**Fix:** Add organization validation before update.

### 3. Missing Organization Validation on Bulk Update

**Location:** `main.py:12723-12776`

Same pattern - updates items without verifying organization ownership.

---

## High Priority Issues

### 4. Bare Except Clauses

**Locations:** `main.py:12691`, `main.py:12737`

```python
try:
    data = json.loads(body)
except:  # BAD: Catches all exceptions including KeyboardInterrupt
    return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
```

**Fix:**
```python
except json.JSONDecodeError:
    return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)
```

### 5. Race Condition in Complete Procurement

**Location:** `main.py:12387-12410` (JavaScript)

```javascript
window.completeProcurement = function() {{
    // First save all changes
    window.saveAllChanges();

    // Then complete
    setTimeout(function() {{  // Race condition!
        fetch('/api/procurement/' + quoteId + '/complete', ...
```

**Problem:** Using `setTimeout(500)` is unreliable. The save request might not complete before the complete request fires.

**Fix:** Use Promise chaining:
```javascript
window.completeProcurement = async function() {{
    if (!confirm('Завершить закупку?')) return;

    try {{
        await window.saveAllChanges();  // Make this async and await it
        const response = await fetch('/api/procurement/' + quoteId + '/complete', ...);
        // Handle response
    }} catch(e) {{
        alert('Ошибка: ' + e.message);
    }}
}};
```

### 6. N+1 Query Pattern in Bulk Update

**Location:** `main.py:12748-12771`

```python
for item in items:  # Iterates each item
    # ...
    supabase.table("quote_items") \
        .update(update_data) \
        .eq("id", item_id) \
        .execute()  # Separate query per item!
```

**Problem:** With 50-60 items, this creates 50-60 database queries.

**Fix:** Use batch update or RPC:
```python
# Option 1: PostgreSQL function for batch update
# Option 2: Collect updates and use upsert
# Option 3: Use supabase-py bulk operations if available
```

---

## Medium Priority Issues

### 7. Large Inline JavaScript Block

**Location:** `main.py:12184-12505` (~320 lines of JS in Python string)

**Problem:** Hard to maintain, no syntax highlighting, no linting, hard to test.

**Recommendation:** Extract to `/static/js/procurement.js` and load with:
```python
Script(src="/static/js/procurement.js")
```

### 8. Duplicate Supplier/Buyer Fetching Logic

The code fetches supplier and buyer names in multiple places:
- `main.py:11902-11927` (GET route)
- `main.py:12867-12877` (render_invoices_list helper)

**Recommendation:** Create a helper function:
```python
async def get_supplier_buyer_maps(supabase, invoices):
    """Fetch supplier and buyer company names for invoices."""
    supplier_ids = list(set(inv.get("supplier_id") for inv in invoices if inv.get("supplier_id")))
    buyer_ids = list(set(inv.get("buyer_company_id") for inv in invoices if inv.get("buyer_company_id")))

    suppliers = {}
    if supplier_ids:
        result = supabase.table("suppliers").select("id, name").in_("id", supplier_ids).execute()
        suppliers = {s["id"]: s["name"] for s in result.data or []}

    buyers = {}
    if buyer_ids:
        result = supabase.table("buyer_companies").select("id, name").in_("id", buyer_ids).execute()
        buyers = {b["id"]: b["name"] for b in result.data or []}

    return suppliers, buyers
```

### 9. Magic Placeholder Weight Value

**Location:** `main.py:12572`

```python
"total_weight_kg": 0.001,  # Placeholder, will be updated
```

**Problem:** Database has constraint `CHECK (total_weight_kg > 0)`. Using 0.001 as a magic placeholder is confusing.

**Recommendation:** Either:
- Make weight nullable in migration
- Or use `None` and handle in UI as "не указан"

### 10. Hardcoded Country Options in Two Places

**Location:** JavaScript `main.py:12443` and likely in Python forms elsewhere

```javascript
var countryOptions = ['', 'RU', 'CN', 'TR', 'DE', 'US', 'IT', 'OTHER'];
```

**Recommendation:** Define countries in a single place and pass to both Python and JavaScript.

---

## Low Priority / Style Issues

### 11. Inconsistent Error Response Format

Some endpoints return `JSONResponse({"success": False, "error": "..."})` while others might return different shapes. Consider a consistent error response helper:

```python
def api_error(message: str, status_code: int = 400):
    return JSONResponse({"success": False, "error": message}, status_code=status_code)
```

### 12. Missing Docstrings on Some Functions

`render_invoices_list` has a docstring, but some inline functions in JavaScript lack comments explaining their purpose.

### 13. Console.log for Debugging

Ensure no `console.log` statements remain in production JavaScript. Add ESLint or similar if extracting to external JS file.

---

## Security Recommendations

1. **Add rate limiting** to API endpoints to prevent abuse
2. **Validate invoice_id format** (should be UUID) before database queries
3. **Audit log** for invoice creation/deletion for compliance
4. **CSRF protection** - verify requests come from legitimate forms

---

## Positive Observations

1. ✅ **Role-based access control** consistently applied with `user_has_any_role`
2. ✅ **Brand-based filtering** correctly filters items for procurement users
3. ✅ **HTMX integration** well-implemented for invoice list updates
4. ✅ **Handsontable configuration** clean with proper column types
5. ✅ **Workflow integration** properly calls `complete_procurement` for status transitions

---

## Recommended Actions

### Immediate (Before Next Deploy)
1. [ ] Fix missing org_id validation on DELETE/ASSIGN/BULK endpoints
2. [ ] Replace bare `except:` with specific exception types

### Short Term (This Week)
3. [ ] Fix race condition in completeProcurement JavaScript
4. [ ] Extract JavaScript to external file

### Medium Term (Next Sprint)
5. [ ] Optimize bulk update with batch query
6. [ ] Refactor duplicate supplier/buyer fetching
7. [ ] Make weight nullable or handle placeholder properly

---

## Testing Recommendations

Add integration tests for:
- [ ] Invoice CRUD with different organization contexts (security)
- [ ] Bulk item assignment with 100+ items (performance)
- [ ] Complete procurement with some items missing prices (validation)
- [ ] Concurrent invoice updates (race conditions)

---

*Generated by code-inspector skill*
