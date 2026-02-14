# Browser Test Report

**Timestamp:** 2026-02-14T17:06:00Z
**Session:** 2026-02-14 #1
**Base URL:** https://kvotaflow.ru
**Overall:** 1/3 PASS

## Task: [86afdkuux] Verify quote_items.name bug fixed on production
**URL:** /procurement/482c0486-cebe-410e-a670-364a32feecb4
**Status:** FAIL

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Login as admin | PASS | Logged in as admin@test.kvota.ru |
| 2 | Navigate to quote with items in procurement stage | PASS | Opened Q-202602-0092 (status: Закупки, customer: АО Экокожа) |
| 3 | Open procurement tab | PASS | Procurement page loaded at /procurement/482c0486-cebe-410e-a670-364a32feecb4 |
| 4 | Click "Новый" to create new invoice | FAIL | Alert dialog: "Таблица не инициализирована" — Handsontable not initialized (separate bug) |
| 5 | Click "Редактировать" on existing invoice | PASS | Edit modal opened with invoice INV-01-Q-202602-0092, shows 3 items with names correctly |
| 6 | Save edited invoice (no changes) | **FAIL** | **Alert: `{'message': 'column quote_items.name does not exist', 'code': '42703', 'hint': None, 'details': None}`** |
| 7 | Check /supplier-invoices page | PASS | Page loaded correctly, 27 invoices displayed, no errors |

**Console Errors:**
- `TypeError: Cannot read properties of null (reading 'style')` — Handsontable renderer error on procurement page load
- `Failed to load resource: 500` — on `/api/procurement/.../invoices/update` when saving invoice
- `Failed to load resource: 404` — favicon.ico (minor)

**Screenshots:** bug-verify-procurement-page.png, bug-verify-edit-invoice-modal.png, bug-verify-supplier-invoices.png

---

## Bug Details

### BUG 1 (Primary): `column quote_items.name does not exist`
- **Trigger:** Saving an edited procurement invoice (clicking "Сохранить" in edit invoice modal)
- **Error:** `{'message': 'column quote_items.name does not exist', 'code': '42703', 'hint': None, 'details': None}`
- **HTTP:** POST to `/api/procurement/482c0486-cebe-410e-a670-364a32feecb4/invoices/update` returns **500**
- **Root cause:** Server-side code references `quote_items.name` column which does not exist in the database (PostgreSQL error code 42703 = undefined_column)
- **Impact:** Cannot save any edits to procurement invoices
- **Status:** BUG IS STILL PRESENT ON PRODUCTION

### BUG 2 (Secondary): Handsontable "Таблица не инициализирована"
- **Trigger:** Clicking "Новый" button in ИНВОЙСЫ section on procurement page
- **Error:** JavaScript alert "Таблица не инициализирована"
- **Console:** `TypeError: Cannot read properties of null (reading 'style')` in handsontable renderer
- **Impact:** Cannot create new invoices via the "Новый" button
- **Note:** This is a separate JS initialization bug, not related to the quote_items.name DB error

---

## Console Errors (all tasks)
1. `TypeError: Cannot read properties of null (reading 'style')` — Handsontable renderer on procurement page
2. `500 on /api/procurement/.../invoices/update` — quote_items.name column error
3. `404 on /favicon.ico` — minor, missing favicon

## Summary for Terminal 1
PASS: /supplier-invoices page loads correctly
FAIL: [86afdkuux] — `column quote_items.name does not exist` error still present when saving edited invoice (HTTP 500 on `/api/procurement/.../invoices/update`)
ACTION: Fix server-side code that references `quote_items.name` — likely needs to be `quote_items.product_name` or similar. Also fix Handsontable initialization for "Новый" invoice button.
