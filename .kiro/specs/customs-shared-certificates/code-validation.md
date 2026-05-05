# Code Validation Report — Phase B Pre-Design

**Date:** 2026-05-04
**Validator:** deep code reads + targeted greps against current codebase (post Phase A, last commit c1b45017).
**Validates:** `gap-analysis.md` (161 lines, 2026-05-04).

---

## Summary

- **Decision 1 (`customs_value_rub` as canonical column) — REFUTED.** `customs_value_rub` is **NOT a column on `quote_items`**. It is a *derived* `Decimal` value computed in `services/calculation_helpers.py:_customs_value_in_rub()` from `purchase_price_original × quantity` (then converted to RUB via `convert_amount`). The only DB columns named `customs_value_rub` live on `kvota.customs_declaration_items` / `kvota.customs_declarations` (migration 191) — a completely separate entity. The user's "lock `customs_value_rub` as canonical input" must be re-framed as **"call the helper `_customs_value_in_rub(item, quote_currency)` (or refactor it into `services/cost_split.py` as a public utility) — there is no column to read."** This is the single most consequential correction.
- **Decision 2 (Migrate-then-drop old `customs_*_expenses`) — VALID, with concrete mapping.** Tables exist (293), have working write paths (`api/customs.py:605-797`), and live UI (`<QuoteCustomsExpenses />`, `<ItemCustomsExpenses />`). Schema mapping to `quote_certificates` is straightforward (label, amount_rub, notes, created_by). Migrate-then-drop is safe; recommend two-step (306 backfill + UI swap, 307 drop after verification — but if user prefers one-shot atomic, that also works since old UI is being deleted in same PR).
- **Decision 3 (shadcn Button + design tokens) — VALID.** Zero `.btn` BEM matches in `frontend/src/`. Project standard is shadcn `<Button variant="…">` from `frontend/src/components/ui/button.tsx`, with full design-tokens system in `design-system.md` (Slate & Copper palette, semantic CSS variables).
- **Bonus correction:** `CUSTOMS_AVAILABLE_COLUMNS` has **24** entries (not 18). Column id list confirmed below — REQ-11 view definitions must reference these exact ids.
- **All 7 requested files read in full.** No new blockers beyond the `customs_value_rub` framing issue (which the user's locked decision already half-anticipated).

---

## Decision validation

### Decision 1: `customs_value_rub` as canonical cost-split input

- **Verified status:** **NOT a `quote_items` column.** It is a function parameter / derived value.
- **Where it actually lives:**
  - **As a function argument in calc:** `services/customs_calc.py:172, 206, 247, 277, 303, 396, 418, 487, 500` — pure-function parameter typed `Decimal`.
  - **As a derived Decimal in calc-helpers:** `services/calculation_helpers.py:407` calls `_customs_value_in_rub(item, quote_currency, convert_amount)`. Definition at `calculation_helpers.py:433-460`:
    ```python
    base_price = safe_decimal(item.get("purchase_price_original") or item.get("base_price_vat"))
    quantity   = safe_decimal(item.get("quantity") or 1)
    src_currency = item.get("purchase_currency") or item.get("currency_of_base_price") or quote_currency
    total = base_price * quantity
    return total if src_currency == "RUB" else convert_amount(total, src_currency, "RUB")
    ```
  - **Item shape:** the `item` dict passed in is **NOT a `quote_items` row** — it is an aggregated payload from `invoice_items` where `purchase_price_original` and `purchase_currency` actually live (`database.types.ts:1387-1388`, `invoice_items` table).
  - **As a column** (different entity): `kvota.customs_declaration_items.customs_value_rub` (migration 191:58) and `kvota.customs_declarations.total_customs_value_rub` (191:19). Used only in customs-declaration ingest from XML — unrelated to quote-items cost split.
- **Currency confirmation:** RUB. Always converted via `convert_amount(total, src_currency, "RUB")` (helpers:459). Calc-engine input contract treats it as RUB.
- **Defensive frontend access:** `customs-item-dialog.tsx:1335-1342` does `row.customs_value_rub ?? row.customs_value ?? proforma_amount_excl_vat` via a `Record<string, unknown>` cast — pure escape hatch; **neither field exists on `quote_items`**, so this always falls through to `proforma_amount_excl_vat` today. The fallback is approximate (proforma is in original currency, not RUB).
- **Risk if Phase B copies REQ wording verbatim:** every reference to "read `customs_value_rub` column" will silently fail at PostgREST (column doesn't exist), or worse: the TS escape hatch makes runtime read return `undefined` and Phase B sums $0 share-cost.
- **Recommended Phase B contract:**
  1. Refactor `_customs_value_in_rub` from `calculation_helpers.py:433` into `services/cost_split.py` as a public `customs_value_rub_for_item(item: dict, quote_currency: str) -> Decimal` (or import it directly from calc-helpers — calc-engine module ban does not apply because helpers is a wrapper).
  2. Backend `POST /api/customs/certificates/{id}/items` handler resolves each `quote_item_id` → joined `invoice_items` payload (already established pattern in customs.py and `useSupplierByQuoteItemId` in customs-step.tsx:39-123) → calls helper → splits by ratio.
  3. Frontend `cost-split.ts` operates on already-resolved `cost_rub: number` values (passed as input from server) — no client-side currency conversion. Server pre-resolves and sends RUB amounts down.
  4. Add a backend parity test: `attached_items[].share_rub` sum == cert `cost_rub` (not == calc-engine import_tariff base — they share the SAME helper, so parity is mechanical).

### Decision 2: Migrate-then-drop `customs_*_expenses`

#### `customs_item_expenses` schema (migration 293:55-103)

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | `gen_random_uuid()` |
| `quote_item_id` | `UUID NOT NULL` | FK `→ quote_items(id) ON DELETE CASCADE` |
| `label` | `TEXT NOT NULL` | CHECK `length(trim(label)) > 0` |
| `amount_rub` | `DECIMAL(15,2) NOT NULL DEFAULT 0` | CHECK `>= 0` |
| `notes` | `TEXT NULL` | |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `created_by` | `UUID NULL` | FK `→ auth.users(id)` |

Index: `idx_customs_item_expenses_quote_item ON (quote_item_id)`. RLS: select = org-membership join; mutate = `r.slug IN ('customs','head_of_customs','admin')`.

#### `customs_quote_expenses` schema (migration 293:105-152)

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK` | `gen_random_uuid()` |
| `quote_id` | `UUID NOT NULL` | FK `→ quotes(id) ON DELETE CASCADE` |
| `label` | `TEXT NOT NULL` | CHECK length > 0 |
| `amount_rub` | `DECIMAL(15,2) NOT NULL DEFAULT 0` | CHECK >= 0 |
| `notes` | `TEXT NULL` | |
| `created_at` | `TIMESTAMPTZ` | default now() |
| `created_by` | `UUID NULL` | FK `→ auth.users(id)` |

Index: `idx_customs_quote_expenses_quote ON (quote_id)`. RLS pattern identical to per-item.

#### Mapping to `quote_certificates` (Phase B target)

| Old column | New column | Notes |
|---|---|---|
| `customs_item_expenses.label` | `quote_certificates.name` (or new `type`?) | "Test report", "Translation" — these are NOT certificates per se, they're "Custom expenses". REQ-6 introduces an `is_custom_expense` flag — perfect fit. |
| `customs_item_expenses.amount_rub` | `quote_certificates.cost_rub` | direct rename (DECIMAL(15,2) → NUMERIC(15,2) — same). |
| `customs_item_expenses.notes` | `quote_certificates.notes` | same name. |
| `customs_item_expenses.quote_item_id` | `quote_certificate_items.quote_item_id` (M2M) | each row → 1 cert + 1 attachment row, ratio=1.0 by default (single-item attachment). |
| `customs_item_expenses.created_at` / `created_by` | `quote_certificates.created_at` / `created_by` | direct copy. |
| `customs_quote_expenses.quote_id` | derive `organization_id` via JOIN, attach to ALL items in quote | one-to-many fan-out: 1 quote_expense row → 1 cert + N attachment rows (one per quote_item, equal-ratio split). |
| `customs_quote_expenses.label` / `amount_rub` / `notes` / etc. | same fields on `quote_certificates` | with `is_custom_expense=true`, `expiry_date=null`. |

**Existing data write paths** (verified):
- `api/customs.py:605-671` POST item expense
- `api/customs.py:704-769` POST quote expense
- `frontend/src/features/quotes/ui/customs-step/quote-customs-expenses.tsx` (187 lines) — full CRUD UI in production
- `frontend/src/features/quotes/ui/customs-step/item-customs-expenses.tsx` (194 lines) — full CRUD UI in production

So **production data exists** (in user organizations using Phase A customs flow) — migrate-then-drop is required, not optional.

**Migration strategy recommendation:** **One atomic migration 306** that creates `quote_certificates` + `quote_certificate_items` + RLS + INSERTs from the two old tables in one transaction; `customs_*_expenses` tables get DROP TABLE in the same migration *only if* code dropping the old UI ships in the same PR (which Phase B already does per REQ-6 AC#9). One-shot is safer than two migrations because:
1. `customs_*_expenses` write-paths ship inside `api/customs.py` — same file the new `quote_certificates` write-paths land in. A single PR touches both.
2. Two-migration (expand-contract) requires keeping the old UI working between 306 and 307, which contradicts REQ-6 AC#9 (delete old sections).
3. Per project memory rule `feedback_oneshot_migrations_when_engine_locked.md`: when the surface area is small and ships atomically with code, expand-contract is unnecessary ceremony.

```sql
-- migration 306 sketch
CREATE TABLE kvota.quote_certificates ( ... );
CREATE TABLE kvota.quote_certificate_items ( ... );

-- backfill custom-expenses data
INSERT INTO kvota.quote_certificates (organization_id, quote_id, name, cost_rub, notes, is_custom_expense, ...)
SELECT q.organization_id, e.quote_id, e.label, e.amount_rub, e.notes, true, e.created_by, e.created_at
FROM kvota.customs_quote_expenses e
JOIN kvota.quotes q ON q.id = e.quote_id;

-- per-item: one cert per row, attached to 1 item
WITH ins AS (
  INSERT INTO kvota.quote_certificates (organization_id, quote_id, name, cost_rub, notes, is_custom_expense, created_by, created_at)
  SELECT q.organization_id, qi.quote_id, e.label, e.amount_rub, e.notes, true, e.created_by, e.created_at
  FROM kvota.customs_item_expenses e
  JOIN kvota.quote_items qi ON qi.id = e.quote_item_id
  JOIN kvota.quotes q ON q.id = qi.quote_id
  RETURNING id, ...
)
INSERT INTO kvota.quote_certificate_items (...) SELECT ...;

DROP TABLE kvota.customs_item_expenses;
DROP TABLE kvota.customs_quote_expenses;
```

(Final SQL goes in design phase; this is a sketch.)

### Decision 3: shadcn Button + design tokens

- **Confirmed:** zero matches for `\.btn\b|className="btn` in `frontend/src/`.
- **Existing pattern:** `frontend/src/components/ui/button.tsx` — shadcn Button. Variants in use throughout customs-step:
  - `<Button variant="outline" size="sm">` (`table-views-dropdown.tsx:105`)
  - Other variants: `default`, `secondary`, `ghost`, `destructive`, `link` (standard shadcn).
- **Design tokens reference:** `design-system.md` at repo root — comprehensive Slate & Copper palette, OKLCH-based semantic tokens (`--accent`, `--primary`, `--background`, `--card`, `--text`, `--text-muted`, `--text-subtle`, `--border`, `--border-light`, `--ring`, etc.), spacing scale, type scale, radius scale (`--radius-sm/md/lg`), button padding rules. Tokens consumed via Tailwind v4 (`bg-accent`, `text-text-muted`, `border-border-light`).
- **Note:** design-system.md states "Plus Jakarta Sans" font but old CLAUDE.md notes mention "Inter" — minor doc drift, not Phase B's concern. Phase B should reference `design-system.md` as the authority and use Tailwind tokens (e.g., `bg-accent-subtle text-accent` for the warning banner).

---

## File Reading Findings

### `migrations/261_create_user_table_views.sql` (131 lines)

- **Schema:** `(id UUID PK, user_id UUID NOT NULL FK auth.users CASCADE, table_key VARCHAR(50), name TEXT, filters JSONB DEFAULT '{}', sort VARCHAR(50), visible_columns TEXT[], is_shared BOOLEAN DEFAULT false, organization_id UUID FK organizations CASCADE, is_default BOOLEAN DEFAULT false, created_at, updated_at)`.
- **Constraints:** `chk_shared_has_org` (shared ⇒ org NOT NULL), `chk_personal_no_org` (personal ⇒ org NULL).
- **Indexes:** `uq_table_views_personal (user_id, table_key, name) WHERE NOT is_shared`; `uq_table_views_shared (organization_id, table_key, name) WHERE is_shared`; `idx_table_views_user_table (user_id, table_key) WHERE NOT is_shared`.
- **Triggers:** `enforce_single_default_view` (auto-clears other defaults), `set_updated_at`.
- **RLS:** personal owner-only ALL; shared org-member SELECT; shared owner UPDATE/DELETE/INSERT (note: line 130 comment says "Always false in initial release" — but `is_shared` IS used today; comment is stale).
- **NO `is_system` concept anywhere.** Migration uses `is_shared=true` + `organization_id` for org-shared views; there is no separate "system view" / "immutable seed" mechanism.
- **Phase B implication:** to ship 4 system views without inventing a column, options are:
  - (a) **Seed as `is_shared=true, organization_id=<each org>` rows.** Pros: works with existing RLS, dropdown groups them under "Общие". Cons: per-org seed (loop over orgs in migration), org admins can edit them via existing settings dialog (no "immutable" concept).
  - (b) **Inject as virtual non-DB rows client-side** in `customs-step.tsx` views state. Pros: truly immutable, no migration. Cons: `?customs_view=<id>` URL persistence needs synthetic IDs (e.g. `system:cert-overview`), TableViewsDropdown must distinguish virtual from real rows.
  - **Recommendation:** option (b) for Phase B simplicity. Avoids per-org seed loop and lets us skip one whole class of "what if user deletes a system view" edge cases. Synthetic IDs prefixed `system:` are easy to detect in `handleViewChange`.

### `migrations/293_customs_cleanup_and_expenses.sql` (157 lines)

- Documented in Decision 2 above.
- **Idempotent:** `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, DO-block guards on column rename.
- **RLS pattern (293):** multi-table JOIN — `quote_items → quotes → organization_members` for SELECT; `quote_items → quotes → user_roles → roles WHERE r.slug IN (...)` for mutate.
- **Note:** RLS `customs_item_expenses_org_select` uses `om.status = 'active'` filter. Phase B `quote_certificates` SELECT policy must mirror this for consistency (existing pattern — copy it).

### `migrations/304_tnved_user_choices.sql` (80 lines)

- Audit-log table for tariff choices.
- **RLS pattern (304):** **single-line JWT-based** — `organization_id = (auth.jwt() -> 'app_metadata' ->> 'organization_id')::uuid`. No JOIN to `organization_members` or `roles`.
- **Why it diverged:** Phase A's TNVED user-choices is a *write-only audit log* with org isolation only (no per-role gating — every customs role writes; every customs role reads). The simpler JWT-claim policy is sufficient because:
  1. Visibility is already gated upstream by org-membership (you can't be in an org's JWT without being a member).
  2. There are no role-specific permissions on this table — it's all-or-nothing per org.
- **Phase B implication:** Phase B `quote_certificates` is **NOT** a write-only audit log — it's a primary entity with role-based mutation rights (per REQ-1 AC#6: read = sales, customs, quote_controller, spec_controller, finance, top_manager, head_of_*, admin; write = customs, head_of_customs, admin). Therefore Phase B **must use the 293 multi-table-JOIN RLS pattern, NOT the 304 JWT-claim pattern.** Document this rationale in the 306 SQL header comment so future migrations don't copy the wrong pattern.

### `migrations/305_quote_items_customs_manual_override.sql` (33 lines)

- Adds 2 cols to `quote_items`: `customs_manual_override BOOLEAN DEFAULT FALSE`, `customs_manual_rate_payload JSONB`.
- Idempotent via `ADD COLUMN IF NOT EXISTS`.
- **Highest existing migration number is 305.** Next safe: 306. (gap-analysis was correct: collision-free.)

### `customs-step.tsx` (451 lines)

- **`<TableViewsDropdown />` rendered:** lines 383-397 (gap-analysis cited 385-390 — close enough; props span 385-395).
- **`<ItemCustomsExpenses />`:** rendered lines 410-417 (only when `selectedItem` truthy).
- **`<QuoteCustomsExpenses />`:** rendered line 419 (always when in customs step).
- **`<CustomsExpenses />`:** rendered line 421 — calc-engine variables form (different concern).
- **REQ-6 «Расходы по таможне» plug-in point:** the natural location is **between line 419 and line 421** (REPLACE both `<ItemCustomsExpenses />` and `<QuoteCustomsExpenses />` with `<CertificatesSection />`; LEAVE `<CustomsExpenses />` for calc-engine vars unless user says otherwise).
- **Imports relevant to wiring:** lines 17 (TableView type), 18 (`fetchAllAvailable` query), 19 (TableViewsDropdown), 31 (QuoteCustomsExpenses), 32 (ItemCustomsExpenses).
- **Active-view URL persistence:** lines 170-194 — `?customs_view=<id>` query param via `useSearchParams` + `router.push`. **Crucial for system-view option (b):** synthetic ID `customs_view=system:cert-overview` works with this exact code path (no changes needed).

### `customs-handsontable.tsx` (1189 lines) + `customs-columns.ts` (50 lines)

#### `CUSTOMS_AVAILABLE_COLUMNS` (`customs-columns.ts:22-47`) — **24 entries**

| # | key | label |
|---|---|---|
| 1 | `position` | № |
| 2 | `brand` | Бренд |
| 3 | `product_code` | Артикул |
| 4 | `product_name` | Наименование |
| 5 | `quantity` | Кол-во |
| 6 | `supplier_country` | Страна |
| 7 | `hs_code` | Код ТН ВЭД |
| 8 | `customs_duty_composite` | Пошлина |
| 9 | `customs_util_fee` | Утильсбор |
| 10 | `customs_excise` | Акциз |
| 11 | `customs_antidumping` | Антидемпинг |
| 12 | `customs_psm_pts` | ПСМ/ПТС |
| 13 | `customs_notification` | Нотификация |
| 14 | `customs_licenses` | Лицензии |
| 15 | `customs_eco_fee` | Экосбор |
| 16 | `customs_honest_mark` | Честный знак |
| 17 | `import_banned` | Запрет ввоза |
| 18 | `import_ban_reason` | Причина запрета |
| 19 | `license_ds_required` | ДС |
| 20 | `license_ds_cost` | Ст-ть ДС |
| 21 | `license_ss_required` | СС |
| 22 | `license_ss_cost` | Ст-ть СС |
| 23 | `license_sgr_required` | СГР |
| 24 | `license_sgr_cost` | Ст-ть СГР |

- **NO `certificates` column.** **NO `cost_rub` column.** REQ-11 view definitions referencing these will silently filter out (the `filterColumns` helper at handsontable.tsx:725 silently drops unknown keys).
- `country_of_origin_oksm` exists in handsontable's COLUMN_KEYS (line 238) but **NOT** in CUSTOMS_AVAILABLE_COLUMNS (the user-facing column picker) — minor pre-existing inconsistency, not Phase B's concern.

#### Toolbar structure

- **Above grid:** `<div className="flex items-center justify-end">` containing `<TableViewsDropdown />` (customs-step.tsx:383-397).
- **Below toolbar, above grid:** `<CustomsItemsEditor>` which mounts `<HotTable />`. No existing hint banner area — REQ-11's "active view ≠ all" hint banner needs new render between dropdown and editor.

### TableViewsDropdown component (`features/table-views/ui/table-views-dropdown.tsx`, 197 lines)

- **Exact name:** `TableViewsDropdown` (default export via `index.ts`).
- **Props (lines 30-47):**
  ```typescript
  views: readonly TableView[];        // all available, personal + shared mixed
  activeViewId: string | null;
  onViewChange: (viewId: string | null) => void;
  onViewsRefresh: () => void;          // called after settings dialog saves
  tableKey: string;
  availableColumns: readonly AvailableColumn[];
  userId: string;
  orgId: string;
  canCreateShared: boolean;
  ```
- **Persistence pattern:** **Component does NOT call API itself.** It accepts a `views` array (already fetched server-side via `fetchAllAvailable` in customs-step.tsx:200-205) + `onViewChange` callback (parent updates URL param). Settings dialog mutates DB via `@/entities/table-view/mutations`, then calls `onViewsRefresh()`. Clean separation.
- **Display grouping:** `personalViews` (NOT shared) under "Личные", `sharedViews` (shared) under "Общие" — lines 124-167. **No "system" group.**
- **System-view support:** **None.** No `isSystem` flag, no separate slot in `TableView` type, no special rendering. Adding system views requires either DB rows (option a) or virtual rows (option b) injected into `views` prop by parent.
- **Settings dialog gate:** `canCreateShared` prop hides shared-view actions; no equivalent for system views.

---

## Verification Results

| Item | Expected | Found | Status |
|---|---|---|---|
| `quote_items.customs_value_rub` exists as a column | yes | **NO — does not exist on `quote_items`. Lives only on `customs_declaration_items` (different entity).** | FAIL (refutes user's locked decision wording) |
| `quote_items.cost_rub` does NOT exist | true | confirmed: `cost_rub` only on `logistics_segments` table | PASS |
| `quotes.organization_id` exists | yes | yes — `database.types.ts:4368` (`string`, NOT NULL) | PASS |
| `quote_items.brand` exists | yes | yes — `database.types.ts:3990` (`string \| null`) | PASS |
| `quote_items.supplier_id` exists | yes | yes — `database.types.ts:4002` (`string \| null`); references `suppliers` (separate from `invoices`) | PASS |
| Migration 305 highest sequential | yes | yes — 305 is highest, no 306 yet, no collisions | PASS |
| TableViewsDropdown already integrated in customs-step | yes | yes — lines 385-395 with full props wired | PASS |
| `customs_*_expenses` tables have production write paths | yes | yes — `api/customs.py:605-797`, full CRUD UI in 2 frontend components | PASS |
| `is_system` / system-view concept on `user_table_views` | unknown | **NO — does not exist; only `is_shared` distinguishes view types** | informational |
| `.btn` BEM classes in frontend | absent | **confirmed absent** — project uses shadcn Button | PASS (validates Decision 3) |

---

## Requirements.md Corrections (concrete)

Below are the corrections needed to align `requirements.md` with code reality. The coordinator should apply these in the next step.

### REQ-1 corrections (entity & RLS)

- AC#6 wording about RLS: keep multi-table JOIN pattern (293-style with `r.slug`), do NOT switch to JWT-claim (304-style). Add explicit reasoning to spec.
- Make sure `is_custom_expense BOOLEAN NOT NULL DEFAULT false` is part of the schema (needed for the data migration from `customs_*_expenses`).

### REQ-3 corrections (cost split)

- AC#1: replace any "read `customs_value_rub` from `quote_items`" wording with "**use `services.calculation_helpers._customs_value_in_rub(item, quote_currency, convert_amount)` to derive RUB cost basis from the (resolved) item payload — NOT a column read**". Recommend extracting that helper into `services/cost_split.py` as `customs_value_rub_for_item(item, quote_currency)` so Phase B doesn't import from a "helpers" module.
- AC#10 (parity fixture): the column name in fixture is **NOT** `customs_value_rub` on the input row. Fixture rows should use `purchase_price_original` + `purchase_currency` + `quantity` (the actual upstream fields), and the fixture's expected output is the derived `customs_value_rub: <Decimal as string>`. Same fixture feeds both Python and TS tests.
- Add new AC: "Backend resolves invoice_items payload server-side; frontend `cost-split.ts` only operates on already-RUB inputs (no client-side currency conversion)."

### REQ-5 corrections (loose-match history)

- AC#1 join keys still valid (`hs_code` + `brand` + `supplier_id` all confirmed present on `quote_items`).
- AC#11 banner text/format reuse `formatDateRussian` from `@/features/customs-history/lib/format-date` — confirmed.

### REQ-6 corrections (unified Расходы по таможне section)

- AC#1: rename source — sections to remove are `<QuoteCustomsExpenses />` (`customs-step.tsx:419`) + `<ItemCustomsExpenses />` (line 411). **Do NOT remove `<CustomsExpenses />` at line 421** — it is the calc-engine variables form ("Таможенный сбор / Сертификат происхождения / Документация / Брокерские расходы") connected to `quote_versions.input_variables`, unrelated to certificate entity.
- AC#2 / AC#5 / AC#10 (any `.btn` BEM): replace with `<Button variant="…">` per shadcn convention.
- AC#9 (data migration): rewrite to "Migration 306 backfills `quote_certificates` from `customs_item_expenses` + `customs_quote_expenses` (mapping in `code-validation.md`); same migration drops both old tables in one transaction; old UI deletion ships in same PR." (No 307.)

### REQ-7, REQ-8, REQ-9 corrections

- Replace any `cost_rub` column-read wording on quote_items with the helper-call pattern from REQ-3.
- REQ-7 multi-select: use `frontend/src/shared/ui/geo/country-combobox.tsx` filter pattern + shadcn `<Checkbox />`. No `cmdk` library required.
- REQ-8 popover: use existing `frontend/src/components/ui/popover.tsx`. Already imported in customs-item-dialog.tsx — no new dependency.

### REQ-11 corrections (4 system views)

- AC#1: TableViewsDropdown is **ALREADY integrated** at `customs-step.tsx:385-395`. Phase B does NOT integrate it. Phase B adds 4 system views to the `views` prop and wires hint banner.
- AC#2: rewrite the four view definitions with **actual column ids from `CUSTOMS_AVAILABLE_COLUMNS`** (24 entries listed above). Drop any references to `certificates` and `cost_rub` columns (they do not exist).
  - Suggested view 1 "Базовый": `position, brand, product_code, product_name, quantity, supplier_country`
  - Suggested view 2 "Тарифы": `position, product_name, hs_code, customs_duty_composite, customs_antidumping, customs_excise, customs_util_fee`
  - Suggested view 3 "Сертификация": `position, product_name, hs_code, license_ds_required, license_ss_required, license_sgr_required, customs_notification, customs_licenses, customs_eco_fee, customs_honest_mark`
  - Suggested view 4 "Запреты": `position, brand, product_code, product_name, supplier_country, hs_code, import_banned, import_ban_reason`
  - (Concrete final picks belong to design phase — these are starters that match column reality.)
- AC#5: REPLACE `kvota.quote_view_preferences.customs_columns_view` storage. Recommendation: **virtual rows injected client-side** (option b above), synthetic IDs prefixed `system:` (e.g. `system:cert-overview`). Persistence via existing `?customs_view=` URL param works as-is. Pros: zero schema change; immutable by construction.
- AC#6: Migration 307 CANCELLED.

### LD corrections

- LD-12: replace «307 для quote_view_preferences» with «only migration 306 — schema + data migration + drop old tables, single transaction.»
- LD-13: replace «`.btn` BEM classes» with «shadcn `<Button variant="…">` from `@/components/ui/button` + design tokens (`design-system.md`).»
- **New LD-15:** «Cost-basis input for cost split = derived value from `services.calculation_helpers._customs_value_in_rub(item, quote_currency, convert_amount)`. Phase B extracts this helper into `services/cost_split.py` as the public `customs_value_rub_for_item()` and re-exports from helpers for backward-compat. Calc-engine itself remains untouched.»
- **New LD-16:** «System views ship as virtual client-side rows, not DB rows. Synthetic IDs `system:<slug>`. URL persistence via existing `?customs_view=` pattern.»

---

## Recommended Sequencing (revised)

**Wave 1 (parallel):**
- Migration 306: `quote_certificates` + `quote_certificate_items` + RLS + indexes + INSERT-from-old + DROP TABLE old (one atomic file).
- Refactor `_customs_value_in_rub` → `services/cost_split.py` + add `split_cost(items, total_rub) → list[Decimal]` + tests + JSON fixture in `tests/fixtures/cost_split_fixtures.json`.
- Frontend: `frontend/src/shared/lib/cost-split.ts` + `__tests__/cost-split.test.ts` consuming same fixture.
- Apply migration 306 via `scripts/apply-migrations.sh`; regenerate `database.types.ts`.

**Wave 2 (sequential, depends on Wave 1):**
- Backend API: `_certificates_*` handlers in `api/customs.py` (POST/GET/DELETE certificate, POST/DELETE attach, GET history). Register in `api/routers/customs.py`.
- `services/quote_certificates_history.py` (mirror `customs_user_choices.py`).
- Backend integration tests.

**Wave 3 (parallel after Wave 2):**
- FSD feature `frontend/src/features/customs-certificates/` (api/, model/, lib/, ui/, __tests__/, index.ts).
- 4 system view definitions as TS const in `customs-columns.ts` or new `customs-system-views.ts`. Inject into `views` array in customs-step.tsx server component (or client merge).

**Wave 4 (sequential after Wave 3):**
- `customs-step.tsx` — replace `<QuoteCustomsExpenses />` + `<ItemCustomsExpenses />` with new `<CertificatesSection />`. Keep `<CustomsExpenses />` (calc-engine vars) untouched.
- `customs-item-dialog.tsx` — add "Сертификация" section (popover for attach + cert list per item).
- `customs-handsontable.tsx` — add hint banner above `<HotTable>` for "active view ≠ all".

**Wave 5 — Verification:**
- Browser test on localhost:3000 + prod Supabase per `reference_localhost_browser_test.md`.
- Test scenarios per gap-analysis: create cert → multi-select → save → cert card → edit → attach via popover → unattach → history banner → expired-cert red border → custom-expense flow → 4 system views toggle.

---

## Blockers Remaining

**None — design phase is unblocked.** The single sharp edge is the `customs_value_rub` framing (was treated as a column; is actually a derived value). Decision 1 wording in the user-locked answer must be reframed as "use the existing helper, no column lookup" — but the underlying intent (RUB cost basis sourced from purchase data, calc-engine-consistent) is preserved.

The 24-column reality (vs the 18 REQ-11 imagined) and the absence of `certificates`/`cost_rub` columns in the registry are also material to REQ-11 view definitions, but those are concrete corrections not blockers.
