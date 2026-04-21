# Cost Analysis Port — Tasks

1. **Backend handler.** Create `api/cost_analysis.py` with
   `get_cost_analysis(request, quote_id)` that implements auth, role gate,
   org isolation, aggregation, and returns the standard JSON envelope.
2. **Backend router.** Create `api/routers/cost_analysis.py` wiring the
   handler to `GET /{quote_id}/cost-analysis`.
3. **Wire router.** Update `api/app.py` to register the router at
   `prefix="/quotes"` and export from `api/routers/__init__.py`.
4. **Backend tests.** Add `tests/test_cost_analysis_api.py` covering:
   401 no-auth, 403 wrong role, 403 org mismatch, 404 missing quote,
   200 `has_calculation=false`, 200 happy path with 2-item aggregation,
   markup zero-division safety.
5. **Frontend types + fetcher.** Create
   `frontend/src/features/cost-analysis/types.ts` and
   `frontend/src/features/cost-analysis/api/queries.ts`.
6. **Frontend UI.** Build `cost-analysis-view`, `summary-cards`,
   `waterfall-table`, `not-calculated`.
7. **Frontend route.** Wire
   `frontend/src/app/(app)/quotes/[id]/cost-analysis/page.tsx` —
   server component with session + role gate + fetch + render.
8. **Validation.** Run `ruff check .`, `pytest -v`, `pip install -e .`.
9. **Browser test.** Start localhost stack, verify page + empty state +
   role gate, capture screenshots.
10. **Commit + PR.** Single commit, co-authored, opens PR against main.
