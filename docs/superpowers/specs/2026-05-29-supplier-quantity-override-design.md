# Supplier-quantity override — shown everywhere

**Date:** 2026-05-29
**Status:** Design (approved in brainstorming; pending written-spec review)
**Supersedes:** Testing 2 Row 85 narrow round-up (PR #285 + #287, already shipped) — this widens and **reverses** part of it.

---

## 1. Problem

Procurement records, per supplier invoice line, a quantity the supplier will actually ship. Today the field `invoice_items.minimum_order_quantity` is treated as a **minimum** and only adjusts the calc quantity **upward** (`max(ordered, MOQ)`, PR #285), and only the calc engine + composition picker honour it. Every other surface (calc-results table, logistics, customs, KP PDF, specification/contract/invoice exports, XLS) still shows the **ordered** quantity, so the same line shows different quantities in different places.

Reality is two-sided: sometimes the supplier's minimum is **higher** than our order (we must buy more), sometimes he has **less** in stock than our order (we get fewer). In both cases the order must be adjusted to what the supplier will ship.

## 2. Decision (locked in brainstorming)

1. **Override, both directions.** The field, **if set (non-null, non-zero)**, *replaces* the ordered quantity in every downstream calc and display — up or down. Empty/zero → use the ordered quantity.
   - `effective_quantity = COALESCE(NULLIF(supplier_qty, 0), ordered_quantity)`
   - This **reverses** PR #285's `max(...)`: the shared helpers `effective_calc_quantity` (Python) and `effectiveQuantity` (TS) flip from *max* to *override*.
2. **Repurpose the existing field** — no second column. `invoice_items.minimum_order_quantity` is renamed **on the UI** to **«Кол-во поставщика»** ("supplier quantity"). The DB column name stays `minimum_order_quantity` (renaming a column is a needless breaking migration); only its semantics + UI label change.
3. **Shown everywhere.** Every surface that displays a per-item quantity shows the **effective** quantity — except the procurement entry grid, which shows both the ordered qty and the supplier-qty input (it is the entry point).
4. **ALTA is out of scope** — it is being removed separately. Customs reads `effective_quantity` like every other surface; no ALTA-declaration special-casing.

## 3. Single source of truth (architecture)

To keep ~12 read-sites from drifting (the KP dual renderer already drifted once), the effective value is defined **once**:

- **Migration:** add a STORED generated column
  ```sql
  ALTER TABLE kvota.invoice_items
    ADD COLUMN effective_quantity INTEGER
    GENERATED ALWAYS AS (COALESCE(NULLIF(minimum_order_quantity, 0), quantity)) STORED;
  ```
  (Sequential migration number, applied via `scripts/apply-migrations.sh`; wrap in BEGIN/COMMIT.)
- **Backend:** `composition_service` (`_build_calc_item`, `_legacy_shape`, `get_composed_items`, `get_composition_view`) carries the DB `effective_quantity` and emits it as the calc quantity for all composed-item consumers. `build_calculation_inputs` reads that `effective_quantity` directly (it no longer calls the helper to floor `quantity`). The shared helper `effective_calc_quantity` is **kept** but its formula flips to the override rule (`COALESCE(NULLIF(supplier_qty,0), ordered)`) — it remains the single in-app definition for surfaces that hold both numbers and compute it client-side (the picker, the calc-results join fallback).
- **`quote_items`-direct surfaces** (calc-results table, `specification_export`, `contract_spec_export`) join to the **selected** invoice_item (`quote_items.composition_selected_invoice_id` → coverage → invoice_item) and read its `effective_quantity`.
- **Shared display helpers** keep the same formula for surfaces that already hold both numbers (override, not max), so SSR/JS and Python agree.

The DB column guarantees the *value* is identical everywhere; each surface still chooses to read it (a mechanical, testable change).

## 4. Surface inventory

| Stage | Surface | Source today | Change |
|---|---|---|---|
| Calc | Composition picker | composition view + field | ✅ rework hint copy (built) |
| Calc | `build_calculation_inputs` (engine input) | composed item | flip helper → override; read `effective_quantity` |
| Calc | Calc-results table (`calculation-results.tsx`) | `quote_items.quantity` | join selected invoice_item → effective |
| Procurement | Entry grid (`procurement-handsontable.tsx`) | invoice_items | rename column → «Кол-во поставщика» + explainer tooltip; keep ordered «Кол-во» alongside |
| Logistics | `invoice-cargo-summary.tsx` | invoice_items/cargo | show effective |
| Customs | `customs-handsontable` / `customs-views` / `customs-columns` | invoice/quote items | show effective |
| Customer | KP PDF — Python (`kp_export.py`) | spec/quote items | show effective |
| Customer | KP PDF — React (`widgets/kp-preview/*`) | kp data | show effective |
| Customer | Specification export (`specification_export.py`) | `quote_items` direct | join → effective |
| Customer | Contract export (`contract_spec_export.py`) | `quote_items` direct | join → effective |
| Customer | Invoice / currency-invoice export (`invoice_export.py`, `currency_invoice_service.py`) | composed/items | read effective |
| Other | XLS export, `deal_data_service`, `quote_version_service` snapshot | composed/quote items | read effective |

(Customs *declaration* parsing — `customs_declaration_service` — is ALTA-derived and **excluded** per §2.4.)

## 5. UI copy

- **Column label** (procurement grid + anywhere the input shows): **«Кол-во поставщика»**.
- **Explainer tooltip** (informational, on the renamed column): *"Если задано, переопределяет заказанное кол-во в расчёте — укажите, сколько поставщик реально отгрузит."*
- **Picker hint** — replace the now-wrong «мин. заказ N» with a neutral, two-sided label, e.g. **«кол-во поставщика: N (заказано M)»**, shown whenever the supplier qty differs from the ordered qty (either direction).
- **`isMoqViolation`** (the procurement soft-warning that fired when ordered < minimum) is **retired** — under override semantics a smaller supplier qty is a deliberate adjustment, not a violation. The two-sided "differs from order" signal is conveyed by the label above, not a warning.

## 6. Existing-data impact (decision required during rollout)

Audit of `invoice_items` on prod (2026-05-29): **69** rows have a value set →
- **25 flip up** (supplier qty > ordered) — already the live behaviour.
- **25 equal** — no change.
- **19 flip down** (supplier qty < ordered) — **NEW**: these orders/calcs reduce. They were entered under "minimum order" semantics, so some may be stale true-minimums rather than intentional supplier-qty caps.
- **2 zero** — treated as unset (`NULLIF`), no effect.

**Action:** before/at rollout, list the 19 downward-flip rows for the team to confirm (keep as intentional supplier qty, or clear). Totals shift on every affected quote — flag PO/testers (consistent with the original Row 85 calc-impact note).

## 7. Out of scope

- ALTA functionality (being removed separately).
- Renaming the DB column (UI-only rename).
- Customs declaration document parsing.

## 8. Testing

- **Helper unit tests** (Python + TS): override formula incl. null/0/down/up/equal cases (replaces the current max-based assertions).
- **Generated-column migration test**: column computes `COALESCE(NULLIF(moq,0), qty)` for up/down/null/zero rows.
- **`build_calculation_inputs` regression**: effective qty reaches the engine for up *and* down; null → ordered.
- **Per-surface tests**: each surface renders the effective qty (SSR/dom tests for React; render tests for Python exports; golden master stays green — no golden fixture sets the field).
- **Browser smoke per stage** on `app.kvotaflow.ru` after each surface ships.

## 9. Rollout (staged, not one mega-PR)

1. **Foundation:** migration (generated column) + flip the shared helpers (override) + `build_calculation_inputs`/composition emit `effective_quantity`. (Corrects #285 semantics.)
2. **Calc surfaces:** picker hint + calc-results table.
3. **Internal:** logistics cargo + customs grid.
4. **Customer docs:** KP PDF (Python + React together — avoid renderer drift), then specification / contract / invoice / currency-invoice exports + XLS.
5. **Procurement UI:** rename column → «Кол-во поставщика» + explainer tooltip.
6. **Existing-data review** (the 19 downward flips).

Each stage: TDD + adversarial review (no commit without PASS) → CI green → deploy → browser smoke.

## 10. Risks

- **Behaviour reversal** for the 19 downward-flip rows — surfaced in §6; needs team confirmation.
- **Renderer drift** (KP Python vs React) — mitigated by the single DB-sourced value + shipping both KP renderers in one PR.
- **`quote_items`-direct exports** need a composition join they don't do today — adds a query per export; verify FK path (`composition_selected_invoice_id`).
- **Schema-drift lint** must pass for the new column (`tools/check_select_columns.py`) — regenerate `database.types.ts` after the migration.
