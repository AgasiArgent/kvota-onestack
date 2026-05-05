# Implementation Plan — customs-shared-certificates (Phase B)

> **For agentic workers:** Execute tasks per dependency graph. Each task is independently committable. Each commit touches ONLY the files its task explicitly changes — use `git add <explicit-paths>`, never `git add .` or `-A`. All commits include `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` footer.

**Spec references:**
- Requirements: `.kiro/specs/customs-shared-certificates/requirements.md` (419 lines, 11 REQ, 16 LD, 17 acceptance gates)
- Design: `.kiro/specs/customs-shared-certificates/design.md` (1389 lines, 12 subsections, 5 data flows, 10 risks)
- Gap analysis: `.kiro/specs/customs-shared-certificates/gap-analysis.md`
- Code validation: `.kiro/specs/customs-shared-certificates/code-validation.md`
- UI mockup: `docs/mockups/customs-after-phases.html` (v3, утверждён 2026-05-03; Phase B секции 111, 881-1000)

---

## Overview

- **Total tasks:** 14 (Wave 5 — 1 verification task; Task 14 explicitly out-of-scope tracker)
- **Waves:** 5
- **Estimated parallel agents:** 3 in Wave 1, 2 in Wave 2, 6 in Wave 3, 3 in Wave 4
- **Total estimated effort:** ~22-27 working hours (≈3-4 working days for solo + parallel execution)
- **Phase A locked files (NEVER modify):** `services/calculation_engine.py`, `services/calculation_models.py`, `services/calculation_mapper.py`
- **Phase A regression baseline:** 241 backend tests + 677 frontend tests must stay green после каждой Wave (design.md §7.4)
- **Parallel marker `(P)`:** task safe to run concurrently with other `(P)`-marked tasks in the same wave (no shared files)
- **Worktree:** `/Users/andreynovikov/workspace/tech/projects/kvota/onestack-customs-phase1` — branch per `/lean-tdd skip-to-impl`

---

## Wave 1 — Foundation (3 parallel tasks)

### Task 1: Migration 306 — `quote_certificates` + `quote_certificate_items` + atomic backfill (P)

**REQ coverage:** REQ-1 (AC#1..#11)
**Dependencies:** none
**Files (only):**
- Create: `migrations/306_quote_certificates.sql`
- Create: `tests/migrations/test_306_backfill.py`
- Modified after apply: `frontend/src/database.types.ts` (regenerated, committed as part of this task)

**Description:**
Атомарная миграция за SQL-контрактом из design.md §4.1 — создать `kvota.quote_certificates` (14 колонок включая `display_name`, `is_custom_expense`, `cost_rub` NUMERIC(14,2)) и `kvota.quote_certificate_items` (M2M с UNIQUE `(certificate_id, item_id)`), 3 индекса, CHECK constraint `cost_rub >= 0`, RLS-политики 293-паттерна (multi-table JOIN organization_members + user_roles + roles, `r.slug` IN write/read role lists per LD-14). В заголовке SQL — обязательный комментарий объясняющий выбор 293 vs 304 паттерна (REQ-1 AC#6, R3 mitigation).

Atomic backfill в той же транзакции: `customs_quote_expenses` → 1 cert + N attachments per quote_item; `customs_item_expenses` → multi-attach grouping `GROUP BY (quote_id, label)` с AVG(amount_rub) safety (см. design.md §4.1 raw SQL). Старые таблицы НЕ дропаются (REQ-1 AC#8 — drop deferred).

**Tests (`tests/migrations/test_306_backfill.py`):**
- 3 fixture сценария: empty source tables (no-op backfill), one-cert-one-item from `customs_quote_expenses`, multi-attach grouping from `customs_item_expenses`.
- Assert: row counts соответствуют formula (cqe count → certs + attachments на каждое quote_item; cie count → cert per (quote_id, label) tuple + N attachments).
- Assert: `cost_rub` сумма не расходится с источником > 1 копейки на квоту (R2 mitigation).
- Idempotency: применить миграцию дважды локально — без ошибок и дубликатов (CREATE IF NOT EXISTS + WHERE NOT EXISTS guard).

**Pre-steps:**
- Verify migration number 306 free: `ls migrations/30[0-9]*.sql` (highest = 305 per gap-analysis).

**Apply:**
```bash
scripts/apply-migrations.sh 306
ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c '\\d kvota.quote_certificates'"
```

**Post-step (REQ-1 AC#11):**
```bash
cd frontend && npm run db:types
cd frontend && npx tsc --noEmit       # must remain green
```

**Estimate:** 75-90 min

---

### Task 2: `services/cost_split.py` — pure proportional split + Decimal precision (P)

**REQ coverage:** REQ-3 (Python side: AC#1, #2, #5, #6, #7, #8, #10)
**Dependencies:** none (Python-only, файл greenfield)
**Files (only):**
- Create: `services/cost_split.py`
- Create: `tests/services/test_cost_split.py`
- Create: `tests/fixtures/cost_split_fixtures.json`

**Description:**
Чистая функция распределения per design.md §4.2 + §4.4. Public API:
- `split_cost(item_value, total_items_value, cert_cost) -> Decimal` — single-share формула с `Decimal.quantize('0.01', ROUND_HALF_UP)`.
- `split_cost_batch(item_values, cert_cost) -> list[Decimal]` — batch с правилом «последняя позиция поглощает residual» (REQ-3 AC#7).
- Re-export `customs_value_rub_for_item` из `services/calculation_helpers.py:_customs_value_in_rub` (LD-15) — НЕ модифицировать `calculation_helpers.py`, только импортировать.

Edge cases (REQ-3 AC#5, AC#6): `total_items_value == 0` → equal-split `cert_cost / N`; `len(items) == 1` → `[cert_cost]`; `len(items) == 0` → `ValueError`.

**Tests (`tests/services/test_cost_split.py`):**
6 сценариев из REQ-3 AC#10, загружающих `tests/fixtures/cost_split_fixtures.json`:
- (a) single item → 100%
- (b) two equal items → 50/50
- (c) three items 150k/350k/90k of 590k, cert 12500 → точные доли
- (d) all-zero items → equal-split fallback
- (e) cert 10₽, 3 равных items → residual absorbed by last (3.33/3.33/3.34)
- (f) large numbers cert=999999.99 → no drift

Plus parity hook: тест парсит JSON, считает `purchase_price_original × quantity × currency_rate_to_rub`, передаёт в `split_cost_batch`, сравнивает с `expected_shares` копейка-в-копейку.

**Estimate:** 45-60 min

---

### Task 3: `frontend/src/shared/lib/cost-split.ts` — TS port + parity tests (P)

**REQ coverage:** REQ-3 (TS side: AC#3, #4, #11, #12)
**Dependencies:** none (TS-only, файл greenfield; fixture JSON совместно с Task 2 — порядок коммитов любой)
**Files (only):**
- Create: `frontend/src/shared/lib/cost-split.ts`
- Create: `frontend/src/shared/lib/__tests__/cost-split.test.ts`

**Description:**
TS-зеркало `services/cost_split.py` per design.md §4.3. Public API:
- `roundHalfUp2(value: number): number` — explicit `Math.floor(value * 100 + 0.5) / 100` shim (НЕ `Math.round` — banker's rounding несовместимо с Python ROUND_HALF_UP, LD-6).
- `splitCost(itemValue, totalItemsValue, certCost): number`
- `splitCostBatch(itemValues, certCost): number[]` — с тем же residual-rule (последний элемент = `certCost - sum(others)`).

Edge cases identical к Python (single, equal-split fallback, throw on empty array).

**Tests (`frontend/src/shared/lib/__tests__/cost-split.test.ts`):**
Те же 6 сценариев из `tests/fixtures/cost_split_fixtures.json` (vitest resolver: `await import('../../../../../tests/fixtures/cost_split_fixtures.json')`). Любое расхождение копейка-в-копейку с Python = CI fail.

**Post-step:**
```bash
cd frontend && npx vitest run src/shared/lib/__tests__/cost-split.test.ts
cd frontend && npx tsc --noEmit
```

**Estimate:** 30-45 min

---

## Wave 2 — Backend services + API (sequential after Wave 1)

### Task 4: `services/quote_certificates_history.py` — loose 2-of-3 history match

**REQ coverage:** REQ-5 (AC#1, #2, #3 — backend SQL contract)
**Dependencies:** Task 1 (DB tables exist)
**Files (only):**
- Create: `services/quote_certificates_history.py`
- Create: `tests/services/test_quote_certificates_history.py`

**Description:**
Mirror `services/customs_user_choices.py` (Phase A blueprint, 351 строк). Public API per design.md §4.5:
- `@dataclass(frozen=True) HistoryCertMatch` — все поля cert + `is_actual: bool` + `source_quote_id` + `source_item_id`.
- `find_match(*, organization_id, current_quote_id, hs_code, brand, supplier_id) -> HistoryCertMatch | None` — выполняет SQL из design.md §4.5 (12-month window, org isolation, `is_custom_expense=FALSE` filter, 2-of-3 CASE WHEN счётчик ≥ 2, `ORDER BY created_at DESC LIMIT 1`).
- Error handling: `try/except` с `logger.warning` + `return None` (history лучше чем 500).

**Tests (`tests/services/test_quote_certificates_history.py`):**
- `test_find_match_2_of_3_loose` — match по hs_code+brand (supplier mismatch) → возвращается
- `test_find_match_1_of_3_no_match` — only hs_code совпадает → None
- `test_find_match_12_month_cutoff` — старше 12 месяцев → None
- `test_find_match_org_isolation` — другая организация → None
- `test_find_match_excludes_current_quote` — тот же quote_id → None
- `test_find_match_excludes_custom_expense` — `is_custom_expense=TRUE` → не попадает в результат
- `test_is_actual_computed_in_sql` — `valid_until > today` → `is_actual=True`; expired → `False`; NULL → `True`
- `test_find_match_returns_latest_desc` — два match-а, возвращается с большим `created_at`
- `test_swallow_db_error` — exception → logger.warning + None

**Estimate:** 60-75 min

---

### Task 5: `api/customs.py` certificates handlers + `api/routers/customs.py` registration

**REQ coverage:** REQ-2 (AC#1..#15 — все 7 endpoints), REQ-5 (AC#1, #4 — history endpoint)
**Dependencies:** Task 1 (tables), Task 2 (cost_split), Task 4 (history service)
**Files (only):**
- Modify: `api/customs.py` (extend — добавить 6 handlers + new role-list constant `_CERT_READ_ROLES`)
- Modify: `api/routers/customs.py` (register 6 routes)
- Create: `tests/api/test_customs_certificates.py`
- Create: `tests/api/test_customs_certificates_history.py`
- Create: `tests/api/test_rls_quote_certificates.py`

**Description:**
6 новых endpoints per design.md §4.6 + §4.7 (полные signatures + handler contracts):
1. `POST /api/customs/certificates` — create cert + N attachments в одной транзакции (Supabase RPC `kvota.create_certificate_with_items` если нужен явный TX — R6 mitigation; иначе REST chain с manual rollback)
2. `GET /api/customs/certificates?quote_id={uuid}` — список с pre-computed `attached_items[].share_rub`/`share_percent`
3. `POST /api/customs/certificates/{cert_id}/items` — attach + recompute shares
4. `DELETE /api/customs/certificates/{cert_id}/items/{item_id}` — detach + recompute
5. `DELETE /api/customs/certificates/{cert_id}` — каскад через FK
6. `GET /api/customs/certificates/history?hs_code&brand&supplier_id&current_quote_id` — wrapper над Task 4

Auth: `_resolve_dual_auth(request)` (`api/customs.py:86`-pattern). Role gate: `_CUSTOMS_ROLES` для writes, новая константа `_CERT_READ_ROLES` (frozenset из 8 ролей per REQ-1 AC#6) для reads. Error envelope: `_err()` (`api/customs.py:806`-pattern). Cross-quote validation 422 NOT_IN_QUOTE.

**Cost-split integration (REQ-2 AC#2/AC#4):** для каждого `attached_items[]` элемента — resolve invoice_items payload по `item_id`, вычислить RUB basis через `customs_value_rub_for_item(...)` (импорт из `services/cost_split.py` re-export), передать список в `split_cost_batch`.

**Removal in same PR (REQ-2 AC#16):** удалить старые expense handlers `POST/PATCH/DELETE /api/customs/expenses/*` (`api/customs.py:605-797` per gap-analysis). NO commenting out — full delete per code-quality «no dead code».

**Tests:**
- `tests/api/test_customs_certificates.py` — happy path POST/GET/POST items/DELETE items/DELETE; 401, 403 (role gate), 404, 422 NOT_IN_QUOTE, 409 (UNIQUE), 400 VALIDATION_ERROR; transaction rollback on cross-quote item.
- `tests/api/test_customs_certificates_history.py` — auth + envelope + match shape + null-match path + is_actual variants.
- `tests/api/test_rls_quote_certificates.py` — RLS enforcement: customs role can write, sales role can read (200), sales role cannot write (403/empty), other-org user gets empty SELECT.

**Post-step:** `python3 -m pytest tests/services tests/api -q` — 241 baseline + new tests pass; no regressions.

**Estimate:** 120-150 min (largest task; 6 handlers + 3 test files + Phase A endpoint deletion)

---

## Wave 3 — Frontend FSD feature (parallel sub-tasks after Wave 2)

> Wave 3 tasks share folder `frontend/src/features/customs-certificates/` but operate on **disjoint files** within it. Тaskы 7-8e safe для parallel execution.

### Task 6: FSD scaffold — api/ + model/ + lib/ + index.ts (P)

**REQ coverage:** REQ-2 (TS API consumer), REQ-3 (re-export shared/lib/cost-split), REQ-5 (history API wrapper), REQ-6/7/8/9/10 (types contract)
**Dependencies:** Task 3 (shared/lib/cost-split.ts), Task 5 (API contracts locked)
**Files (only):**
- Create: `frontend/src/features/customs-certificates/api/certificates.ts`
- Create: `frontend/src/features/customs-certificates/api/history.ts`
- Create: `frontend/src/features/customs-certificates/model/types.ts`
- Create: `frontend/src/features/customs-certificates/lib/derive-rub-basis.ts`
- Create: `frontend/src/features/customs-certificates/lib/format-rub.ts`
- Create: `frontend/src/features/customs-certificates/lib/cost-split.ts`
- Create: `frontend/src/features/customs-certificates/index.ts`
- Create: `frontend/src/features/customs-certificates/__tests__/derive-rub-basis.test.ts`
- Create: `frontend/src/features/customs-certificates/__tests__/format-rub.test.ts`

**Description:**
Mirror folder layout `frontend/src/features/customs-history/` per design.md §4.8. Public API surface (LD-13 / Compliance Contract):
- `api/certificates.ts` — typed `apiClient<T>` wrappers per design.md §4.8.2 (5 functions returning `Promise<ApiResponse<T>>`).
- `api/history.ts` — `fetchCertificateHistory({hs_code?, brand?, supplier_id?, current_quote_id})`.
- `model/types.ts` — TS-зеркало Python dataclasses per design.md §4.8.1: `Certificate`, `AttachedItem`, `HistoryCertMatch`, `QuoteItemForSelect`.
- `lib/derive-rub-basis.ts` — pure helper `deriveRubBasis(item)` = `purchase_price_original × quantity × currency_rate_to_rub` (REQ-3 AC#4, LD-15).
- `lib/format-rub.ts` — `formatRub(value)` через `Intl.NumberFormat('ru-RU')` («12 500 ₽», «999 999,99 ₽»).
- `lib/cost-split.ts` — `export * from '@/shared/lib/cost-split'` (single namespace).
- `index.ts` — re-export public API per design.md §4.8.5 (UI components добавятся в следующих задачах).

**Tests:** 2 unit-теста на pure helpers (rub-basis edge cases — zero quantity, zero rate; format-rub digit grouping + 2-decimal). UI-тесты будут в задачах 7a-7f.

**Post-step:** `cd frontend && npx vitest run src/features/customs-certificates/__tests__ && npx tsc --noEmit`

**Estimate:** 45-60 min

---

### Task 7a: `CertificateCard` + `CustomExpenseCard` (P)

**REQ coverage:** REQ-6 (AC#4, #5), REQ-4 (AC#3 — красная рамка expired)
**Dependencies:** Task 6 (types + lib)
**Files (only):**
- Create: `frontend/src/features/customs-certificates/ui/CertificateCard.tsx`
- Create: `frontend/src/features/customs-certificates/ui/CustomExpenseCard.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/certificate-card.test.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/custom-expense-card.test.tsx`

**Description:**
Per design.md §4.8.4:
- `CertificateCard` — emerald-bordered tile с type badge, `№{number}`, `cost_rub` (через `formatRub`), counter «N из M», `valid_until` через `formatDateRussian`. Красная рамка если `isExpired=true` (через design-system token, NO hex).
- `CustomExpenseCard` — gray-bordered tile с «Расход» badge (neutral token), `display_name`, `cost_rub`, counter. Без `valid_until`/`type`/`legal_doc`.

Compliance (LD-13): shadcn `<Button>`, Inter font, design tokens, NO inline `style=`, NO `transition: all`, NO `transform: translateY()`.

**Tests:** rendering + props variants (expired красная рамка, click handler, counter math).

**Estimate:** 45 min

---

### Task 7b: `PositionsMultiSelect` + `LivePreviewPanel` shared sub-components (P)

**REQ coverage:** REQ-7 (AC#4, AC#5), REQ-10 (AC#2 — переиспользуется в ExpenseModal)
**Dependencies:** Task 6
**Files (only):**
- Create: `frontend/src/features/customs-certificates/ui/PositionsMultiSelect.tsx`
- Create: `frontend/src/features/customs-certificates/ui/LivePreviewPanel.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/positions-multi-select.test.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/live-preview-panel.test.tsx`

**Description:**
Per design.md §4.8.4:
- `PositionsMultiSelect` — checkbox list per `quote_items`, search input case-insensitive, «Выбрать все» / «Снять все» toggle. Per row: `№{position} {item.name}` + derived RUB-basis (через `deriveRubBasis`). Composition pattern из `country-combobox.tsx` (LD-5).
- `LivePreviewPanel` — правая колонка с распределением: для каждого `selectedItems` строка `№{position} → {share_rub} ₽ ({share_percent}%)` + итог «Всего: {sum} ₽». Empty state «Выберите позиции для распределения». Пересчёт через `splitCostBatch` (debounce 0мс — расчёт дешёвый).

**Tests:** select-all toggle, search filter, RUB-basis rendering, live preview math correctness, empty state.

**Estimate:** 60-75 min

---

### Task 7c: `CertificateModal` + `ExpenseModal` (P)

**REQ coverage:** REQ-7 (AC#1..#11 — full modal), REQ-10 (AC#1..#8 — simplified expense modal)
**Dependencies:** Task 6, Task 7b (PositionsMultiSelect + LivePreviewPanel sub-components)
**Files (only):**
- Create: `frontend/src/features/customs-certificates/ui/CertificateModal.tsx`
- Create: `frontend/src/features/customs-certificates/ui/ExpenseModal.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/certificate-modal.test.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/expense-modal.test.tsx`

**Description:**
Per design.md §4.8.4:
- `CertificateModal` — two-column layout, full form (8 fields per REQ-7 AC#3: type/number/issuer/legal_doc/issued_at/valid_until/cost_rub/notes) + multi-select + live-preview. Searchable `type` Combobox с seeded constants `["ДС ТР ТС", "СС", "СГР", "ОТТС", "EUR.1", "Form A", "CT-1", "CT-2", "CT-3", "A.TR"]` + creatable. Modes: `'create'` / `'edit'` с `initial?: Partial<Certificate>` для pre-fill из history.
- `ExpenseModal` — упрощённая (REQ-10 AC#2): только `display_name` + `notes` + `cost_rub` + multi-select + live-preview. Submit с `is_custom_expense=true` + `type='custom_expense'`.

Submit вызывает `createCertificate(input)` из Task 6. Error handling: остаётся открытой + toast + красная рамка на `error.field` (REQ-7 AC#8).

**Compliance (LD-5, LD-13):** все dropdowns — searchable Combobox; shadcn `<Button variant="default|secondary|ghost">`; design tokens; tab-order: form → multi-select → buttons.

**Tests:** mode='create' vs 'edit' rendering, submit flow (mock API), validation errors, searchable type Combobox, ALL-dropdowns-are-searchable audit.

**Estimate:** 90-120 min (largest UI task)

---

### Task 7d: `CertificateBindPopover` (P)

**REQ coverage:** REQ-8 (AC#1..#11)
**Dependencies:** Task 6, Task 7b (live-preview sub-component re-used for after-attach preview)
**Files (only):**
- Create: `frontend/src/features/customs-certificates/ui/CertificateBindPopover.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/certificate-bind-popover.test.tsx`

**Description:**
Per design.md §4.8.4 + §5.2:
- shadcn Popover (~360px width) anchored на кнопке.
- Header: «Привязать позицию №{N} «{item.name}» к сертификату» (точная копия мокапа).
- Search input (searchable pattern, LD-5).
- Radio-list candidates (only-same-quote, otherwise empty state с link на CertificateModal). Per row: type+number / mono full number / cost_rub + «уже на N позициях». Expired certs disabled с tooltip «Сертификат истёк {DD.MM.YYYY}» (REQ-4 AC#3).
- After-attach preview: info-blue card. Per item line `№{position} ({item_rub_basis} ₽ / {total_rub_basis} ₽) → {new_share} ₽`. Текущая item — amber highlight. Frontend pure compute через `splitCostBatch`.
- Footer: «Отмена» + «Привязать». Optimistic UI + POST `/items` + rollback on error.

**Tests:** open/close, search filter, expired-disabled, after-attach preview math, optimistic update + rollback, empty-quote state.

**Estimate:** 75 min

---

### Task 7e: `CertificateCoverageList` + `CertificateDetailsModal` (P)

**REQ coverage:** REQ-9 (AC#1..#9)
**Dependencies:** Task 6, Task 7a (cards reused or specialized)
**Files (only):**
- Create: `frontend/src/features/customs-certificates/ui/CertificateCoverageList.tsx`
- Create: `frontend/src/features/customs-certificates/ui/CertificateDetailsModal.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/certificate-coverage-list.test.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/certificate-details-modal.test.tsx`

**Description:**
Per design.md §4.8.4:
- `CertificateCoverageList` — list emerald-bordered (cert) / gray-bordered (expense) cards. Per card sub row: `№{number} · доля {share_rub} ₽ ({share_percent}% пропорционально стоимости {item_rub_basis} / {total_rub_basis})`. Footer buttons: «Открыть сертификат» / «Подробнее» + «Отвязать» (visible **только** для `customs/admin/head_of_customs` per REQ-9 AC#6). Sorted `ORDER BY cert.created_at DESC`. Expired cert красная рамка > emerald (priority).
- `CertificateDetailsModal` — read-only: все cert fields + таблица «Прикреплено к {N} позициям» (`№{position} {name} → {share_rub} ₽ ({share_percent}%)`) + footer «Закрыть». NO edit form (REQ-9 AC#7).

Detach: optimistic + DELETE + rollback on error.

**Tests:** role-gated «Отвязать» visibility, expired красная рамка priority, custom-expense gray variant, optimistic detach + rollback, details modal read-only assertions.

**Estimate:** 60-75 min

---

### Task 7f: `HistoryBanner` + `CertificatesSection` wrapper (P)

**REQ coverage:** REQ-5 (AC#6, #7, #9, #10), REQ-6 (AC#1, #2, #3, #7 — section + empty state)
**Dependencies:** Task 6, Task 7a, Task 7c (modals opened from section + banner)
**Files (only):**
- Create: `frontend/src/features/customs-certificates/ui/HistoryBanner.tsx`
- Create: `frontend/src/features/customs-certificates/ui/CertificatesSection.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/history-banner.test.tsx`
- Create: `frontend/src/features/customs-certificates/__tests__/certificates-section.test.tsx`

**Description:**
Per design.md §4.8.4 + §5.3:
- `HistoryBanner` — variants:
  - `'apply'` (info-blue): «Возможно подойдёт сертификат {type} №{number} от {DD.MM.YYYY}, ~{cost_rub}₽» + «Применить» + «×»
  - `'create-new'` (amber/warning): «Прежний сертификат истёк {DD.MM.YYYY}, нужен новый ~{cost_rub}₽» + «Создать новый» + «×»
  - Variant derived from `match.is_actual` (REQ-4 AC#5/AC#6).
  - Использует `formatDateRussian` (LD-11) + `formatRub` (Task 6).
- `CertificatesSection` — header «Расходы по таможне» + 2 кнопки («+ Добавить сертификат» variant=default, «+ Добавить расход» variant=secondary). Body: vertical stack `<CertificateCard>` / `<CustomExpenseCard>` sorted DESC. Empty state: «Расходов нет» + «Нажмите ➕ чтобы добавить сертификат или расход» + центрированные duplicate buttons (REQ-6 AC#7). Click on card → role-based: edit modal (customs/admin) или details modal (read roles, REQ-6 AC#6).

**Index.ts update:** добавить exports `CertificatesSection`, `HistoryBanner`, `CertificateModal`, `ExpenseModal`, `CertificateBindPopover`, `CertificateCoverageList`, `CertificateDetailsModal` (per design.md §4.8.5 — internal cards/sub-components NOT re-exported).

**Tests:** banner variant switching by `is_actual`, дата + cost формат, dismiss callback, section empty state, role-based click handler, two-button header rendering.

**Estimate:** 60-75 min

---

## Wave 4 — Wiring (sequential — same-file conflicts in customs-step.tsx + customs-item-dialog.tsx)

### Task 8: `customs-views.ts` + TableViewsDropdown grouping update

**REQ coverage:** REQ-11 (AC#1..#12)
**Dependencies:** none на frontend/back (pure TS constants); может идти параллельно с Wave 3 если требуется speedup, но безопаснее в Wave 4 чтобы не блокировать spam-merge
**Files (only):**
- Create: `frontend/src/features/quotes/ui/customs-step/customs-views.ts`
- Create: `frontend/src/features/quotes/ui/customs-step/__tests__/customs-views.test.ts`
- Modify: `frontend/src/features/table-views/ui/table-views-dropdown.tsx` (lines 124-167 — добавить группу «Системные» детектируемую по `view.is_system === true`)
- Create: `frontend/src/features/quotes/ui/customs-step/hint-banner.tsx`
- Create: `frontend/src/features/quotes/ui/customs-step/__tests__/hint-banner.test.tsx`

**Description:**
Per design.md §4.11 + §4.12:
- `customs-views.ts` — `CUSTOMS_SYSTEM_VIEWS` constant (4 виртуальных views с синтетическими ID `system:all|tariffs-nds|documents|identification`). Column ids verified против `customs-columns.ts` (24 entries). Plus helpers: `findSystemView(id)`, `isSystemViewId(id)` (type guard через template literal), `defaultSystemViewId(): 'system:all'`.
- `table-views-dropdown.tsx` — добавить третью группу «Системные» (выше «Личные» / «Общие»). Group detection: `views.filter(v => v.is_system === true)`. Pure additive, без новых props.
- `hint-banner.tsx` — local component для customs-step (НЕ feature-level — скопирование специфично для одного места). Tailwind `bg-info-bg text-info border-info`. Иконка 💡 inline-emoji. Props: `viewLabel`, `hiddenLabels[]`, `ctaDisabled`, `ctaTooltip`. Disabled link «Создать свой вид: Колонки → Сохранить как...» с tooltip «Доступно в следующей фазе» (REQ-11 AC#10).

**Tests (`__tests__/customs-views.test.ts`):**
- `findSystemView('system:all')` → row
- `findSystemView('uuid-or-other')` → null
- `isSystemViewId('system:tariffs-nds')` → true
- `isSystemViewId('uuid')` → false
- `defaultSystemViewId()` → 'system:all'
- All 4 view defs reference column ids that exist в `CUSTOMS_AVAILABLE_COLUMNS` (verify against constant import)

**Tests (`hint-banner.test.tsx`):** rendering with hidden labels, disabled CTA tooltip, conditional show (active view !== 'system:all').

**Tests update on `table-views-dropdown`:** добавить assertion что system group renders above личные/общие when `is_system=true` rows present.

**Estimate:** 60-75 min

---

### Task 9: Wire `<CertificatesSection />` into `customs-step.tsx`

**REQ coverage:** REQ-6 (AC#9 — replace existing sections), REQ-11 (AC#3 — system views injected via prop)
**Dependencies:** Task 7f (`CertificatesSection` ready), Task 8 (`customs-views.ts` ready)
**Files (only):**
- Modify: `frontend/src/features/quotes/ui/customs-step/customs-step.tsx`

**Description:**
Per design.md §4.9 (line-range table):
- DELETE imports `QuoteCustomsExpenses`, `ItemCustomsExpenses` (lines 31, 32 — current).
- DELETE renders `<ItemCustomsExpenses />` (line 411-417), `<QuoteCustomsExpenses />` (line 419) — full deletion, no commenting (REQ-6 AC#9, code-quality «no dead code»).
- KEEP `<CustomsExpenses />` (line 421) unchanged — это calc-engine variables form, отдельная концепция (REQ-6 AC#1 explicit).
- INSERT `<CertificatesSection quoteId={quoteId} items={...} certificates={...} canEdit={canEditCustoms} onRefresh={refetchCertificates} />` между линиями 419 (now removed) и 421.
- Add new import: `import { CertificatesSection } from '@/features/customs-certificates';`
- Add new state hook (`useCertificates(quoteId)`) или RSC server fetch через `listCertificates(quoteId)`.
- Inject `CUSTOMS_SYSTEM_VIEWS` в `views` prop `<TableViewsDropdown />` (concat with userViews from `fetchAllAvailable`).

**No changes** to: toolbar block (lines 383-397), URL parsing block (lines 170-194 — синтетика `system:*` уже работает as-is).

**Tests:**
- Update existing customs-step tests если `<QuoteCustomsExpenses>` / `<ItemCustomsExpenses>` появляются в snapshots.
- Add test: `<CertificatesSection>` renders в правильной позиции; system views группа в dropdown содержит 4 строки.

**Post-step:**
```bash
cd frontend && npx vitest run src/features/quotes/ui/customs-step
cd frontend && npx tsc --noEmit
```

**Estimate:** 45-60 min

---

### Task 10: «Сертификация» секция в `customs-item-dialog.tsx`

**REQ coverage:** REQ-5 (AC#5, #6, #7, #8, #11 — banner + autofill), REQ-8 (AC#1, #2, #3 — empty + popover + create-new), REQ-9 (AC#1..#9 — coverage list + details modal mount)
**Dependencies:** Task 7d (`CertificateBindPopover`), Task 7e (`CertificateCoverageList` + `CertificateDetailsModal`), Task 7f (`HistoryBanner`), Task 7c (`CertificateModal` mode='create' с pre-selected current item)
**Files (only):**
- Modify: `frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx`

**Description:**
Per design.md §4.10:
- Add imports: `CertificateCoverageList`, `CertificateBindPopover`, `CertificateModal`, `HistoryBanner` from `@/features/customs-certificates`.
- Add state: `attachedCertificates: Certificate[]`, `bindOpen: boolean`, `historyMatch: HistoryCertMatch | null`, `historyApplied: boolean`.
- Add useEffect: на `item.hs_code/brand/supplier_id` change (debounce 300ms) — `fetchCertificateHistory({hs_code, brand, supplier_id, current_quote_id})` (REQ-5 AC#5/AC#11).
- Render `<HistoryBanner>` ABOVE «Сертификация» section (when `historyMatch && !historyApplied`).
- ADD new section «Сертификация» (UPPERCASE label через `.text-xs uppercase` design-system class) после Phase A тарифных секций, ДО Phase C «Нетарифные требования» placeholder (мокап lines 884-910).
- Section visibility: `{form?.hs_code ? <Section /> : null}` (REQ-8 AC#2).
- Body: `{attachedCertificates.length === 0 ? <EmptyAmberCard /> : <CertificateCoverageList ... />}`.
- EmptyAmberCard: amber-bordered с копией «Сертификат соответствия не оформлен» (точная мокап копия) + 2 кнопки: «Привязать к существующему» (открывает `<CertificateBindPopover>`) + «Создать новый» (`variant=default`, открывает `<CertificateModal mode="create">` с pre-selected current item).
- `<CertificateBindPopover />` mounted рядом с кнопкой через `useRef` anchorRef.

**Tests update:**
- existing customs-item-dialog tests should remain green (Phase A regression).
- New tests: section visibility (hs_code-gated), banner appears on history match, empty-amber → popover open → bind flow, coverage list rendering.

**Post-step:** `cd frontend && npx vitest run customs-item-dialog && npx tsc --noEmit`

**Estimate:** 75-90 min

---

### Task 11: `customs-handsontable.tsx` synthetic-ID resolver + hint banner

**REQ coverage:** REQ-11 (AC#5, #7, #8, #9)
**Dependencies:** Task 8 (`customs-views.ts` + `hint-banner.tsx` exist)
**Files (only):**
- Modify: `frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx`

**Description:**
Per design.md §4.12:
- Add imports: `isSystemViewId`, `findSystemView`, `CUSTOMS_SYSTEM_VIEWS` from `./customs-views`; `HintBanner` from `./hint-banner`.
- Resolver logic: `activeView = isSystemViewId(activeViewId) ? findSystemView(activeViewId) : userViews.find(...)`.
- `visibleColumnIds = activeView?.visibleColumnIds ?? CUSTOMS_SYSTEM_VIEWS[0].visibleColumnIds` (default `system:all`).
- Existing `filterColumns(...)` (line ~725) consumes — no change.
- NEW: render `<HintBanner>` ABOVE `<HotTable />` when `activeView?.is_system === true && activeView.id !== 'system:all'` (REQ-11 AC#9).
- Compute `hiddenLabels = computeHiddenLabels(visibleColumnIds, CUSTOMS_AVAILABLE_COLUMNS)` (helper inline или вынести в `lib/`).

**Tests update:**
- existing customs-handsontable tests remain green.
- New tests: synthetic ID `system:tariffs-nds` resolves correctly; banner shows on non-default system view; banner hidden on `system:all`; banner hidden when no active view (default fallback).

**Post-step:** `cd frontend && npx vitest run customs-handsontable && npx tsc --noEmit`

**Estimate:** 45-60 min

---

## Wave 5 — Verification (1 task)

### Task 12: Browser test on localhost:3000 + prod Supabase

**REQ coverage:** Acceptance Gates (browser-test gate); cross-cuts REQ-4..REQ-11
**Dependencies:** all Wave 1-4 deployed + green tests
**Files (only):** verification only — no source files

**Description:**
Per design.md §7.3 + memory `reference_localhost_browser_test.md`. Localhost Next.js (3000) + prod Supabase via `frontend/.env.local`. Browser test через Playwright MCP (Mode A, `mcp__plugin_playwright_playwright__*`). Light verification — Alta degraded per gap-analysis, Phase B не зависит от Alta-калькулятора напрямую.

**Pre-steps:**
- Backend tests: `python3 -m pytest tests/services tests/api -q` — 241 baseline + Phase B new tests pass
- Frontend tests: `cd frontend && npx vitest run` — 677 baseline + Phase B new tests pass
- Type-check: `cd frontend && npx tsc --noEmit` — clean
- Push to main → wait CI green → wait Deploy success → verify on `app.kvotaflow.ru`

**Browser scenarios (per design.md §7.3):**
1. **REQ-7 modal flow**: open existing quote → click «+ Добавить сертификат» → fill form → multi-select 3 позиций → live-preview обновляется → save → card появляется.
2. **REQ-8 popover flow**: open per-item dialog → empty-amber → click «Привязать к существующему» → popover opens → radio-list (only-same-quote) → after-attach preview math correct → click «Привязать» → coverage list updates.
3. **REQ-9 detach flow**: «Отвязать» в coverage list → optimistic UI → API call → list update.
4. **REQ-5 history banner**: open dialog для new item с тем же hs_code/brand/supplier_id → banner появляется (debounce 300ms) → click «Применить» → cert привязан.
5. **REQ-4 expired cert**: cert с `valid_until` в прошлом → красная рамка card → popover radio disabled с tooltip.
6. **REQ-10 expense flow**: «+ Добавить расход» → simple form (display_name + cost) → save → grey card с «Расход» badge.
7. **REQ-11 system view switch**: TableViewsDropdown → «Тарифы и НДС» → URL updates `?customs_view=system:tariffs-nds` → hint-banner появляется → page reload → view preserved.

**DB verification:**
```sql
SELECT count(*) FROM kvota.quote_certificates;
SELECT count(*) FROM kvota.quote_certificate_items;
SELECT * FROM kvota.quote_certificates ORDER BY created_at DESC LIMIT 5;
-- Verify backfill: row counts == cqe + cie sources
```

Document any deviations / follow-ups в `docs/plans/` или ClickUp tasks. Final commit message includes Phase B summary + browser-test scenarios verified + ClickUp references.

**Estimate:** 60-90 min

---

### Task 13: (deferred) Drop migration for `customs_*_expenses` tables — NOT IN PHASE B SCOPE

**Status:** TRACKED for future release after production verification (≥2 недели наблюдения per design.md §6).

Phase B оставляет `kvota.customs_item_expenses` + `kvota.customs_quote_expenses` нетронутыми (REQ-1 AC#8 — non-destructive backfill, rollback safety). Drop migration ≥307 — отдельный последующий релиз.

**Action:** add ClickUp task «Phase B follow-up: drop customs_*_expenses tables после verification» в backlog после merge Phase B.

---

## REQ Coverage Matrix

| REQ | Tasks |
|---|---|
| **REQ-1** — Migration 306 (atomic schema + backfill) | Task 1 |
| **REQ-2** — Backend API CRUD (POST/GET/DELETE/items + remove old endpoints) | Task 5 |
| **REQ-3** — Shared cost-split (Python + TS parity) | Task 2 (Python), Task 3 (TS), Task 6 (FE re-export) |
| **REQ-4** — `valid_until` expiry UI prompt | Task 7a (red border on card), Task 7d (popover disabled), Task 7f (HistoryBanner variant) |
| **REQ-5** — Cost-aware history autofill | Task 4 (service), Task 5 (endpoint), Task 6 (TS API), Task 7f (HistoryBanner UI), Task 10 (wiring + debounce) |
| **REQ-6** — Unified UI section «Расходы по таможне» | Task 7a (cards), Task 7f (CertificatesSection + empty state), Task 9 (wire into customs-step) |
| **REQ-7** — Modal с multi-select + live-preview | Task 7b (sub-components), Task 7c (CertificateModal) |
| **REQ-8** — Popover «Привязать к существующему» | Task 7d (CertificateBindPopover), Task 10 (wiring in dialog) |
| **REQ-9** — Per-item read-only coverage list | Task 7e (CoverageList + DetailsModal), Task 10 (wiring) |
| **REQ-10** — «Свой расход» упрощённая модалка | Task 7c (ExpenseModal) |
| **REQ-11** — TableViewsDropdown 4 виртуальных видa + hint banner | Task 8 (constants + dropdown grouping + hint-banner), Task 9 (inject views), Task 11 (handsontable resolver + banner mount) |
| **Acceptance Gates** — browser test, db:types green, tsc green, parity tests pass | Tasks 1, 3, 6, 9, 10, 11, 12 (cross-cutting) |

Every REQ-1..REQ-11 covered by ≥1 task. No orphans.

---

## File Isolation Audit (parallel safety per wave)

**Wave 1 (3 parallel):**
- Task 1: `migrations/306_*.sql`, `tests/migrations/test_306_*.py`, `database.types.ts` (regen)
- Task 2: `services/cost_split.py`, `tests/services/test_cost_split.py`, `tests/fixtures/cost_split_fixtures.json`
- Task 3: `frontend/src/shared/lib/cost-split.ts`, `frontend/src/shared/lib/__tests__/cost-split.test.ts`
- **Conflict check:** disjoint. `tests/fixtures/cost_split_fixtures.json` is shared output of Task 2 — Task 3 reads it. If Task 3 starts before Task 2 commits, fixture won't exist; coordinator should sequence Task 3 to start after Task 2's fixture is committed (~15 min delay) or Task 2 owns the fixture creation explicitly.

**Wave 2 (sequential 4 → 5):**
- Task 4: `services/quote_certificates_history.py`, `tests/services/test_quote_certificates_history.py`
- Task 5: `api/customs.py`, `api/routers/customs.py`, 3 new test files in `tests/api/`
- Both touch backend services — но disjoint files. Task 5 imports from Task 4, hence sequential.

**Wave 3 (6 parallel — Tasks 7a-7f after Task 6):**
- Task 6: scaffold (api/, model/, lib/, index.ts) — must complete first
- Task 7a: `ui/CertificateCard.tsx` + `ui/CustomExpenseCard.tsx`
- Task 7b: `ui/PositionsMultiSelect.tsx` + `ui/LivePreviewPanel.tsx`
- Task 7c: `ui/CertificateModal.tsx` + `ui/ExpenseModal.tsx` (uses 7b sub-components — sequential to 7b OR import via partial-stub if parallel)
- Task 7d: `ui/CertificateBindPopover.tsx` (uses 7b LivePreviewPanel — same caveat)
- Task 7e: `ui/CertificateCoverageList.tsx` + `ui/CertificateDetailsModal.tsx`
- Task 7f: `ui/HistoryBanner.tsx` + `ui/CertificatesSection.tsx` (imports 7a, 7c via index.ts — sequential to 7a + 7c)
- **Conflict check:** all task files disjoint в `ui/`. `index.ts` updated incrementally — coordinator должен сериализовать `index.ts` edits OR last task делает full re-export sweep. Recommended: each task adds its own export to `index.ts` in its commit; merge conflicts resolved via rebase.

**Wave 4 (3 sequential — same files):**
- Task 8: `customs-views.ts` (new), `table-views-dropdown.tsx` (modify), `hint-banner.tsx` (new)
- Task 9: `customs-step.tsx` (modify) — depends on 7f + 8
- Task 10: `customs-item-dialog.tsx` (modify) — depends on 7c, 7d, 7e, 7f
- Task 11: `customs-handsontable.tsx` (modify) — depends on 8
- **Conflict check:** all distinct files. Task 8/11 could be parallel if `table-views-dropdown.tsx` not edited by 11 (it isn't). Task 9 + 10 + 11 all distinct files.

**Wave 5:** verification only, no file conflicts.

**Locked files audit:** zero tasks reference `services/calculation_engine.py`, `services/calculation_models.py`, `services/calculation_mapper.py` ✅

---

## Total Effort Estimate

| Wave | Tasks | Sequential time | Parallel time (max agents) |
|---|---|---|---|
| 1 | 1, 2, 3 | 75+45+30 = 150 min | 90 min (slowest = Task 1) |
| 2 | 4, 5 | 75+135 = 210 min | 210 min (sequential) |
| 3 | 6, 7a-7f | 60+45+75+105+75+75+75 = 510 min | 165 min (Task 6 then 7c at 105 min) |
| 4 | 8, 9, 10, 11 | 75+60+90+60 = 285 min | 90 min (Task 10 critical path; 9/11 parallel after 8) |
| 5 | 12 | 75 min | 75 min |

**Sequential total:** 1230 min (≈20.5h)
**With max parallelism:** ~630 min (≈10.5h) — solo dev sees ~3-4 working days end-to-end including reviews.

Phase A precedent: 12 tasks / 5-7 working days. Phase B sized similarly (14 tasks but smaller average — UI-heavy with shared sub-components).

---

## Dependency Graph

```
Wave 1 (parallel):
  Task 1 (migration 306) (P)         ─┐
  Task 2 (cost_split.py) (P)         ─┼─► Wave 2/3
  Task 3 (cost-split.ts) (P)         ─┘
                │
                ▼
Wave 2 (sequential):
  Task 4 (history service) ◄── Task 1
  Task 5 (API handlers)    ◄── Task 1, 2, 4
                │
                ▼
Wave 3 (Task 6 first, then 7a-7f parallel where files differ):
  Task 6 (FSD scaffold)    ◄── Task 3, 5
  Task 7a (cards) (P)      ◄── Task 6
  Task 7b (sub-components) (P) ◄── Task 6
  Task 7c (modals)         ◄── Task 6, 7b
  Task 7d (popover)        ◄── Task 6, 7b
  Task 7e (coverage list) (P) ◄── Task 6, 7a
  Task 7f (history banner + section) ◄── Task 6, 7a, 7c
                │
                ▼
Wave 4 (mostly sequential — same-file conflicts):
  Task 8 (views + dropdown grouping) ◄── (independent of Wave 3 UI; can start parallel with Task 6)
  Task 9 (wire customs-step.tsx)     ◄── Task 7f, 8
  Task 10 (customs-item-dialog.tsx)  ◄── Task 7c, 7d, 7e, 7f
  Task 11 (customs-handsontable.tsx) ◄── Task 8
                │
                ▼
Wave 5:
  Task 12 (browser test)             ◄── all Wave 1-4 deployed
```

---

## Compliance Notes

- **Code-quality**: NO dead code (REQ-2 AC#16 — old `/expenses/*` endpoints deleted in same PR; REQ-6 AC#9 — old UI sections deleted, не закомментированы).
- **API-first** (`api-first.md`): все 6 new endpoints доступны AI-агентам через REST envelope; Server Actions обёртка не требуется (frontend вызывает напрямую через `apiClient<T>`).
- **Immutability**: cost-split helpers — pure functions; never mutate input arrays.
- **File-size budgets**: каждый UI файл < 250-400 LOC (mockup-driven design.md §4.8 split rationale). `api/customs.py` post-Phase-B ≈ 1900 LOC — flagged as R7 mitigation для отдельного refactor commit (вне Phase B scope).
- **Designsystem compliance** (LD-13): shadcn `<Button variant="…">`; Inter font; constrained scales; design tokens; NO `transition: all`; NO `transform: translateY()`; NO inline `style=` для colors/fonts/spacing.
- **Phase A regression**: 241 backend + 677 frontend tests must stay green после каждой Wave (design.md §7.4).
- **Locked files**: `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` — never modified. `services/calculation_helpers.py:_customs_value_in_rub` — read-only (imported, never edited).
- **Migration discipline**: `scripts/apply-migrations.sh` only — no manual `psql` (project convention). `npm run db:types` after every migration apply.

---

## Next Phase

После approval этих tasks:

```bash
# Lean-TDD execution (recommended — full quality funnel: impl → simplify → review → tests → commit → CI gate → deploy):
/lean-tdd skip-to-impl .kiro/specs/customs-shared-certificates/

# OR single-task execution (clear context between tasks):
/kiro:spec-impl customs-shared-certificates 1
/kiro:spec-impl customs-shared-certificates 2
# ...etc

# Multi-task batch (use cautiously):
/kiro:spec-impl customs-shared-certificates 1,2,3
```

Recommended: запускать через `/lean-tdd skip-to-impl` per project standard.
