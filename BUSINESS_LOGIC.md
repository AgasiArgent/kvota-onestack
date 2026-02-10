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
