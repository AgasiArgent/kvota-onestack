# Wave 2 — After-Compact Prompt (paste into new session 2026-05-29)

Wave 2 of Testing 2 Round 5 Phase 3. All 4 calc-step fixes from 2026-05-28 (PR #271/#272/#273/#274) are shipped + verified. KP totals diff vs Excel ≤0.003% on Q-202605-0014.

## Locked product decisions

| Row | Decision |
|---|---|
| **36 price source** | МОП-selected КПП (`included_in_calc=true`) |
| **36 currency** | Supplier-local (USD/CNY/EUR) + tooltip with KP-currency equivalent |
| **48a layout** | Replace supplier rows in PR #244 info card with per-segment cost+time |
| **48b picker** | Only seller_company. No auto-recalc — show hint to recalculate. Source = `kvota.seller_companies` |

## Open question to confirm tomorrow

- Row 48b scope: visible to ALL calc-step roles (sales/МОП/МОЗ/head_of_sales) OR МОП-only?

## After-compact prompt (paste verbatim)

```
/lean-tdd skip-init

WORKFLOW: Testing 2 Round 5 — Phase 3 Wave 2 (calc-step UX improvements).

CONTEXT (from 2026-05-28 session — calc family fully resolved):
- PR #271/#272/#273/#274 all shipped + verified. Q-202605-0014 calc 200 OK, KP totals diff vs Excel ≤0.003%.
- Memory notes auto-loaded: project_phase_5cd6b_consumer_drift_family, feedback_agent_base_staleness_rapid_pr, feedback_stash_three_strikes.
- Wave 1 (Rows 81/89/84') still smoke-verified.
- Latest migration: m332. NO new migrations for Wave 2.

WAVE 2 SCOPE — 3 parallel agents (Rows 36, 48a, 48b):

═══════════════════════════════════════════════════════
Row 36 — Цена/Сумма columns on composition-picker items table
═══════════════════════════════════════════════════════
DECISIONS (locked):
- Price source: МОП-selected КПП (included_in_calc=true from Row 90).
- Currency: supplier-local (USD/CNY/EUR) + tooltip with KP-currency equivalent. Historical FX on КПП date (same pattern as Row 84').
- Empty state: "—" if no КПП selected.
- Сумма = unit_price × quantity (in supplier-local currency).

LOCATION: frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx

═══════════════════════════════════════════════════════
Row 48a — Per-segment cost+time on calc step info card
═══════════════════════════════════════════════════════
DECISIONS (locked):
- Source: kvota.logistics_route_segments — main_cost_rub + transit_days (agent verifies exact column names via \d).
- Placement: REPLACE existing supplier rows in PR #244's info card. Same card, swap invoice-per-row → segment-per-row.
- Format: One row per segment: [segment label] [cost ₽] [transit_days дн]. Hide supplier name.

LOCATION: PR #244's info card on calc step (find via grep for the component).

═══════════════════════════════════════════════════════
Row 48b — Seller_company picker on calc step
═══════════════════════════════════════════════════════
DECISIONS (locked):
- Scope: ONLY seller_company (юр.лицо) picker. NOT bank account, NOT incoterms, NOT payment terms.
- Data source: existing kvota.seller_companies table. Need GET /api/seller-companies (org-scoped).
- NO AUTO-RECALC. After change: show banner/hint "Изменён продавец — нажмите Пересчитать чтобы применить новую ставку НДС". User confirms manually to avoid misclick iterations.
- Placement: calc step, near info card (other quote-level controls).
- Backend: PATCH /api/quotes/{id} accepting seller_company_id change.
- TBD with user before dispatch: visible to all calc-step roles, or МОП-only?

YESTERDAY'S RELATED FIX: PR #274 made calc resolve seller_company from quote.seller_company_id automatically. So changing seller_company_id + clicking Пересчитать flows the new value correctly into engine + Excel.

═══════════════════════════════════════════════════════

CRITICAL CONSTRAINTS:
- Local main locked in onestack-customs-phase1 — branches via `git checkout -b <br> origin/main`
- gh pr create ALWAYS --head <branch> --base main
- LOCKED: calculation_engine.py / calculation_models.py / calculation_mapper.py
- 90s between merges OR `|| true` for cosmetic local-branch-delete error
- BEFORE dispatching back-to-back agents: `git fetch origin main` in parent worktree (per feedback_agent_base_staleness_rapid_pr — PR #274 incident yesterday)
- Stash discipline: POSITIVE alternatives only (`ruff check $(git diff --name-only HEAD)`, `git show HEAD:<file>`). 3 consecutive agents violated prohibition framing yesterday — build positive alternatives into every dev prompt.
- Co-author: Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
- Admin: admin@test.kvota.ru / Mb2026Beta!  МОП: anatoliy.e@masterbearing.ru / Mb2026Beta!
- Latest migration: m332.

KNOWN STATE FROM YESTERDAY:
- Q-202605-0014's invoice_items have synthetic data (country=Китай, weight=10kg, customs_code=8418300000, base_price_vat=purchase_price_original). Left in place from validation experiments. Reset if tester reports issues.
- Bug A (logistics allocation engine vs Excel) and Bug B2 (financing fields not persisted to summary) — deferred, out of scope for Wave 2.

DISPATCH PLAN:
STEP 1: Quick sanity check — confirm with user the locked decisions still apply + answer the Row 48b role-scope question above.
STEP 2: Dispatch 3 parallel agents (Row 36, Row 48a, Row 48b) with isolation:worktree.
STEP 3: Review + sequential merge (90s pause, || true) + browser smoke per row.
STEP 4 (after all 3): Тестер ping if tester is unblocked on anything.
```

## How to use tomorrow

1. Open new Claude Code session in `~/workspace/tech/projects/kvota/onestack`
2. Paste the prompt block above
3. Memory notes auto-load (Phase 5cd6b consumer-drift, agent base-staleness, stash three-strikes)
4. Claude asks the Row 48b scope question
5. Then dispatches 3 parallel agents
