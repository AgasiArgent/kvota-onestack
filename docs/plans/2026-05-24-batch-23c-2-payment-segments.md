# Batch 23C-2 — Сегментация платежей клиента (Row 46)

**Дата:** 2026-05-24
**Source:** docs/plans/2026-05-24-product-decisions.md (Row 46)
**Tester quote (РОП + МОП):**
> «На данный момент, мы предоставляем любые условия оплаты - 30/70, 70/30, 50/50 и тд. Также есть комбинированные 20/30/50 и тд. На каждый сегмент указать сроки оплаты в календарных днях. Важно выделить - Срок оплаты Аванса Клиентом, Срок оплаты Клиентом после отгрузки Товара»

---

## Анализ существующего состояния

**Calc engine** (`calculation_models.py::PaymentTerms`) уже принимает **5 anchor events** × 2 fields:

| # | Anchor | Engine % var | Engine days var |
|---|---|---|---|
| 1 | Аванс клиента (T0) | `advance_from_client` | `time_to_advance` |
| 2 | При погрузке | `advance_on_loading` | `time_to_advance_loading` |
| 3 | При прибытии в страну назначения | `advance_on_going_to_country_destination` | `time_to_advance_going_to_country_destination` |
| 4 | При таможенном оформлении | `advance_on_customs_clearance` | `time_to_advance_on_customs_clearance` |
| 5 | После получения (балансовый) | — (= 100% - Σ) | `time_to_advance_on_receiving` |

**Текущая DB (specifications):**
- ✅ `advance_percent_from_client` → anchor 1 (%)
- ✅ `payment_deferral_days` → anchor 1 (days)
- ✅ `client_payment_term_after_upd` ≈ anchor 5 (days после УПД) — близкая семантика
- 🆕 Нет 6 полей для anchors 2/3/4 (3 пары pct + days)

**Текущий UI (`calculation-form.tsx`):**
- «Аванс клиента» (%) — line 143
- «До аванса» (days) — line 160
- «До расчёта» (days) — line 175

Только 3 поля из 10. Остальные anchors сейчас передаются в engine как `0`.

---

## DB Migration

```sql
-- migrations/3XX_add_payment_segments_to_specifications.sql
BEGIN;

ALTER TABLE kvota.specifications
  ADD COLUMN payment_on_loading_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
  ADD COLUMN payment_on_loading_days INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN payment_on_country_arrival_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
  ADD COLUMN payment_on_country_arrival_days INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN payment_on_customs_clearance_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
  ADD COLUMN payment_on_customs_clearance_days INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN payment_on_receiving_days INTEGER NOT NULL DEFAULT 0;

-- Validation constraints
ALTER TABLE kvota.specifications
  ADD CONSTRAINT spec_payment_pct_loading_range
    CHECK (payment_on_loading_pct >= 0 AND payment_on_loading_pct <= 100),
  ADD CONSTRAINT spec_payment_pct_arrival_range
    CHECK (payment_on_country_arrival_pct >= 0 AND payment_on_country_arrival_pct <= 100),
  ADD CONSTRAINT spec_payment_pct_customs_range
    CHECK (payment_on_customs_clearance_pct >= 0 AND payment_on_customs_clearance_pct <= 100),
  ADD CONSTRAINT spec_payment_days_loading_nonneg
    CHECK (payment_on_loading_days >= 0),
  ADD CONSTRAINT spec_payment_days_arrival_nonneg
    CHECK (payment_on_country_arrival_days >= 0),
  ADD CONSTRAINT spec_payment_days_customs_nonneg
    CHECK (payment_on_customs_clearance_days >= 0),
  ADD CONSTRAINT spec_payment_days_receiving_nonneg
    CHECK (payment_on_receiving_days >= 0),
  -- Total of explicit pcts must not exceed 100 (anchor 5 is balance)
  ADD CONSTRAINT spec_payment_pct_sum_max
    CHECK (
      COALESCE(advance_percent_from_client, 0)
      + payment_on_loading_pct
      + payment_on_country_arrival_pct
      + payment_on_customs_clearance_pct
      <= 100
    );

COMMENT ON COLUMN kvota.specifications.payment_on_loading_pct IS '% оплаты при погрузке (anchor 2)';
COMMENT ON COLUMN kvota.specifications.payment_on_loading_days IS 'Дней до оплаты с момента погрузки';
COMMENT ON COLUMN kvota.specifications.payment_on_country_arrival_pct IS '% оплаты при прибытии в страну назначения (anchor 3)';
COMMENT ON COLUMN kvota.specifications.payment_on_country_arrival_days IS 'Дней до оплаты с момента прибытия';
COMMENT ON COLUMN kvota.specifications.payment_on_customs_clearance_pct IS '% оплаты при таможенном оформлении (anchor 4)';
COMMENT ON COLUMN kvota.specifications.payment_on_customs_clearance_days IS 'Дней до оплаты с момента таможни';
COMMENT ON COLUMN kvota.specifications.payment_on_receiving_days IS 'Дней до балансовой оплаты после получения (anchor 5)';

COMMIT;
```

**Verify after apply:**
```sql
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'kvota' AND table_name = 'specifications'
  AND column_name LIKE 'payment_%';
-- Should return 7 new column names
```

---

## UI Wireframe

**Location:** Calc-step, заменить текущие 3 поля (Аванс/До аванса/До расчёта) на единый блок «Условия оплаты».

```
┌─────────────────────────────────────────────────────────────────┐
│  УСЛОВИЯ ОПЛАТЫ                                  Σ = 100% ✓     │
├─────────────────────────────────────────────────────────────────┤
│  Quick presets:  [30/70]  [50/50]  [70/30]  [20/30/50]  [Сброс] │
├─────────────────────────────────────────────────────────────────┤
│                              %        Дней (календарных)         │
│  1. Аванс клиента          [30]      [7]   до отгрузки           │
│  2. При погрузке           [0 ]      [0]   с момента погрузки    │
│  3. При прибытии           [0 ]      [0]   с момента прибытия    │
│  4. При таможне            [0 ]      [0]   с момента очистки     │
│  5. После получения        [70]*     [30]  с момента приёмки     │
│                            ↑ авто = 100 - Σ                     │
└─────────────────────────────────────────────────────────────────┘
* — read-only, вычисляется автоматически
```

**Behaviors:**
- **% инпуты:** numeric, validation 0-100, on blur normalize
- **Days инпуты:** integer, ≥ 0
- **Anchor 5 % (читается):** автоматически = 100 - sum(anchors 1-4). Подсветка красным если sum > 100.
- **Sum indicator** в заголовке: `Σ = 100% ✓` (зелёный) / `Σ = 80% — добавьте 20%` (warning) / `Σ = 120% — превышение` (error)
- **Quick presets:** preset кнопки заполняют типовые комбинации; default value для days если pct > 0
- **Сброс:** обнуляет все pct/days кроме anchor 1 (= 100%)

**Empty state:** при создании КП — заполнить anchor 1 = 100% / 0 days (100% аванс).

---

## Implementation steps

### 1. DB migration (m3XX)
Apply via VPS: `git pull && bash scripts/apply-migrations.sh`. Verify schema after.

### 2. Backend (`build_calculation_inputs()` в main.py)
Расширить mapping:
```python
'advance_from_client': spec.get('advance_percent_from_client', 100),
'time_to_advance': spec.get('payment_deferral_days', 0),
'advance_on_loading': spec.get('payment_on_loading_pct', 0),
'time_to_advance_loading': spec.get('payment_on_loading_days', 0),
'advance_on_going_to_country_destination': spec.get('payment_on_country_arrival_pct', 0),
'time_to_advance_going_to_country_destination': spec.get('payment_on_country_arrival_days', 0),
'advance_on_customs_clearance': spec.get('payment_on_customs_clearance_pct', 0),
'time_to_advance_on_customs_clearance': spec.get('payment_on_customs_clearance_days', 0),
'time_to_advance_on_receiving': spec.get('payment_on_receiving_days', 0),
```

### 3. Frontend type regen
`cd frontend && npm run db:types` после применения миграции.

### 4. UI component (calculation-step)
- New component `<PaymentSegmentsBlock>` в `frontend/src/features/quotes/ui/calculation-step/`.
- Replace 3 existing FormRows (line 143, 160, 175 в `calculation-form.tsx`) на этот блок.
- Add `<QuickPresets>` sub-component с типовыми комбинациями.
- Add `<SumIndicator>` с live-validation.

### 5. Server action
Update existing `update_specification` (или mutation handler) — accept 7 новых полей. PostgREST уже принимает через JS client после type regen.

### 6. Tests
- DB CHECK constraints: попытаться вставить sum > 100 → reject
- Unit test для `<PaymentSegmentsBlock>`: presets, sum validation, balance = 100 - others
- Golden master suite **mandatory pass** — calc engine получает новые inputs, должен давать те же результаты для existing fixtures (все anchors 2/3/4 = 0 в golden fixtures → no change in calc output)
- E2E: создать спек с 30/30/40, verify saved

### 7. ERPS view update (optional, follow-up)
`migrations/161_fix_erps_registry_spec_sum_usd.sql` сейчас computes advance_payment_deadline только из single anchor. Расширить для multi-segment — но это не блокирует main task.

---

## Risks + Mitigations

| Risk | Mitigation |
|---|---|
| Calc engine получает new inputs → ломает golden master | Все fixture sums = single anchor (100% advance). New columns = 0 → no behavior change. Verify in CI. |
| `client_payment_term_after_upd` ≠ `payment_on_receiving_days` (близкие но не одинаковые семантики) | Оставить `client_payment_term_after_upd` для legacy use cases (ERPS reports). Новый `payment_on_receiving_days` — только для calc engine input. Document both в comments. |
| User вводит non-integer % (e.g., 33.33) | NUMERIC(5,2) поддерживает 2 decimals — OK. Validation sum=100 учитывает float drift через `<= 100` (не `=`). |
| Existing specs/quotes — все 7 new columns = 0 → engine думает «100% receiving» | Default = 0, но anchor 1 % из существующего `advance_percent_from_client`. Anchors 2-4 = 0. Anchor 5 days = `payment_on_receiving_days` default 0 — calc treats as "remainder due immediately on receipt". Это совпадает с current single-anchor behavior. |

---

## Связь с Row 69 (% аванса поставщика)

Row 69 = `advance_to_supplier_percent` + `supplier_payment_terms` на `quote_items` — это **поставщик**, не клиент. Schema разная (per-item, single %, free text terms). НЕ переделываем под multi-segment в этом батче.

Однако: в будущем можно унифицировать UI компонент — `<PaymentSegmentsBlock>` мог бы переиспользоваться для supplier side с другим storage. Парковка на follow-up batch если потребуется.

---

## Status

- ⏳ Awaiting wireframe review
- 📋 Migration drafted
- 📋 Implementation plan drafted
- 🔲 Spec creation (Phase 2) — после wireframe approval
