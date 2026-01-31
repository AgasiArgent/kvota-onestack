# Multi-Offer Procurement Feature (JSONB Version)

**Author:** Claude (Anthropic)
**Date:** 2026-01-30

## Overview

Alternative implementation using JSONB array in `quote_items` table instead of separate table.

## Files

```
features/procurement-offers-jsonb/
├── README.md
├── migrations/
│   └── 145_item_price_offers_jsonb.sql
├── services/
│   └── price_offer_service.py
└── ui_components.py
```

## Architecture

**Approach:** JSONB array column in existing `quote_items` table

```sql
ALTER TABLE quote_items ADD COLUMN price_offers JSONB DEFAULT '[]';

-- Structure:
[
  {
    "id": "uuid-string",
    "supplier_id": "uuid",
    "supplier_name": "ООО Поставщик",  -- denormalized
    "price": 1500.00,
    "currency": "USD",
    "production_days": 14,
    "is_selected": true,
    "created_at": "2026-01-30T12:00:00Z"
  },
  { ... }
]
```

### Key Differences from Separate Table

| Aspect | JSONB | Separate Table |
|--------|-------|----------------|
| Schema change | ALTER COLUMN | CREATE TABLE |
| Data location | One table | Two tables |
| Sync needed | No | Yes (SP handles) |
| Foreign keys | No (denormalized) | Yes |
| SQL queries | JSONB operators | Standard JOINs |
| Max offers | Enforced in SP | Could add CHECK |
| RLS | Inherits from quote_items | Needs own policies |

### Data Flow

1. Procurement adds offer → appends to `price_offers` JSONB array
2. Procurement selects offer → updates `is_selected` in array + syncs main fields
3. Calculation engine reads from `quote_items` main fields (unchanged)

## Stored Procedures

All operations use stored procedures for atomicity:

```sql
-- Add offer (with max 5 check)
SELECT kvota.add_jsonb_offer(item_id, supplier_id, supplier_name, price, currency, days);

-- Select offer (updates is_selected + syncs main fields)
SELECT kvota.select_jsonb_offer(item_id, offer_id);

-- Delete offer (clears main fields if was selected)
SELECT kvota.delete_jsonb_offer(item_id, offer_id);
```

## Pros

1. **Single source of truth** — no sync issues between tables
2. **Simpler migration** — just ADD COLUMN
3. **No RLS to write** — inherits from quote_items
4. **Easier debugging** — all data in one row
5. **Atomic by nature** — updating one row is inherently atomic

## Cons

1. **Denormalized supplier_name** — if supplier renamed, old offers show old name
2. **JSONB queries less familiar** — team needs to know `->`, `->>`, `jsonb_array_elements`
3. **No FK constraints** — supplier_id in JSONB not validated by DB
4. **Harder aggregation** — "all offers from supplier X" needs JSONB unnesting

## Query Examples

```sql
-- Get all offers for an item
SELECT jsonb_array_elements(price_offers) as offer
FROM kvota.quote_items
WHERE id = 'item-uuid';

-- Find items with offers from specific supplier
SELECT id, product_name
FROM kvota.quote_items
WHERE price_offers @> '[{"supplier_id": "supplier-uuid"}]';

-- Count total offers across all items
SELECT SUM(jsonb_array_length(price_offers))
FROM kvota.quote_items
WHERE quote_id = 'quote-uuid';
```

## Migration from Separate Table (if needed later)

```sql
-- Move data from separate table to JSONB
UPDATE kvota.quote_items qi
SET price_offers = (
    SELECT jsonb_agg(jsonb_build_object(
        'id', ipo.id,
        'supplier_id', ipo.supplier_id,
        'supplier_name', s.name,
        'price', ipo.price,
        'currency', ipo.currency,
        'production_days', ipo.production_days,
        'is_selected', ipo.is_selected,
        'created_at', ipo.created_at
    ))
    FROM kvota.item_price_offers ipo
    JOIN kvota.suppliers s ON s.id = ipo.supplier_id
    WHERE ipo.quote_item_id = qi.id
);
```

## Comparison Summary

| Criteria | JSONB | Separate Table | Winner |
|----------|-------|----------------|--------|
| Implementation complexity | Lower | Higher | JSONB |
| Data integrity (FK) | Lower | Higher | Table |
| Query flexibility | Lower | Higher | Table |
| Sync risk | None | Medium | JSONB |
| Debugging ease | Higher | Lower | JSONB |
| Future reporting | Harder | Easier | Table |
| Team familiarity | Lower | Higher | Table |

**Recommendation:** For MVP, JSONB is faster to implement and has fewer moving parts. If reporting on offers becomes important, migrate to separate table later.
