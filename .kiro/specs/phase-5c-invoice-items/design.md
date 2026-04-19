# Design Document — Phase 5c: Invoice Items

**Depends on:** Phase 5b (shipped 2026-04-11, v0.6.0) ✅
**Locks:** calculation_engine.py, calculation_models.py, calculation_mapper.py (zero changes)
**Ship order:** Migrations 281 → 282 → 283 → 284, application code in same PR

---

## 1. Data Model

### 1.1 New tables

#### `kvota.invoice_items`

Per-invoice positions. Each row is one line item inside one КП поставщика, with its own identity and supplier-specific attributes. Split/merge/substitution express structural differences from the customer's quote_items via this table and the coverage junction.

```sql
CREATE TABLE kvota.invoice_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES kvota.organizations(id),
  position INT NOT NULL,

  -- Identity (supplier's version of the product; may differ from quote_items)
  product_name TEXT NOT NULL,
  supplier_sku TEXT,
  brand TEXT,

  -- Pricing
  quantity NUMERIC NOT NULL CHECK (quantity > 0),
  purchase_price_original NUMERIC(18,4),
  purchase_currency TEXT NOT NULL,
  base_price_vat NUMERIC(18,4),
  price_includes_vat BOOLEAN NOT NULL DEFAULT false,
  vat_rate NUMERIC(5,2),

  -- Supplier-specific attributes (may vary per supplier)
  weight_in_kg NUMERIC,
  customs_code TEXT,
  supplier_country TEXT,
  production_time_days INTEGER,
  minimum_order_quantity INTEGER,
  dimension_height_mm INT,
  dimension_width_mm INT,
  dimension_length_mm INT,
  license_ds_cost NUMERIC,
  license_ss_cost NUMERIC,
  license_sgr_cost NUMERIC,
  supplier_notes TEXT,

  -- Versioning (same pattern as Phase 5b invoice_item_prices)
  version INT NOT NULL DEFAULT 1 CHECK (version >= 1),
  frozen_at TIMESTAMPTZ,
  frozen_by UUID REFERENCES auth.users(id),

  -- Audit
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by UUID REFERENCES auth.users(id),

  UNIQUE (invoice_id, position, version)
);

CREATE INDEX idx_invoice_items_invoice ON kvota.invoice_items(invoice_id);
CREATE INDEX idx_invoice_items_organization ON kvota.invoice_items(organization_id);
CREATE INDEX idx_invoice_items_active ON kvota.invoice_items(invoice_id, position) WHERE frozen_at IS NULL;
```

#### `kvota.invoice_item_coverage`

M:N junction. Maps each invoice_item to the quote_item(s) it fulfills, with a ratio coefficient.

```sql
CREATE TABLE kvota.invoice_item_coverage (
  invoice_item_id UUID NOT NULL REFERENCES kvota.invoice_items(id) ON DELETE CASCADE,
  quote_item_id UUID NOT NULL REFERENCES kvota.quote_items(id) ON DELETE CASCADE,
  ratio NUMERIC NOT NULL DEFAULT 1 CHECK (ratio > 0),
  PRIMARY KEY (invoice_item_id, quote_item_id)
);

CREATE INDEX idx_coverage_invoice_item ON kvota.invoice_item_coverage(invoice_item_id);
CREATE INDEX idx_coverage_quote_item ON kvota.invoice_item_coverage(quote_item_id);
```

**Ratio semantics:** `ratio = invoice_item_units per quote_item_unit`.

- **1:1 (no structural change):** ratio = 1. E.g., quote_item "болт ×100" + invoice_item "болт ×100" → coverage(ratio=1). Validation: `100 = 100 × 1` ✓.
- **Split (1 quote → N invoice):** one quote_item, N invoice_items, each with its own ratio. E.g., quote_item "крепёж ×100" split into invoice_items "болт ×100" (ratio=1) + "шайба ×200" (ratio=2). Validation: bolt `100 = 100 × 1` ✓, washer `200 = 100 × 2` ✓.
- **Merge (N quote → 1 invoice):** N quote_items, one invoice_item, N coverage rows each ratio=1. E.g., quote_items "болт ×100", "гайка ×100", "шайба ×100" all covered by invoice_item "крепёж ×100" via 3 coverage rows. Validation: `100 = 100 × 1` for each row ✓.

### 1.2 Changed tables

#### `kvota.quote_items` — columns preserved

- `id`, `quote_id`, `idn_sku`, `product_name`, `brand`, `quantity`, `position`
- `composition_selected_invoice_id` (repurposed: points to invoice, coverage resolves which invoice_items apply)
- `is_unavailable`, `import_banned` (customer-side exclusion flags)
- `vat_rate` (customer-side tax context; invoice_items.vat_rate is supplier-side)
- `supplier_sku`, `supplier_sku_note`, `manufacturer_product_name` (1:1 substitution — kept from Phase 4a/prior)
- `name_en` (bilingual export)
- `created_at`, `updated_at`

**Note:** `markup` and `supplier_discount` columns live on `kvota.quotes` (not on `quote_items`). This is consistent with quote-level pricing metadata.

#### `kvota.quote_items` — columns dropped in migration 284

- `invoice_id` — legacy FK from migration 123; superseded by composition_selected_invoice_id + coverage
- `purchase_price_original`, `purchase_currency`, `base_price_vat`, `price_includes_vat` — move to invoice_items
- `customs_code`, `supplier_country` — move to invoice_items (supplier-specific)
- `weight_in_kg`, `production_time_days`, `minimum_order_quantity` — move to invoice_items
- `dimension_height_mm`, `dimension_width_mm`, `dimension_length_mm` — move to invoice_items
- `license_ds_cost`, `license_ss_cost`, `license_sgr_cost` — move to invoice_items

### 1.3 Dropped tables

- `kvota.invoice_item_prices` — fully replaced by `invoice_items` + `invoice_item_coverage` after backfill

---

## 2. Composition Service Rewrite

File: `services/composition_service.py` (retain public API surface, rewrite internals).

### 2.1 `get_composed_items(quote_id, supabase) -> list[dict]`

New algorithm:

```python
def get_composed_items(quote_id, supabase):
    # Query 1: all quote_items for this quote (customer-side fields)
    qi_rows = supabase.table("quote_items").select(
        "id, idn_sku, product_name, brand, quantity, "
        "is_unavailable, import_banned, markup, supplier_discount, "
        "composition_selected_invoice_id, supplier_sku, manufacturer_product_name"
    ).eq("quote_id", quote_id).execute().data or []

    # Collect invoice_ids to resolve
    selected_invoice_ids = {
        qi["composition_selected_invoice_id"]
        for qi in qi_rows
        if qi.get("composition_selected_invoice_id")
    }
    if not selected_invoice_ids:
        # Legacy fallback: no compositions set → emit items with customer-side fields only
        return [_legacy_shape(qi) for qi in qi_rows]

    # Query 2: coverage + invoice_items for the selected invoices
    coverage_rows = supabase.table("invoice_item_coverage").select(
        "invoice_item_id, quote_item_id, ratio, "
        "invoice_items!inner(*)"
    ).in_("quote_item_id", [qi["id"] for qi in qi_rows]).execute().data or []

    # Filter coverage to only rows where invoice_item.invoice_id matches selected
    relevant = [
        c for c in coverage_rows
        if c["invoice_items"]["invoice_id"] in selected_invoice_ids
    ]

    # Build (quote_item_id → [covering invoice_items]) lookup
    by_qi = defaultdict(list)
    for c in relevant:
        by_qi[c["quote_item_id"]].append(c)

    # Emit results: for each quote_item, one result per covering invoice_item
    # (merge case: same invoice_item covers N quote_items → emitted once per distinct id)
    emitted_ii = set()
    results = []
    for qi in qi_rows:
        coverings = by_qi.get(qi["id"], [])
        if not coverings:
            # Uncovered (e.g., this supplier doesn't provide this quote_item) → skip
            continue
        for c in coverings:
            ii = c["invoice_items"]
            if ii["id"] in emitted_ii:
                continue  # merge: already emitted for another qi
            emitted_ii.add(ii["id"])
            results.append(_build_calc_item(qi, ii, c["ratio"]))
    return results


def _build_calc_item(qi, ii, ratio):
    """Merge quote_item (customer-side) + invoice_item (supplier-side) into calc dict."""
    return {
        # From invoice_item (supplier-side)
        "product_name": ii["product_name"],
        "supplier_sku": ii.get("supplier_sku"),
        "brand": ii.get("brand") or qi.get("brand"),
        "quantity": ii["quantity"],
        "purchase_price_original": ii.get("purchase_price_original"),
        "purchase_currency": ii.get("purchase_currency"),
        "base_price_vat": ii.get("base_price_vat"),
        "price_includes_vat": ii.get("price_includes_vat", False),
        "weight_in_kg": ii.get("weight_in_kg"),
        "customs_code": ii.get("customs_code"),
        "supplier_country": ii.get("supplier_country"),
        "license_ds_cost": ii.get("license_ds_cost"),
        "license_ss_cost": ii.get("license_ss_cost"),
        "license_sgr_cost": ii.get("license_sgr_cost"),

        # From quote_item (customer-side)
        "is_unavailable": qi.get("is_unavailable", False),
        "import_banned": qi.get("import_banned", False),
        "markup": qi.get("markup"),
        "supplier_discount": qi.get("supplier_discount"),
        "vat_rate": qi.get("vat_rate"),
    }
```

### 2.2 `get_composition_view(quote_id, supabase, user_id=None) -> dict`

Returns alternatives grouped by quote_item. Each alternative = one invoice; UI shows one radio per invoice. Merge/split handling: invoice is shown once per quote_item; the "coverage summary" field indicates `"covers: bolt, nut, washer"` (merge) or `"splits into: bolt (1x), washer (2x)"` (split).

### 2.3 `apply_composition(quote_id, selection_map, supabase, user_id, quote_updated_at=None)`

Input: `{quote_item_id: invoice_id}`. For each entry, update `quote_items.composition_selected_invoice_id`. Merge case: when UI picks an invoice whose one invoice_item covers N quote_items, the picker submits N entries with the same invoice_id — server validates coverage exists for each and updates all.

### 2.4 `freeze_composition(quote_id, user_id, supabase) -> int`

Unchanged semantics: stamps `frozen_at`/`frozen_by` on invoice_items rows reached via active compositions. Logic walks quote_items → selected invoice → invoice_items (in that invoice, covered by these quote_items).

### 2.5 `validate_composition(quote_id, selection_map, supabase) -> ValidationResult`

Checks every `(quote_item_id, invoice_id)` pair has ≥1 covering invoice_item. Error structure unchanged.

---

## 3. Edit-Gate Refactor

### 3.1 Backend: `services/invoice_send_service.py`

```python
# Before (Phase 4a):
def is_invoice_sent(invoice_id: str) -> bool:
    row = supabase.table("invoices").select("sent_at").eq("id", invoice_id).single().execute()
    return row.data and row.data.get("sent_at") is not None

def check_edit_permission(invoice_id: str, user_roles: list[str]) -> bool:
    if not is_invoice_sent(invoice_id):
        return True  # unsent: anyone in roles can edit
    return bool(_EDIT_OVERRIDE_ROLES & set(user_roles))  # sent: only override roles

# After (Phase 5c):
def is_quote_procurement_locked(invoice_id: str) -> bool:
    """Lookup invoice → quote → procurement_completed_at."""
    inv = supabase.table("invoices").select("quote_id").eq("id", invoice_id).single().execute()
    if not inv.data:
        return False  # invoice missing → no lock (let downstream handle)
    quote_id = inv.data["quote_id"]
    q = supabase.table("quotes").select("procurement_completed_at").eq("id", quote_id).single().execute()
    return q.data and q.data.get("procurement_completed_at") is not None

def check_edit_permission(invoice_id: str, user_roles: list[str]) -> bool:
    if not is_quote_procurement_locked(invoice_id):
        return True  # procurement still active: anyone in roles can edit
    return bool(_EDIT_OVERRIDE_ROLES & set(user_roles))  # locked: only override
```

### 3.2 Main.py call sites (unchanged)

- `main.py:19210` — POST invoice update: no signature change, behavior follows new `check_edit_permission`
- `main.py:19683` — POST assign items: same
- `main.py:19803` — POST bulk update: same

Return code string changes: `EDIT_REQUIRES_APPROVAL` → `PROCUREMENT_LOCKED`.

### 3.3 API rename: `api/invoices.py`

- `request_edit_approval` → `request_procurement_unlock`
- Approval row: `approval_type="edit_sent_invoice"` → `approval_type="edit_completed_procurement"`
- HTTP path: `/api/invoices/{id}/edit-request` → `/api/invoices/{id}/procurement-unlock-request` (frontend mutations updated in same commit)

### 3.4 Frontend: `invoice-card.tsx` + `edit-approval-button.tsx`

- Rename file `edit-approval-button.tsx` → `procurement-unlock-button.tsx`
- Component `EditApprovalButton` → `ProcurementUnlockButton`
- `invoice-card.tsx:68` `isSent = invoice.sent_at != null` → `isLocked = quote.procurement_completed_at != null`
- `invoice-card.tsx:243-246` keep the green "Отправлено [date]" badge (informational, no gate effect)
- `invoice-card.tsx:254-256` render `ProcurementUnlockButton` when `isLocked` instead of when `isSent`
- Prop drilling: `procurement-step.tsx` passes `quote.procurement_completed_at` to invoice-card (already passes `procurement_completed_at != null` as `procurementCompleted` — reuse that prop)

### 3.5 sent_at remains

- `invoices.sent_at` column stays in schema
- `commit_invoice_send()` service function stays — writes `sent_at` as metadata ("отправлено поставщику на запрос цен")
- Send history panel (Phase 4b) still uses `sent_at` for display
- No blocking effect downstream

---

## 4. Frontend: Procurement UI

### 4.1 Rename + un-filter: `quote-positions-list.tsx`

- File move: `unassigned-items.tsx` → `quote-positions-list.tsx`
- Component rename: `UnassignedItems` → `QuotePositionsList`
- Header: "Нераспределённые позиции (N)" → "Позиции заявки (N)"
- Filter `items.filter(i => i.invoice_id == null)` → removed; render all `items`
- New column "В КП": chip list of invoice_numbers that cover this quote_item (query: `invoice_item_coverage` JOIN `invoice_items` JOIN `invoices` WHERE coverage.quote_item_id = qi.id). Cached per render; refetched on invoices mutation.
- "Назначить в КП" dropdown lists all `invoices` of the quote (not just unassigned-items' sibling set) + "➕ Создать новый КП"
- `assignItemsToInvoice(itemIds, invoiceId)` mutation (entities/quote/mutations.ts) rewrites: INSERT invoice_items + invoice_item_coverage instead of UPDATE quote_items.invoice_id. Upsert semantics: `ON CONFLICT (invoice_item_id, quote_item_id) DO NOTHING` for coverage.

### 4.2 `invoice-card.tsx` items list

- Source: query `invoice_items` WHERE `invoice_id = invoice.id` + JOIN `invoice_item_coverage` for the "covers X quote_items" display
- Display: each row shows invoice_item's `product_name`, `supplier_sku`, `quantity`, `purchase_price_original` (invoice-specific values, not quote_item's)
- "Coverage" sub-row per invoice_item: small text listing quote_items covered, with ratio (`болт ×1, шайба ×2`)

### 4.3 `procurement-items-editor.tsx` column bindings

- Columns that edit supplier-specific fields now write to `invoice_items` (not `quote_items`): `supplier_sku`, `purchase_price_original`, `production_time_days`, `weight_in_kg`, `dimensions`, `customs_code`, `supplier_country`, `minimum_order_quantity`, `supplier_sku_note`
- Columns that edit customer-side fields (read-only here, edited in sales step): `product_name`, `brand`, `idn_sku`, `quantity`, `manufacturer_product_name`, `name_en`, `is_unavailable` (is_unavailable toggle stays here because procurement knows first whether supplier can provide)
- `readOnly` when `procurementCompleted=true` — already handled by handsontable:331,401,414-415 pattern, extends to new columns

### 4.4 New: `split-modal.tsx`

- Trigger: "⚡ Разделить позицию" button on invoice-card (visible when `!procurementCompleted` AND `!invoice.frozen_at`)
- Form steps:
  1. Pick source quote_item (dropdown, filtered to quote_items currently 1:1 covered in this invoice)
  2. Add N ≥ 2 child rows, each with: `product_name` (required), `supplier_sku`, `brand`, `quantity_ratio` (required, > 0), `purchase_price_original` (required), `purchase_currency`, `weight_in_kg`, `customs_code`
  3. Each child's `invoice_item.quantity` = `source_quote_item.quantity × quantity_ratio` (computed, shown read-only)
- Submit: server transaction
  - DELETE source invoice_item
  - DELETE source coverage row
  - INSERT N new invoice_items
  - INSERT N new coverage rows `(new_ii_id, source_qi_id, ratio=quantity_ratio_i)`

### 4.5 New: `merge-modal.tsx`

- Trigger: "⚡ Объединить позиции" button on invoice-card
- Form steps:
  1. Select N ≥ 2 source quote_items via checkbox (from invoice-card's current 1:1 coverage)
  2. Define merged row: `product_name` (required), `supplier_sku`, `brand`, `quantity` (default: max of sources, editable), `purchase_price_original`, `purchase_currency`, `weight_in_kg`, `customs_code`
  3. Validation: each selected quote_item must have exactly 1 covering invoice_item in this invoice (no chain-merge)
- Submit: server transaction
  - DELETE N source invoice_items
  - DELETE N source coverage rows
  - INSERT 1 merged invoice_item
  - INSERT N new coverage rows `(merged_ii_id, source_qi_id_i, ratio=1)`

### 4.6 `composition-picker.tsx` (sales-side) updates

- Alternative card now shows:
  - Supplier name + country (unchanged)
  - Price (unchanged)
  - **Coverage summary**: e.g., "→ болт ×1 + шайба ×2" (split) or "← болт, гайка, шайба объединены" (merge) or nothing (1:1)
- Picking an alternative for a merged invoice_item: backend applies same invoice_id to all N covered quote_items atomically

---

## 5. RLS Policies

### 5.1 `invoice_items` (mirror `invoice_item_prices` from migration 263)

- SELECT: admin, top_manager, procurement, procurement_senior, head_of_procurement, sales, head_of_sales, finance, quote_controller, spec_controller
- INSERT: admin, procurement, procurement_senior, head_of_procurement
- UPDATE: admin, procurement, procurement_senior, head_of_procurement
- DELETE: admin, head_of_procurement

Policy template:
```sql
CREATE POLICY "invoice_items_select" ON kvota.invoice_items FOR SELECT
USING (
  organization_id IN (
    SELECT ur.organization_id FROM kvota.user_roles ur
    JOIN kvota.roles r ON r.id = ur.role_id
    WHERE ur.user_id = auth.uid()
    AND r.slug IN (...)
  )
);
-- repeat for INSERT, UPDATE, DELETE with appropriate role sets
```

### 5.2 `invoice_item_coverage` (org-scoped via JOIN)

Same 10/4/2 role pattern, but org resolved via invoice_items:
```sql
CREATE POLICY "coverage_select" ON kvota.invoice_item_coverage FOR SELECT
USING (
  invoice_item_id IN (
    SELECT id FROM kvota.invoice_items
    -- invoice_items RLS already filters to user's org
  )
);
```

---

## 6. Migration Order

Single PR with:
- `migrations/281_create_invoice_items.sql` — CREATE TABLE + indexes + RLS
- `migrations/282_create_invoice_item_coverage.sql` — CREATE TABLE + indexes + RLS
- `migrations/283_backfill_invoice_items.sql` — INSERT from invoice_item_prices + quote_items; INSERT coverage with ratio=1; idempotent with ON CONFLICT DO NOTHING
- `migrations/284_drop_legacy_schema.sql` — DROP TABLE invoice_item_prices; ALTER TABLE quote_items DROP COLUMN invoice_id, purchase_price_original, purchase_currency, base_price_vat, price_includes_vat, customs_code, supplier_country, weight_in_kg, production_time_days, minimum_order_quantity, dimension_height_mm, dimension_width_mm, dimension_length_mm, license_ds_cost, license_ss_cost, license_sgr_cost;

Apply via `scripts/apply-migrations.sh` on VPS. Python + frontend code for new schema ships in the same commit range.

---

## 7. Open Items

### 7.1 Markup/supplier_discount semantics with merge

When 1 invoice_item (crepёж ×100) covers 3 quote_items (болт, гайка, шайба ×100 each) with different markups/discounts, `get_composed_items()` must pick one. Options:
- **(a) Use first quote_item's markup** — arbitrary, may be wrong
- **(b) Use max markup across covered quote_items** — conservative for sales
- **(c) Weighted average by quantity** — mathematically sound but complex
- **(d) Force procurement to set markup on invoice_items directly for merged positions** — moves decision to procurement; contradicts "markup is sales-side"

**Proposal:** Default (a), surface a UI warning in sales composition picker when merged invoice has divergent markups across covered quote_items. Fine-tune based on real usage.

### 7.2 Backfill of product_name when iip row has no direct mapping

Migration 283 copies `product_name` from `quote_items`. If a quote_item's `product_name` is ambiguous (e.g., many-to-many in existing data), backfill assigns per the 1:1 mapping in `invoice_item_prices` — no data is invented. Verified by test against prod snapshot.

### 7.3 position INT ordering within invoice

During backfill, `position` assigned ORDER BY source `iip.created_at`. Manual reordering via drag-drop is out of scope for Phase 5c — if procurement needs it, propose in follow-up.

### 7.4 Invoice XLS export

`services/xls_export_service.py` currently reads `quote_items WHERE invoice_id = :id`. After migration 284, rewrite to `SELECT FROM invoice_items WHERE invoice_id = :id JOIN coverage for covers-list column`. Fields to export stay the same. Ensure bilingual XLS (Phase 4b) still works — `name_en` stays on quote_items (customer-side); invoice_items has `product_name` only. English export uses `quote_item.name_en` fallback when invoice_item matches a single quote_item, and `invoice_item.product_name` when invoice_item is split/merged (no customer-side translation available by design).

---

## 8. Success Criteria

1. `invoice_items` and `invoice_item_coverage` tables exist with RLS enabled (post-migration 282).
2. Backfill produces invoice_items rows for every iip row; bit-identity test passes on 5+ prod quotes (calc output unchanged).
3. `invoice_item_prices` table and 16 legacy columns on `quote_items` are DROP'ed (post-migration 284).
4. Procurement user can create a second invoice from a different supplier for already-assigned items via the non-destructive "Назначить в КП" dropdown; items remain visible in the first invoice's coverage.
5. Split modal produces N invoice_items from 1 quote_item; calc engine receives N calc-ready rows.
6. Merge modal produces 1 invoice_item from N quote_items; calc engine receives 1 calc-ready row.
7. Edit-gate: user can edit invoice after `sent_at` without approval, as long as `quote.procurement_completed_at IS NULL`.
8. CompositionPicker correctly displays split and merged alternatives with coverage summary text.
9. Engine immutability: `git diff` on 3 locked files shows zero changes in the Phase 5c merge commit range.
