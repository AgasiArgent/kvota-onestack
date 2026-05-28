# Requirements Document

## Introduction

Тестеры Testing 2 (Row 46, РОП + МОП) запросили возможность задавать сегментированные условия оплаты клиентом — комбинации вида **30/70**, **50/50**, **20/30/50** и т.п. — с указанием срока оплаты в календарных днях для каждого сегмента и привязкой к одному из событий жизненного цикла (Аванс, Погрузка, Прибытие в страну, Таможня, Получение).

**Tester quote:**
> «На данный момент, мы предоставляем любые условия оплаты - 30/70, 70/30, 50/50 и тд. Также есть комбинированные 20/30/50 и тд. На каждый сегмент указать сроки оплаты в календарных днях. Важно выделить - Срок оплаты Аванса Клиентом, Срок оплаты Клиентом после отгрузки Товара»

**Scope:** Эта фича только для **клиент-side payment terms** на `kvota.specifications`. Поставщик-side (`quote_items.advance_to_supplier_percent` — Row 69) пока не трогаем.

**Source design:** `docs/plans/2026-05-24-batch-23c-2-payment-segments.md`

**Calc engine constraint (CRITICAL):** `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` — **LOCKED**. Эти файлы НЕ модифицируются. Schema engine'а `PaymentTerms` уже поддерживает все 5 anchor events × 2 fields каждый. Имплементация заполняет gap между DB ↔ engine inputs через mapping в `main.py::build_calculation_inputs()`.

**Key terminology:**
- **Anchor event** — событие жизненного цикла к которому привязан платёж: `advance` (T0, до отгрузки), `loading` (погрузка), `country_arrival` (прибытие в страну назначения), `customs_clearance` (таможенное оформление), `receiving` (приёмка груза).
- **Payment segment** — пара (% от общей суммы, срок в днях с момента anchor event). Может быть 0% если anchor неактивен.
- **Balance anchor** — anchor 5 «После получения» — его % всегда = 100 - Σ(anchors 1-4). Не вводится явно, вычисляется UI / используется engine'ом implicitly.

**Locked decisions:**
1. Storage = 7 новых columns на `kvota.specifications` (не JSONB, не отдельная таблица). Решено пользователем 2026-05-24 на основе матчинга 1:1 с engine fields + DB-level CHECK constraints.
2. UI placement = calc-step (заменить текущие 3 поля «Аванс клиента / До аванса / До расчёта» единым блоком).
3. 5 anchor events (matching engine эталон), не 2 (минимум) и не 4+ (overkill). User confirmed 2026-05-24.
4. Existing `client_payment_term_after_upd` columns на specifications остаётся **для legacy ERPS reports** — не переиспользуем под `payment_on_receiving_days` (другая семантика: УПД ≠ приёмка). Новые columns параллельные.

---

## Requirements

### Requirement 1: DB Schema — добавить 7 columns для multi-anchor segments

**Objective:** Как разработчик, я хочу хранить 4 дополнительных anchor events (loading, country_arrival, customs_clearance + days для receiving) на `kvota.specifications`, чтобы calc engine получал все 10 payment fields из persistent storage.

#### Acceptance Criteria

1. WHEN migration выполнена THEN `kvota.specifications` HAS 7 new columns:
   - `payment_on_loading_pct NUMERIC(5,2) NOT NULL DEFAULT 0`
   - `payment_on_loading_days INTEGER NOT NULL DEFAULT 0`
   - `payment_on_country_arrival_pct NUMERIC(5,2) NOT NULL DEFAULT 0`
   - `payment_on_country_arrival_days INTEGER NOT NULL DEFAULT 0`
   - `payment_on_customs_clearance_pct NUMERIC(5,2) NOT NULL DEFAULT 0`
   - `payment_on_customs_clearance_days INTEGER NOT NULL DEFAULT 0`
   - `payment_on_receiving_days INTEGER NOT NULL DEFAULT 0`

2. WHEN тестер пытается вставить значение % > 100 в любую из 3 новых pct-columns THEN DB rejects через CHECK constraint `IN (0, 100)`.

3. WHEN тестер пытается вставить отрицательное число дней THEN DB rejects через CHECK constraint `>= 0`.

4. WHEN sum (`advance_percent_from_client` + 3 new pct) > 100 THEN DB rejects через CHECK constraint `spec_payment_pct_sum_max` — итого по 4 явным anchor'ам не может превышать 100%, остаток автоматически на anchor 5 (receiving).

5. WHEN existing specifications записи присутствовали до миграции THEN они получают DEFAULT 0 для всех 7 новых columns и НЕ нарушают constraint #4 (исходная анкор 1 % осталась прежней).

6. WHEN migration применена через `scripts/apply-migrations.sh` THEN verification query `SELECT column_name FROM information_schema.columns WHERE table_schema='kvota' AND table_name='specifications' AND column_name LIKE 'payment_%' AND column_name NOT IN ('payment_deferral_days', 'payment_calendar_days')` возвращает все 7 новых имён.

### Requirement 2: Calc engine mapping — пробрасывать новые fields через build_calculation_inputs

**Objective:** Как разработчик, я хочу что calc engine получил все 10 payment fields из DB через `build_calculation_inputs()`, чтобы движок мог корректно рассчитывать cash-flow с учётом многосегментных платежей.

#### Acceptance Criteria

1. WHEN `build_calculation_inputs(spec)` вызывается с specification объекта THEN return dict содержит все 10 PaymentTerms fields:
   - `advance_from_client` ← `spec['advance_percent_from_client']`
   - `time_to_advance` ← `spec['payment_deferral_days']`
   - `advance_on_loading` ← `spec['payment_on_loading_pct']`
   - `time_to_advance_loading` ← `spec['payment_on_loading_days']`
   - `advance_on_going_to_country_destination` ← `spec['payment_on_country_arrival_pct']`
   - `time_to_advance_going_to_country_destination` ← `spec['payment_on_country_arrival_days']`
   - `advance_on_customs_clearance` ← `spec['payment_on_customs_clearance_pct']`
   - `time_to_advance_on_customs_clearance` ← `spec['payment_on_customs_clearance_days']`
   - `time_to_advance_on_receiving` ← `spec['payment_on_receiving_days']`

2. WHEN specification отсутствует или fields = None THEN default = 0 (engine treats как «100% advance, no other payments»).

3. WHEN spec record имеет нулевые новые fields (default state) AND `advance_percent_from_client = 100` THEN calc engine output идентичен output до миграции (backward-compatible).

4. WHEN golden master test suite `pytest tests/test_calc_engine_golden_master.py` запускается after изменений THEN все existing fixtures проходят с теми же 3 ACCEPTED_DIFFERENCES (никаких новых diff'ов).

5. WHEN `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` модифицированы THEN spec FAILS valid (these files are LOCKED). Только `main.py::build_calculation_inputs()` (или эквивалентный mapper в FastAPI sub-app) может изменяться.

### Requirement 3: UI блок «Условия оплаты» на calc-step

**Objective:** Как МОП, я хочу видеть 5 строк payment segments на calc-step с возможностью ввести % и дни для каждого anchor + quick presets для типовых комбинаций, чтобы быстро выставить условия оплаты для КП.

#### Acceptance Criteria

1. WHEN МОП открывает quote на calc-step THEN UI showsa новый блок «Условия оплаты» вместо текущих 3 FormRow'ов («Аванс клиента», «До аванса», «До расчёта» в `calculation-form.tsx`).

2. WHEN блок rendered THEN 5 anchors visible как rows, каждый с label + % input + days input:
   - Row 1: «Аванс клиента» — `advance_percent_from_client` + `payment_deferral_days`
   - Row 2: «При погрузке» — `payment_on_loading_pct` + `payment_on_loading_days`
   - Row 3: «При прибытии в страну» — `payment_on_country_arrival_pct` + `payment_on_country_arrival_days`
   - Row 4: «При таможне» — `payment_on_customs_clearance_pct` + `payment_on_customs_clearance_days`
   - Row 5: «После получения» — % READ-ONLY (= 100 - Σ rows 1-4) + `payment_on_receiving_days`

3. WHEN МОП изменяет % в row 1-4 THEN row 5 % обновляется live (formula `100 - sum`). Если результат < 0 — display красным.

4. WHEN sum % < 100 OR > 100 THEN UI showsa warning badge возле header блока («Σ = 80% — добавьте 20%» / «Σ = 120% — превышение»).

5. WHEN sum % = 100 THEN UI showsa green checkmark badge («Σ = 100% ✓»).

6. WHEN МОП кликает quick preset button (30/70, 50/50, 70/30, 20/30/50) THEN форма заполняется соответствующими значениями (anchor 1 + anchor 5, или anchor 1+2+3 для 20/30/50), days = 0/30/30 (sensible defaults).

7. WHEN МОП кликает «Сброс» THEN форма зануляется, anchor 1 = 100%, days = 0.

8. WHEN МОП вводит negative number OR non-numeric in any field THEN input rejects value (HTML5 validation + on-blur normalize to nearest valid).

9. WHEN МОП пытается submit/save форму с sum != 100% THEN client-side validation блокирует save AND showsa error message.

### Requirement 4: Persistence — server action updates new fields

**Objective:** Как МОП, я хочу что мои изменения payment segments сохраняются в DB через server action, чтобы возврат на quote показывал актуальные значения.

#### Acceptance Criteria

1. WHEN МОП вводит valid payment segments AND clicks save THEN server action `updateSpecificationPayment(specId, segments)` отправляет updated values на Supabase.

2. WHEN server action executes THEN ALL 9 payment fields (6 new pct/days + existing advance pct/days + receiving days) пишутся в одной транзакции PATCH.

3. WHEN PATCH succeeds THEN UI refetches spec AND showsa toast «Условия оплаты сохранены».

4. WHEN PATCH fails (e.g., DB CHECK violation, network) THEN UI showsa toast с error message AND user может retry.

5. WHEN другой user одновременно изменил spec THEN our PATCH wins last-write-wins (consistent с existing PATCH-pattern; нет оптимистичного locking).

6. WHEN existing legacy quotes (без payment_on_* values) загружены THEN UI defaults: anchor 1 = `advance_percent_from_client` (если есть) или 100%, остальные = 0.

### Requirement 5: Frontend type safety + tests

**Objective:** Как разработчик, я хочу что TypeScript types отражают новые DB columns и tests покрывают core логику.

#### Acceptance Criteria

1. WHEN migration applied AND `npm run db:types` выполнено THEN `frontend/src/shared/types/database.types.ts` содержит 7 новых fields в Specifications row type.

2. WHEN `<PaymentSegmentsBlock>` rendered с empty spec THEN unit test verifies default state (anchor 1 = 100, остальные = 0).

3. WHEN user changes anchor 1 % to 30 THEN unit test verifies anchor 5 % = 70 (auto-balance).

4. WHEN sum > 100 THEN unit test verifies warning badge appears AND save disabled.

5. WHEN quick preset «30/70» clicked THEN unit test verifies anchor 1 = 30, anchor 5 = 70, others = 0.

6. WHEN frontend builds локально (`npm run build`) после type regen THEN no TypeScript errors related к payment fields.

### Requirement 6: ERPS view (deferred follow-up)

**Objective:** ERPS view `kvota.erps_registry` (миграция 161) сейчас computes `advance_payment_deadline` from single anchor (`advance_percent_from_client` + `payment_deferral_days`). После expand до multi-segment может потребоваться richer представление для finance dashboard.

#### Acceptance Criteria

1. WHEN this spec ships THEN ERPS view NOT modified (deferred to follow-up).

2. WHEN finance team requires multi-segment view of ERPS THEN отдельный spec будет создан для view migration.

3. WHEN main batch 23C-2 deployed AND smoke tested THEN finance team notified что ERPS view computes только anchor 1 deadline; full multi-segment ERPS отложен.

---

## Out of scope (для этого spec'а)

- Row 69 (% аванса поставщика) рефактор под multi-segment — оставляем `quote_items.advance_to_supplier_percent` single %. Может быть унифицирован в будущем батче.
- ERPS view migration для multi-segment view — deferred (см. Req 6).
- Migration legacy quotes с `client_payment_terms` (free text) — не парсим и не auto-fill segments. МОП вводит вручную при редактировании.
- Calc engine extension (новые anchor events за 5) — engine эталон locked, расширение требует separate change request.
- Email/PDF templates показывающие сегменты — отдельный follow-up если нужно.
- Inline editing payment segments на context-panel — может появиться позже; в этом spec только calc-step.
