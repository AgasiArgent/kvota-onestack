# Architecture Blueprint: POST /api/deals — API-First Deal Creation

## Architecture Decision

New module `api/deals.py` with a single `create_deal(request)` handler, following the `api/plan_fact.py` pattern. Two helper functions extracted from `main.py` into `services/deal_data_service.py`. The `confirmSignatureAndCreateDeal` Server Action becomes a thin wrapper. Route registered in `main.py`.

## Files

### CREATE: `api/deals.py`
Full deal creation orchestration — validate, create, trigger side effects, return structured response.

Imports: `services.database.get_supabase`, `services.logistics_service.initialize_logistics_stages`, `services.currency_invoice_service.generate_currency_invoices, save_currency_invoices`, `services.deal_data_service.fetch_items_with_buyer_companies, fetch_enrichment_data`

Structured docstring per api-first.md standard:
```python
"""Create a deal from a confirmed specification.

Path: POST /api/deals
Params:
    spec_id: str (required) — Specification to convert to deal
    user_id: str (required) — Acting user
    org_id: str (required) — Organization
Returns:
    deal_id: str — Created deal UUID
    deal_number: str — Generated deal number (DEAL-{year}-{NNNN})
    logistics_stages: int — Number of logistics stages created (always 7)
    invoices_created: int — Number of currency invoices generated
    invoices_skipped_reason: str | null — Why invoices were skipped
Side Effects:
    - Updates specification status to 'signed'
    - Updates quote workflow_status to 'deal'
    - Creates 7 logistics stages for the deal
    - Generates currency invoices (when data available)
Roles: sales, admin
"""
```

### CREATE: `services/deal_data_service.py`
Data fetching helpers extracted verbatim from `main.py`:
- `fetch_items_with_buyer_companies(supabase, quote_id)` → `(items, bc_lookup)`
- `fetch_enrichment_data(supabase, org_id)` → `(contracts, bank_accounts)`

### MODIFY: `main.py` (2 changes)
1. Add route registration after existing API routes:
```python
from api.deals import create_deal
@rt("/api/deals", methods=["POST"])
async def post_deals(request):
    return await create_deal(request)
```
2. Replace `_fetch_items_with_buyer_companies` and `_fetch_enrichment_data` bodies with imports from `deal_data_service` (preserves function names for existing callers).

### MODIFY: `frontend/src/features/quotes/ui/specification-step/mutations.ts`
Replace only `confirmSignatureAndCreateDeal` body with `apiServerClient("/deals", ...)` call. All other exports unchanged.

## Data Flow

```
Browser: user clicks "Confirm Signature"
  ↓
Server Action: confirmSignatureAndCreateDeal(specId)
  1. getSessionUser() → {id, orgId}
  2. apiServerClient("/deals", POST, {spec_id, user_id, org_id})
     ↓
     api/deals.create_deal(request):
       1. Parse + validate body (spec_id, user_id, org_id)
       2. SELECT specification → verify org match + signed_scan_url
       3. SELECT quote → total_amount, currency, idn_quote, seller_company_id
       4. SELECT seller_company → {id, name}
       5. Generate deal_number: DEAL-{year}-{count+1:04d}
       6. UPDATE specification SET status='signed'
       7. INSERT deal → on error: rollback spec status, return 500
       8. UPDATE quote SET workflow_status='deal'
       9. initialize_logistics_stages(deal_id, user_id) → 7 stages
      10. Currency invoices:
          - fetch_items_with_buyer_companies(quote_id)
          - if no items → skip_reason = "No items in quote"
          - elif no bc_lookup → skip_reason = "No buyer companies assigned"
          - elif no seller_company → skip_reason = "No seller company on quote"
          - else: generate + save → invoices_created = len(invoices)
     ↓
     return {success, data: {deal_id, deal_number, logistics_stages, invoices_created, invoices_skipped_reason}}
  3. revalidatePath("/quotes")
  4. return res.data
```

## Build Sequence

1. **Extract helpers** — create `deal_data_service.py`, replace main.py bodies with imports
2. **Python endpoint** — create `api/deals.py`, register route in main.py
3. **Server Action refactor** — replace `confirmSignatureAndCreateDeal` body
4. **Tests** — unit tests for endpoint + helpers

## Risks & Critical Details

### Workflow status — RESOLVED
Confirmed with product: use `WorkflowStatus.DEAL = "deal"` (the canonical final status). `spec_signed` was a Next.js bug — no intermediate state needed. The current Server Action incorrectly writes `spec_signed`; the new endpoint writes `deal`.

### Deal number race condition
Count-based numbering has a race under concurrent requests. Acceptable at current scale. Future: DB sequence.

### Logistics failure = full request failure
REQ-003 requires logistics failure to fail the request. This differs from FastHTML (which swallows). The deal record will exist but without stages — log deal_id for manual repair.

### Invoice skip vs error
Missing prerequisites → `invoices_skipped_reason`, `success: true`. Exception during generation → also `success: true` with reason = "Invoice generation failed: {error}". Deal is valid without invoices.

### `_get_api_user` duplication
Each `api/` module has its own copy (existing convention from `plan_fact.py`). Future cleanup → `api/auth_helpers.py`.
