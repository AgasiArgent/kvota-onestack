# Design Document

## Overview

Многосегментные условия оплаты клиента — расширение модели payment terms на `kvota.specifications` с 1 anchor (% + days) до 5 anchors. Сегментация даёт МОП возможность выставлять кастомные комбинации платежей 30/70, 50/50, 20/30/50 и т.п. с привязкой к событиям жизненного цикла (Аванс, Погрузка, Прибытие, Таможня, Получение).

**Архитектурный принцип:** matching 1:1 с calc engine `PaymentTerms` model. Engine эталон locked — поэтому schema, mapping и UI adapt **к engine'у**, а не наоборот.

## Architecture

### Data flow

```
[User edits payment segments в UI на calc-step]
   ↓
[<PaymentSegmentsBlock> validates locally (sum=100%)]
   ↓
[Server action updateSpecificationPayment(spec_id, segments)]
   ↓
[Supabase PATCH kvota.specifications (9 fields)]
   ↓ DB CHECK constraints validate
[On success → revalidatePath('/quotes/{id}')]
   ↓
[Calculate request to FastAPI /api/calculate/{quote_id}]
   ↓
[main.py::build_calculation_inputs(spec) maps 10 fields → PaymentTerms]
   ↓
[calculation_engine.calculate() — LOCKED, no changes]
   ↓
[Result rendered в <CalculationResults>]
```

### Layered separation

| Layer | Responsibility | Files |
|---|---|---|
| DB schema | Storage + integrity constraints | `migrations/3XX_*.sql` |
| Mapper | DB row → engine input dict | `main.py` (or `api/calculation.py`) |
| Engine | Pure calculation (LOCKED) | `calculation_engine.py`, `_models.py`, `_mapper.py` |
| Server action | Validate + persist UI changes | `entities/specification/server-actions.ts` |
| UI block | Form + live balance + presets | `features/quotes/ui/calculation-step/payment-segments-block.tsx` |
| Page composition | Replace 3 FormRows with new block | `calculation-form.tsx` |

## Components and Interfaces

### Component 1: DB migration

**File:** `migrations/3XX_add_payment_segments_to_specifications.sql` (assign next available number at implementation time, current latest = 320, so likely **323** if batch 23A lands 321/322).

**Migration shape:** See full SQL in `docs/plans/2026-05-24-batch-23c-2-payment-segments.md`. Wrap в BEGIN/COMMIT per memory note про m309/m318 incidents.

**Key constraints:**
- 3 pct ranges (0-100), 4 days ranges (>= 0).
- Composite sum constraint: `advance_percent_from_client + payment_on_loading_pct + payment_on_country_arrival_pct + payment_on_customs_clearance_pct <= 100`.
- Comments документируют semantics каждого column.

**Verification после apply:**
```sql
-- Schema check
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_schema = 'kvota' AND table_name = 'specifications'
  AND column_name LIKE 'payment_on_%';
-- Expect 7 rows

-- Constraint check
SELECT conname FROM pg_constraint
WHERE conrelid = 'kvota.specifications'::regclass
  AND conname LIKE 'spec_payment_%';
-- Expect 8 constraints
```

### Component 2: `main.py::build_calculation_inputs()` mapping extension

**File:** `main.py` (or whichever endpoint builds calc inputs — verify в Phase 2 spec-impl).

**Change shape:**
```python
# Before
'advance_from_client': spec.get('advance_percent_from_client', 100),
'time_to_advance': spec.get('payment_deferral_days', 0),
# ... other fields ...
'time_to_advance_on_receiving': spec.get('client_payment_term_after_upd', 0),

# After (add 8 new lines for anchors 2/3/4, change anchor 5 source)
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

**Critical:** `time_to_advance_on_receiving` source меняется с `client_payment_term_after_upd` на `payment_on_receiving_days`. Reason: semantics — УПД (Universal Transfer Document signed) ≠ receiving (физическая приёмка груза). Сохраняем legacy column для ERPS reports.

**Risk mitigation:** golden master fixtures имеют `client_payment_term_after_upd = X` для legacy data. После migration `payment_on_receiving_days` default = 0. Это может изменить golden output. **Migration backfill:** copy `client_payment_term_after_upd` → `payment_on_receiving_days` для existing rows (см. Tasks). Это обеспечивает backward-compat.

### Component 3: `<PaymentSegmentsBlock>` React component

**File:** `frontend/src/features/quotes/ui/calculation-step/payment-segments-block.tsx` (NEW)

**Props:**
```typescript
interface PaymentSegmentsBlockProps {
  specId: string;
  // Initial values (5 anchors × 2 fields − 1 because anchor 5 % auto-computed)
  initial: {
    advance_percent_from_client: number;
    payment_deferral_days: number;
    payment_on_loading_pct: number;
    payment_on_loading_days: number;
    payment_on_country_arrival_pct: number;
    payment_on_country_arrival_days: number;
    payment_on_customs_clearance_pct: number;
    payment_on_customs_clearance_days: number;
    payment_on_receiving_days: number;
  };
  onSaved?: () => void;
  disabled?: boolean;
}
```

**State shape:** identical to props.initial (controlled inputs).

**Derived state:**
```typescript
const explicitPctSum = anchor1Pct + anchor2Pct + anchor3Pct + anchor4Pct;
const receivingPct = 100 - explicitPctSum;
const sumValid = explicitPctSum >= 0 && explicitPctSum <= 100;
const sumStatus: 'valid' | 'low' | 'over' =
  explicitPctSum === 100 ? 'valid' :
  explicitPctSum < 100 ? 'low' : 'over';
```

**Sub-components:**
- `<PaymentRow>` — отдельная строка (label, pct input или read-only badge, days input).
- `<QuickPresets>` — кнопки 30/70, 50/50, 70/30, 20/30/50, Сброс.
- `<SumIndicator>` — badge с цветом по `sumStatus`.

**Layout (Tailwind):**
```tsx
<section className="rounded-md border border-border bg-card p-4 space-y-3">
  <header className="flex items-center justify-between">
    <h3 className="text-sm font-medium">Условия оплаты</h3>
    <SumIndicator status={sumStatus} sum={explicitPctSum + receivingPct} />
  </header>
  <QuickPresets onApply={applyPreset} />
  <div className="space-y-2">
    <PaymentRow label="Аванс клиента" pct={anchor1Pct} days={anchor1Days} onChange={...} />
    <PaymentRow label="При погрузке" pct={anchor2Pct} days={anchor2Days} onChange={...} />
    <PaymentRow label="При прибытии в страну" pct={anchor3Pct} days={anchor3Days} onChange={...} />
    <PaymentRow label="При таможне" pct={anchor4Pct} days={anchor4Days} onChange={...} />
    <PaymentRow label="После получения" pct={receivingPct} pctReadOnly days={anchor5Days} onChange={...} />
  </div>
  <footer className="flex justify-end">
    <Button onClick={handleSave} disabled={!sumValid || saving}>
      {saving ? 'Сохранение…' : 'Сохранить'}
    </Button>
  </footer>
</section>
```

**Presets:**
```typescript
const PRESETS = {
  '30/70': { anchor1Pct: 30, anchor1Days: 7, anchor2Pct: 0, anchor3Pct: 0, anchor4Pct: 0, anchor5Days: 30 },
  '50/50': { anchor1Pct: 50, anchor1Days: 7, anchor2Pct: 0, anchor3Pct: 0, anchor4Pct: 0, anchor5Days: 30 },
  '70/30': { anchor1Pct: 70, anchor1Days: 7, anchor2Pct: 0, anchor3Pct: 0, anchor4Pct: 0, anchor5Days: 30 },
  '20/30/50': { anchor1Pct: 20, anchor1Days: 7, anchor2Pct: 0, anchor3Pct: 30, anchor3Days: 30, anchor4Pct: 0, anchor5Days: 60 },
  'Reset': { anchor1Pct: 100, anchor1Days: 0, anchor2Pct: 0, anchor3Pct: 0, anchor4Pct: 0, anchor5Days: 0 },
};
```

### Component 4: Server action

**File:** `frontend/src/entities/specification/server-actions.ts` (existing — add new function)

```typescript
"use server";

import { z } from "zod";
import { createAdminClient } from "@/shared/lib/supabase/admin";
import { revalidatePath } from "next/cache";

const PaymentSegmentsSchema = z.object({
  advance_percent_from_client: z.number().min(0).max(100),
  payment_deferral_days: z.number().int().min(0),
  payment_on_loading_pct: z.number().min(0).max(100),
  payment_on_loading_days: z.number().int().min(0),
  payment_on_country_arrival_pct: z.number().min(0).max(100),
  payment_on_country_arrival_days: z.number().int().min(0),
  payment_on_customs_clearance_pct: z.number().min(0).max(100),
  payment_on_customs_clearance_days: z.number().int().min(0),
  payment_on_receiving_days: z.number().int().min(0),
}).refine(
  (data) =>
    data.advance_percent_from_client
    + data.payment_on_loading_pct
    + data.payment_on_country_arrival_pct
    + data.payment_on_customs_clearance_pct
    <= 100,
  { message: "Сумма % по anchor'ам 1-4 не должна превышать 100" }
);

export async function updateSpecificationPayment(
  specId: string,
  segments: z.infer<typeof PaymentSegmentsSchema>
) {
  const parsed = PaymentSegmentsSchema.parse(segments); // throws on invalid
  const admin = createAdminClient();
  const { error } = await admin
    .from("specifications")
    .update(parsed)
    .eq("id", specId);
  if (error) {
    console.error("updateSpecificationPayment failed", error);
    throw new Error(error.message);
  }
  revalidatePath(`/quotes/${specId}`); // or quote.id mapping
  return { success: true };
}
```

**Auth:** через session-scoped admin client (как existing server actions). RLS на specifications уже purposed.

### Component 5: Integration в calculation-form.tsx

**Change:** Remove FormRows на lines 143, 160, 175. Insert `<PaymentSegmentsBlock>` на их место.

```tsx
// Before (3 FormRows)
<FormRow label="Аванс клиента">...</FormRow>
<FormRow label="До аванса">...</FormRow>
<FormRow label="До расчёта">...</FormRow>

// After
<PaymentSegmentsBlock
  specId={spec.id}
  initial={{
    advance_percent_from_client: spec.advance_percent_from_client ?? 100,
    payment_deferral_days: spec.payment_deferral_days ?? 0,
    payment_on_loading_pct: spec.payment_on_loading_pct ?? 0,
    payment_on_loading_days: spec.payment_on_loading_days ?? 0,
    payment_on_country_arrival_pct: spec.payment_on_country_arrival_pct ?? 0,
    payment_on_country_arrival_days: spec.payment_on_country_arrival_days ?? 0,
    payment_on_customs_clearance_pct: spec.payment_on_customs_clearance_pct ?? 0,
    payment_on_customs_clearance_days: spec.payment_on_customs_clearance_days ?? 0,
    payment_on_receiving_days: spec.payment_on_receiving_days ?? 0,
  }}
  onSaved={() => router.refresh()}
/>
```

## Data Models

### DB shape (new columns on `kvota.specifications`)

```sql
payment_on_loading_pct          NUMERIC(5,2)  DEFAULT 0  NOT NULL  CHECK (0 <= val <= 100)
payment_on_loading_days         INTEGER       DEFAULT 0  NOT NULL  CHECK (val >= 0)
payment_on_country_arrival_pct  NUMERIC(5,2)  DEFAULT 0  NOT NULL  CHECK (0 <= val <= 100)
payment_on_country_arrival_days INTEGER       DEFAULT 0  NOT NULL  CHECK (val >= 0)
payment_on_customs_clearance_pct  NUMERIC(5,2) DEFAULT 0 NOT NULL  CHECK (0 <= val <= 100)
payment_on_customs_clearance_days INTEGER     DEFAULT 0  NOT NULL  CHECK (val >= 0)
payment_on_receiving_days       INTEGER       DEFAULT 0  NOT NULL  CHECK (val >= 0)
```

### Composite constraint

```sql
CONSTRAINT spec_payment_pct_sum_max
  CHECK (
    COALESCE(advance_percent_from_client, 0)
    + payment_on_loading_pct
    + payment_on_country_arrival_pct
    + payment_on_customs_clearance_pct
    <= 100
  )
```

### TypeScript types (after `npm run db:types`)

Database types regen из Supabase. Existing `Specifications` row type получит 7 новых fields с `number | null` (PostgreSQL NUMERIC ↔ TS number).

## Error Handling

| Failure mode | Detection | User-facing handling |
|---|---|---|
| Sum > 100 (client) | Live validation в `<PaymentSegmentsBlock>` | Red badge + save disabled |
| Sum > 100 (DB CHECK violation) | PostgREST error | Toast "DB rejected: проверьте суммы" |
| % outside 0-100 | HTML5 input + onBlur normalize | Auto-clamp |
| Days < 0 | HTML5 input + onBlur normalize | Auto-clamp to 0 |
| Network failure при save | Server action catch | Toast "Сохранение не удалось, повторите" |
| Legacy spec без новых fields | Server-side `?? 0` defaults | UI starts с anchor 1 = `advance_percent_from_client` или 100 |
| Engine ломается с новым input | Golden master test FAIL | CI block, PR не мержится |

## Testing Strategy

### DB tests
- Apply migration locally → verify 7 columns + 8 constraints exist.
- INSERT с pct = 150 → expect CHECK violation.
- INSERT с pct sum = 110 → expect CHECK violation.
- INSERT с pct sum = 100 → success.

### Backend tests
- Unit test для `build_calculation_inputs` mapping — verify 10 fields populated correctly.
- **Golden master:** `pytest tests/test_calc_engine_golden_master.py` MUST pass без новых diff'ов.
- Snapshot test: для каждого golden fixture, передаём `payment_on_*` = 0 и проверяем что output identical к previous.

### Frontend tests (Vitest)
- `<PaymentSegmentsBlock>` initial render с default state.
- onChange anchor1Pct: 100 → 30 → expect anchor5Pct = 70.
- Sum > 100 → expect warning badge + save disabled.
- Preset «30/70» click → expect state matches PRESETS['30/70'].
- Preset «Сброс» click → expect anchor1 = 100, others = 0.

### Integration tests
- Server action call с invalid sum → Zod throws.
- Server action successful → revalidatePath called.
- (Optional) Playwright E2E: open spec на calc-step, change preset, save, refetch — verify persisted.

## Risks + Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Migration ломает existing ERPS view | Medium | View использует только `advance_percent_from_client` + `payment_deferral_days` — не trogamy. ERPS view migration deferred (Req 6). |
| Golden master fails из-за изменения `time_to_advance_on_receiving` source | High (CI block) | Migration backfill: `UPDATE specifications SET payment_on_receiving_days = client_payment_term_after_upd WHERE client_payment_term_after_upd IS NOT NULL`. |
| User вводит 33.33 + 33.33 + 33.34 = 100 (float drift) | Low | NUMERIC(5,2) хранит точно. Sum check `<= 100` tolerant к малым превышениям. UI normalizes to 2 decimals on blur. |
| Existing API callers (FastHTML legacy) ломаются | Low | Legacy routes использовали single anchor. New columns добавляют, не удаляют — backward-compat. |
| User confusion «зачем 5 anchors если я использую только 2» | Low (UX) | Preset «30/70» по умолчанию заполняет 2 anchors. Anchors 2-4 = 0 → не отображаются в KP экспорте/email если pct = 0 (отдельный fix в exports если потребуется). |

## Open Questions (заранее resolved by user 2026-05-24)

- ✅ Storage shape: 7 columns (not JSONB, not separate table) — confirmed.
- ✅ Anchor count: 5 (matching calc engine эталон) — confirmed.
- ✅ UI placement: calc-step (replacing existing 3 FormRows) — confirmed.

## Out of Scope (carry forward)

- ERPS view migration к multi-segment view → следующий батч (см. Req 6).
- Row 69 (% аванса поставщика) рефактор → существующий single-% сохраняем.
- Email/PDF КП templates с расширенным payment view → отдельный батч.
- Inline edit payment segments в context-panel → возможно в будущем; сейчас только calc-step.
- Auto-fill из legacy `client_payment_terms` free text → НЕТ. МОП заполняет вручную.
