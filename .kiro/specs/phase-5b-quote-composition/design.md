# Technical Design — Phase 5b: Quote Composition Engine

## Architecture Decision

A new junction table `kvota.invoice_item_prices` holds per-item prices from each competing supplier invoice, with `(invoice_id, quote_item_id, version)` uniqueness and a `frozen_at` column for immutability. A pointer column `quote_items.composition_selected_invoice_id` designates which invoice's prices apply to each item. A new Python module `services/composition_service.py` joins these tables and returns item dicts in the exact shape the current `quote_items` SELECT returns — so `build_calculation_inputs()` and the locked calculation engine receive the same contract as today. The adapter hook is placed at the three `quote_items` read sites in `main.py` (not inside `build_calculation_inputs()` itself), keeping the locked files byte-identical. A new `api/composition.py` module exposes the composition GET/POST endpoints following the project's API-first pattern; the Next.js calculation step renders a new `CompositionPicker` card between `CalculationForm` and `CalculationResults`. Invoice verification is a new state on `kvota.invoices` (`verified_at`/`verified_by` columns), and edit-verified approval reuses the existing `services/approval_service.py` + `kvota.approvals` infrastructure — no new approval machinery.

---

## Requirements Traceability

| Requirement | Satisfied by |
|---|---|
| 1.1 — Multiple invoices on same quote | Migration 263 (junction); 1.2 no schema constraint preventing overlap |
| 1.2 — Junction row inserted on invoice creation | `api/composition.py` or modified `api/procurement_invoices.py` insert hook; also direct invoice creation path in `main.py:18971-19094` |
| 1.3 — Legacy pointer preserved | No change to `quote_items.invoice_id` write logic |
| 1.4 — `created_by` persistence | Migration 263 column + service write |
| 1.5 — Neither invoice overrides silently | Composition Service returns all alternatives, picker shows them all |
| 2.1-2.2 — GET composition returns selections + alternatives | `api/composition.py::get_composition(request)` |
| 2.3-2.4 — Picker renders with fallback | `composition-picker.tsx` + `useQuoteComposition` hook |
| 2.5-2.7 — POST composition atomic validation+apply | `api/composition.py::apply_composition(request)` + `composition_service.apply_composition()` |
| 2.8 — Picker above Calculate button | Modification in `calculation-step.tsx` |
| 3.1-3.7 — Composition Service contract + 3 call site replacement | `services/composition_service.py` + main.py diffs at 13303/14188/14846 |
| 4.1-4.4 — Engine immutability + regression test | `tests/test_calc_regression_phase_5b.py` |
| 5.1-5.5 — Invoice verification state | Migration 264 + `api/composition.py::verify_invoice` + migration 265 backfill |
| 6.1-6.7 — Edit-verified approval flow | `api/composition.py::edit_request`/`approve`/`reject` reusing `approval_service.request_approval` |
| 7.1-7.5 — Bypass logic | Modification in `main.py:18971-19094` invoice creation flow |
| 8.1-8.5 — KP version freeze | `composition_service.freeze_composition()` + hook at send flow (or admin action) |
| 9.1-9.5 — Backward compatibility | Migration 265 idempotent backfill + regression test |
| 10.1-10.6 — RLS + access control | Migration 263 RLS policies + `canAccessQuoteComposition()` in `entities/quote/queries.ts` |

---

## Data Model

### Migration 263 — `invoice_item_prices` junction

```sql
-- migrations/263_invoice_item_prices.sql
-- Phase 5b Task 1: Junction table for multi-supplier quote composition
-- Holds per-item prices from competing supplier invoices with versioning.

SET search_path TO kvota, public;

CREATE TABLE IF NOT EXISTS kvota.invoice_item_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Junction keys
    invoice_id    UUID NOT NULL REFERENCES kvota.invoices(id)    ON DELETE CASCADE,
    quote_item_id UUID NOT NULL REFERENCES kvota.quote_items(id) ON DELETE CASCADE,

    -- Price fields — mirror quote_items shape so composition_service can overlay
    purchase_price_original NUMERIC(18,4) NOT NULL,
    purchase_currency       TEXT          NOT NULL,
    base_price_vat          NUMERIC(18,4),
    price_includes_vat      BOOLEAN       NOT NULL DEFAULT false,

    -- Optional supplier-offer metadata
    production_time_days   INTEGER,
    minimum_order_quantity INTEGER,
    supplier_notes         TEXT,

    -- Versioning
    version    INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    frozen_at  TIMESTAMPTZ,
    frozen_by  UUID REFERENCES auth.users(id),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES auth.users(id),

    CONSTRAINT uq_iip_invoice_item_version
        UNIQUE (invoice_id, quote_item_id, version)
);

CREATE INDEX IF NOT EXISTS idx_iip_invoice
    ON kvota.invoice_item_prices(invoice_id);

CREATE INDEX IF NOT EXISTS idx_iip_quote_item
    ON kvota.invoice_item_prices(quote_item_id);

-- Partial index for "current editable row" lookups — the 99% path
CREATE INDEX IF NOT EXISTS idx_iip_active
    ON kvota.invoice_item_prices(quote_item_id, invoice_id)
    WHERE frozen_at IS NULL;

COMMENT ON TABLE kvota.invoice_item_prices IS
    'Phase 5b: Per-item prices from supplier invoices. Junction between invoices and quote_items. Multiple invoices can hold prices for the same quote_item; quote_items.composition_selected_invoice_id picks the active one.';

COMMENT ON COLUMN kvota.invoice_item_prices.frozen_at IS
    'NULL = editable; NOT NULL = frozen snapshot (set when KP is sent or manually frozen). Frozen rows are immutable — edits create a new version row.';

-- RLS — mirror the invoices table visibility via a reference predicate
ALTER TABLE kvota.invoice_item_prices ENABLE ROW LEVEL SECURITY;

CREATE POLICY iip_select ON kvota.invoice_item_prices
    FOR SELECT
    USING (
        invoice_id IN (SELECT id FROM kvota.invoices)
        -- invoices RLS policy already filters by tier; referencing it keeps
        -- iip visibility in sync automatically. Do not duplicate the predicate.
    );

CREATE POLICY iip_insert ON kvota.invoice_item_prices
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('procurement', 'procurement_senior', 'head_of_procurement', 'admin')
        )
    );

CREATE POLICY iip_update ON kvota.invoice_item_prices
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('procurement', 'procurement_senior', 'head_of_procurement', 'admin')
        )
    );

CREATE POLICY iip_delete ON kvota.invoice_item_prices
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('head_of_procurement', 'admin')
        )
    );
```

### Migration 264 — Composition pointer + verification columns

```sql
-- migrations/264_composition_pointer_and_verification.sql
-- Phase 5b Task 2: Add composition pointer on quote_items and verification state on invoices.

SET search_path TO kvota, public;

-- Composition pointer: which invoice's iip row is active for this item?
ALTER TABLE kvota.quote_items
    ADD COLUMN IF NOT EXISTS composition_selected_invoice_id UUID NULL
        REFERENCES kvota.invoices(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_quote_items_composition_pointer
    ON kvota.quote_items(composition_selected_invoice_id)
    WHERE composition_selected_invoice_id IS NOT NULL;

COMMENT ON COLUMN kvota.quote_items.composition_selected_invoice_id IS
    'Phase 5b: Active composition — which invoice provides this item''s price. NULL = use legacy quote_items.invoice_id values (pre-composition quotes).';

-- Verification state on invoices
ALTER TABLE kvota.invoices
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS verified_by UUID NULL REFERENCES auth.users(id);

CREATE INDEX IF NOT EXISTS idx_invoices_verified
    ON kvota.invoices(verified_at)
    WHERE verified_at IS NOT NULL;

COMMENT ON COLUMN kvota.invoices.verified_at IS
    'Phase 5b: When procurement marked this invoice as ready for composition. Locks direct edits — subsequent edits require head_of_procurement approval.';
```

### Migration 265 — Backfill

```sql
-- migrations/265_backfill_composition.sql
-- Phase 5b Task 3: Idempotent backfill of iip + composition pointer + verification.

SET search_path TO kvota, public;

-- 1) Populate invoice_item_prices from existing quote_items.invoice_id assignments
INSERT INTO kvota.invoice_item_prices (
    invoice_id,
    quote_item_id,
    purchase_price_original,
    purchase_currency,
    base_price_vat,
    price_includes_vat,
    version,
    created_at,
    updated_at,
    created_by
)
SELECT
    qi.invoice_id,
    qi.id AS quote_item_id,
    COALESCE(qi.purchase_price_original, qi.base_price_vat, 0) AS purchase_price_original,
    COALESCE(qi.purchase_currency, 'USD') AS purchase_currency,
    qi.base_price_vat,
    COALESCE(qi.price_includes_vat, false),
    1,
    qi.created_at,
    qi.updated_at,
    qi.created_by
FROM kvota.quote_items qi
WHERE qi.invoice_id IS NOT NULL
ON CONFLICT (invoice_id, quote_item_id, version) DO NOTHING;

-- 2) Set composition pointer = legacy invoice_id for existing items
UPDATE kvota.quote_items
SET composition_selected_invoice_id = invoice_id
WHERE invoice_id IS NOT NULL
  AND composition_selected_invoice_id IS NULL;

-- 3) Mark existing completed invoices as verified
UPDATE kvota.invoices
SET verified_at = COALESCE(verified_at, updated_at, created_at)
WHERE status = 'completed'
  AND verified_at IS NULL;
```

**Post-migration steps (manual, after SSH apply):**
```bash
ssh beget-kvota 'docker exec -i supabase-db psql -U postgres -d postgres -c "NOTIFY pgrst, '\''reload schema'\''"'
cd frontend && npm run db:types
```

---

## File Structure

### CREATE

| Path | Purpose |
|---|---|
| `migrations/263_invoice_item_prices.sql` | Junction table |
| `migrations/264_composition_pointer_and_verification.sql` | Column additions |
| `migrations/265_backfill_composition.sql` | Idempotent backfill |
| `services/composition_service.py` | Pure Python service — the composition brain |
| `api/composition.py` | Python API endpoint module (follows `api/deals.py` pattern) |
| `tests/test_composition_service.py` | Pytest unit tests for composition_service |
| `tests/test_composition_api.py` | Pytest API tests for the endpoints |
| `tests/test_calc_regression_phase_5b.py` | Regression test asserting bit-identical calculations on 5 existing quotes |
| `frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx` | CompositionPicker component |
| `frontend/src/features/quotes/ui/calculation-step/edit-verified-request-modal.tsx` | Modal for editing verified invoices (approval request) |
| `frontend/src/features/quotes/ui/calculation-step/mutations.ts` | Server Actions wrapping the composition API |

### MODIFY

| Path | Lines | Purpose |
|---|---|---|
| `main.py` | ~13303, 14188, 14846 | Replace `quote_items` reads with `composition_service.get_composed_items()` call |
| `main.py` | register new routes | `/api/quotes/{id}/composition`, `/api/invoices/{id}/verify`, `/api/invoices/{id}/edit-request`, `/api/invoices/{id}/edit-approval/{approval_id}/{action}` |
| `main.py` | 18971-19094 | Add same-supplier bypass detection to invoice creation flow; include `bypass_reason` in response |
| `frontend/src/entities/quote/queries.ts` | add `useQuoteComposition` hook + `canAccessQuoteComposition` guard |
| `frontend/src/features/quotes/ui/calculation-step/calculation-step.tsx` | ~line 40 | Render `<CompositionPicker />` between `<CalculationForm />` and `<CalculationResults />` |
| `frontend/src/shared/lib/roles.ts` | add `canEditComposition()` / `canApproveInvoiceEdit()` helpers if not present |

### DO NOT TOUCH

- `calculation_engine.py`
- `calculation_models.py`
- `calculation_mapper.py`

---

## Composition Service Interface

```python
# services/composition_service.py

from typing import TypedDict, List, Dict, Optional
from dataclasses import dataclass

class ComposedItem(TypedDict):
    """Shape returned by get_composed_items — matches current quote_items read shape.
    Fields below are the minimum the calculation pipeline relies on.
    """
    id: str
    quote_id: str
    invoice_id: Optional[str]
    purchase_price_original: float
    purchase_currency: str
    base_price_vat: Optional[float]
    price_includes_vat: bool
    quantity: int
    weight_in_kg: Optional[float]
    customs_code: Optional[str]
    supplier_country: Optional[str]
    is_unavailable: bool
    import_banned: bool
    # ... all remaining quote_items fields passed through unchanged

@dataclass
class ValidationResult:
    valid: bool
    errors: List[Dict[str, str]]  # [{"item_id": ..., "reason": ...}]

@dataclass
class CompositionView:
    """Shape returned to the GET composition endpoint."""
    quote_id: str
    items: List[Dict]  # items with nested alternatives
    can_edit: bool
    composition_complete: bool  # True if every item has a selection

def get_composed_items(
    quote_id: str,
    supabase_client,
) -> List[ComposedItem]:
    """Return items for calculation, with price fields overlaid from the active composition.

    For each quote_item:
      - If composition_selected_invoice_id IS NOT NULL AND an iip row exists for
        (composition_selected_invoice_id, quote_item_id):
          → overlay purchase_price_original, purchase_currency, base_price_vat,
            price_includes_vat from the iip row
      - Otherwise:
          → return the quote_items row as-is (legacy path)

    Executes one SQL query using a LEFT JOIN (no N+1).
    Does NOT import from calculation_engine.py / calculation_models.py / calculation_mapper.py.
    """

def get_composition_view(
    quote_id: str,
    supabase_client,
    user_id: str,
) -> CompositionView:
    """Return composition + all alternatives for the picker UI.

    Query: LEFT JOIN quote_items ↔ invoice_item_prices ↔ invoices ↔ suppliers.
    Groups alternatives per quote_item.
    """

def apply_composition(
    quote_id: str,
    selection_map: Dict[str, str],  # {quote_item_id: invoice_id}
    supabase_client,
    user_id: str,
    quote_updated_at: str,  # optimistic concurrency check
) -> None:
    """Persist the user's composition choice.

    1. Validate via validate_composition().
    2. Check quotes.updated_at matches the provided value (409 if stale).
    3. UPDATE quote_items.composition_selected_invoice_id for all affected items
       in a single transaction.

    Raises:
      ValidationError — if any selection doesn't exist in invoice_item_prices
      ConcurrencyError — if the quote was modified since the user loaded it
    """

def validate_composition(
    quote_id: str,
    selection_map: Dict[str, str],
    supabase_client,
) -> ValidationResult:
    """Verify every (quote_item_id, invoice_id) pair has a matching iip row.

    Returns ValidationResult with per-item error reasons.
    Uses a single SELECT to check all pairs.
    """

def freeze_composition(
    quote_id: str,
    user_id: str,
    supabase_client,
) -> int:
    """Stamp frozen_at on all iip rows currently selected for this quote.

    Returns the number of rows frozen.
    Idempotent — already-frozen rows are skipped.
    """
```

---

## API Endpoint Contracts

All endpoints follow `api-first.md` docstring standard and response format.

### `GET /api/quotes/{quote_id}/composition`

```python
async def get_composition(request):
    """Return composition state with alternatives for the calculation step picker.

    Path: GET /api/quotes/{quote_id}/composition

    Params:
        quote_id: str (required, path) — Quote to compose

    Returns:
        quote_id: str
        items: List[{quote_item_id, name, quantity, selected_invoice_id, alternatives: [{invoice_id, supplier_name, supplier_country, purchase_price_original, purchase_currency, production_time_days}]}]
        can_edit: bool — Whether the current user can POST composition changes
        composition_complete: bool — True if every item has a selected_invoice_id

    Roles: sales, head_of_sales, head_of_procurement, admin
    """
```

### `POST /api/quotes/{quote_id}/composition`

```python
async def apply_composition(request):
    """Persist per-item supplier selection.

    Path: POST /api/quotes/{quote_id}/composition

    Params:
        quote_id: str (required, path)
        selection: Dict[quote_item_id, invoice_id] (required, body)
        quote_updated_at: str (required, body) — Optimistic concurrency token

    Returns:
        quote_id: str
        composition_complete: bool

    Side Effects:
        - Updates quote_items.composition_selected_invoice_id for affected items
        - Bumps quotes.updated_at

    Errors:
        400 VALIDATION_ERROR — selection references (item, invoice) pair with no iip row
        404 NOT_FOUND — quote not visible to current user
        409 CONFLICT — quote_updated_at doesn't match current value (concurrent edit)

    Roles: sales, head_of_sales, head_of_procurement, admin
    """
```

### `POST /api/invoices/{invoice_id}/verify`

```python
async def verify_invoice(request):
    """Mark a supplier invoice as verified (ready for composition).

    Path: POST /api/invoices/{invoice_id}/verify

    Returns:
        invoice_id: str
        verified_at: ISO timestamp
        verified_by: user_id

    Side Effects:
        - Sets invoices.verified_at = now()
        - Sets invoices.verified_by = current_user_id

    Roles: procurement, procurement_senior, head_of_procurement, admin
    """
```

### `POST /api/invoices/{invoice_id}/edit-request`

```python
async def request_invoice_edit(request):
    """Request head_of_procurement approval to edit a verified invoice.

    Path: POST /api/invoices/{invoice_id}/edit-request

    Params:
        invoice_id: str (required, path)
        proposed_changes: Dict[field, {old, new}] (required, body) — Field-level diff
        reason: str (required, body) — Justification

    Returns:
        approval_id: str — Created approval row ID
        status: "pending"

    Side Effects:
        - Creates a row in kvota.approvals via approval_service.request_approval()
        - payload JSONB = { "type": "edit_verified_invoice", "invoice_id": ..., "diff": ..., "reason": ... }
        - Target role: head_of_procurement

    Roles: procurement, procurement_senior, head_of_procurement, admin
    """
```

### `POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/approve`

```python
async def approve_invoice_edit(request):
    """Approve a pending edit request and apply the changes atomically.

    Path: POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/approve

    Returns:
        approval_id: str
        status: "approved"
        applied_changes: Dict[field, new_value]

    Side Effects:
        - Reads the JSON diff from kvota.approvals.payload
        - Applies the diff to invoices + invoice_item_prices rows atomically
        - Marks approval row as approved with approver_id = current_user

    Errors:
        403 FORBIDDEN — current user is not head_of_procurement or admin
        404 NOT_FOUND — approval not found or already processed
        409 CONFLICT — invoice was modified since the edit request was created

    Roles: head_of_procurement, admin
    """
```

### `POST /api/invoices/{invoice_id}/edit-approval/{approval_id}/reject`

Symmetric to approve; marks the approval as rejected, applies no changes, records rejector's reason.

---

## Frontend Component Tree

```
<CalculationStep>                          ← frontend/.../calculation-step.tsx (MODIFY)
├── <CalculationActionBar>                 ← unchanged, Calculate button at lines 90-102
└── <div className="p-6 space-y-6">
    ├── <CalculationForm>                  ← unchanged
    ├── <CompositionPicker>                ← NEW: composition-picker.tsx
    │   ├── data: useQuoteComposition(id)
    │   ├── table row per quote_item
    │   │   └── radio per alternative invoice
    │   └── onChange → applyComposition() Server Action
    └── <CalculationResults>               ← unchanged
```

### `useQuoteComposition(quoteId)` — entity query

Location: `frontend/src/entities/quote/queries.ts`

```typescript
// Pseudocode — real impl reads from Supabase via TanStack Query
export function useQuoteComposition(quoteId: string) {
  return useQuery({
    queryKey: ['quote', quoteId, 'composition'],
    queryFn: () => fetchQuoteComposition(quoteId),
    staleTime: 30_000,
  });
}

// Server-side data fetcher — uses Supabase direct (simple read, no business logic)
async function fetchQuoteComposition(quoteId: string): Promise<CompositionView> {
  // LEFT JOIN quote_items → invoice_item_prices → invoices → suppliers
  // Return shape matches Composition API GET response (same Python DTO)
}

// Access guard — used by the page component before rendering the picker
export async function canAccessQuoteComposition(
  quoteId: string,
  user: { id: string; roles: string[]; orgId: string }
): Promise<boolean> {
  // Delegates to canAccessQuote() — composition inherits quote visibility
}
```

### `applyComposition(quoteId, selection)` — Server Action

Location: `frontend/src/features/quotes/ui/calculation-step/mutations.ts`

```typescript
"use server";
import { apiServerClient } from "@/shared/lib/api-server";

export async function applyComposition(
  quoteId: string,
  selection: Record<string, string>,
  quoteUpdatedAt: string,
) {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(`/quotes/${quoteId}/composition`, {
    method: "POST",
    body: JSON.stringify({ selection, quote_updated_at: quoteUpdatedAt }),
  });
  if (!res.success) throw new Error(res.error?.message || "Failed");

  revalidatePath(`/quotes/${quoteId}`);
  return res.data;
}
```

---

## Adapter Hook Strategy

The three `quote_items` read sites in `main.py` each look roughly like:

```python
# Before (3 sites): main.py:13303, main.py:14188, main.py:14846
items_result = supabase.from_("quote_items") \
    .select("*") \
    .eq("quote_id", quote_id) \
    .execute()
items = items_result.data
```

Replace with:

```python
# After
from services.composition_service import get_composed_items
items = get_composed_items(quote_id, supabase)
```

**Key properties:**
- `build_calculation_inputs(items, variables)` signature unchanged — still takes `List[Dict]`.
- The dict shape from `get_composed_items()` is a superset of the current read (all current fields preserved, price fields potentially overlaid).
- The third call site at `main.py:14846` will be verified by grepping for `build_calculation_inputs(` at Task 5 start; if the exact line number drifted, the grep finds the new location.

**Why not inject composition into the calc function itself:** Keeps the locked function byte-identical. Preserves its pure-function signature for testing. See `research.md` § "Architecture pattern evaluation" for the rejected alternatives.

---

## Invoice Creation Bypass Logic

Existing invoice creation at `main.py:18971-19094`. Add this detection step after validating the supplier and before pre-filling defaults:

```python
# Detect whether this supplier already has an invoice on this quote
existing = supabase.from_("invoices") \
    .select("id") \
    .eq("quote_id", quote_id) \
    .eq("supplier_id", supplier_id) \
    .limit(1) \
    .execute()

if existing.data:
    bypass_reason = "same_supplier"
    # Skip BOTH logistics AND customs pre-fill
    pickup_country = form_data.get("pickup_country")  # user-provided only
    pickup_location_id = form_data.get("pickup_location_id")
    total_weight_kg = form_data.get("total_weight_kg")
    total_volume_m3 = form_data.get("total_volume_m3")
else:
    bypass_reason = "new_supplier"
    # Pre-fill logistics (existing Phase 5a behavior), skip customs
    pickup_country = form_data.get("pickup_country") or supplier.get("country")
    # ... other logistics pre-fills stay
    # Customs fields NOT pre-filled either way — customs is per-item (HS codes on quote_items)
```

Response shape additions:

```python
return {
    "success": True,
    "data": {
        "invoice_id": new_invoice_id,
        "bypass_reason": bypass_reason,  # "same_supplier" | "new_supplier"
        # ... rest unchanged
    }
}
```

Frontend displays a small info banner when `bypass_reason == "same_supplier"`:
> ℹ Уже есть КП от этого поставщика — поля не предзаполнены.

---

## Access Control Integration

Per `.kiro/steering/access-control.md`:

| Layer | Enforcement |
|---|---|
| Database (RLS) | `invoice_item_prices` policies defined in Migration 263 — SELECT references `invoices` visibility, write ops restricted to procurement roles |
| Python API | Every endpoint in `api/composition.py` calls existing quote-visibility check (same pattern as `api/deals.py`) before proceeding; returns 404 on denial |
| Next.js page | `canAccessQuoteComposition(quoteId, user)` guard in `entities/quote/queries.ts`; renders `notFound()` if denied |
| Role helpers | `canEditComposition(user)` in `shared/lib/roles.ts` — returns true for `sales` (own), `head_of_sales` (group), `head_of_procurement` (all), `admin` |
| Org scope | Every query in `composition_service.py` filters by `organization_id` as outer boundary — inherited from the existing quote-read pattern |

**Fail-closed default:** unknown role → `canEditComposition` returns `false`.

---

## Error Handling Matrix

| Scenario | HTTP status | Error code | Notes |
|---|---|---|---|
| Selection references non-existent iip row | 400 | `COMPOSITION_INVALID_SELECTION` | Body includes `fields: { item_id: "no matching offer" }` |
| User cannot see quote | 404 | `NOT_FOUND` | Per "404 on denial" rule |
| Concurrent edit (quote_updated_at mismatch) | 409 | `STALE_QUOTE` | User must reload |
| Direct invoice edit while verified, no approval | 409 | `INVOICE_VERIFIED` | Must use edit-request flow |
| Approval applied to already-processed approval | 404 | `APPROVAL_NOT_FOUND` | |
| Head_of_procurement role check fails | 403 | `FORBIDDEN` | Applies to approve/reject endpoints |
| Freeze called on a quote with no composition | 200 | — | Returns `{ frozen_count: 0 }` — not an error |
| Migration 265 re-run | — | — | No-op due to `ON CONFLICT DO NOTHING` + NULL guard on pointer |

---

## Testing Strategy

| Layer | Tool | Coverage |
|---|---|---|
| Unit — `composition_service` | pytest | get_composed_items overlay logic (with/without composition); validate_composition happy + error paths; apply_composition atomicity; freeze_composition idempotency; org_id filter |
| Unit — `api/composition.py` | pytest (using test client) | All endpoints: success, 400, 404, 409, 403 paths |
| Unit — frontend | Vitest | CompositionPicker logic: render with/without selection, handle empty alternatives list, show "only supplier" label, optimistic UI update |
| Regression — calc bit-identity | pytest | Load 5 representative existing quotes (by ID), compute calculations, assert every monetary field matches a pre-migration snapshot |
| E2E — full composition flow | Playwright MCP (localhost:3000 + prod Supabase) | Create quote → procurement creates 2 invoices from 2 suppliers → sales picks per item → Calculate → verify totals |
| E2E — edit-verified approval | Playwright MCP | Mark invoice verified → try to edit → approval modal → submit → approve as head_of_procurement → edit applies |
| E2E — bypass logic | Manual scripted | Create A/B from supplier X (no pre-fill on B); create C from supplier Y (pickup pre-filled, customs not) |

---

## Rollout & Migration Plan

1. **Migrations 263, 264, 265** apply sequentially via `scripts/apply-migrations.sh` (SSH to VPS). Each migration is independently commit-able.
2. **Post-migration:** `NOTIFY pgrst, 'reload schema'` to refresh PostgREST; `cd frontend && npm run db:types` to regenerate Supabase JS types.
3. **Composition service + 3 call-site replacement** ships together (Task 4 + Task 5) so `build_calculation_inputs()` always receives items from the new source. Before that, the backfill ensures the legacy reads still work untouched.
4. **API endpoints** ship before the frontend picker so the backend is callable for testing.
5. **Frontend picker** ships after the API is stable.
6. **Bypass logic** can ship independently of composition — it only affects new invoice creation and is backward-compatible.
7. **Edit-verified approval** ships as a coupled backend+frontend pair (Task 7 + Task 12).
8. **KP freeze** ships last (Task 11 or 13, depending on whether a send flow exists).
9. **Final E2E** on localhost:3000 with prod Supabase, then `git push origin main` → GitHub Actions auto-deploys.

---

## Risks & Mitigations

See `research.md` § "Risk assessment" — not duplicated here.

Most load-bearing risks:
- **Third calc entry point verification:** grep for `build_calculation_inputs(` at start of Task 5.
- **KP-send flow existence for Decision #4:** R8 AC5 allows scope adjustment at implementation time.
- **Backfill idempotency:** `ON CONFLICT DO NOTHING` + `IS NULL` guards.

---

## Out of Scope (deferred to later phases)

- KP version history UI — versioning supported by data model, but no "view old versions" page yet.
- Bulk "select all from supplier X" composition action.
- Automatic supplier scoring / recommendation.
- Multi-currency display conversion inside the picker.
- Changes to the actual KP send mechanism (email, PDF generation).
- Real-time updates when another user changes a composition on the same quote (current MVP uses stale-data 409).
