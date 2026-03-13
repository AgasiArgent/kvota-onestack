# Database

## Schema

All tables live in the `kvota` schema — never `public`. Both Python and JS clients must be configured accordingly:

```python
# Python
supabase = create_client(url, key, options=ClientOptions(schema="kvota"))
```

```typescript
// TypeScript
const supabase = createClient(url, key, { db: { schema: 'kvota' } })
```

## Entity Model

### Core Lifecycle: Quote → Specification → Deal

Same business entity at different stages, linked via foreign keys:

```
Quote (КП) ──[approved]──→ Specification (Спец) ──[signed]──→ Deal (Сделка)
   ↑                            ↑                                ↑
quote_items              specifications.quote_id          deals.specification_id (1:1)
```

**Rule:** Never create separate data layers for specs and deals. They share `plan_fact_items` through the deal.

### Two Invoice Tables (Don't Merge)

| Table | Purpose | Used By |
|-------|---------|---------|
| `invoices` | Procurement workflow groupings (items by supplier/buyer) | Procurement, logistics, customs, calculation engine |
| `supplier_invoices` | Finance payment tracking (actual supplier invoices) | Finance, accounts payable |

Different lifecycle, different purpose. The calculation engine reads only from `invoices`.

## PostgREST Patterns

### FK Joins — Specify Explicitly

When a table has multiple FKs to the same target:

```python
# WRONG — ambiguous, silent failure after deploy
quotes(customer_id, customers(name))

# RIGHT — explicit FK
quotes!customer_id(name)
```

### FK Null Safety

FK joins return `null` when no match (key exists, value is `None`):

```python
# WRONG — crashes when FK is null
obj.get("customers", {}).get("name")  # {} only triggers when key MISSING

# RIGHT
(obj.get("customers") or {}).get("name", "")
```

## RLS Policies

- Role column: `r.slug` (never `r.code`)
- All tables use `kvota.` prefix in policies
- Supabase Auth JWT carries role info; RLS enforces access

## Migrations

- Sequential numbering: `001_initial.sql` through `210_...sql`
- Applied via SSH: `scripts/apply-migrations.sh`
- Each migration does one thing
- Never modify applied migrations — create new ones
- Use idempotent operations where possible (`IF NOT EXISTS`)

## Key Tables

- `quotes`, `quote_items` — quotation data and line items
- `specifications` — approved quotes with contract binding
- `deals` — execution tracking (1:1 with spec via unique constraint)
- `plan_fact_items` — payment tracking (16 categories, plan vs actual)
- `invoices` — procurement groupings (workflow: pending_procurement → completed)
- `supplier_invoices` — finance payment obligations
- `customers`, `suppliers` — counterparties
- `logistics_stages` — 7-stage deal-level tracking
- `roles`, `user_roles` — RBAC (12 active roles)

## Frontend Type Safety

Auto-generated `database.types.ts` makes the Supabase JS client type-aware — wrong column names fail at build time.

**After any migration:** `cd frontend && npm run db:types` to regenerate. Build catches stale queries.

**Limits:** FK joins (`quotes!inner(...)`) aren't type-checked (empty Relationships in generated types). RPC function types must be added manually to the Functions section.

## Confusable Columns

Many columns sound similar but have different meanings. Use this reference when writing frontend queries.

### quotes — Financial Totals (109 columns)

The quotes table has 15+ "total/amount" columns across different currencies and calculation stages:

| Business Meaning | Column | Currency | Notes |
|-----------------|--------|----------|-------|
| Base subtotal (no margin) | `subtotal` | quote | Pre-calculation |
| Base subtotal | `subtotal_usd` | USD | Pre-calculation |
| VAT amount | `tax_amount` | quote | |
| Total for client (pre-calc) | `total_amount` | quote | Legacy, pre-calculation |
| **Total for client (calculated)** | `total_amount_quote` | quote | **Use this for display** |
| Total for client (calculated) | `total_amount_usd` | USD | Internal reporting |
| Total incl. VAT | `total_with_vat_quote` | quote | Client-facing final price |
| Total incl. VAT | `total_with_vat_usd` | USD | |
| Revenue excl. VAT | `revenue_no_vat_quote_currency` | quote | For margin analysis |
| Total COGS | `cogs_quote_currency` | quote | Cost of goods sold |
| Profit | `profit_quote_currency` | quote | Revenue minus COGS |
| Profit | `total_profit_usd` | USD | |
| Internal calc total | `total_usd` | USD | Engine intermediate |
| Internal calc total | `total_quote_currency` | quote | Engine intermediate |
| VAT on import | `total_vat_on_import_usd` | USD | Customs |
| VAT payable | `total_vat_payable_usd` | USD | Tax |

**Pattern:** `*_quote` / `*_quote_currency` = in client's currency. `*_usd` = in USD. No suffix = legacy/base.

**Statuses:**
- `status` — lifecycle stage: draft → calculating → calculated → in_review → approved → rejected
- `workflow_status` — approval flow state (separate from lifecycle)
- `workflow_state` — legacy, same as workflow_status

### quote_items — Prices and Proformas (62 columns)

| Business Meaning | Column | Notes |
|-----------------|--------|-------|
| Supplier price (their currency) | `purchase_price_original` | **Primary price field** |
| Calculated cost incl. VAT | `base_price_vat` | Set by calculation engine, not manually |
| Does price include VAT? | `price_includes_vat` | Boolean flag |
| Proforma excl. VAT (supplier currency) | `proforma_amount_excl_vat` | From supplier invoice |
| Proforma incl. VAT (supplier currency) | `proforma_amount_incl_vat` | From supplier invoice |
| Proforma excl. VAT (USD) | `proforma_amount_excl_vat_usd` | Converted |
| Proforma incl. VAT (USD) | `proforma_amount_incl_vat_usd` | Converted |

**Identifiers:**
- `idn_sku` — internal system SKU (auto-generated)
- `supplier_sku` — supplier's own product code
- `product_code` — legacy field, same purpose as supplier_sku

**Logistics cost columns** (days, not currency):
- `logistics_supplier_to_hub` — days from supplier to consolidation hub
- `logistics_hub_to_customs` — days from hub to customs
- `logistics_customs_to_customer` — days from customs to final delivery
- `logistics_total_days` — sum of above

### specifications — Dates and Periods (40 columns)

| Business Meaning | Column | Notes |
|-----------------|--------|-------|
| Contract sign date | `sign_date` | When spec was signed |
| Planned arrival to Russia | `planned_dovoz_date` | Logistics planning |
| Actual delivery date | `actual_delivery_date` | When goods arrived |
| Delivery period (days) | `delivery_period_days` | Contractual commitment |
| Logistics transit period | `logistics_period` | Text description |
| Payment deferral | `payment_deferral_days` | Days after delivery |

**Identifiers:**
- `specification_number` — human-readable spec number (e.g. "S-202603-0001")
- `proposal_idn` — linked quote's IDN
- `item_ind_sku` — items identifier (legacy)

### customers — Addresses (31 columns)

| Business Meaning | Column | Notes |
|-----------------|--------|-------|
| Delivery address (from quote) | `address` | Generic/legacy |
| Registered legal address | `legal_address` | For contracts |
| Actual office/warehouse | `actual_address` | Where they operate |
| Mailing address | `postal_address` | For correspondence |
| Warehouse list (JSON) | `warehouse_addresses` | Multiple delivery points |

---
_Patterns and conventions, not exhaustive schema_
