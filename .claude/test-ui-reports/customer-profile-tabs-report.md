# E2E Bug Reproduction Report: Customer Profile Tabs

**Date:** 2026-02-06
**Tester:** e2e-tester (code analysis - browser tools unavailable)
**Page:** /customers/{customer_id}

---

## Summary
- Tabs analyzed: 10 (Общая, Адреса, Контакты, Договоры, КП, Спецификации, Позиции, Ещё, Звонки, Встречи)
- Bugs found: 3 (1 critical routing bug, 2 broken link bugs)
- Code issues: 0 service-layer issues found
- HTMX tab switching: Looks correct (hx_get + hx_target + switchTab JS)

---

## Test Results

| Tab | Status | Notes |
|-----|--------|-------|
| Общая (general) | PASS | Loads stats, contacts/contracts preview, quotes/specs tables |
| Адреса (addresses) | PASS | Shows legal, actual, postal addresses + warehouse list with add/delete |
| Контакты (contacts) | PASS | Table with inline editing, add button works |
| Договоры (contracts) | FAIL | "Добавить" button links to wrong URL; "Просмотр" links to wrong URL |
| КП (quotes) | PASS | Loads quotes with sums, profits, status badges |
| Спецификации (specifications) | PASS | Loads specs via quote relationship |
| Позиции (requested_items) | PASS | Aggregated items with product details |
| Ещё (additional) | PASS | Notes with inline editing |
| Звонки (calls) | PASS | Placeholder page |
| Встречи (meetings) | PASS | Placeholder page |

---

## Bug #1: Contracts tab - "Добавить" button has wrong URL

**Severity:** High

**URL:** /customers/{customer_id}?tab=contracts

**Location in code:** `main.py:31133`

**Steps to Reproduce:**
1. Navigate to any customer profile
2. Click "Договоры" tab
3. Click "+ Добавить" button

**Expected:** Opens new contract form for this customer
**Actual:** 404 or route not found error

**Root Cause:**
The "Добавить" button links to:
```
/customers/{customer_id}/contracts/new
```
But the actual route is defined as:
```
/customer-contracts/new?customer_id={customer_id}
```
(See `main.py:33245` for the route definition)

**Fix:** Change line 31133 from:
```python
href=f"/customers/{customer_id}/contracts/new",
```
to:
```python
href=f"/customer-contracts/new?customer_id={customer_id}",
```

---

## Bug #2: Contracts tab - "Просмотр" (view) link has wrong URL

**Severity:** Medium

**URL:** /customers/{customer_id}?tab=contracts

**Location in code:** `main.py:31126`

**Steps to Reproduce:**
1. Navigate to a customer profile that has contracts
2. Click "Договоры" tab
3. Click the file icon (Просмотр) for any contract

**Expected:** Opens contract detail page
**Actual:** 404 or route not found

**Root Cause:**
The view link uses:
```python
href=f"/contracts/{contract['id']}"
```
But the actual route is:
```python
@rt("/customer-contracts/{contract_id}")  # main.py:33440
```

**Fix:** Change line 31126 from:
```python
A(icon("file-text", size=16), href=f"/contracts/{contract['id']}", title="Просмотр")
```
to:
```python
A(icon("file-text", size=16), href=f"/customer-contracts/{contract['id']}", title="Просмотр")
```

---

## Bug #3 (Potential): Specifications tab - PostgREST relationship query

**Severity:** Low (may not manifest currently)

**Location in code:** `services/customer_service.py:1594`

**Details:**
The query `supabase.table("specifications").select("*, quotes(idn, customer_id)")` uses a PostgREST relationship join. If there are multiple FK relationships between `specifications` and `quotes` tables, this could cause an "ambiguous relationship" error. This was previously a known issue (see git commit `be11b83` "Fix PostgREST ambiguous relationship for quote_versions").

**Current behavior:** Need to verify in production. If the `specifications` table has only one FK to `quotes`, this works fine.

---

## Tabs That Work Correctly

### КП tab (quotes) - main.py:31160-31230
- Calls `get_customer_quotes(customer_id)` from customer_service.py
- Query: Gets quotes by customer_id, then fetches quote_items for sum/profit calculation
- Renders table with IDN, sum, profit, date, status
- "Создать КП" button correctly links to `/quotes/new?customer_id={customer_id}`

### Спецификации tab (specifications) - main.py:31232-31300
- Calls `get_customer_specifications(customer_id)` from customer_service.py
- Query: Gets quotes by customer_id, then specifications by quote_ids, then items for sums
- Renders table with spec number, quote IDN, sum, profit, date, status

### Позиции tab (requested_items) - main.py:31302-31370
- Calls `get_customer_requested_items(customer_id)` from customer_service.py
- Query: Aggregates all quote_items across all customer's quotes
- Groups by product_id, tracks brands, quantities, prices, sold status

### Адреса tab (addresses) - main.py:30991-31034
- Uses inline editing via `_render_field_display()` for legal, actual, postal addresses
- Warehouse addresses: dynamic add/delete with HTMX
- Postal address logic: shows "Совпадает с фактическим адресом" if same

### HTMX Tab Switching Mechanism
- `tab_nav()` function (main.py:3651-3685) renders DaisyUI tabs with hx_get, hx_target, hx_push_url
- `switchTab()` JS function (main.py:2927-2935) handles CSS class toggling
- Server returns only tab content for HTMX requests (main.py:31422-31423)

---

## Screenshots
**Note:** Browser testing tools (Claude-in-Chrome MCP) were not available in this session. All findings are from code analysis. Browser verification recommended.

---

## Recommendations
1. Fix contracts tab URLs (Bug #1 and #2) - straightforward 2-line fix
2. Consider adding a route alias for `/customers/{customer_id}/contracts/new` -> redirect to `/customer-contracts/new?customer_id={customer_id}` for consistency
3. Verify PostgREST specification query in production (Bug #3)
