# Bug Report — 2026-02-10

Verified by browser testing on https://kvotaflow.ru. One bug was already fixed; four remain.

---

## BUG-1: Seller Company Edit — "Не удалось обновить компанию"

**Status:** FIXED
**URL:** `/seller-companies/{id}/edit`
**Test:** Filled INN/KPP, clicked "Сохранить" — saved successfully, redirected to detail page.
**No action needed.**

---

## BUG-2: Delivery City Not Saving on Quote Page

**Status:** OPEN
**URL:** `/quotes/b4187728-864b-486e-b825-cc4b8b6d477b`
**Severity:** High (blocks "Передать в закупки" button)

### Steps to Reproduce
1. Open any quote in draft status
2. Type a city name in the "ГОРОД" field (e.g., "Москва")
3. Click "Сохранить"
4. Reload the page — city field is empty

### Root Cause
The Save button (`showSaveConfirmation()` at `main.py:8254`) calls `window.saveAllItems()` which only saves the Handsontable item rows. It does **not** save `delivery_city`.

The city field relies on a separate JS function `saveDeliveryCity()` (`main.py:8391`) that fires on the `change` event of the input (`main.py:8432`). Problem: the `change` event only fires on **blur** (losing focus). If the user types a city and clicks "Сохранить" directly, the input never loses focus first, so `saveDeliveryCity()` never executes.

Compare: `delivery_country` uses `hx_patch` with `hx_trigger="change"` (`main.py:7626`) — same timing issue but works because HTMX handles it slightly differently.

### Fix Approach
Add `saveDeliveryCity()` call inside `showSaveConfirmation()` before calling `saveAllItems()`, like:

```javascript
// In showSaveConfirmation(), before saveAllItems:
var cityInput = document.getElementById('delivery-city-input');
if (cityInput && cityInput.value.trim()) {
    saveDeliveryCity(cityInput.value);
}
```

**Files:** `main.py:8254-8288` (showSaveConfirmation), `main.py:8391-8397` (saveDeliveryCity)

---

## BUG-3: Procurement Invoice Not Clickable

**Status:** OPEN
**URL:** `/procurement/0203dc4e-a32f-474b-bbfc-25709000155b`
**Severity:** Medium (UX issue — no way to view invoice details from procurement page)

### Steps to Reproduce
1. Open procurement page for a quote that has invoices
2. Click on the invoice card (e.g., "Инвойс #1")
3. Nothing happens — no detail view opens

### Root Cause
The invoice card is rendered as a plain `Div` with static text (`main.py:14504`). There is no `onclick`, no link (`A` tag), and no modal trigger. The card is not interactive.

### Fix Approach
Two options:
1. **Wrap invoice card in a link/button** that opens a detail modal (similar to edit modal at `main.py:14925`)
2. **Add onclick to toggle an expand/collapse** showing invoice item details inline

**Files:** `main.py:14504-14560` (invoice card rendering)

---

## BUG-4: Customs Table Missing АРТИКУЛ Column

**Status:** OPEN
**URL:** `/customs/0203dc4e-a32f-474b-bbfc-25709000155b`
**Severity:** Medium (user can't identify items by article number)

### Current Columns
`№ | Бренд | Наименование | Кол-во | Страна закупки | Код ТН ВЭД | Пошлина % | ДС | Ст-ть ДС | СС | Ст-ть СС | СГР | Ст-ть СГР`

### Missing
**АРТИКУЛ** (product_code/SKU) column — should be between Бренд and Наименование (or between № and Бренд).

### Fix
Add `product_code` column to the Handsontable config:

1. Add to `colHeaders` array at `main.py:18498`:
   ```
   'Артикул' — insert after 'Бренд'
   ```

2. Add column definition after `brand` column at `main.py:18509`:
   ```javascript
   {data: 'product_code', readOnly: true, type: 'text', width: 100, ...}
   ```

3. Ensure `product_code` is included in the initial data query that populates the table.

**Files:** `main.py:18491-18558` (customs Handsontable config)

### Also Requested: ТН ВЭД Mandatory
User wants ТН ВЭД (hs_code) to be required before customs completion. Currently it's just a text field — no validation prevents empty values. Add validation in the "Завершить таможню" handler.

---

## BUG-5: Supplier Invoices Not Appearing in Registry

**Status:** OPEN
**URL:** `/supplier-invoices`
**Severity:** High (registry is completely empty despite invoices existing)

### Steps to Reproduce
1. Procurement page `/procurement/0203dc4e-...` shows "Инвойс #1" (Поставщик Китай, USD, 5,000.00 $)
2. Navigate to `/supplier-invoices` — shows "Инвойсы не найдены", all counters at 0

### Root Cause
**Two separate invoice systems using different tables:**

- **Procurement** creates invoices in the `invoices` table (`main.py:15586`):
  ```python
  supabase.table("invoices").insert(invoice_data).execute()
  ```

- **Registry** reads from the `supplier_invoices` table via `v_supplier_invoices_with_payments` view (`services/supplier_invoice_service.py:727`):
  ```python
  supabase.table("v_supplier_invoices_with_payments").select("*")
  ```

These are **different tables**. Procurement writes to `invoices`, registry reads from `supplier_invoices`. Nothing bridges them.

### Fix Approach (choose one)
1. **Migrate procurement** to write to `supplier_invoices` table instead of `invoices` (breaking change, needs data migration)
2. **Update the registry view** `v_supplier_invoices_with_payments` to UNION both `invoices` and `supplier_invoices` tables
3. **Create a sync** — after procurement creates an invoice in `invoices`, also insert a corresponding record into `supplier_invoices`

Option 1 is cleanest long-term. Option 3 is quickest short-term fix.

**Files:**
- `main.py:15567-15586` (procurement invoice creation → `invoices` table)
- `services/supplier_invoice_service.py:695-744` (registry query → `v_supplier_invoices_with_payments` view)
- DB: `kvota.invoices` vs `kvota.supplier_invoices` tables

---

## Feature Requests (from same user feedback, not bugs)

| Request | Description |
|---------|-------------|
| КП date + exchange rate | Add quote date field and RUB exchange rate for that date from quote currency |
| КП details redesign | Reorganize "Детали КП" block per Figma mockup; add multiple contact persons |
| Seller company card download | Add download button on `/seller-companies/{id}` profile page |
| ТН ВЭД mandatory | Make HS code required before customs can be marked complete |
