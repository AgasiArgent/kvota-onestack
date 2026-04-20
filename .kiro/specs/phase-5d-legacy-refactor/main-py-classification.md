# main.py Classification — Phase 5d Group 3 Task 8

Generated: 2026-04-18
Scope: 16 main.py ambiguous sites + 4 open questions
Author: Explore agent `ab55c17ae137104f9` + coordinator re-classification

## Classification policy applied

Per user decision 2026-04-18 + design.md §2.5:
**FastHTML HTML-rendering paths are DORMANT regardless of whether they contain raw `quote_items` SELECTs. Migration 284 will break them at runtime — accepted trade-off.**

Only paths that (a) return JSON for a Next.js or `/api/*` consumer AND (b) read legacy columns directly are BLOCKER.

Coordinator re-classified several sites from BLOCKER → DORMANT after noting the explore agent's own "HTML rendering" annotation triggers the DORMANT rule.

## Part 1: Line-by-line classification

| Line | Function / context | Items source | Classification | Notes |
|------|--------------------|--------------|----------------|-------|
| 13044 | `_calc_combined_duty` helper | helper parameter | FALSE POSITIVE | Calc helper — items pass through from upstream composed output |
| 13174 | `build_calculation_inputs` | param from caller | FALSE POSITIVE | Receives from `get_composed_items` via caller |
| 13381 | `preview_calculation_form` handler | `get_composed_items(quote_id, supabase)` L13371 | FALSE POSITIVE | Explicit composition_service call |
| 14076 | `POST /calculate` handler | `get_composed_items(quote_id, supabase)` L14062 | FALSE POSITIVE | Explicit composition_service call |
| 14799 | `api_create_calculation` | `get_composed_items(quote_id, supabase)` L14749 | FALSE POSITIVE | Explicit composition_service call |
| 17814 | `invoice_card()` nested fn (HTML render) | raw `quote_items` SELECT L17653 | DORMANT | FastHTML `/procurement/{id}` workspace; migration 284 breaks accepted |
| 17845 | `invoice_card()` detail table (HTML render) | raw `quote_items` SELECT L17653 | DORMANT | Same FastHTML handler as 17814 |
| 20095 | invoice cards loop (HTML render) | raw `quote_items` SELECT L20041 | DORMANT | FastHTML page |
| 20105 | invoice detail table (HTML render) | raw `quote_items` SELECT L20041 | DORMANT | Same FastHTML handler as 20095 |
| 20932-20935 | logistics card (HTML render) | raw `quote_items` SELECT L20474 | DORMANT | FastHTML logistics page |
| 22240 | `customs_item_card()` (HTML render) | raw `quote_items` SELECT L22131 | DORMANT | FastHTML customs workspace (per Q3 below) |
| 22293 | `customs_item_card()` price calc (HTML render) | raw `quote_items` SELECT L22131 | DORMANT | Same FastHTML handler |
| 25234 | invoice detail render (HTML render) | raw `quote_items` SELECT L25209 | DORMANT | FastHTML invoice detail page |
| 25314 | invoice detail display (HTML render) | raw `quote_items` SELECT L25286 | DORMANT | Same FastHTML detail family |
| 30482 | finance tab totals (HTML render) | raw `quote_items` SELECT L30475 | DORMANT | FastHTML finance page |
| 43312 | registry invoice totals (HTML render) | raw `quote_items` SELECT L43302 | DORMANT | FastHTML registry page |

## Part 2: Open questions

### Q1: main.py:19828-19844 `api_bulk_update_items`

- **Route:** `PATCH /api/procurement/{quote_id}/items/bulk`
- **Response type:** `JSONResponse`
- **Decorator:** `@rt` (FastHTML router) BUT returns JSON
- **Next.js caller evidence:** Next.js procurement-handsontable save path
- **Answer:** **BLOCKER** — JSON API despite FastHTML router; Next.js consumer
- **Pattern:** B (write to `invoice_items` directly) or E (skip write if column dropped, surface move to Next.js entity-mutation path per Phase 5c)

### Q2: main.py:19438-19442 `api_complete_invoice`

- **Route:** `POST /api/procurement/{quote_id}/invoices/{invoice_id}/complete`
- **Response type:** JSON validation response
- **Next.js caller evidence:** Pure JSON API, called by completion mutation
- **Answer:** **BLOCKER** — JSON validation reading legacy columns
- **Pattern:** D (use `composition_service.is_procurement_complete`)

### Q3: main.py:22131-22144 customs workspace

- **Route:** `GET /customs/{quote_id}` (`@rt` FastHTML)
- **Response type:** HTML (`page_layout` + FT components)
- **Next.js caller evidence:** none — not referenced from `frontend/src/features/customs/`
- **Answer:** **DORMANT** — FastHTML legacy page
- **Implication:** 22240/22293 (inside this handler) are also DORMANT

### Q4: `services/quote_version_service.py::create_quote_version`

- **File:** `services/quote_version_service.py`
- **Function:** `create_quote_version` (L13-99+)
- **Data source:** receives `items` as parameter — does NOT call `get_composed_items` internally
- **Answer:** **MIXED / VERIFY UPSTREAM**
  - The function itself is parameter-safe
  - ALL callers must be audited to confirm they pass composed items (not raw `quote_items`)
  - Group 2 Task 7 must include a caller-audit step; if any caller passes raw rows, escalate that caller to BLOCKER

## Summary

| Category | Count | Action |
|----------|-------|--------|
| FALSE POSITIVE | 5 lines | No refactor needed |
| BLOCKER | 2 JSON API handlers (Q1 + Q2) | Refactor in Group 3 Task 10 |
| DORMANT | 14 lines (16 of initial + Q3 handler) | No refactor — FastHTML accepts 284 breakage |
| MIXED / VERIFY | 1 (Q4 quote_version_service callers) | Audit in Group 2 Task 7 |

## Group 3 task refinement

Based on this classification, **Group 3 Task 10 scope shrinks to 2 handlers**:

1. **`api_bulk_update_items`** (main.py:19828-19844) — Pattern B or migration to Next.js
2. **`api_complete_invoice`** (main.py:19438-19442) — Pattern D (`is_procurement_complete`)

Combined with existing **Group 3 Task 9** (`api/procurement.py:240` kanban aggregate = Pattern B on `invoice_item_prices` → `invoice_items`), Group 3 = 3 refactor sites total.

**Not needed anymore:** per-site refactor of 17814, 20095, 20932, 22240, 25234, 30482, 43312 (all FastHTML HTML-rendering — will silently break on 284 apply, accepted).

## Note: migration 284 regression test policy

`tests/test_migration_284_no_legacy_refs.py` must explicitly **allowlist** the DORMANT FastHTML region (e.g., `main.py:17594-18800`, `main.py:19292-19900` FastHTML subset, `main.py:22131+` customs, `main.py:25209-25320`, `main.py:30475+`, `main.py:43302+`). Otherwise test will fail with 14 "legacy refs" that are intentional DORMANT.

Define allowlist via either:
- Regex exclusion by line range, OR
- Comment marker `# phase-5d: dormant-fasthtml-exempt` above each raw SELECT

Coordinator picks marker approach — more robust to line-number drift.
