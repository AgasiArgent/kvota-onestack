# Currency Invoices (Валютные инвойсы) — Design Document

**Date:** 2026-02-25
**Status:** Approved
**Author:** Andrey + Claude

---

## Problem

When a deal is signed, internal currency invoices must be generated between group companies in the supply chain. These documents transfer ownership of goods between companies (e.g., European purchasing company → Turkish company → Russian selling company). Currently this is done manually in Word/Excel.

## Solution

Auto-generate currency invoices when a deal is created, store as editable snapshots, allow export to DOCX/PDF.

---

## Data Model

### New table: `kvota.currency_invoices`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| deal_id | FK → deals | Which deal |
| segment | TEXT NOT NULL | 'EURTR' or 'TRRU' |
| invoice_number | TEXT UNIQUE NOT NULL | Format: `CI-Q202601-0004-EUR-EURTR-1` |
| seller_entity_type | TEXT | 'buyer_company' or 'seller_company' |
| seller_entity_id | UUID | Polymorphic FK to buyer_companies or seller_companies |
| buyer_entity_type | TEXT | 'buyer_company' or 'seller_company' |
| buyer_entity_id | UUID | Polymorphic FK to buyer_companies or seller_companies |
| markup_percent | DECIMAL DEFAULT 2.0 | Markup for this segment |
| total_amount | DECIMAL | Calculated total |
| currency | VARCHAR(3) | Invoice currency (EUR/USD) |
| status | TEXT DEFAULT 'draft' | draft → verified → exported |
| source_invoice_ids | UUID[] | Which procurement invoices contributed items |
| generated_at | TIMESTAMPTZ | When auto-generated |
| verified_by | FK → users | Who verified |
| verified_at | TIMESTAMPTZ | When verified |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### New table: `kvota.currency_invoice_items`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| currency_invoice_id | FK → currency_invoices | |
| source_item_id | FK → quote_items | Original item (for regeneration) |
| product_name | TEXT NOT NULL | Snapshot |
| sku | TEXT | Product SKU |
| idn_sku | TEXT | IDN-SKU |
| manufacturer | TEXT | Brand/manufacturer |
| quantity | DECIMAL | |
| unit | TEXT | 'kg', 'pcs', etc. |
| hs_code | TEXT | |
| base_price | DECIMAL | Supplier price |
| price | DECIMAL | Price with markup(s) for this segment |
| total | DECIMAL | quantity x price |
| sort_order | INT | |

### New role: `currency_controller`

Added to `kvota.roles` table. Has access to:
- Currency invoices tab on deal pages
- Currency invoices registry (`/currency-invoices`)
- Tasks assigned to this role on `/tasks`

---

## Invoice Numbering

**Format:** `CI-{KP_number}-{currency}-{segment}-{sequential}`

**Examples:**
- `CI-Q202601-0004-EUR-EURTR-1` — first EUR invoice, Europe→Turkey segment, for quote Q-202601-0004
- `CI-Q202601-0004-USD-TRRU-1` — first USD invoice, Turkey→Russia segment

---

## Generation Logic

### Trigger

Automatic when deal status transitions to "deal" (specification signed).

### Algorithm

1. Collect all procurement invoices for the deal
2. Group by buyer_company (our purchasing company)
3. Determine chain by buyer_company's country (from `buyer_companies.country` or `seller_companies.country`):
   - Country = EU → 2 segments (EURTR + TRRU)
   - Country = TR → 1 segment (TRRU only)
4. Create `currency_invoices`:
   - EURTR segment: seller = buyer_company (European), buyer = empty (draft, specialist selects Turkish company)
   - TRRU segment: seller = Turkish company (empty if from EU chain), buyer = seller_company from quote (Russian)
5. Copy items into `currency_invoice_items` as snapshot
6. Calculate prices:
   - EURTR: `base_price × (1 + markup_percent/100)`
   - TRRU from EU chain: `base_price × (1 + eurtr_markup/100) × (1 + trru_markup/100)`
   - TRRU from TR chain: `base_price × (1 + markup_percent/100)`
7. Create task for `currency_controller` role — "Проверить валютные инвойсы" (visible on `/tasks`)

### Grouping Rule

Multiple procurement invoices from different suppliers but with the same buyer_company merge into ONE currency invoice per segment. Example:

```
Deal:
  Procurement invoice 1 (supplier A) → bought by "EuroInvest" (EU)
  Procurement invoice 2 (supplier B) → bought by "EuroInvest" (EU)
  Procurement invoice 3 (supplier C) → bought by "MB TR" (TR)

Generated currency invoices:
  EURTR: EuroInvest → [Turkish company TBD]  (items from invoices 1+2)
  TRRU:  [Turkish company] → MB Rus           (items from invoices 1+2+3, all items)
```

### Regeneration

"Пересоздать из источника" button — re-collects items from procurement invoices, recalculates prices. Warning: "Ваши ручные изменения будут потеряны".

---

## Interface

### Deal Detail Page — New Tab "Валютные инвойсы"

Table with columns:
- Номер инвойса
- Сегмент (EURTR / TRRU)
- Продавец (seller company name)
- Покупатель (buyer company name)
- Сумма
- Валюта
- Статус (draft / verified / exported)

### Currency Invoice Detail Page

- **Header:** invoice number, date, segment, status badge
- **Companies:** seller and buyer — editable dropdowns from buyer_companies + seller_companies, filtered by country
- **Markup:** editable field, default 2%, recalculates prices on change
- **Items table:** product name, SKU, IDN-SKU, manufacturer, qty, unit, HS code, price, total
- **Footer:** total amount
- **Actions:** "Подтвердить" (→ verified), "Пересоздать из источника", "Экспорт DOCX", "Экспорт PDF"

### Registry Page `/currency-invoices`

Table of all currency invoices across all deals. Accessible to `currency_controller` and `admin`.
Columns mirror the existing CSV registry: date, invoice numbers, companies, client, spec number, amounts.

### Tasks Integration

When currency invoices are generated, a task is created for `currency_controller` role:
- Appears on `/tasks` page
- Links to the deal's currency invoices tab
- Task text: "Проверить валютные инвойсы по сделке [deal_number]"

---

## Export

### DOCX (via python-docx)

Format based on existing invoice example:
- Invoice header (number, date)
- Supplier block (name, address, tax ID from company record)
- Buyer block (name, address, tax ID from company record)
- Items table: #, Product, SKU, Manufacturer, Qty, HS Code, Unit Price, Total
- Total amount
- Payment terms (from template or deal)

### PDF

Generated by converting DOCX (via `libreoffice --headless` in Docker container).

---

## Status Flow

```
draft → verified → exported
  ↑                    |
  └── regenerated ─────┘ (resets to draft)
```

- **draft:** Auto-generated, may have empty Turkish company
- **verified:** Specialist confirmed all data is correct
- **exported:** DOCX/PDF has been downloaded

---

## Existing Infrastructure Leveraged

- `buyer_companies` + `seller_companies` tables (with country, requisites, bank accounts)
- `bank_accounts` polymorphic table (entity_type + entity_id pattern)
- 6 existing export services (patterns for XLSX/PDF generation)
- `document_service.py` for file upload/download
- Task system on `/tasks` page
- Deal detail page with tabs
