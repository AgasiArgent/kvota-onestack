# Invoice Cargo Places (Грузовые Места)

**Date:** 2026-04-03
**Feedback:** FB-260403-110304-312b
**Type:** FEATURE | BIG

---

## Problem

When creating an invoice, users fill `total_weight_kg` and `total_volume_m3` as single numbers. Then they fill per-item `weight_in_kg` and dimensions in the Handsontable. The invoice-level totals are redundant and don't capture the real-world structure: shipments come in **boxes** (грузовые места), each with its own weight and dimensions.

## Solution

Replace invoice-level `total_weight_kg` / `total_volume_m3` with **cargo places** (boxes). Each invoice has 1+ boxes, each box has weight and dimensions.

---

### 1. Database Migration

**New table: `kvota.invoice_cargo_places`**

```sql
CREATE TABLE kvota.invoice_cargo_places (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES kvota.quote_invoices(id) ON DELETE CASCADE,
  position INT NOT NULL DEFAULT 1,
  weight_kg DECIMAL(10,3) NOT NULL CHECK (weight_kg > 0),
  length_mm INT NOT NULL CHECK (length_mm > 0),
  width_mm INT NOT NULL CHECK (width_mm > 0),
  height_mm INT NOT NULL CHECK (height_mm > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(invoice_id, position)
);
```

**Backward compatibility:** After inserting boxes, update `quote_invoices` computed fields:
- `total_weight_kg` = SUM(box weights)
- `total_volume_m3` = SUM(L×W×H / 1e9) for each box (mm³ → m³)

This keeps the Python backend (main.py) working without changes — it reads the same columns.

**RLS:** Same policy as `quote_invoices` — access through quote → org membership.

### 2. Invoice Create Modal Redesign

**File:** `invoice-create-modal.tsx`

**Remove:** `total_weight_kg` and `total_volume_m3` input fields.

**Add:** "Грузовые места" section with:
- Default: 1 box form (Место 1)
- Each box: 4 mandatory fields in a row:
  - Вес (кг) — numeric, required
  - Длина (мм) — integer, required
  - Ширина (мм) — integer, required
  - Высота (мм) — integer, required
- "Добавить место" button below to add more boxes
- Each box (except the first if only one exists) has a remove (×) button
- Validation: all 4 fields required per box, all > 0

**State:** `boxes: Array<{ weight_kg: string; length_mm: string; width_mm: string; height_mm: string }>`
Default: `[{ weight_kg: "", length_mm: "", width_mm: "", height_mm: "" }]`

### 3. Mutations

**`createInvoice`** — change signature:
- Remove: `total_weight_kg`, `total_volume_m3` params
- Add: `boxes: Array<{ weight_kg: number; length_mm: number; width_mm: number; height_mm: number }>`
- After inserting invoice: bulk-insert boxes into `invoice_cargo_places`
- Compute and update `total_weight_kg` and `total_volume_m3` on the invoice row

### 4. Invoice Card (Procurement Step)

**File:** `invoice-card.tsx`

Show cargo places summary in the invoice card header or expanded view:
- "N мест · XX.X кг · X.XX м³" (computed from boxes)
- On expand: list each box: "Место 1: 25.0 кг, 600×400×300 мм"

### 5. Logistics Step

**File:** `logistics-invoice-row.tsx`

Replace current total weight/volume display with per-box breakdown:
- Show each box: weight + dimensions
- Show computed totals at bottom

### 6. Per-item weight

**No change.** `weight_in_kg` in procurement Handsontable stays optional. It's a different concept (product weight for customs/pricing) vs cargo place weight (shipping weight).

---

## Scope

| Change | File(s) | Impact |
|--------|---------|--------|
| DB migration | `migrations/188_...` | New table + RLS |
| Invoice create modal | `invoice-create-modal.tsx` | Remove old fields, add boxes UI |
| Mutations | `mutations.ts` | New signature + bulk insert boxes |
| Queries | `queries.ts` (new) | Fetch boxes with invoice |
| Invoice card | `invoice-card.tsx` | Display boxes summary |
| Logistics row | `logistics-invoice-row.tsx` | Per-box breakdown |

**Not in scope:**
- Python backend changes (backward compat via computed totals)
- Per-item weight changes (stays as-is)
- Existing invoice editing (create-only for now, edit can be a follow-up)
