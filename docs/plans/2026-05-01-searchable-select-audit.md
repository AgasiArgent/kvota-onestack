# Searchable-Select Audit — 2026-05-01

## Why this doc

CLAUDE.md "UI Standards" section (re-confirmed 2026-05-01 after МОЗ Тест fail items #76, #78) mandates that **every entity-picker dropdown in the app must be searchable**. Plain shadcn `<Select>` is forbidden for entity pickers because it (a) shows raw UUIDs during SSR before the option labels hydrate and (b) offers no filter, which is unusable for any list ≥ 10 items.

This doc inventories every `<Select>` (and a few native `<select>`) in `frontend/src/`, classifies each as **entity-picker** (must be searchable) or **simple-choice** (small fixed enum, can stay), and tracks migration status.

## Canonical searchable pattern

The reference implementation is `features/customers/ui/tab-assignees.tsx` — Input + filtered list + click-outside-to-close + "Не найдено" empty state, zero new dependencies. After this PR there's a second canonical example: `features/admin-routing/ui/user-select.tsx` (a reusable component used by 6+ admin-routing files).

```
+ Input with Search icon prefix
+ value + onValueChange API matches the old <Select>
+ filteredUsers = users.filter(name.toLowerCase().includes(search.toLowerCase()))
+ click outside via useEffect mousedown listener
+ "Не найдено" branch for empty filtered set
```

## Verdict table

Source: Explore agent inventory 2026-05-01 + manual sample-verification on the foundation files. Verdicts marked ⚠ are best-guess from the agent — verify before migration.

### entity-picker (must be searchable)

| File | Status |
|---|---|
| `features/admin-routing/ui/user-select.tsx` | ✅ migrated (this PR) — reusable component used by below |
| `features/admin-routing/ui/groups-tab.tsx` | inherited via UserSelect |
| `features/admin-routing/ui/group-assignment-dialog.tsx` | inherited via UserSelect |
| `features/admin-routing/ui/brand-assignment-dialog.tsx` | inherited via UserSelect |
| `features/admin-routing/ui/tender-step-dialog.tsx` | inherited via UserSelect |
| `features/admin-routing/ui/unassigned-tab.tsx` | inherited via UserSelect |
| `features/admin-routing/ui/brands-tab.tsx` | inherited via UserSelect |
| `features/procurement-distribution/ui/quote-brand-card.tsx` | inherited via UserSelect (uses its own UserSelect copy or imports the reusable — verify) |
| `features/procurement-kanban/ui/assign-popover.tsx` | ⚠ likely entity-picker (procurement user assignment) — verify next |
| `features/suppliers/ui/tab-assignees.tsx` | ⚠ similar pattern to customers/tab-assignees — verify if it uses Select or already searchable |
| `features/route-constructor/ui/segment-details-panel.tsx` | ⚠ location picker with grouping — needs custom searchable with group headers |
| `features/customers/ui/customers-table.tsx` | ⚠ verify; likely a manager filter — is the manager set big? |
| `features/customers/ui/contact-form-modal.tsx` | ⚠ verify; contact role / type — may be simple-choice |
| `features/customers/ui/contract-form-modal.tsx` | ⚠ verify; contract type — likely simple-choice (≤7 options) |
| `features/customers/ui/call-form-modal.tsx` | ⚠ verify |
| `features/plan-fact/ui/plan-fact-create-dialog.tsx` | ⚠ verify |
| `features/plan-fact/ui/plan-fact-sheet.tsx` | ⚠ verify |
| `features/quotes/ui/create-quote-dialog.tsx` | ⚠ multi-entity picker; high traffic — top priority for next batch |
| `features/quotes/ui/calculation-step/calculation-form.tsx` | ⚠ verify |
| `features/quotes/ui/specification-step/specification-step.tsx` | ⚠ verify |
| `features/quotes/ui/context-panel/context-panel.tsx` | ⚠ verify |
| `features/quotes/ui/documents-step/promote-document-dialog.tsx` | ⚠ verify; user assignment for promotion |
| `features/admin-users/ui/create-user-dialog.tsx` | ⚠ sales group + department — bounded, may be simple-choice in practice |
| `features/locations/ui/locations-page.tsx` | ⚠ location type may be simple-choice |
| `shared/ui/data-table/data-table.tsx` | ⚠ generic; the column-filter Select may stay simple-choice for status enums |

### simple-choice (can stay as plain `<Select>`)

| File | Reason |
|---|---|
| `features/admin-feedback/ui/feedback-detail.tsx` | status enum (new / in_progress / resolved) |
| `features/admin-feedback/ui/feedback-list.tsx` | status + type filters |
| `features/positions/ui/positions-table.tsx` | dept / position type |
| `features/currency-invoices/ui/ci-detail.tsx` | currency + payment-method enums |
| `features/quotes/ui/documents-step/document-upload.tsx` | document type (≤7 options) |
| `features/quotes/ui/procurement-step/letter-draft-composer.tsx` | RU / EN language toggle (2 options) |

## Migration plan

Wave 4 of the МОЗ Тест batch ships only the foundation `UserSelect`. The audit catches the rest of the inventory. Next migration batch (P3) should:

1. **Verify** all ⚠ rows — open each file, confirm the picker IS for an entity (not a fixed enum). Update verdicts.
2. **Migrate** the verified entity-pickers in groups by feature (customers / quotes / plan-fact). One PR per group keeps blast radius small.
3. **Add a lint rule** (eslint custom or grep CI check) banning `import { Select } from "@/components/ui/select"` in feature files matching glob `**/ui/*-picker.tsx`, `**/ui/*-select.tsx`. The shared simple-choice usages stay allowed via inline disable comments.

## Out of scope

- Native `<select>` elements (HTML element, not shadcn) — there are a handful in the codebase. Pre-existing pattern; the rule applies to new code. Don't migrate just for parity.
- `@/shared/ui/geo/CountryCombobox` — already searchable (Combobox by name).
- `@/shared/ui/geo/CityAutocomplete` — already searchable (HERE-backed).
