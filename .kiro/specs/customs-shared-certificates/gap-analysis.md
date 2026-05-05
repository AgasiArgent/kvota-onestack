# Gap Analysis — customs-shared-certificates (Phase B)

**Документ цель:** Сравнить требования Phase B (`requirements.md`) с текущим состоянием кодовой базы и описать что есть, что нужно расширить, что построить с нуля.

**Период исследования:** 2026-05-04. Verified files: `migrations/261_create_user_table_views.sql`, `migrations/293_customs_cleanup_and_expenses.sql`, `migrations/304_tnved_user_choices.sql`, `frontend/src/features/customs-history/`, `frontend/src/features/table-views/`, `frontend/src/features/quotes/ui/customs-step/customs-step.tsx`, `frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx`, `frontend/src/features/quotes/ui/customs-step/customs-columns.ts`, `frontend/src/shared/types/database.types.ts`, `services/customs_user_choices.py`, `api/customs.py`, `api/routers/customs.py`, `frontend/src/app/globals.css`, `docs/mockups/customs-after-phases.html`.

---

## Summary

- **Storage decision is locked by existing schema:** `kvota.user_table_views` ALREADY exists (migration 261, FSD wiring complete in `customs-step.tsx:385-390`). `kvota.quote_view_preferences` referenced in REQ-11 AC#5 — **does NOT exist** and **should not be created**. Phase B's REQ-11 should be re-scoped to seed 4 system views as rows in `user_table_views` (`is_shared=true`, org-scoped) rather than introduce a new column/table. **migration 307 is unnecessary** — saves one migration.
- **Phase A's expense tables (`customs_item_expenses` + `customs_quote_expenses`, migration 293) ARE the "Сертификаты на КП" + "Общие расходы" the unified section replaces.** Phase B must include a deprecation/migration plan for those two tables (or accept long-running coexistence).
- **`cost_rub` field referenced throughout REQs is undefined on `quote_items`** — closest match is `customs_value_rub` (calc-engine input) or `proforma_amount_excl_vat_usd × usd_to_quote_rate`. Design phase MUST pick one canonical source. Risk: silent mismatch with calc engine if wrong field chosen.
- **All other foundations exist** — `kvota.quotes.organization_id`, `kvota.quote_items.{hs_code, brand, supplier_id}`, `auth.users`, dual-auth pattern, `apiClient<T>` wrapper, `Combobox` reference impl (`country-combobox.tsx`), shadcn Dialog/Popover/Checkbox/Input/Textarea, design-system tokens for `success/warning/error/info`, `formatDateRussian` helper. ~85% of Phase B's plumbing already lives in the project.
- **Recommended sequencing:** 5 waves; backend (migration + cost_split + API) parallel with frontend FSD scaffolding; integration into `customs-step.tsx` + `customs-item-dialog.tsx` last. Phase B should be tractable in 5–7 working days.

---

## Verified Facts

### Database

- `kvota.quotes` — exists. Has `id` (UUID PK), `organization_id` (UUID NOT NULL). `database.types.ts:4365-4366`. **OK as FK target.**
- `kvota.quote_items` — exists with all fields needed for loose-match (REQ-5 AC#1): `hs_code` (`text`), `brand` (`text`), `supplier_id` (`uuid`). `database.types.ts:4009, 3990, 4002`. **OK as FK target.**
- `kvota.organizations` — exists, FK target via `quotes.organization_id`. `migrations/304_tnved_user_choices.sql:24` uses `REFERENCES kvota.organizations(id)`.
- `auth.users` — exists, FK target. `migrations/304:25` uses `REFERENCES auth.users(id)`.
- `kvota.user_table_views` — **EXISTS** (migration 261). Schema: `(id, user_id, table_key, name, filters jsonb, sort, visible_columns text[], is_shared, organization_id, is_default, created_at, updated_at)`. RLS already covers personal + shared org. **This is the storage layer for Phase B's TableViewsDropdown views — no new table or column needed.**
- `kvota.quote_view_preferences` — **DOES NOT EXIST.** Zero references in `migrations/`, `services/`, `frontend/src/`. **REQ-11 AC#5 must be revised in design phase** — see Open Questions Resolved.
- `kvota.customs_item_expenses` + `kvota.customs_quote_expenses` — exist (migration 293). RLS via `JOIN organization_members + JOIN user_roles + r.slug IN ('customs','head_of_customs','admin')`. **These are the tables the unified UI replaces.** REQ-6 AC#9 instructs full removal of "Общие расходы по таможне" section but does not explicitly cover migrating data from these tables.
- `kvota.tnved_classification_log` (migration 298) + `kvota.tnved_user_choices` (migration 304) — exist; provide proven audit-log + cost-aware history pattern for Phase B's `services/quote_certificates_history.py`.
- Highest existing migration number: **305** (`migrations/305_quote_items_customs_manual_override.sql`). **Next safe numbers: 306, 307.** No collisions with existing files.
- RLS pattern divergence: migration 304 uses `auth.jwt() -> 'app_metadata' ->> 'organization_id'` (single-line JWT-only); migration 293 uses `JOIN organization_members + JOIN user_roles + r.slug` (multi-table). Phase B requirements (REQ-1 AC#6) explicitly mandate `r.slug`-based RLS — must follow 293 pattern, not 304.

### Backend

- `services/cost_split.py` — **DOES NOT EXIST.** Pure greenfield file. Validate via `find services -name "cost_split.py" -o -name "split_cost.py"` (zero matches).
- `services/customs_user_choices.py` (Phase A, 351 lines) — proven blueprint for `services/quote_certificates_history.py`. Pattern: typed dataclass `HistoryMatch`, `find_recent()` + `log_choice()` with `try/except` swallowing.
- `api/customs.py` — 1,868 lines. Auth helpers at `api/customs.py:86` (`_resolve_dual_auth`) and `api/customs.py:806` (`_err`). Role gate constant at `api/customs.py:36`: `_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}`. Existing history-lookup endpoint (`history_lookup_handler`) at `api/customs.py:1668-1750` is the exact template for `GET /api/customs/certificates/history`.
- `api/routers/customs.py` — thin router; new endpoints register here as `@router.post("/certificates")`, `@router.get("/certificates")`, etc.
- Dual auth pattern: `request.state.api_user` (JWT via `ApiAuthMiddleware`) + session fallback. Verified in `api/customs.py:1699-1703`.
- `services/customs_calc.py` — uses `Decimal` for currency math. Confirms `Decimal` viability for Phase B `split_cost`.

### Frontend

- `frontend/src/features/customs-history/` — Phase A reference FSD feature. Exports `formatDateRussian`, `fetchHistory`, `HistoryBanner`, types. **Reuse** `formatDateRussian` directly (REQ-4 AC#7, REQ-5 AC#11). Folder structure to mirror in `customs-certificates/`: `api/`, `lib/`, `model/`, `ui/`, `__tests__/`, `index.ts`.
- `frontend/src/features/table-views/` — exports `TableViewsDropdown` and `TableViewsSettingsDialog` (`index.ts:1-5`). Component already wired into `customs-step.tsx:19, 385-390` with `tableKey={CUSTOMS_TABLE_KEY}` + `activeViewId={activeViewId}` + `onViewChange` callback. **Phase B does not introduce TableViewsDropdown — it is already present.** REQ-11 work reduces to: seed 4 system views + adjust dropdown to surface a "system" group + (optionally) hint banner.
- `frontend/src/features/quotes/ui/customs-step/customs-step.tsx` — 451 lines. Lines 411–421 render `<ItemCustomsExpenses />` + `<QuoteCustomsExpenses />` + `<CustomsExpenses />`. **`<QuoteCustomsExpenses />` (Phase A, "Общие расходы на КП") and `<ItemCustomsExpenses />` are the sections REQ-6 AC#9 instructs to delete.** `<CustomsExpenses />` (line 421) is a separate calc-engine variable form ("Таможенный сбор / Сертификат происхождения / Документация / Брокерские расходы") — likely OUT of REQ-6 scope but should be confirmed in design.
- `frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx` — 1,385 lines. Already imports `HistoryBanner`, `fetchHistory`, `formatDateRussian` (lines 58-62) and renders banner at line 605–614. New "Сертификация" section (REQ-8/REQ-9) inserts BELOW existing tariff/НДС sections, ABOVE Phase C "Нетарифные требования" placeholder (mockup lines 884–910).
- `frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx` — 1,189 lines. Receives `visibleColumns?: readonly string[]` prop (line 718). Filtering logic at lines 760–765. Toolbar location for hint banner = ABOVE the `<HotTable />` element.
- `frontend/src/features/quotes/ui/customs-step/customs-columns.ts` — **24 columns** registered (NOT 18 as REQ-11 AC#2 assumes). REQ-11's promised view definitions reference `certificates` and `cost_rub` keys that do NOT exist in `CUSTOMS_AVAILABLE_COLUMNS`. Design phase must reconcile.
- `frontend/src/shared/lib/api.ts` — `apiClient<T>(path, options)` wrapper sends JWT, returns `ApiResponse<T>`. Standard for new `/certificates/*` endpoints.
- `frontend/src/shared/lib/cost-split.ts` — **DOES NOT EXIST.** Pure greenfield file (REQ-3 AC#2, parity with Python).
- shadcn primitives present in `frontend/src/components/ui/`: `button`, `card`, `checkbox`, `dialog`, `dropdown-menu`, `input`, `popover`, `select`, `textarea`, `tooltip`. **NO `command` (cmdk) primitive** — searchable Combobox uses bespoke `Popover + Input + filtered list` pattern (proven in `country-combobox.tsx`).
- Existing Combobox reference: `frontend/src/shared/ui/geo/country-combobox.tsx` exposes `filterCountries(...)` pure-fn pattern + clearable + listMaxHeight props. Direct template for `type` Combobox (REQ-7 AC#3) and quote-positions multi-select.
- Design tokens (`frontend/src/app/globals.css:130-136`): `--color-success`, `--color-success-bg`, `--color-warning`, `--color-warning-bg`, `--color-error`, `--color-error-bg`, `--color-info`. **Missing:** `--color-info-bg`, `--color-neutral`, `--color-neutral-bg` (gray for "Расход" badge per REQ-6 AC#5). Design phase must either add tokens or reuse `--color-text-subtle`/`--color-border-light` (`globals.css:125-126`).
- `.btn` BEM classes mentioned in CLAUDE.md/spec — **not actually present in codebase** (zero matches for `className="btn`). Project uses shadcn `<Button variant="…">` via `frontend/src/components/ui/button.tsx`. REQ-7 AC#10 / REQ-6 AC#2 wording about `.btn` classes is inherited from older convention; current standard is shadcn Button.

### Existing Components to Reuse

- `frontend/src/features/customs-history/lib/format-date.ts` — `formatDateRussian(iso): string` (DD.MM.YYYY).
- `frontend/src/features/customs-history/ui/history-banner.tsx` — banner layout pattern (info-blue / amber-warning) for REQ-5 AC#6/AC#7.
- `frontend/src/features/customs-history/api/history.ts` — typed `apiClient` wrapper template for REQ-5 endpoint.
- `frontend/src/features/table-views/index.ts` — `TableViewsDropdown` + `TableViewsSettingsDialog`. Already integrated.
- `frontend/src/entities/table-view/server-queries.ts:fetchAllAvailable(orgId, tableKey, userId)` + `frontend/src/entities/table-view/queries.ts` (reads) + `mutations.ts` (CRUD) — full preference persistence layer.
- `frontend/src/shared/ui/geo/country-combobox.tsx` — searchable Combobox blueprint.
- `frontend/src/components/ui/dialog.tsx`, `popover.tsx`, `checkbox.tsx`, `dropdown-menu.tsx` — primitives for REQ-7/REQ-8/REQ-10 modals + popover.
- `services/customs_user_choices.py` — Phase A history-service blueprint (HistoryMatch dataclass, `find_recent` + `log_choice`). Mirror in `services/quote_certificates_history.py`.
- `api/customs.py:_resolve_dual_auth` (line 86) + `_err` (line 806) — auth + error helpers used verbatim.
- `api/customs.py:_CUSTOMS_ROLES` (line 36) — write-role gate. READ role list (REQ-1 AC#6) needs new constant `_CERT_READ_ROLES` covering `sales/quote_controller/spec_controller/finance/top_manager` in addition.

---

## Open Questions Resolved

- **REQ-11 AC#5 (`quote_view_preferences.customs_columns_view`):** `kvota.quote_view_preferences` does NOT exist anywhere (verified by `grep -rln "quote_view_preferences" --include="*.sql" --include="*.py" --include="*.ts" --include="*.tsx"` → zero matches). The functional equivalent is `kvota.user_table_views` (migration 261). **Recommendation: drop migration 307 entirely.** Phase B's 4 system views ship as seed rows in `user_table_views` (`is_shared=true`, `organization_id` per org, `table_key='quote_customs_items'`) OR as virtual non-DB rows injected client-side into `TableViewsDropdown` `views` prop. Persistence of selection already works via `?customs_view=<id>` URL param (verified in `customs-step.tsx:170-194`).
- **`cost_rub` field on `quote_items`:** does not exist. Closest candidates: `customs_value_rub` (calc-engine input — `customs_calc.py:172` uses it for ad-valorem), or `proforma_amount_excl_vat_usd * quotes.usd_to_quote_rate`. **Design phase must pick one canonical source.** Recommendation: pull `customs_value_rub` if available, fallback to `proforma_amount_excl_vat_usd × quote currency conversion`. The REQ wording assumes "cost in RUB" exists; design must concretize.
- **Existing "Сертификаты на КП" / "Общие расходы по таможне" sections (REQ-6 AC#1):** These are the rendered output of `<QuoteCustomsExpenses />` ("Общие расходы на КП", `customs-step.tsx:419`) and `<ItemCustomsExpenses />` (`customs-step.tsx:411`), backed by `kvota.customs_item_expenses` + `kvota.customs_quote_expenses` (migration 293). REQ-6 AC#9 says delete the rendered sections; design phase decides whether to also drop the DB tables (data migration) or leave them dormant.
- **`<CustomsExpenses />` at `customs-step.tsx:421`:** Different entity — calc-engine variable form for "Таможенный сбор / Сертификат происхождения / Документация / Брокерские расходы". Connected to `quote_versions.input_variables`, not `customs_*_expenses` tables. Likely OUT of Phase B replacement scope; confirm with user before deletion.
- **TableViewsDropdown integration (REQ-11 AC#1):** Already integrated at `customs-step.tsx:385-390`. Phase B does not "integrate" it; Phase B seeds 4 system views and (per AC#9-10) adds the "active view ≠ all" hint banner.
- **Migration sequencing (LD-12):** Phase B's "two new migrations 306 + 307" → REVISED to ONE migration (306) given `user_table_views` already exists.

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `cost_rub` source-of-truth ambiguity for live preview + share calc — silent data drift between calc-engine and Phase B sums | **HIGH** | Design phase: lock canonical source (recommend `customs_value_rub`); cite exact column path. Add backend test asserting Phase B `attached_items[].share_rub` sums match canonical "item value" used by calc-engine. |
| REQ-11 specifies a non-existent storage table (`quote_view_preferences`) | **HIGH** | Resolved here: use existing `user_table_views`. Spec needs amendment before design phase locks in fictional schema. |
| RLS pattern inconsistency: REQ-1 AC#6 requires `r.slug`-based gates (293 pattern), but neighboring Phase A migration 304 uses JWT `app_metadata.organization_id` (304 pattern). New 306 must pick one. | MEDIUM | Use 293 pattern (multi-tenant + role-based) since REQ-1 AC#6 explicitly enumerates roles. Document rationale in 306 SQL comment. |
| Phase A `customs_item_expenses` + `customs_quote_expenses` coexist with new `quote_certificates` after Phase B — two sources of truth for "customs costs" | MEDIUM | Phase B requirements should add a 5th item: deprecation/migration plan. Either (a) backfill into `quote_certificates` with `is_custom_expense=true` then drop, or (b) leave dormant + remove UI. Decide in design. |
| REQ-11 AC#2 view definitions reference column keys (`certificates`, `cost_rub`) NOT in `CUSTOMS_AVAILABLE_COLUMNS` — view will silently filter to empty result | MEDIUM | Design phase: amend view definitions to use real keys (`hs_code, customs_duty_composite, customs_antidumping`, etc.) OR add new computed columns to handsontable + register in `customs-columns.ts`. |
| REQ-7 multi-select positions UI is greenfield; no prior art for "checkbox list with search + Select-all + live preview" in this codebase | MEDIUM | Compose from existing primitives: `Checkbox`, `Input` with `country-combobox.tsx`-style filter pattern. Budget extra time (estimated +1 day). |
| `--color-info-bg` and gray "neutral" tokens missing — REQ-6 AC#5 / REQ-8 AC#7 specify color-coded card variants | LOW | Add 2-3 tokens to `globals.css` and `design-system.md` in same PR. Pure additive change. |
| Cost-split parity between `services/cost_split.py` (Decimal `ROUND_HALF_UP`) and `frontend/src/shared/lib/cost-split.ts` (`Math.round(value * 100) / 100`) — JS uses Banker's-style Math.round, NOT half-up | LOW | Use explicit half-up shim in TS: `Math.floor(value * 100 + 0.5) / 100`. Verify in shared JSON fixture tests. |
| Phase B requirements assume `.btn` BEM classes that do not exist in current frontend | LOW | Use shadcn `<Button variant="…">` per current convention. Update spec wording in design phase. |
| 4 deprecated `301_*` and `302_*` migration files share numbers (`301_tnved_rate_variants.sql` + `301_widen_documents_rls_for_chat_attachments.sql`, etc.) — `apply-migrations.sh` ordering is filesystem-dependent | LOW | Use `306_quote_certificates.sql` (single number, no collision). Verified that 305 is highest unique. |

---

## Sequencing Recommendation

- **Wave 1 — Foundation (parallel):**
  - DB: write `migrations/306_quote_certificates.sql` (table + M2M + RLS + indexes + FK CASCADEs).
  - Backend pure: `services/cost_split.py` + `tests/services/test_cost_split.py` + `tests/fixtures/cost_split_fixtures.json`.
  - Frontend pure: `frontend/src/shared/lib/cost-split.ts` + `__tests__/cost-split.test.ts` consuming same fixture.
  - Apply migration 306 via `scripts/apply-migrations.sh`; regenerate `frontend/src/database.types.ts` via `npm run db:types`.

- **Wave 2 — Backend API (depends on Wave 1 DB):**
  - `services/quote_certificates_history.py` (mirror `customs_user_choices.py`).
  - `api/customs.py` — new `_certificates_*` handlers (POST/GET/DELETE/items POST/items DELETE/history).
  - `api/routers/customs.py` — register new routes.
  - Backend integration tests.

- **Wave 3 — Frontend FSD scaffolding (depends on Wave 1 cost-split.ts; uses Wave 2 API contracts):**
  - `frontend/src/features/customs-certificates/api/{certificates,history}.ts` (typed wrappers around Wave 2 endpoints).
  - `frontend/src/features/customs-certificates/model/types.ts` (mirror Python dataclasses).
  - `frontend/src/features/customs-certificates/ui/{certificate-modal,custom-expense-modal,attach-popover,cert-card,cert-list-section,coverage-list}.tsx`.
  - `frontend/src/features/customs-certificates/index.ts`.

- **Wave 4 — Wiring (depends on Wave 3):**
  - `customs-step.tsx` — replace `<QuoteCustomsExpenses />` + `<ItemCustomsExpenses />` with new `<CertificatesSection />`. Decide fate of `<CustomsExpenses />` (calc-engine vars) with user.
  - `customs-item-dialog.tsx` — add "Сертификация" section + popover trigger.
  - `customs-handsontable.tsx` — add hint banner for active-view ≠ all + verify new columns render (or amend `customs-columns.ts`).
  - Seed 4 system views into `user_table_views` (one-shot SQL or service-layer seed).

- **Wave 5 — Verification:**
  - Browser test (localhost:3000 + prod Supabase) covering: create cert → multi-select → save → see card → edit → attach via popover → unattach → history banner → expired-cert red border → custom-expense flow → 4 system views toggle.
  - Update `.kiro/specs/customs-shared-certificates/spec.json` `phase`.

---

## Out of Scope (re-confirmed)

- Calculation engine modification (`calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`) — locked.
- Phase C: Расширенные нетарифные требования (санитарка / ветконтроль / IP / параллельный импорт).
- Phase C: Тип сертификата происхождения как enum (CT-1 / EUR.1 / Form A) — `type` остаётся свободным TEXT в Phase B.
- Phase C: «Честный знак» selectbox.
- Phase C: ОТТС / ОТТС МУ.
- Phase D: Россельхознадзор, Минкульт, военка.
- User-editable custom views, drag-and-drop column reordering — отложено (Phase B = 4 system views only).
- Mobile UI (Phase B desktop-only).
- Cert-attachment audit-log table (history of attach/detach actions).
- Migration of existing `customs_item_expenses` + `customs_quote_expenses` data into `quote_certificates` — escalate to user during design phase.

---

## Next Step

Two HIGH-severity items require user input before `/kiro:spec-design`:

1. **Confirm `quote_view_preferences` is dropped** from Phase B scope (use existing `user_table_views`). Migration 307 cancelled.
2. **Lock the `cost_rub` source-of-truth column** for cost split + live preview (`customs_value_rub` recommended, but design phase needs explicit answer).

After approval of these resolutions:

```
/kiro:spec-design customs-shared-certificates    # technical design (требует approval)
/kiro:spec-tasks customs-shared-certificates     # task breakdown (auto-approve)
/lean-tdd skip-to-impl .kiro/specs/customs-shared-certificates/
```
