# Requirements: Customs per-invoice refactor

## Introduction

Customs-step сейчас показывает «плоскую» таблицу всех `quote_items` КП с колонками «Страна» (отгрузки) и «Страна происхождения». При multi-supplier multi-country товарах (когда один и тот же `quote_item` покрыт инвойсами от разных поставщиков из разных стран) колонки пустые или агрегат, и таможенный клерк не понимает с какой страной работать.

Корневая причина — `country_of_origin_oksm` и `has_origin_certificate` живут per-`quote_item` (одно значение), хотя реальный таможенный флоу — **per-invoice**: ДТ подаётся на конкретный инвойс, сертификат происхождения выдаёт конкретный поставщик, ТН ВЭД оформляется на конкретный контракт.

Фича переносит customs-step на per-invoice flow (как уже сделано в procurement-step и logistics): сверху чипы КПП → клик по чипу → таблица позиций ЭТОГО инвойса. Колонки origin и certificate переезжают с `quote_items` на `invoice_items`. Multi-supplier multi-country перестаёт быть проблемой архитектурно: каждая страница customs показывает один инвойс одного поставщика одной страны.

Контекст:
- МОЗ Тест 07 row 4.3 — тестер `sidorov.a@masterbearing.ru` открыл КП Q-202605-0004 (`a126adee-a9e4-4f4f-8541-11ffda77b6e2`) на этапе таможни и увидел пустую колонку «Страна» для 4 товаров.
- В БД эти 4 товара покрыты 3 КПП: INV-01 (ADLER, Италия), INV-02 (CHONGQING, Китай), INV-03 (ADLER, Италия).
- Тестер задал прямой вопрос: «есть 2 поставщика из разных стран — что будем делать?».

Решение продукта: per-invoice flow.

**Контекст по сертификатам происхождения:** Phase B (миграция 306) уже создал `kvota.quote_certificates` + `kvota.quote_certificate_items` (cost_rub, valid_until, M:N с `quote_items`) — эта сущность остаётся каноническим store для метаданных сертификатов происхождения. Refactor переносит только per-supplier флаг `has_origin_certificate` («есть у этого поставщика» — input для duty-rate selection через `payment_type.depends_on_certificate`) с `quote_items` на `invoice_items`. Phase B таблицы и UI не трогаем.

---

## Requirements

### Requirement 1: Per-invoice country of origin column

**Objective:** As a customs clerk, I want each `invoice_item` to carry its own `country_of_origin_oksm` value, so that the same SKU can have different country of origin per supplier (e.g., Bosch GB 4×30 made in Germany from ADLER but made in China from CHONGQING).

#### Acceptance Criteria

1. The DB schema shall add `country_of_origin_oksm INTEGER NULL` to `kvota.invoice_items`.
2. The DB schema shall add `has_origin_certificate BOOLEAN NOT NULL DEFAULT false` to `kvota.invoice_items`.
3. The migration shall be sequential (next free number after 312) and idempotent (`IF NOT EXISTS`).
4. The migration shall include a backfill step that copies the existing `quote_items.country_of_origin_oksm` and `has_origin_certificate` values into every covering `invoice_item` via `invoice_item_coverage` (one quote_item value → N invoice_items rows).
5. The migration shall NOT drop the original columns from `quote_items` in the same migration (legacy reads must keep working until all consumers are switched). Removal is staged for a follow-up migration.
6. `database.types.ts` shall be regenerated and include the new columns on `invoice_items.Row/Insert/Update`.

### Requirement 2: Customs step UI switches to per-invoice flow

**Objective:** As a customs clerk, I want to see customs work organized as per-КПП cards (like in procurement-step), so that I see exactly one supplier × one country × one positions table at a time, and never have to mentally aggregate across suppliers.

#### Acceptance Criteria

1. The customs-step shall render a list of КПП chips at the top of the page (mirroring procurement-step), one chip per non-deleted `kvota.invoices` row of the quote, showing: invoice number, supplier name, supplier country, and a status badge.
2. The currently-active chip shall be visually highlighted; clicking another chip shall swap the positions table content without a full page reload.
3. The active chip shall be reflected in the URL via `?invoice=<uuid>` so the state survives reload, can be linked, and matches the procurement-step convention.
4. When the quote has zero invoices, the customs step shall render an empty-state message «Нет КПП для оформления таможни» (no broken layout).
5. When the URL `?invoice=<uuid>` references a non-existent invoice, the step shall fall back to the first invoice with a non-dismissable warning toast («КПП не найден, открыт первый»).

### Requirement 3: Positions table is scoped to the active invoice

**Objective:** As a customs clerk, I want the positions table to show only `invoice_items` belonging to the currently-selected КПП, so that all rows have exactly one country and one supplier — no aggregation required.

#### Acceptance Criteria

1. The customs-handsontable shall accept `invoice_id` as a required prop and render only `invoice_items` whose `invoice_id` matches.
2. The «Страна» column shall display `invoices.pickup_country` for the active invoice (single value, never a list, never empty if the invoice has a pickup_country set).
3. The «Страна происхождения» column shall read from `invoice_items.country_of_origin_oksm` (the new per-invoice column from Requirement 1), not from `quote_items.country_of_origin_oksm`.
4. Edits to «Страна происхождения» shall write back to `invoice_items.country_of_origin_oksm` for the specific row only (no cascade to sibling invoices, no write to `quote_items`).
5. The header «Все суммы в таблице — в рублях ₽» banner shall be retained.
6. Empty-state inside a КПП («КПП ещё не наполнен позициями») shall be shown when the invoice has zero `invoice_items`.

### Requirement 4: КП-level customs sections stay КП-level

**Objective:** As a customs clerk, I want the «Расходы по таможне», «Общие расходы на КП», «Примечания», and «Заметки таможни по КП» blocks to remain at quote level (not duplicated per КПП), so that I record cross-invoice information once.

#### Acceptance Criteria

1. The «Расходы по таможне» (item-level certificates and expenses) shall remain visible above the per-invoice positions table when an active КПП is selected. Item-level expenses already scope to a selected row — that scoping is unchanged.
2. The «Общие расходы на КП» (quote-level customs fee, broker, documentation, certificate of origin total) block shall render once, below the KПП chip row, regardless of active КПП.
3. The «Примечания» (`quotes.customs_notes`) shall remain a single КП-level field.
4. The «Заметки таможни по КП» entity-notes section shall remain attached to the quote, not the invoice.

### Requirement 5: Calc engine input mapper reads per-invoice country

**Objective:** As the calculation engine, I want `country_of_origin` resolved per `invoice_item` (not per `quote_item`), so that duty calculation uses the right country for the selected supplier — especially when the quote has been «split» across suppliers from different countries.

#### Acceptance Criteria

1. `build_calculation_inputs` in `main.py` shall, for each quote_item, look up the country_of_origin from the `invoice_item` referenced by `quote_items.composition_selected_invoice_id`.
2. If `composition_selected_invoice_id` is NULL, the mapper shall fall back to the legacy `quote_items.country_of_origin_oksm` (compatibility with not-yet-resolved quotes).
3. The `calculation_engine.py` and `calculation_models.py` and `calculation_mapper.py` files shall NOT be modified — the change is in `build_calculation_inputs` only (per CLAUDE.md: «If data schema changes, adapt in `build_calculation_inputs()`»).
4. Existing calc-engine tests shall pass with no changes to their expected outputs (no rate change for existing fixtures).

### Requirement 6: Autofill suggestions endpoint becomes per-invoice_item

**Objective:** As a customs clerk filling «Страна происхождения», I want the autofill banner suggestions to be keyed to invoice_items (the new editable unit), so that accepting a suggestion writes to the correct row.

#### Acceptance Criteria

1. The autofill suggestions API endpoint shall return suggestions keyed by `invoice_item_id` (not `quote_item_id`).
2. Each suggestion payload shall include the source signals used (hs_code, supplier_country, brand) for diagnostics.
3. The frontend `AutofillBanner` and bulk-accept transition shall persist accepted suggestions via UPDATE on `invoice_items`, not `quote_items`.
4. When the autofill endpoint cannot resolve a row (e.g., no historical match), it shall return an empty suggestions array — never a fabricated guess.

### Requirement 7: Legacy columns kept for read backward-compat

**Objective:** As a maintainer, I want `quote_items.country_of_origin_oksm` and `quote_items.has_origin_certificate` to remain in the schema during the transition window, so that legacy code paths (reports, exports, calc-engine fallback) keep working until they are explicitly switched.

#### Acceptance Criteria

1. The migration from Requirement 1 shall NOT drop the original `quote_items.country_of_origin_oksm` or `quote_items.has_origin_certificate` columns.
2. A lint rule in `tools/check_supabase_write_types.py` shall reject any `.update()`, `.insert()`, or `.upsert()` call writing to `quote_items.country_of_origin_oksm` or `quote_items.has_origin_certificate`. The legacy columns remain readable for backward compatibility (see AC 7.1) but are unwritable from new code. (Note: `database.types.ts` is auto-generated by `npm run db:types` and would erase any JSDoc `@deprecated` markers — the deprecation lives in the lint rule, not in the auto-gen types file.)
3. A follow-up cleanup migration shall be planned (referenced in the design doc), but is OUT OF SCOPE for this spec.
4. No writes from new code shall target `quote_items.country_of_origin_oksm` or `quote_items.has_origin_certificate` after the refactor (writes go exclusively to `invoice_items`).
5. The Phase B tables `kvota.quote_certificates` and `kvota.quote_certificate_items` (added in migration 306) shall NOT be modified by this refactor. The certificate-of-origin metadata model (cost_rub, valid_until, M:N) remains canonical at quote level; only the per-supplier «have it» flag moves to `invoice_items`.

### Requirement 8: RLS and permissions

**Objective:** As a security reviewer, I want the new `invoice_items` columns to inherit the existing RLS posture, so that no role gains unexpected access to customs data.

#### Acceptance Criteria

1. The new columns shall NOT require new RLS policies — they ride the existing `invoice_items_select` / `invoice_items_update` policies (which already gate by `organization_id`).
2. The migration shall not modify existing RLS policies on `invoice_items`.
3. Manual verification: under `nagumanova.u@masterbearing.ru` (procurement) — can SELECT but NOT UPDATE `invoice_items.country_of_origin_oksm` (procurement role is not in the customs Update policy if such restriction exists). Confirm or document.
4. Under `sidorov.a@masterbearing.ru` (head_of_logistics) — the user can switch chips and edit origin freely (matches current customs handsontable editability).

### Requirement 9: Test coverage

**Objective:** As a maintainer, I want the new flow to be covered by tests at three levels, so that regressions in the next refactor (column drop in `quote_items`) are caught at CI gate.

#### Acceptance Criteria

1. A migration backfill test shall verify: given 1 quote_item with origin=DE, 3 covering invoice_items, all 3 invoice_items have origin=DE after the migration.
2. A `customs-step.dom.test.tsx` jsdom-substrate test shall verify: clicking a КПП chip swaps the positions table content and updates the URL `?invoice=` parameter. (Filename uses `*.dom.test.tsx` glob per project vitest 4 convention — SSR `renderToString` is the default substrate; jsdom is opt-in via the dom-glob.)
3. A `customs-handsontable.dom.test.tsx` jsdom-substrate test shall verify: «Страна» column displays the active invoice's pickup_country; «Страна происхождения» writes to the active row's `invoice_items.country_of_origin_oksm` (asserted via mock spy).
4. The schema-drift lint (`tools/check_select_columns.py`) shall pass with the new column references.
5. The write-type lint (`tools/check_supabase_write_types.py`) shall pass — no new `as Record<string, ...>` casts introduced.

### Requirement 10: Backfill data correctness for tester's reference data

**Objective:** As tester `sidorov.a@masterbearing.ru`, I want КП Q-202605-0004 to show non-empty country columns after the migration, so that my МОЗ Тест 07 row 4.3 verification passes.

#### Acceptance Criteria

1. After the migration is applied to prod, the customs step for `a126adee-a9e4-4f4f-8541-11ffda77b6e2` shall render 3 КПП chips: INV-01 (ADLER, Италия), INV-02 (CHONGQING, Китай), INV-03 (ADLER, Италия).
2. Switching to INV-01 shall show positions with «Страна» = Италия.
3. Switching to INV-02 shall show positions with «Страна» = Китай.
4. «Страна происхождения» shall remain empty (legacy `quote_items.country_of_origin_oksm` is also empty for this test data) — but the column is now editable per-invoice for the customs clerk to fill in.
