# Implementation Tasks

## Task 1: Extract data helpers into deal_data_service.py
- [ ] Create `services/deal_data_service.py`
- [ ] Copy `fetch_items_with_buyer_companies` from main.py:44841-44869
- [ ] Copy `fetch_enrichment_data` from main.py:44872-44897
- [ ] In main.py, replace both function bodies with import delegations
- [ ] Run `pytest` to verify no regressions

## Task 2: Create api/deals.py endpoint
- [ ] Create `api/deals.py` with `create_deal(request)` handler
- [ ] Add `_get_api_user(request)` helper (same pattern as api/plan_fact.py)
- [ ] Implement full orchestration: validate → spec update → deal create → logistics → invoices → quote update
- [ ] Add structured docstring per api-first.md
- [ ] Register route in main.py: `@rt("/api/deals", methods=["POST"])`
- [ ] Write unit tests: happy path, missing spec_id, no signed scan, wrong org, invoice skip reasons

## Task 3: Refactor Server Action to thin wrapper
- [ ] Replace `confirmSignatureAndCreateDeal` body in `frontend/src/features/quotes/ui/specification-step/mutations.ts`
- [ ] Use `apiServerClient("/deals", { method: "POST", body: ... })`
- [ ] Keep `getSessionUser()` for auth, `revalidatePath` for cache
- [ ] Remove unused Supabase imports if no other function needs them
