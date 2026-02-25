# Browser Test Report

**Timestamp:** 2026-02-11T02:45:00+03:00
**Session:** 2026-02-10 #1 (invoices revert + BUG-2 fix)
**Base URL:** https://kvotaflow.ru
**Tool:** Chrome DevTools MCP (Playwright unavailable — Chrome already running)
**Overall:** 6/6 PASS, 0/6 SKIP

---

## Task: [REVERT] Procurement invoice creation works

### TEST 1: Procurement page loads without errors
**URL:** /procurement/ba4a486f-d2cb-4356-8832-db9db3c54246 (Q-202602-0073)
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to procurement | PASS | "Закупки: Q-202602-0073" loads, 0 console errors |
| 2 | Invoice section visible | PASS | "ИНВОЙСЫ" section with "Инвойс #1" |
| 3 | Invoice details | PASS | 3 поз., Test Supplier Company → ООО "Закупки", USD, 150.0 кг, Σ 3,000.00 $ |
| 4 | Items table | PASS | Handsontable with 3 items, all assigned to invoice #1 |
| 5 | No server errors | PASS | No "column does not exist" or 500 errors |
| 6 | Console errors | PASS | 0 errors |

**Also checked:** /procurement/0203dc4e-a32f-474b-bbfc-25709000155b (Q-202602-0065)
- Loads correctly with Инвойс #1 (1 поз., Поставщик Китай → ООО "Закупки", USD, 1.0 кг, Σ 5,000.00 $)
- Invoice shows workflow status "→ Логистика"

### TEST 2: Create a new procurement invoice
**URL:** /procurement/d9942a7f-d6b0-4843-a283-51acd8e2ef86 (Q-202602-0076)
**Status:** PASS

Created a new quote Q-202602-0076 (Test Company E2E, RAD seller, Москва, Авто delivery) with 1 item (SKF 6205-2RS, qty 10), transferred to procurement, then created invoice.

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Create new quote Q-202602-0076 | PASS | Auto-created, filled client, seller, city, country, delivery method |
| 2 | Add item to quote | PASS | SKF / 6205-2RS / Подшипник шариковый 6205-2RS / qty 10 via Handsontable |
| 3 | Transfer to procurement | PASS | "Передать в закупки" → status changed to ЗАКУПКИ |
| 4 | Select item checkbox | PASS | Item checked, "1 выбрано" displayed |
| 5 | Click "Новый" invoice | PASS | Invoice creation form appeared with fields |
| 6 | Fill supplier | PASS | TST - Test Supplier Company (Германия) |
| 7 | Fill buyer company | PASS | ZAK - ООО "Закупки" (ИНН: 1234567890) |
| 8 | Fill country/currency/weight | PASS | DE (Германия), USD, 15 кг |
| 9 | Click "Создать" | PASS | Invoice created, no errors |
| 10 | Console errors | PASS | 0 errors |

### TEST 3: Invoice details are visible after creation
**URL:** /procurement/d9942a7f-d6b0-4843-a283-51acd8e2ef86 (Q-202602-0076)
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Invoice appears in list | PASS | "Инвойс #1" visible in ИНВОЙСЫ section |
| 2 | Item count | PASS | "1 поз." |
| 3 | Supplier → Buyer | PASS | "Test Supplier Company → ООО "Закупки"" |
| 4 | Currency and weight | PASS | "USD", "15.0 кг" |
| 5 | Action buttons | PASS | Редактировать, Назначить ↓, Завершить инвойс |
| 6 | Item assigned in table | PASS | ИНВОЙС column shows "#1" for the item |
| 7 | Progress updated | PASS | "| 1 назначено" (was "| 0 назначено") |
| 8 | Invoice in Finance tab | PASS | /finance?tab=invoices shows 23 records (was 22), includes Q-202602-0076 |
| 9 | Console errors | PASS | 0 errors |

---

## Task: [REVERT] Finance Инвойсы tab shows invoices from procurement

### TEST 4: Инвойсы tab loads and shows data
**URL:** /finance?tab=invoices
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to /finance | PASS | Page loads, 0 console errors |
| 2 | Инвойсы tab exists | PASS | 4 tabs: Рабочая зона, ERPS, Платежи, Инвойсы |
| 3 | Invoice count | PASS | "Итого записей: 22" — was 0 in previous test! |
| 4 | Table columns | PASS | №, НОМЕР ИНВОЙСА, ПОСТАВЩИК, ДАТА, СУММА, СТАТУС |
| 5 | Supplier names resolved | PASS | "Test Supplier Company", "Поставщик Китай", "SKF", "FAG", etc. (no UUIDs) |
| 6 | Date format | PASS | DD.MM.YYYY: "10.02.2026", "09.02.2026", "27.01.2026", etc. |
| 7 | Status column | PASS | Workflow statuses: "Закупка" (18), "Логистика" (4) |
| 8 | Summary footer | PASS | Totals by currency: CNY 19,000 / EUR 154,169 / RUB 40,000 / TRY 27,000 / USD 78,637 |
| 9 | Console errors | PASS | 0 errors |

**This is a major fix** — BUG-5 (two-table mismatch) is now resolved. The Инвойсы tab reads from the `invoices` table (same as procurement writes to).

---

## Task: [RETEST] BUG-2 Delivery city persists after save

### TEST 5: City autocomplete saves and persists
**URL:** /quotes/ba4a486f-d2cb-4356-8832-db9db3c54246
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to Q-202602-0073 | PASS | Page loads, 0 console errors |
| 2 | Find city input | PASS | `delivery-city-input` exists |
| 3 | `saveDeliveryCity` function exists | PASS | `typeof window.saveDeliveryCity === 'function'` → TRUE (was FALSE before!) |
| 4 | Type "Москва" | PASS | Input accepts value |
| 5 | Autocomplete works | PASS | No TypeError, 0 console errors |
| 6 | Blur triggers save | PASS | Change event dispatched, waited 3s |
| 7 | **Reload — city persisted** | **PASS** | `input.value === "Москва"` after reload! |
| 8 | Console errors | PASS | 0 errors |

**BUG-2 is FIXED.** The `saveDeliveryCity` function now exists and fires on blur, saving the city via PATCH to `/quotes/{id}/inline`.

---

## Task: [RETEST] Design fixes still working

### TEST 6: Quick regression check on design fixes
**URL:** /finance?tab=erps, /suppliers
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | ERPS dates | PASS | 6 dates in DD.MM.YYYY, 0 ISO dates |
| 2 | Profit colors | PASS | $228.04, $1,853.17, $757.31 all green rgb(5,150,105) |
| 3 | Zero amounts | PASS | 3 gray dashes "—" (not "$0.00") |
| 4 | Supplier countries | PASS | "Германия", "Италия", "Китай", "Турция" — all Russian, no duplicates |
| 5 | Console errors | PASS | 0 errors across both pages |

**No regression.** All previous design fixes intact.

---

## Console Errors (all tasks)
None — 0 console errors across all 6 tests.

---

## Summary for Terminal 1
PASS: TEST 1 (procurement loads), TEST 2 (invoice created on Q-202602-0076!), TEST 3 (invoice details correct, visible in Finance), TEST 4 (invoices tab — 23 records!), TEST 5 (BUG-2 city FIXED), TEST 6 (design regression OK)
SKIP: none
FAIL: none
ACTION: none — all critical bugs fixed, invoice creation works, design intact

### Bugs Resolved This Session
- **BUG-2 (Delivery city):** FIXED — `saveDeliveryCity` function now exists, city persists after reload
- **BUG-5 (Invoice two-table mismatch):** FIXED — Инвойсы tab now reads from `invoices` table, shows 22 records
