# Browser Test Report

**Timestamp:** 2026-02-16T21:17:00Z
**Session:** procurement-btn-fix
**Base URL:** https://kvotaflow.ru
**Commit:** af724cd
**Overall:** 1/5 PASS (1 FAIL, 2 BLOCKED, 1 N/A)

---

## Test 1: Draft quote with ALL fields filled → Позиции sub-tab
**URL:** /quotes/2c939f4c-e506-414e-a8b7-1ef835faa468?tab=overview&subtab=products
**Status:** FAIL

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to filled draft quote (Q-202602-0093) | PASS | Customer=Test Company E2E, Seller=МАСТЕР БЭРИНГ ООО, Country=Аргентина, City=Buenos Aires, Method=Авто, Terms=DDP |
| 2 | Go to Позиции sub-tab | PASS | Sub-tab loaded correctly |
| 3 | Button is GREEN (enabled) | **FAIL** | Button is GRAY/disabled: `class="btn-submit-disabled"`, `cursor: not-allowed`, `bg: rgb(229, 231, 235)` |
| 4 | Tooltip says "Передать КП в отдел закупок" | **FAIL** | Tooltip says: "Заполните: Клиент, Продавец, Город доставки, Страна, Способ доставки, Условия поставки" — lists ALL fields as missing even though they are filled |

**Root Cause:** The visible button is `<a id="btn-submit-procurement">` (not the `<button id="checklist_submit">` which is inside the hidden `#checklist_modal`). The server-side validation for the `<a>` button still reports all fields as missing when rendered on the Позиции sub-tab, despite all fields being filled on the Обзор sub-tab. The fix from commit af724cd did NOT resolve this — the validation is still checking DOM fields that don't exist on the Позиции sub-tab.

**Console Errors:** none
**Screenshots:** test1-pozicii-btn-filled.png

---

## Test 2: Draft quote with MISSING fields → Позиции sub-tab
**URL:** /quotes/401e6f17-23e2-42d4-962f-64c4ccd8885d?tab=overview&subtab=products
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to empty draft quote (Q-202602-0094) | PASS | No customer, no delivery info |
| 2 | Go to Позиции sub-tab | PASS | Sub-tab loaded correctly |
| 3 | Button is GRAY (disabled) | PASS | `class="btn-submit-disabled"`, `cursor: not-allowed`, gray background |
| 4 | Tooltip lists missing fields | PASS | "Заполните: Клиент, Продавец, Город доставки, Страна, Способ доставки, Условия поставки, Хотя бы одна позиция (наименование, количество, ед.изм.)" |

**Console Errors:** none

---

## Test 3: Fill fields on Обзор, switch to Позиции → button becomes GREEN
**Status:** BLOCKED (by Test 1 failure)

Cannot verify — Test 1 shows the button stays disabled even with all fields filled. The underlying validation is broken.

---

## Test 4: Button click works when enabled
**Status:** BLOCKED (by Test 1 failure)

Cannot test click behavior — button is always disabled on Позиции sub-tab.

---

## Test 5: Validation on Обзор sub-tab
**URL:** /quotes/2c939f4c-e506-414e-a8b7-1ef835faa468?tab=overview&subtab=info
**Status:** N/A

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Check if button is visible on Обзор sub-tab | N/A | Button (`#btn-submit-procurement`) does NOT exist on Обзор sub-tab. It only exists on Позиции sub-tab. |

---

## Console Errors (all tasks)
None

## Summary for Terminal 1
PASS: Test 2 (empty quote correctly disabled)
FAIL: Test 1 — **Button always disabled on Позиции sub-tab, even when all fields are filled.** Tooltip reports all fields missing. The `<a id="btn-submit-procurement">` validation is NOT using server-side data.
BLOCKED: Test 3, Test 4 (depend on Test 1)
N/A: Test 5 (button not present on Обзор sub-tab)

ACTION:
- **Critical bug:** The server-side rendering of `btn-submit-procurement` on the Позиции sub-tab does not have access to the quote's field values (customer_id, seller_company_id, delivery_city, delivery_country, delivery_method, delivery_terms). It renders as disabled with ALL fields listed as missing. The fix in commit af724cd did not resolve this — validation still fails to read saved data from the database when rendering the Позиции sub-tab.
