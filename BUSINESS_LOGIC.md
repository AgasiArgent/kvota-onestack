# OneStack Business Logic Reference

## Entity Lifecycle: Quote → Specification → Deal

Same business entity at different stages:

```
Quote (КП)              → customer request, pricing, items
  ↓ approved + signed by client
Specification (Спец)    → contractual document, spec number, contract binding
  ↓ signed (scan uploaded)
Deal (Сделка)           → auto-created from signed spec, tracks execution
```

### Relationships

| From | To | FK | Cardinality |
|------|----|----|-------------|
| Specification | Quote | `specifications.quote_id` | many:1 |
| Deal | Specification | `deals.specification_id` | 1:1 (unique constraint) |
| Quote Items | Quote | `quote_items.quote_id` | many:1 |
| Plan-Fact Items | Deal | `plan_fact_items.deal_id` | many:1 |

### Payment Architecture

**Active system:** `plan_fact_items` on deals — full CRUD on deal detail page.

16 categories (3 income, 13 expense):
- **Income:** client payment, client advance, client final payment
- **Expense:** supplier payment, logistics (3 segments), customs (3 types), taxes, commissions, FX loss, etc.

Each item tracks: planned vs actual amount/date/currency, variance, status (planned/partial/completed/cancelled/overdue).

**ERPS view:** `kvota.erps_registry` — shows signed specs with payment columns (`total_paid_usd`, `remaining_payment_usd`, `days_until_advance`). Currently reads from `specification_payments` (deprecated, nothing writes there). TODO: migrate to read from `plan_fact_items` via deal→spec join.

**Deprecated:** `specification_payments` — DB table only, no code writes to it.
**Unused:** `payment_schedule` — no references in code.

### Rule

Never create separate payment/data systems for specs and deals. They share `plan_fact_items` through the deal.

---

## Invoice Architecture: Two-Table Design

Two invoice tables coexist — different business purposes, do NOT merge.

### `kvota.invoices` — Procurement Workflow Groupings

**Purpose:** Group quote items by supplier/buyer/pickup for the procurement→logistics→customs workflow.

**Lifecycle:** `pending_procurement → pending_logistics → pending_customs → completed`

**Key columns:** `quote_id` (required), `supplier_id`, `buyer_company_id`, `pickup_location_id`, `invoice_number`, `currency`, `total_weight_kg`, `total_volume_m3`, logistics cost columns (3-segment model: `logistics_supplier_to_hub/hub_to_customs/customs_to_customer` + currency variants), workflow status + completion timestamps.

**Used by:** Procurement workspace, Logistics workspace, Customs workspace, Calculation engine (`build_calculation_inputs()`), Finance "Инвойсы" tab.

**Children:** `quote_items.invoice_id` → `invoices.id`

### `kvota.supplier_invoices` — Finance Payment Registry

**Purpose:** Track actual supplier invoices for payment obligations. Used by finance/accounts payable.

**Lifecycle:** `pending → partially_paid → paid → overdue (auto) → cancelled`

**Key columns:** `organization_id` (required), `supplier_id`, `invoice_number`, `invoice_date`, `due_date`, `total_amount`, `currency`, `status`, `created_by`.

**Used by:** `supplier_invoice_service.py`, finance payment tracking, overdue detection trigger.

**Children:** `supplier_invoice_items`, `supplier_invoice_payments`

### Rules

1. **Procurement CRUD** always uses `invoices` table
2. **Finance payment tracking** always uses `supplier_invoices` table
3. **Logistics cost entry** writes to `invoices.logistics_*` columns
4. **Calculation engine** reads from `invoices` (never `supplier_invoices`)
5. Never mix the two — they serve different lifecycle stages

---

## Logistics: Two Models

### 3-Segment Cost Model (Quote-Level)

On `invoices` table: `logistics_supplier_to_hub`, `logistics_hub_to_customs`, `logistics_customs_to_customer` + currency variants.

**Purpose:** Cost estimation during quote calculation. Feeds into 13-phase calculation engine.
**Used by:** `/logistics/{quote_id}` workspace, `build_calculation_inputs()`.

### 7-Stage Tracking Model (Deal-Level)

Tables: `logistics_stages` + `plan_fact_items` (with `logistics_stage_id` FK).

**Stages:** first_mile → hub → hub_hub → transit → post_transit → gtd_upload → last_mile

**Purpose:** Track actual logistics progress and real expenses after deal is signed.
**Used by:** `/finance/{deal_id}` logistics section.

These are complementary, not replacements. Quote-level estimates vs deal-level actuals.
