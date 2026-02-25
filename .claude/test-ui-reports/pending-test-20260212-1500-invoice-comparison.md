# Pending Browser Test: Invoice Scan Comparison Feature

**Date:** 2026-02-12
**Commit:** 4295617
**ClickUp:** 86afb2hgf
**Changes:** Clickable checklist card #2 on quote control page expands to show invoice list with scan status, per-invoice detail with split-screen layout (items table + PDF iframe)

---

## Test 1: Checklist Card #2 is Clickable

**URL:** https://kvotaflow.ru/quote-control/870af36f-6c27-4c8a-98c1-39f9a709a6b2
**Expected:** Card "Цены КП ↔ инвойс закупки" has a pointer cursor and is clickable
**How to verify:**
1. Navigate to the URL (login as admin / Test123!)
2. Find checklist card #2 "Цены КП ↔ инвойс закупки"
3. Verify it has a pointer cursor (hover over it)
4. Click on the card
5. A details section should expand below with invoice list

## Test 2: Invoice Comparison Expansion

**URL:** https://kvotaflow.ru/quote-control/870af36f-6c27-4c8a-98c1-39f9a709a6b2
**Expected:** Clicking card #2 loads an HTMX panel showing invoices for this quote
**How to verify:**
1. Click on card #2
2. Should see a list of invoices with columns: invoice number, supplier, items count, scan status
3. Each invoice should show a green checkmark or red X for scan status
4. Click the card again — the panel should collapse (toggle behavior)
5. No console errors

## Test 3: Invoice Detail View (if invoices exist)

**URL:** https://kvotaflow.ru/quote-control/870af36f-6c27-4c8a-98c1-39f9a709a6b2
**Expected:** Clicking an invoice row opens a split-screen detail view
**How to verify:**
1. Expand card #2 by clicking it
2. If invoices are listed, click on one
3. Should see a split-screen layout:
   - Left side (~40%): items table with product name, quantity, price, currency
   - Right side (~60%): PDF scan iframe (or "Скан не загружен" placeholder if no scan)
4. If a scan exists, the iframe should load the PDF from a signed URL
5. If no scan, should show a file-x icon with "Скан не загружен" message

## Test 4: No Invoices Case

**URL:** Try a quote that has no invoices (e.g., a newly created draft quote)
**Expected:** Card #2 expansion shows "Нет инвойсов для сравнения" or similar message
**How to verify:**
1. Navigate to a quote-control page for a draft quote without invoices
2. Click card #2
3. Should show an appropriate "no invoices" message
4. No errors

## Test 5: Console Errors Check

**All URLs above**
**Expected:** No JavaScript errors in console
**How to verify:**
1. Open DevTools console
2. Navigate through all test steps
3. Verify no errors (warnings are OK)

---

## Login
- Use admin account
- Password: Test123!

## REPORT_TO
.claude/test-ui-reports/report-20260212-1500-invoice-comparison.md
