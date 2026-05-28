# Testing 2 — Round 5 Phase 3 Plan

**Date:** 2026-05-27
**Prerequisites:** Phase 1+2 complete (6 PRs #260–#265 merged, m331+m332 live).
**Source rows:** Bucket A extends (36, 48) + new work deferred from Phase 2 (85, 86, 81, 89) + follow-up (84-USD).

---

## Item Catalog (sized + classified)

| # | Row | Title | Effort | Risk | Product decisions needed |
|---|-----|-------|--------|------|--------------------------|
| 1 | **85** | MOQ propagation through calc/customs (P0 — deferred from Phase 1) | L | **HIGH** (calc engine LOCKED) | Where MOQ entered? Display vs participate-in-math? Round-up or block? |
| 2 | **87'** | Frontend visualisation polish for «Исключено» rows (post-#262 follow-up) | S | low | None — just visual polish if tester pushes back |
| 3 | **36** | Items table Цена/Сумма в валюте КП columns | M | low | Source: alternatives[i].price? After supplier picked? |
| 4 | **48** | Calc step per-segment cost + hide supplier + Компания picker | L | med | Big UX redesign — needs mockup before coding |
| 5 | **86** | Customs certificate modal redesign | L | med | What does "полностью переделать" mean — full UX spec needed |
| 6 | **84'** | Сумма КПП USD conversion (follow-up #146) | S | low | FX rate source: exchange_rates table on KPP date? Live rate? |
| 7 | **81** | Visible «Добавить» button for logistics extras | XS | low | None |
| 8 | **89** | KPP deadline cell in КПП body | S | low | Editable or display-only? Source field name? |

**Total estimated effort:** L+S+M+L+L+S+XS+S ≈ 6–8 dev-agent slots over 2–3 dispatch waves.

---

## Recommended dispatch sequence

### Wave 1 — quick wins (parallel, low risk)
Dispatch 3 agents in parallel (isolation:worktree):
- **Row 81** — visible Add button (XS, polish)
- **Row 89** — KPP deadline cell (S, polish)
- **Row 84'** — USD conversion (S, FX rates)

**Why first:** no product ambiguity, no shared files, fast to merge. Builds momentum.

### Wave 2 — medium scope (parallel)
Dispatch 2 agents in parallel:
- **Row 36** — price/sum columns on composition-picker
- **Row 48 simplified** — per-segment cost only (defer company picker)

**Why second:** Both touch calc-step UI. Row 90 (#265) added КПП selection there — risk of conflict but agents work in isolated worktrees.

### Wave 3 — heavy redesign (sequential)
- **Row 86** — customs cert modal redesign (needs UX spec first)
- **Row 85** — MOQ propagation (needs DB schema investigation first — careful with calc engine LOCK)

**Why last:** Both need product clarification before agent dispatch. Spec-first approach.

---

## Product decisions needed BEFORE Wave 1

### Row 84' USD conversion
- FX rate source: `kvota.exchange_rates` (already exists)
- Lookup key: use the KPP's `created_at` to find historical rate? Or current rate?
- If KPP currency = USD already → no conversion
- Display: rounded to nearest USD? Show 2 decimals?

### Row 89 — KPP deadline placement
- "Тело КПП" = procurement step KPP detail modal? Inline on kanban card?
- Source field: probably `procurement_requests.deadline` or `quotes.deadline_date` — verify
- Editable or read-only display?

### Row 81 — Logistics extras Add button
- Current state: button exists but tester says it's not visible/prominent
- Solution: bigger button, brand color, place near the section header
- No ambiguity — agent can decide visual treatment from design-system.md

---

## Product decisions needed BEFORE Wave 2

### Row 36 — Цена / Сумма в валюте КП columns
- WHERE to add: composition-picker.tsx items table (Phase 1 lookup confirmed only Позиция/Кол-во/Поставщики columns)
- Цена в валюте КП = supplier-quoted unit_price (which alternative? selected one? or show range?)
- Сумма в валюте КП = unit_price × quantity (per selected alternative)
- Display when no supplier selected: "—" or hide?

### Row 48 — Calc step segments + company picker
Tester comment fully: «Сроки и стоимость на каждый сегмент, но не отражать имя поставщика. Компания и условия: выбор нашей организации»
- **Per-segment cost+time**: each `logistics_route_segments` row → show its `main_cost_rub` + transit_days
- **Hide supplier name**: in our shipped info card (#244) we showed which supplier shipped each invoice — tester wants this hidden, show only cost+time per segment
- **Company picker**: select which Юр.лицо (our company) the deal goes through — affects which tax regime + bank account → big scope
- **Recommended**: split into 2 PRs. PR-A: segments + hide supplier. PR-B: company picker (needs schema + workflow integration).

---

## Product decisions needed BEFORE Wave 3

### Row 86 — Customs certificate modal
Tester comment: «Полностью переделать модальное окно. Нет возможности редактирования. Автор - пишет id. Расчет по позициям непонятный»
- **Edit functionality**: currently only create — add Edit button on each row
- **Author display**: replace `user_id` with `user_profiles.full_name`
- **Position calc UX**: show how cert cost distributes across items — currently unclear. Mockup needed?
- **Recommended**: ask tester for screenshot of current modal + sketch of desired layout. Or pair with designer agent.

### Row 85 — MOQ propagation
Tester comment: «При введении MOQ — он отображается и калькулируется на следующих этапах»
- **Where entered**: in procurement step? customs? new field?
- **Behaviour**: if request quantity < MOQ, what happens?
  - Option A: round up to MOQ on calc → final price/quantity changes
  - Option B: show warning «MOQ exceeded — fix in КПП» → block calc
  - Option C: pass MOQ through as info, display on customs/logistics — no calc impact
- **CALC ENGINE LOCKED**: any MOQ logic that affects calc must be in `build_calculation_inputs()` adaptation, NOT in engine itself
- **Recommended**: schema investigation first → find MOQ field → understand current state → propose 3 options to user → dispatch.

---

## Bucket A — Refresh ping (no PR work)

**Ping tester after Wave 1 deploys:**
- Row 58 (logistics scroll, fixed in #248): ask Денис Ctrl+Shift+R + retest «Шаблон маршрута» click
- Row 83 (procurement role gate, fixed in #254): ask Денис to retest after hard refresh — should now see completed procurement quotes as РОЗ/СтМОЗ/МОЗ

If both still red after refresh → re-investigate. Likely cache.

---

## Critical operational reminders

- Local main locked in worktree `onestack-customs-phase1` → branches must be `git checkout -b <br> origin/main`
- `gh pr create` always `--head <branch> --base main`
- LOCKED: `calculation_engine.py` / `calculation_models.py` / `calculation_mapper.py` — Row 85 must adapt input only
- Developer agents use `isolation:"worktree"` + path-discipline block
- Stash discipline: NEW positive guidance per `feedback_lint_baseline_stash_temptation`
- Migrations: SSH → `cd /root/onestack && git pull && bash scripts/apply-migrations.sh` (or per `reference_expand_contract_migration_workflow` for schema-drift cases)
- 90s between merges OR `gh pr merge --auto` (intermittent — fallback to direct merge)
- Latest applied migration: **m332**. Next allocations: m333, m334...

---

## Open question for user

**Are we doing Phase 3 in THIS session or next?** Phase 3 ≈ 6–8 PRs across 3 waves. Context already at ~600K tokens; `/compact` is essentially mandatory before Wave 1 dispatch if continuing here.
