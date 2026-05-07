# /lean-tdd scope — Multi-tab Test Sweep 2026-05-07

**Mode:** /lean-tdd, BUGFIX batch (no spec phase needed beyond per-track minimal spec)
**Source triage:** `docs/plans/2026-05-07-multi-test-triage.md`
**Source exploration:** `docs/plans/2026-05-07-multi-test-explore.md`
**Source repro:** `/tmp/repro-2026-05-07.md` + `/tmp/repro-2026-05-07-bug*.png`
**Branch:** `chore/harden-routing-api` (current)

## Reconciled findings

- **Already fixed (verified by repro), no work:** РОП #24 (PR #119), РОП Cust #1 (PR #119), МОЗ #94 «дублирование» (PR #110)
- **Not bugs (close to tester):** СтМоз C3 (dropdown работает, все 723 клиента активны), МОЗ #93 (modal не воспроизводится на 1280×600/720/800, 1366×768, 1440×900)
- **Known issue (no work this sprint):** СтМоз C9/Q6 backfill — calc engine не прогнан по большинству КП; closing UX-часть в Track B

---

## 5 tracks

| ID | P | Title | Closes | Files (preliminary) | Estimate |
|----|---|-------|--------|---------------------|----------|
| **A** | P3 | МОЗ Контакт + Адрес read-only — frontend gate + RLS UPDATE policy | МОЗ #58 (Bug 6) | `frontend/src/features/quotes/ui/context-panel/context-panel.tsx`, `contact-dropdown-select.tsx`, `address-dropdown-select.tsx`, `entities/quote/mutations.ts` (patchQuote), new migration on `kvota.quotes` UPDATE policy + dom test | M |
| **B** | P4 | Hide финансовые колонки от закупки/логистики/таможни | СтМоз C9 + Q6 (UX-часть Bugs 4/5) | `frontend/src/shared/lib/roles.ts` (new helper `shouldShowFinancials`), `frontend/src/features/customers/ui/customers-table.tsx:241` (Подробно), `frontend/src/features/quotes/ui/quotes-table-client.tsx:240` (СУММА, ПРИБЫЛЬ columns) + dom test | XS-S |
| **C** | P4 | Tooltip на truncated supplier/customer name в КПП header | МОЗ #94 actual (Bug 8 truncation) | `frontend/src/features/quotes/ui/procurement-step/invoice-card.tsx:826` + Tooltip wrapper + dom test | XS |
| **D** | P4 | `/customs/declarations` — fix React hydration mismatch #418 | Bonus repro finding | TBD via grep `customs/declarations` page + likely Date/SSR timezone or randomid issue + dom test | S |
| **E** | P4 | Логисты table: показать ФИО, не UUID `96d797ee` | Bonus repro finding | TBD via grep — likely `frontend/src/app/(app)/workspace/logistics/...` page rendering raw `assigned_user_id` instead of joined `name` | S |

---

## Track A — detailed spec

**Goal:** МОЗ (procurement, head_of_procurement, procurement_senior, logistics, customs) cannot edit `contact_person_id` or `delivery_address` on a quote. Sales-side roles (sales, head_of_sales, admin) can.

**Frontend:**
- New helper in `frontend/src/shared/lib/roles.ts`: `canEditQuoteCustomerFields(roles)` → `roles.includes('sales') || roles.includes('head_of_sales') || roles.includes('admin')`
- `context-panel.tsx`: gate `<ContactDropdownSelect>` and `<AddressDropdownSelect>` — render read-only `<span>` with current label when gate false (mirror existing pattern in `quote-detail-shell.tsx`)
- Tests: `context-panel.dom.test.tsx` — render with each role, assert button vs span

**Backend (defense in depth, per `.claude/rules/api-first.md`):**
- Migration NNN (next sequential): UPDATE policy on `kvota.quotes` restricting `contact_person_id` and `delivery_address` writes to sales/head_of_sales/admin roles. Use `kvota.has_any_role(...)` if it exists; else inline the role check via `auth.uid()` join to `kvota.user_roles`.
- Validate on staging — production migration applied via `scripts/apply-migrations.sh`.

**Acceptance criteria:**
- Logged-in МОЗ: Контакт rendered as plain text, no popover. Same for Адрес.
- Logged-in МОП: full edit affordance preserved.
- Direct PostgREST UPDATE on `quotes.contact_person_id` as МОЗ JWT: 403 / RLS denial.
- Existing dom tests stay green; new tests cover both positive and negative roles.

---

## Track B — detailed spec

**Goal:** Скрыть «Сумма», «Прибыль», «Выручка», «Спец», «Кол-во КП» (financial / aggregation columns) для ролей, которым они не нужны на их этапе пайплайна.

**Visibility rule:**
- **Show:** `admin`, `sales`, `head_of_sales`, `quote_controller`, `spec_controller`, `finance`, `top_manager`
- **Hide:** any role matching `procurement` / `logistics` / `customs` (includes `procurement_senior`, `head_of_procurement`, `head_of_logistics`)

**Implementation:**
- New helper in `frontend/src/shared/lib/roles.ts`: `shouldShowFinancials(roles): boolean`
- `quotes-table-client.tsx`: filter columns array by `shouldShowFinancials(userRoles)` for СУММА, ПРИБЫЛЬ
- `customers-table.tsx`: same — filter Выручка, Прибыль, Спец, Кол-во КП

**Acceptance criteria:**
- Logged-in procurement / procurement_senior / head_of_procurement / logistics / customs: financial columns absent
- Logged-in sales / head_of_sales / admin / finance / quote_controller / spec_controller / top_manager: columns visible
- dom test for both modes per page

---

## Track C — detailed spec

**Goal:** Hover over truncated supplier or customer name in КПП header chip → see full name in native tooltip (`title` attribute or shadcn Tooltip).

**Files:**
- `frontend/src/features/quotes/ui/procurement-step/invoice-card.tsx:826` — где рендерятся `pickup_location` chip + supplier/customer chips
- Use existing `<Tooltip>` from `frontend/src/components/ui/tooltip.tsx` (shadcn)

**Acceptance criteria:**
- Truncated chip shows full name on hover (Tooltip with delay 200-300ms)
- Не truncated chip — без tooltip (избегаем шум)
- dom test: render chip with truncated content, assert `title` or `aria-describedby`

---

## Track D — detailed spec

**Goal:** `/customs/declarations` не должен логировать React hydration mismatch error #418.

**Approach:**
- grep `customs/declarations` page in `frontend/src/app/(app)/...`
- Common причины: timestamp formatted на сервере и клиенте по-разному, `Date.now()` / `Math.random()` в render, или `useId` усиленно
- Fix: либо `useEffect` для client-only логики, либо `suppressHydrationWarning` где это безопасно

**Acceptance criteria:**
- Console на `/customs/declarations` чистый
- Page renders the same layout as before

---

## Track E — detailed spec

**Goal:** В таблице производительности логистов колонка «Логист» показывает ФИО, не UUID.

**Approach:**
- grep страницы Логистов / production stats — likely `app/(app)/workspace/logistics/...` или `app/(app)/admin/...`
- Проверить query — если возвращает только `assigned_user_id`, добавить FK join к `kvota.users` для `full_name`
- Render `users.full_name` (или email fallback)

**Acceptance criteria:**
- ФИО видно вместо `96d797ee`
- При отсутствии user (deleted/unknown) — fallback на «Неизвестный логист» (или `—`)

---

## Post-batch communication to tester

After PRs ship, send tester:

> ✅ Re-test plz: РОП #24 (Q-202604-0017 transition), РОП Cust #1 (subordinate customer profiles), МОЗ #94 (header truncation теперь с tooltip), СтМоз C3 (dropdown — все клиенты активны, не баг), МОЗ #93 (modal не воспроизводится; запиши видео если увидишь)
> ✅ By design (закрыто): СтМоз C9 / Q6 — финансовые колонки скрыты для ролей закупка/логистика/таможня, поскольку они вычисляются после procurement-стадии
> ⚠️ Out of scope this sprint: РОЛ Тест 07 — нужен валидный логин head_of_logistics, `aliev.kemran` not provisioned. Используем `sidorov.a` как backup для логистики

---

## Risk register

- **Migration on `kvota.quotes` UPDATE** (Track A) — if existing RLS uses `USING TRUE`, need to convert to per-column policy via `WITH CHECK`. Postgres does not natively support per-column RLS — may need a trigger or a write-through view. **Fallback:** wrap mutation in Python `/api/quotes/{id}/contact` PATCH endpoint with role allowlist (per api-first.md), bypass direct Supabase write.
- **Track B helper conflict** — if existing role helpers in `roles.ts` already have similar predicates (e.g., `isProcurementOnly`), avoid duplicate logic.
- **Bonus tracks D/E** — may discover larger underlying issues. Time-box; if either takes more than allotted, split out as follow-up PR.
