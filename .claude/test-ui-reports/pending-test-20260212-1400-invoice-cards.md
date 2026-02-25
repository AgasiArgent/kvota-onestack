# Pending Browser Test: Quote Control Cards + Invoice Registry

**Date:** 2026-02-12
**Commit:** 12b8551
**Changes:** Fix advance_from_client variable + rewrite invoice card + rewrite invoice registry

---

## Test 1: Quote Control Card — Advance from Client

**URL:** https://kvotaflow.ru/quote-control/870af36f-6c27-4c8a-98c1-39f9a709a6b2
**Expected:** "Аванс от клиента" card shows "100%" (not "Не указана" or "-")
**How to verify:**
1. Navigate to the URL
2. Find the checklist item "Наценка vs условия оплаты"
3. Verify it correctly shows the prepayment percentage
4. Check no console errors

## Test 2: Invoice Card on Quote Control

**URL:** https://kvotaflow.ru/quote-control/870af36f-6c27-4c8a-98c1-39f9a709a6b2
**Expected:** "Цены КП ↔ инвойс закупки" shows actual invoice counts (not "Нет инвойсов")
**How to verify:**
1. Check the invoice card in the checklist
2. Should show "X инвойсов" with scan and pricing status
3. If no invoices exist for this quote, "Нет инвойсов поставщиков" is acceptable (means the table is genuinely empty for this quote)

## Test 3: Supplier Invoices Registry

**URL:** https://kvotaflow.ru/supplier-invoices
**Expected:** Page shows real invoices from the `invoices` table (25+ records)
**How to verify:**
1. Navigate to /supplier-invoices
2. Should see a table with invoices (not empty)
3. Columns: Invoice #, Supplier, Quote IDN (clickable link), Client, Items count, Amount, Weight, Documents, Date
4. Filter by supplier works
5. "Только сделки" filter works
6. No console errors

## Test 4: Supplier Invoices — Deals Filter

**URL:** https://kvotaflow.ru/supplier-invoices?status=deals_only
**Expected:** Only invoices linked to quotes that have deals
**How to verify:**
1. Click "Только сделки" filter
2. Results should be a subset of all invoices

---

## Login
- Use admin account
- Password: Test123!
