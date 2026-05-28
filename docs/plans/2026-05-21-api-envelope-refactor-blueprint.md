# API Error Envelope Refactor — Blueprint

**Date:** 2026-05-21
**Author:** feature-dev:code-architect (dispatched from follow-up #3)
**Status:** Awaiting user review before any implementation

`.kiro/steering/api-first.md` mandates that ALL `/api/*` endpoints return structured error responses:

```json
{ "success": false, "error": { "code": "UPPER_SNAKE_CASE", "message": "..." } }
```

Current state (post-audit, May 2026): 46 non-compliant touch-points across 5 files emit flat `{"error": "string"}`. This document inventories the work, designs the rollout, and flags decisions needed before implementation kicks off.

---

## 1. Backend Touch-Point Inventory

**46 non-compliant touch-points across 5 files.**

Already compliant (correct `{code, message}` shape): `deals.py`, `plan_fact.py`, `logistics.py`, `notes.py`, `workspace.py`, `geo.py`, `admin_users.py`, `auth.py` (middleware), `soft_delete.py`, `composition.py`, `invoices.py`, `procurement.py`, `cost_analysis.py`, `cron.py`. `integrations.py` uses Telegram webhook contract (`{"ok": bool}`) — excluded.

### Group A — `api/quotes.py` (31 touch-points, oldest session-auth era code)

These emit flat `{"error": "string"}` with NO `success` key.

| file:line | http_status | literal string | proposed_code |
|---|---|---|---|
| quotes.py:113 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:117 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:121 | 403 | "No organization" | FORBIDDEN |
| quotes.py:141 | 404 | "Quote not found" | NOT_FOUND |
| quotes.py:153 | 400 | "Cannot calculate - no products in quote" | EMPTY_QUOTE |
| quotes.py:597 | 500 | str(e) | INTERNAL_ERROR |
| quotes.py:650 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:656 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:673 | 400 | "Заполните контрольный список перед передачей в закупки" | CHECKLIST_INCOMPLETE |
| quotes.py:710 | 500 | f"Ошибка сохранения чеклиста: {str(e)}" | INTERNAL_ERROR |
| quotes.py:725 | 400 | f"Ошибка перехода: {result.error_message}" | TRANSITION_FAILED |
| quotes.py:763 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:770 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:772 | 403 | "No organization" | FORBIDDEN |
| quotes.py:777 | 403 | "У вас нет прав для отмены КП" | FORBIDDEN |
| quotes.py:788 | 400 | "Причина отмены обязательна" | VALIDATION_ERROR |
| quotes.py:801 | 404 | "КП не найдено" | NOT_FOUND |
| quotes.py:808 | 422 | "КП уже отменена" | ALREADY_CANCELLED |
| quotes.py:812 | 422 | "Невозможно отменить КП на этапе сделки" | INVALID_STATE |
| quotes.py:890 | 500 | str(e) | INTERNAL_ERROR |
| quotes.py:929 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:936 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:938 | 403 | "No organization" | FORBIDDEN |
| quotes.py:952 | 400 | "to_status or action is required" | VALIDATION_ERROR |
| quotes.py:969 | 400 | "to_status is required" | VALIDATION_ERROR |
| quotes.py:1036 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:1042 | 401 | "Unauthorized" | UNAUTHORIZED |
| quotes.py:1044 | 403 | "No organization" | FORBIDDEN |
| quotes.py:1051 | 404 | str(e) | NOT_FOUND |
| quotes.py:1060 | 500 | "Failed to fetch quote data" | INTERNAL_ERROR |
| quotes.py:1073 | 500 | "Failed to generate validation Excel" | INTERNAL_ERROR |

### Group B — `api/customs.py` lines 213–263 (6 touch-points, early section only)

These emit `{"success": False, "error": "string"}` — `success` key present but `error` is a flat string, not structured. The REQ-5+ section (line 611+) already uses a local `_err()` helper with correct shape.

| file:line | http_status | literal string | proposed_code |
|---|---|---|---|
| customs.py:213 | 401 | "Not authenticated" | UNAUTHORIZED |
| customs.py:219 | 401 | "Not authenticated" | UNAUTHORIZED |
| customs.py:224 | 403 | "Unauthorized" | FORBIDDEN |
| customs.py:231 | 400 | "Invalid JSON" | BAD_REQUEST |
| customs.py:252 | 404 | "Quote not found" | NOT_FOUND |
| customs.py:263 | 400 | "Quote not editable - waiting for procurement" | INVALID_STATE |

### Group C — `api/chat.py` (4 touch-points + 1 data field)

| file:line | http_status | literal string | proposed_code |
|---|---|---|---|
| chat.py:49 | 401 | "Unauthorized" | UNAUTHORIZED |
| chat.py:56 | 401 | "Unauthorized" | UNAUTHORIZED |
| chat.py:64 | 400 | "Invalid JSON" | BAD_REQUEST |
| chat.py:75 | 400 | "quote_id and body are required" | VALIDATION_ERROR |

Note: `chat.py:92` puts `str(e)` in `data.error` as a soft-error field inside a success response — leave untouched (different semantics: success path with partial failure).

### Group D — `api/documents.py` (4 touch-points)

| file:line | http_status | literal string | proposed_code |
|---|---|---|---|
| documents.py:105 | 404 | "Document not found" | NOT_FOUND |
| documents.py:128 | 401 | "Unauthorized" | UNAUTHORIZED |
| documents.py:134 | 403 | "Forbidden" | FORBIDDEN |
| documents.py:141 | 500 | error or "Delete failed" | INTERNAL_ERROR |

### Group E — `api/feedback.py` line 312 (1 touch-point)

| file:line | http_status | literal string | proposed_code |
|---|---|---|---|
| feedback.py:312 | 401 | "Unauthorized" | UNAUTHORIZED |

`feedback.py:107`, `:144`, `:276`, `:380`, `:390`, `:397`, `:405`, `:412` are already compliant.

---

## 2. Frontend Consumer Inventory

**Total `.error` consumers**: ~75 call-sites across ~20 files.

**Already safe** (use `?.error?.message ?? fallback`): the majority — `mutations.ts` (invoice), all `server-actions.ts` files (logistics-segment, logistics-template, entity-note, customs-expense), `plan-fact-api.ts`, admin-users UI, customs-certificates UI, `composition-picker.tsx`, `classify-modal.tsx` (lines 116, 149), `workspace-analytics/api/server-queries.ts`, `specification-step/mutations.ts`, `cost-analysis/page.tsx`, most of `customs-item-dialog.tsx`, `download-validation-excel.ts` (already handles both shapes via explicit type guard).

**Risky — treat `.error` as string directly** (will display `[object Object]` if backend ships structured first without frontend update):

| file:line | pattern | endpoint it calls |
|---|---|---|
| `entities/quote/mutations.ts:40` | `data.error \|\| "Workflow transition failed"` | `PATCH /api/quotes/{id}/workflow` |
| `entities/quote/mutations.ts:1730` | `data.error \|\| "Не удалось отменить КП"` | `POST /api/quotes/{id}/cancel` |
| `entities/quote/mutations.ts:1897-1898` | `data.error` check + throw | `POST /api/quotes/{id}/submit-procurement` |
| `calculation-action-bar.tsx:44` | `data.error \|\| "Calculation failed"` | `POST /api/quotes/{id}/calculate` |
| `procurement-kanban/assign-popover.tsx:90` | `toast.error(result.error ?? ...)` | `POST /api/quotes/.../substatus` |
| `procurement-distribution/quote-brand-card.tsx:93` | `toast.error(result.error ?? ...)` | `POST /api/quotes/.../substatus` |
| `registration/registration-form.tsx:57` | `setError(result.error ?? ...)` | `POST /api/feedback/` (registration) |
| `customs-classify/classify-modal.tsx:264` | renders `result.error` as JSX inline | `GET /api/customs/classify` |

The first four map directly to non-compliant Group A. Lines 90 and 93 call `procurement.py` (already compliant) — `result.error` is already an object, and `toast.error(result.error)` already shows `[object Object]`. This is a pre-existing bug independent of the refactor.

**Most concentrated impact:**
1. `frontend/src/entities/quote/mutations.ts` — 4 string-error sites (all hit `quotes.py`)
2. `frontend/src/features/procurement-kanban/` + `procurement-distribution/` — 2 existing `[object Object]` bugs to fix alongside

---

## 3. Helper Design

**What already exists:** Five files (`logistics.py`, `plan_fact.py`, `workspace.py`, `customs.py` REQ-5+ section, `notes.py`) each define a private `_err(code, message, status)` helper with identical implementations. `cost_analysis.py` and others define `_err` similarly. **No shared module exists.**

**Recommended location:** `api/lib/errors.py` (`api/lib/` does not yet exist — create with `__init__.py`).

```python
from fastapi.responses import JSONResponse

def error_response(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """Canonical structured error envelope per api-first.md."""
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status_code,
    )

def success_response(data=None, meta=None, status_code: int = 200) -> JSONResponse:
    """Canonical structured success envelope."""
    payload: dict = {"success": True}
    if data is not None:
        payload["data"] = data
    if meta is not None:
        payload["meta"] = meta
    return JSONResponse(payload, status_code=status_code)
```

After `api/lib/errors.py` exists, all five local `_err`/`_ok` helpers become dead code and must be deleted (replaced by imports from `api.lib.errors`). One canonical implementation instead of five copies.

---

## 4. Frontend Type Design

**Current shape** (`frontend/src/shared/types/api.ts`):

```typescript
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}
```

**`apiServerClient`** (`api-server.ts`): Returns `ApiResponse<T>`. On JSON parse failure it synthesizes `{success: false, error: {code: "PARSE_ERROR", message: "HTTP {status}"}}` — already the structured shape. Does NOT throw on `!success` — callers check `res.success` themselves.

**`apiClient`** (`api.ts`): Returns `response.json()` typed as `ApiResponse<T>`. No error normalization. Returns whatever the server sends — if the server sends `{"error": "string"}`, the type lies but the runtime value is wrong shape.

**Recommendation:** Keep the `ApiResponse<T>` discriminated union as-is — it already encodes the correct post-refactor shape. Do NOT restructure into `{success: true, data} | {success: false, error}` — the current loose interface (all fields optional) is intentional for incremental migration tolerance.

`apiClient` doesn't normalize errors — that's acceptable during strangler-fig migration. The 8 risky call-sites all read `.error` either directly from `response.json()` (not via `apiClient`/`apiServerClient`) or from `apiServerClient` results. Fix them by replacing string-coercion patterns with `?.error?.message ??` — the type already supports this.

---

## 5. Compatibility / Rollout Strategy

**Recommendation: Frontend-first (Option C)**

Rationale: The 8 risky call-sites are concentrated in `entities/quote/mutations.ts` and two UI components, calling non-compliant Group A (`quotes.py`). Fixing the frontend consumers first to tolerate both `{error: "string"}` and `{error: {code, message}}` is minimal work (8 one-line changes using `extractErrorMessage()` which already handles both shapes). After that, backend can ship at any time without risk of broken toasts.

The `extractErrorMessage()` helper in `frontend/src/shared/lib/errors.ts` already handles both shapes (its docstring covers `error.message`, and a string `.error` would be handled by the duck-typed path). The only remaining risk is the call-sites that do `data.error || fallback` — they bypass `extractErrorMessage`.

### Staged sequence

1. **PR 1 (Frontend safety)** — 8 call-sites: replace `data.error || fallback` with `extractErrorMessage(data) ?? fallback`. Zero backend dependency, no regression risk.
2. **PR 2 (Backend helper + normalize)** — Create `api/lib/errors.py` with `error_response()` + `success_response()`. Delete the 5 local `_err`/`_ok` copies in compliant files. Add `RequestValidationError` exception handler. No external behavior change.
3. **PR 3 (Group A)** — Fix `api/quotes.py` (31 touch-points) using `error_response()`.
4. **PR 4 (Groups B–E)** — Fix `customs.py` (6), `chat.py` (4), `documents.py` (4), `feedback.py` (1).

After PR 1, PRs 2–4 can ship in any order/combination without frontend risk.

---

## 6. Risks & Open Questions

**Q1.** `chat.py:92` — `data.error` as soft-error inside a success envelope (`{"success": True, "data": {"notified_count": 0, "error": str(e)}}`). Partial-success pattern; frontend doesn't consume it. **Recommendation: leave as-is.**

**Q2.** `integrations.py` Telegram webhook — `{"ok": bool, "error": string}` is Telegram protocol, not OneStack API contract. Telegram reads `ok`, never `error`. **Recommendation: exclude from scope.**

**Q3.** `apiServerClient` does not throw on `!success` — callers handle it. Steering says Server Actions should `throw new Error(res.error?.message)` on failure; some do, some don't. **Recommendation: do NOT change the client contract during this refactor — too much blast radius. Track separately.**

**Q4.** FastAPI `HTTPException` — grep found zero `raise HTTPException` in `api/*.py`. FastAPI's default 422 (Pydantic) could surface in future typed endpoints; its shape `{"detail": [...]}` doesn't match the envelope. The codebase avoids Pydantic request models on most endpoints, so this is latent risk. **Recommendation: add an `exception_handler` for `RequestValidationError` to `api_sub_app` in `api/app.py` as part of PR 2 (one-liner).**

**Q5.** `procurement-kanban/assign-popover.tsx:90` and `procurement-distribution/quote-brand-card.tsx:93` display `[object Object]` today (they call already-compliant endpoints with `toast.error(result.error)`). **Pre-existing bug. Include the fix in PR 1.**

---

## Recommended Sequence (exit criteria per PR)

### PR 1 — Frontend safety (prerequisite for everything else)

- **Files:** `entities/quote/mutations.ts`, `calculation-action-bar.tsx`, `procurement-kanban/assign-popover.tsx`, `procurement-distribution/quote-brand-card.tsx`, `registration/registration-form.tsx`, `customs-classify/classify-modal.tsx`
- **Changes:** 8 string-coercion patterns → `extractErrorMessage(data) ?? fallback` or `data?.error?.message ?? fallback`. Fix 2 pre-existing `[object Object]` toasts.
- **Exit criteria:** All 8 risky sites use safe `?.message` access. No toast displays `[object Object]`.

### PR 2 — Shared helper + normalize compliant files

- **Files:** Create `api/lib/__init__.py`, `api/lib/errors.py`. Modify `logistics.py`, `plan_fact.py`, `workspace.py`, `notes.py`, `customs.py` (REQ-5 section), `cost_analysis.py` to import from `api.lib.errors` and delete local `_err`/`_ok` functions. Add `RequestValidationError` handler in `api/app.py`.
- **Exit criteria:** `api/lib/errors.py` exists. Zero local `_err` helpers remain. Existing tests pass.

### PR 3 — Group A: `api/quotes.py`

- **Files:** `api/quotes.py`
- **Changes:** 31 `JSONResponse({"error": ...})` replaced with `error_response(code, message, status)`. Add `success=False` to bare error returns.
- **Exit criteria:** No `{"error": "..."}` flat patterns remain. Integration tests on `/calculate`, `/cancel`, `/submit-procurement`, `/transition`, `/validation-export`.

### PR 4 — Groups B–E: `customs.py`, `chat.py`, `documents.py`, `feedback.py`

- **Files:** `api/customs.py` (lines 213–263), `api/chat.py`, `api/documents.py`, `api/feedback.py:312`
- **Changes:** 15 remaining flat-error patterns → `error_response()`.
- **Exit criteria:** Zero `{"error": "string"}` patterns remain across all `api/*.py` files. `grep -r '"error"' api/*.py` returns only compliant `{code, message}` shapes and logging calls.

---

**Headline counts:** 46 backend non-compliant touch-points across 5 files (31 in `quotes.py`); 8 frontend risky consumers across 6 files; 5 duplicate `_err` helpers to consolidate.

**Top 3 open questions for user decision before dispatch:**

1. Does the inner `data.error` soft-fail field in `chat.py:92` need migration? (Recommendation: **no** — not consumed by frontend.)
2. Should `apiServerClient` be hardened to auto-throw on `!success` as part of this work, or tracked separately? (Recommendation: **separate ticket** — too much blast radius here.)
3. The `RequestValidationError` / FastAPI 422 normalization in `api/app.py` — in scope for PR 2, or a separate concern? (Recommendation: **include in PR 2** — one-liner exception handler.)
