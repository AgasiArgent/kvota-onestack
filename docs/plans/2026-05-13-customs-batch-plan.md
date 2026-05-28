# Customs Panel — Testing 2 Batch Plan (Rows 1, 2, 3, 5, 7, 8, 9, 10, 11)

**Date:** 2026-05-13
**Source:** `docs/plans/2026-05-13-testing2-bugs.md` (B1–B32 except B19–B20 already in PR #141)
**Base branch:** `main` (rebase after PR #141 lands)
**Already-resolved:** Row 4 + license `_cost` ghost cols + save bug FB-260511-212235-0384 + Alta UI hidden (PR #140/#141).

---

## Row-by-row scope

| Row | Element | File(s) | Root-cause hypothesis | Effort | Sub-batch |
|---|---|---|---|---|---|
| 1 | Инф. панель → Клиент (Контакт, Адрес) | `frontend/src/features/quotes/ui/context-panel/context-panel.tsx`, `frontend/src/features/quotes/ui/context-panel/contact-dropdown-select.tsx`, `frontend/src/entities/quote/queries.ts` (`getQuoteById` ~L440), `frontend/src/features/quotes/ui/context-panel/queries.ts` (`fetchQuoteContextData`) | Contact `name` join only selects `id, name, phone, email` — `last_name` and `patronymic` are dropped, so ФИО displays first-name only. Address row uses `truncate` inside narrow grid column → long address clips. Both bugs are pure display/query. | S | **SB-A** Info-panel display |
| 2 | Инф. панель → Участники | `frontend/src/features/quotes/ui/context-panel/context-panel.tsx` (Participants block L252-308), `frontend/src/features/quotes/ui/context-panel/queries.ts` | Vague "поправить отображение" — likely the participant rows are too tight (date+name+role badge truncated) or the empty-state guard at L302-306 fires when only МОЛ/МОТ are set. Needs browser-test reproduction to pin exactly. Tester expects «участники + дата/время добавления» = workflow_transitions rows, which are already wired — but visually unclear. | S–M (browser-test first) | **SB-A** Info-panel display |
| 3 | Таблица → Кнопка «Все колонки» (dropdown под колонками) | `frontend/src/components/ui/dropdown-menu.tsx` (DropdownMenuContent L33-48, currently `z-50`), or callsite `frontend/src/features/table-views/ui/table-views-dropdown.tsx` | shadcn `DropdownMenuContent` portal uses `isolate z-50` — Handsontable's fixed headers/wtBorder overlays sit higher, so the menu renders behind cells. Project convention: popovers use `z-[300]`, dialogs `z-[200]`. Bump dropdown to `z-[300]` via classname prop OR fix at base component (impacts every dropdown in the app — verify no regression). | S | **SB-B** Z-index + action-bar polish |
| 5 | Примечания (customs_notes) | `frontend/src/features/quotes/ui/customs-step/customs-notes.tsx` | Two issues: (a) UX — saves silently on blur with no button/indicator; tester expects explicit save button. (b) Supabase client returns errors via `.error` (not throws), but the code uses `try/catch` only → no error toast on failure; silent fail. Same family as PR #141 silent-400. **Product question** before fix: tester also suggested «можно удалить, т.к. ниже есть еще одни примечания» — confirm whether to keep this block or delete in favor of `<EntityNotesPanel>` below it. | S (if fix) / Trivial (if delete) | **SB-C** Notes + sticky action |
| 7 | Ответственные (info-block внизу) | `frontend/src/features/quotes/ui/customs-step/customs-info-block.tsx` (L74-104) | Procurement assignee read from `quote_items.assigned_procurement_user` (only one item picked — `procurementUsers[0]`). On the test quote `b4e56dac-…`, that column is null (procurement may have been assigned earlier via the now-dropped `quotes.assigned_procurement_user`, or by completing the stage without touching the per-item field, or RLS hides items from customs role). Falls back to «Не назначен». | M | **SB-D** Responsibles (МОЗ trace) |
| 8 | Таблица → Модал (type chip change in HoT → modal stale) | `frontend/src/features/quotes/ui/customs-step/customs-step.tsx` (L527-540), `customs-handsontable.tsx` (L969-1020 `handleDutyModeChange`), `customs-item-dialog.tsx` (L448-466 reseed effect) | Race condition: HoT inline duty-mode chip mirrors state in HoT via `setDataAtRowProp(..., "internal-mirror")` **immediately**, but `updateQuoteItem(...).then(router.refresh())` is async. If user opens dialog before `router.refresh` completes, dialog seeds from the stale `items` prop. The `[open, item]` reseed effect won't re-fire because the same QuoteItemRow reference is passed. Either await save before allowing dialog open, or lift duty-mode + dialog form state into a shared client store with optimistic update. | M | **SB-E** Table/Dialog sync (Rows 8, 9, 10) |
| 9 | Модал → таблица + не сохраняется | `customs-item-dialog.tsx` (L268-336 `buildUpdates`), `customs-handsontable.tsx` (L394-411 `customs_duty_composite` derivation, COLUMNS L705-746) | Two parts: (a) Save persists fine (no missing columns confirmed). (b) **Display gap**: when user changes "Тип ставки" (simple/combined/specific in Manual mode) and value, the HoT column 7 «Пошлина» shows only the numeric `customs_duty_composite` — no chip/badge for type. Tester reads "value unchanged → не сохранилось". When the `combined` rate type is picked, slot-2 value is stored only in `customs_manual_rate_payload` JSONB; HoT can't render it without parsing the JSONB. Fix: add a small renderer that shows the formatted formula (`formatDutyFormula` already exists in `customs-rate-resolve`). | M | **SB-E** Table/Dialog sync |
| 10 | Модал → Страна происхождения (отражается число) | `customs-handsontable.tsx` (L714-720) | Column `country_of_origin_oksm` declared `type: "numeric", readOnly: true` — the cell renders the raw OKSM digit (e.g. `156`) instead of `Китай`. No renderer maps OKSM → `name_ru`. Fix: fetch `fetchOksmCountries()` once at customs-step level, pass as prop, and add a custom renderer that does `oksmMap.get(value)?.name_ru ?? value`. | S–M | **SB-E** Table/Dialog sync |
| 11 | Кнопка «Таможня завершена» — «Ничего не происходит» | `services/workflow_service.py` (`complete_customs` L1970-2006, role check L2001) | Backend role guard accepts only `customs` or `admin`. Frontend allows the click for `customs`/`head_of_customs`/`head_of_logistics`/`admin` (customs-step.tsx L434-444 `canEditCustoms`). When МВЭД (`head_of_customs`) or РОЛ (`head_of_logistics`) click, server returns `{success:false, error:"Only customs or admin can complete customs"}` → frontend `callWorkflowTransition` throws → toast.error fires but tester may miss the brief toast and reports «ничего не происходит». **Fix:** mirror `complete_logistics` (L1857) — extend allowed roles to `["customs", "admin", "head_of_customs", "head_of_logistics"]`. Same dual-hat reasoning already documented inline at customs-step.tsx L440. Optional UX: also make the toast.error sticky for `requires_action: false` errors. | S | **SB-F** Complete-customs role gate |

**Effort legend:** S=under 30 min, S–M=30-60 min, M=1-2 h, L=2-4 h. All include browser-test pass.

---

## Sub-batches and dispatch plan

### SB-A — Info-panel display (Rows 1, 2)

- **Files:**
  - `frontend/src/features/quotes/ui/context-panel/context-panel.tsx`
  - `frontend/src/features/quotes/ui/context-panel/contact-dropdown-select.tsx`
  - `frontend/src/entities/quote/queries.ts` (extend `contact_person` select to `id, name, last_name, patronymic, phone, email`)
  - `frontend/src/features/quotes/ui/context-panel/queries.ts` (`fetchQuoteContextData` contact join)
- **Branch:** `fix/customs-info-panel-contact-address`
- **Scope:**
  - Include `last_name` + `patronymic` in contact query; render as `"{name} {last_name}".trim()` (mirror `call-form-modal.tsx:180` pattern).
  - Address row: drop `truncate` or replace with `line-clamp-2` so long addresses wrap. Tester expects to see the full address — wrap is the right call given the info-panel real estate.
  - Row 2 needs **browser-test reproduction first** — open `Q-202604-0047` as one of the affected roles and capture screenshot of «Участники». If layout truncation is the issue, widen the column or wrap rows. If empty-state guard fires, fix the conditional.
- **Effort:** S (Row 1) + S–M (Row 2 after repro) = ~1 h total.

### SB-B — Z-index for Все колонки dropdown (Row 3)

- **Files:**
  - `frontend/src/components/ui/dropdown-menu.tsx` (or override at `frontend/src/features/table-views/ui/table-views-dropdown.tsx` via `className` prop)
- **Branch:** `fix/customs-views-dropdown-zindex`
- **Scope:** Pass `className="z-[300]"` to `<DropdownMenuContent>` at the TableViewsDropdown callsite. Avoid touching the base shadcn primitive to prevent app-wide regressions. Verify Handsontable column-resize handle and context menu still render above where appropriate.
- **Effort:** S.

### SB-C — Customs notes UX (Row 5)

- **Files:**
  - `frontend/src/features/quotes/ui/customs-step/customs-notes.tsx`
  - `frontend/src/features/quotes/ui/customs-step/customs-step.tsx` (L511 if deleting)
- **Branch:** `fix/customs-notes-save-or-remove`
- **Scope (decision-gated):**
  - **Option A — Delete the standalone CustomsNotes block** in favor of `<EntityNotesPanel>` below it. Tester explicitly suggested this. Cleaner — single source of customs notes, no duplicate save paths.
  - **Option B — Keep but fix:** read Supabase `.error` field (not try/catch), show a save indicator + explicit «Сохранить» button OR a "Сохранено / Сохранение…" status next to label. Toast on error.
- **Recommendation:** Option A. EntityNotesPanel already supports `defaultVisibleTo` + audit trail. The standalone block was a Phase-A leftover.
- **Effort:** Trivial (Option A, ~15 min) or S (Option B, ~30 min).

### SB-D — Responsibles block (Row 7)

- **Files:**
  - `frontend/src/features/quotes/ui/customs-step/customs-info-block.tsx`
- **Branch:** `fix/customs-info-responsibles-fallback`
- **Scope:** Improve the МОЗ lookup: derive procurement responsible from a stack of sources in priority order:
  1. Distinct `quote_items.assigned_procurement_user` (current behavior — keep as primary)
  2. Most recent `workflow_transitions.actor_id` where `from_status='pending_procurement'` (i.e., who completed procurement)
- Render multiple procurement users if quote_items span several МОЗ. Also consider replacing the entire bottom block with a richer version of the top `<ContextPanel>` Участники column (since they overlap conceptually — but that's UX scope, not in this bug). Stick to data-source fallback for now.
- **Effort:** M.

### SB-E — Table↔Dialog sync (Rows 8, 9, 10)

- **Files:**
  - `frontend/src/features/quotes/ui/customs-step/customs-step.tsx` (lift state)
  - `frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx` (reseed dependency)
  - `frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx` (renderers for duty composite + country column, OKSM map prop)
  - `frontend/src/features/customs-country-dropdown/api/fetch-countries.ts` (already exports `fetchOksmCountries`)
- **Branch:** `fix/customs-table-dialog-sync`
- **Scope:**
  1. **Row 10 (country shows number):** Fetch OKSM countries at `CustomsStep` level (1 call, cache via React state). Pass as `Map<number, string>` to `<CustomsHandsontable>`. Add a custom renderer for column `country_of_origin_oksm` that resolves number → `name_ru`. **No DB change needed.**
  2. **Row 8 (table → dialog stale):** When `handleDutyModeChange` fires in HoT, call a new prop `onItemPatched(rowId, patch)` that updates a local `itemsOverride` map in `CustomsStep`. Pass `itemsOverride` into the dialog's `item` lookup so it returns the optimistic merged value. Clear the override after `router.refresh()` returns fresh items. Alternative (simpler but uglier): bump a `formVersion` counter in CustomsStep state when HoT saves; pass to dialog as a reseed dependency.
  3. **Row 9 (modal → table not visible):** Add a HoT renderer for `customs_duty_composite` that uses `formatDutyFormula({rate_type, value_1, unit_1, value_2, unit_2, sign})` when `customs_manual_override` is true, otherwise the current chip-based display. Pull the formula data into `buildHotRow` from `extras.customs_manual_rate_payload`. Tester sees the type+value, no longer perceives "не сохранилось".
- **Effort:** M for all three (~1.5 h). Single batch because all three touch HoT/dialog wiring and benefit from a single browser-test pass.

### SB-F — Complete-customs role gate (Row 11)

- **Files:**
  - `services/workflow_service.py` (L2001 in `complete_customs`)
- **Branch:** `fix/customs-complete-role-dual-hat`
- **Scope:**
  - Extend `["customs", "admin"]` to `["customs", "admin", "head_of_customs", "head_of_logistics"]` to mirror `complete_logistics` (L1857) and frontend `canEditCustoms` (customs-step.tsx L434-444). Add a unit test in `tests/services/test_workflow_service.py` (or equivalent) that the new roles transition `pending_customs → customs_complete`. Update the docstring at L1980 accordingly.
- **Effort:** S.

---

## Total estimated effort

| Sub-batch | Effort |
|---|---|
| SB-A (Rows 1, 2) | ~1 h |
| SB-B (Row 3) | ~20 min |
| SB-C (Row 5, decision-gated) | ~15-30 min |
| SB-D (Row 7) | ~1.5 h |
| SB-E (Rows 8, 9, 10) | ~1.5 h |
| SB-F (Row 11) | ~30 min |
| **Total** | **~5 h serial / ~2 h parallelized (6 agents)** |

---

## Dispatch recommendation

Run **6 parallel agents**, one per sub-batch. Each owns its own branch off `main`. Order of merge:

1. **SB-B** (z-index) — trivial, lands first, no conflicts
2. **SB-F** (workflow role) — backend-only, no conflicts with FE batches
3. **SB-C** (notes) — touches `customs-step.tsx` L511 only if deleting; product decision blocks if Option B
4. **SB-A** (info-panel) — conflicts only with itself (queries.ts + context-panel.tsx); needs Row 2 browser-test first
5. **SB-D** (responsibles) — isolated file `customs-info-block.tsx`
6. **SB-E** (sync) — biggest blast radius (handsontable + dialog + step); merge last

`customs-step.tsx` is touched by SB-C, SB-D (read-only), and SB-E. Stagger merges: SB-C → SB-D → SB-E with rebase between. SB-A and SB-B are independent.

Per memory note `feedback_parallel_deploys_container_conflict.md` (2026-04-22) — wait ≥90 s between PR merges to main to avoid the docker container-name race.

---

## Open questions for user (3)

1. **Row 5 (Примечания):** delete the standalone `<CustomsNotes>` block in favor of the `<EntityNotesPanel>` already rendered below it (tester's own suggestion), or keep + fix the save UX with a button + status indicator? Recommendation: **delete**. Confirm or override.
2. **Row 2 (Участники):** the actual symptom is vague («Поправить отображение»). OK to take a screenshot in browser-test via `mcp__plugin_playwright_playwright__*` on `Q-202604-0047` as МВЭД to see what they're complaining about, then decide between (a) widen column, (b) tighten rows, (c) restructure entirely? Or wait for tester clarification?
3. **Row 11 (role gate):** confirm МВЭД (`head_of_customs`) and РОЛ (`head_of_logistics`) **should** be able to complete customs in the dual-hat model. The frontend already treats them as editors; the backend hasn't caught up. Mirror is correct, but please confirm before merging since this widens a workflow transition's permission.
