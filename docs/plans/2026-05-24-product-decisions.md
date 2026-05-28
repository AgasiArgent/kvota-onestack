# Product decisions — Testing 2 deferred rows

**Дата обсуждения:** 2026-05-24
**Контекст:** 11 рядов из Testing 2, отложенных из batches 22C+22D потому что нужно продуктовое решение, а не просто фикс.

---

## Group A — Quick decisions (single answer → 30 min code)

### Row 38 ч.2 — роль «Новичок»

**Tester request (РОП):**
> «Добавить роль Новичок - чтобы я мог на нее перекупить людей, которые есть в системе, но не относятся к каому либо отделу. 0 прав - просто голые стены»

**Текущее состояние:**
- В коде роли «Новичок» нет; в DB 12 active roles (memory: migration 168).
- Это **demotion** парковка, а не онбординг.

**Решение:**
- **UX:** пустой dashboard с placeholder «Ожидайте назначения роли. Обратитесь к вашему РОП». Sidebar пустой, все маршруты редиректят сюда.
- **Кто назначает:** `admin` + все `head_of_*` (head_of_sales, head_of_procurement, head_of_logistics).
- **Slug:** `newbie` (англ. для consistency с остальными).

**Реализация (для batch 23A):**
1. Migration: `INSERT INTO kvota.roles (slug, name) VALUES ('newbie', 'Новичок')` + grant 0 permissions.
2. Middleware/route guards: detect `roles.slug = 'newbie'` → redirect to `/awaiting-role` placeholder page.
3. Sidebar (`@/widgets/sidebar`): hide all menu items when current user has only `newbie`.
4. `/admin/users` role-assign popover: allowlist `admin` + `head_of_*` для grant/revoke `newbie` (отдельная проверка от других ролей).
5. Никаких RLS изменений — RLS уже отказывает не-знакомым ролям.

---

### Row 64 + 65 + 66 — фильтры на очередях

**Tester requests:**
- Row 64 (РОЛ/МОЛ/МВЭД, /workspace/logistics): «нет фильтров»
- Row 65 (РОЛ/МОЛ/МВЭД, /workspace/customs): «нет фильтров»
- Row 66 (РОЗ/СтМОЗ/МОЗ, /procurement/kanban): «нет фильтров»

**Решение — фильтры для /workspace/logistics + /workspace/customs:**
1. **Клиент** — multi-select searchable dropdown.
2. **Исполнитель (МОЛ/МОТ/МВЭД)** — multi-select. Показывается только в isHead view (members видят только своё).
3. **Дата входа в этап** — date range (`stageEnteredAt`).
4. **Срочность** — single dropdown: Все / Просрочено / ≤1 день / ≤3 дня / ≤7 дней. Вычисляется из `deadlineAt - now()`.

**Решение — фильтры для /procurement/kanban:**
1. **Клиент** — multi-select searchable.
2. **Бренд** — multi-select searchable.
3. **МОП (закреплённый менеджер)** — multi-select. «Мои КП» для МОП, «по МОП X» для РОП.
4. **МОЗ (исполнитель)** — multi-select. Только в РОЗ/СтМОЗ view.
5. **На этапе > N дней** — single dropdown: Все / >7 / >14 / >30. По `days_in_state`.

**Persistence:** URL params (`?customer=...&urgency=overdue&assignee=...`). Шарабельно, deep-linkable. Совместимо с существующим `?step=...` паттерном.

**Реализация (для batch 23A):**
1. Новый shared component `<FilterBar>` в `@/shared/ui/filter-bar` — общий для 3 страниц.
   - Подкомпоненты: `<MultiSelectFilter>`, `<DateRangeFilter>`, `<UrgencyFilter>`, `<StageAgeFilter>`.
   - URL state via `useSearchParams` + `router.replace` (без navigation).
2. Server fetchers принимают filter params и применяют их в Supabase query.
3. Empty-state: если ни одна карточка не подошла под filters → «Нет карточек по выбранным фильтрам — сбросить?» CTA.
4. Filter chip count badge у каждой колонки канбана (сколько отфильтровано).

---

### Row 73 — упростить типы сертификатов + валюта

**Tester request (РОЛ + МВЭД):**
> «Оставить просто 'Сертификат происхождения', разбивку на разные убрать - луче просто название. Дать возможность изменения валюты и в сертификации, и в расходах»

**Текущее состояние:**
- 10 типов в `SEEDED_TYPES` (frontend/src/features/customs-certificates/ui/certificate-modal.tsx:70-81): ДС ТР ТС, СС, СГР, ОТТС, EUR.1, Form A, CT-1, CT-2, CT-3, A.TR.
- Combobox `creatable` — пользователь может ввести любое значение.
- Стоимость хранится как `cost_rub` (RUB-only).

**Решение — типы (5 вместо 10):**
1. Сертификат происхождения (схлопывает EUR.1 / Form A / CT-1/2/3 / A.TR)
2. СС (Сертификат соответствия)
3. ДС ТР ТС
4. СГР
5. ОТТС

Combobox остаётся creatable — если МВЭД нужен EUR.1 как конкретное обозначение, может ввести вручную.

**Решение — валюта:**
- Добавить поле «Валюта» в форму сертификата + форму расхода.
- Default: валюта КП (consistent с остальным customs-step).
- Список валют — тот же что используется в quotes (RUB / USD / EUR / CNY / etc.).

**Реализация (для batch 23A):**
1. Migration: переименовать `cost_rub` → `cost_original`, добавить `cost_currency text NOT NULL DEFAULT 'RUB'`. Backfill: existing `cost_rub` → `cost_original`, currency = 'RUB'.
2. Тот же паттерн для expense table.
3. UI: добавить `<CurrencySelect>` (если такой есть) рядом с cost input.
4. `SEEDED_TYPES` → новый список 5 типов. Existing сертификаты с типами EUR.1 / Form A / CT-X / A.TR в DB **не мигрируем** — Combobox creatable, они остаются валидными free-text values; в дропдауне их не будет, но в таблице они показываются как есть.
5. Calc engine: проверить что cert/expense cost попадает в калькуляцию с currency conversion (если уже есть FX в калькуляторе — реиспользуем; если нет — отдельный TODO).

---

### Row 70 — XLS upload в КПП-таблицу [DEFERRED]

**Tester request (РОЗ/СтМОЗ/МОЗ):** «нет кнопки»

**Status:** **Отложено** — фича большая, требует отдельного решения по match-key (sales_product_code vs supplier_sku vs row order). Вернёмся позже отдельным батчем.

---

## Group B — Workflow decisions (концептуальные)

### Row 43 — таймер + распределение МОЛ/МОТ

**Tester request (РОЛ + МОЛ + МВЭД):**
> «Сделка автоматически распределилась на МОЛ и МОТ. **ВАЖНО** - ТАЙМЕР ВЫПОЛНЕНИЯ ЛОГИСТИКИ И ТАМОНИ ДОЛЖЕН СТАРТОВАТЬ С МОМЕНТА ОТПРАВКИ СДЕЛКИ НА ДАННЫЙ ЭТАП ВНЕ ЗАВИСИМОСТИ РАСПРЕДЕЛЕН ОН НА СОТРУДНИКА ИЛИ НЕТ»

**Текущее состояние:**
- Auto-assign логистики/таможни существует — `services/workflow_service.py:3224+` («Best-effort: auto-assign logistics managers»), миграция 197 (logistics) + 286 (customs).
- `invoices.{logistics,customs}_deadline_at` = `assigned_at + SLA_DAYS` (вычисляется когда МОЛ назначен).
- Если МОЛ не назначен — deadline = NULL → таймер «no_timer» в UI.

**Решение:**
1. **Убрать auto-distribution.** РОЛ назначает МОЛ/МОТ/МВЭД вручную через assignee picker.
2. **Timer source = stage entry.** Deadline теперь вычисляется от `procurement_completed_at` (момент выхода с этапа закупок = вход на логистику/таможню), а **не** от `_assigned_at`.

**Реализация (для batch 23B):**
1. **Backend:** disable auto-assignment в `services/workflow_service.py` — удалить или закомментировать оба best-effort блока (`3224+` для logistics, `3251+` для customs).
2. **DB:** изменить вычисление `logistics_deadline_at` / `customs_deadline_at`:
   - Option A (trigger): trigger на UPDATE `procurement_completed_at` → set deadline = procurement_completed_at + SLA_DAYS_per_domain.
   - Option B (view/computed): deadline вычисляется в queries как `procurement_completed_at + SLA`. Меньше DB-churn, но дублируется в каждом fetcher.
   - **Recommended: Option A** — single source of truth, у нас уже есть paradigm с триггерами.
3. Migration: backfill existing rows — `UPDATE invoices SET logistics_deadline_at = procurement_completed_at + INTERVAL '{SLA_LOGISTICS} days' WHERE procurement_completed_at IS NOT NULL` (same for customs).
4. UI: stage-timer-badge.tsx + sla-timer-badge.tsx уже основаны на `stageEnteredAt` / `assignedAt ?? stageEnteredAt` — должны корректно работать после migration. Verify post-deploy.

---

### Row 74 — стадия «пауза» в канбане

**Tester request (РОЗ + СтМОЗ + МОЗ):**
> «Необходим этап "пауза"»
> «Просто нужно сделать колонку в канбане, в которую можно перенести сделку. Так бывает что нужно поставить сделку «на паузу»»

**Решение:**
- **Shape:** Новая 5-я колонка `paused` в procurement-kanban — обычная substate, drag-to-pause + drag-out-to-unpause работают как с другими columns.
- **Permission:** Все procurement-роли + admin могут перемещать карточки в/из «Пауза» — без модала, без обязательного комментария.
- **Таймер:** `days_in_state` для substate `paused` = сколько уже на паузе. Это уже работает автоматически (стандартная substate-логика). Никаких дополнительных колонок не нужно.
- **Возврат с паузы:** user перетаскивает карточку в нужную substate-колонку (как обычно). UI не делает «возврат к предыдущей» — слишком implicit.

**Реализация (для batch 23B):**
1. Migration: добавить `paused` в DB enum `procurement_substatus` + в `PROCUREMENT_SUBSTATUSES` в `frontend/src/shared/lib/workflow-substates.ts`.
2. `kanban-board.tsx`: новая 5-я column в render — между `negotiating` и end, или в конце (на твой выбор по wireframe — recommended: в конце).
3. Sort order: cards в `paused` сортируются по newest-paused-first (`updated_at desc`).
4. Никаких extra fields на `quotes` / `quote_brand_substates` — substate `paused` сам по себе достаточен.
5. Visual: column header серый/мьютед — отличается от активных колонок чтобы было ясно что это «парковка».

---

### Row 19 — split-table → toggle (re-decision)

**Tester request (6 testers — РОЗ + СтМОЗ + МОЗ + РОЛ + МОЛ + МВЭД):**
> «Таблица с разделением на Требует вашего действия и Остальные»

8 testers persistent flag (memory). Сильный negative signal.

**Текущее состояние:**
- `DataTable.rowGrouping` с `predicate: (q) => actionStatusSet.has(q.workflow_status)` (`quotes-table-client.tsx:360`).
- 2 visible groups: «Требует вашего действия» (top) и «Остальные».
- `actionStatuses` зависит от роли (sales = draft+confirmation_pending, procurement = pending_procurement, etc.).

**Решение:**
- Заменить `rowGrouping` на **filter-toggle в toolbar**: «Только требует действия» (off by default).
- Когда off → один единый список со всеми КП (текущая сортировка по дате).
- Когда on → показывает только actionable rows.
- Toggle state в URL (`?onlyAction=true`) — sharable/persistent.

**Реализация (для batch 23B):**
1. `quotes-table-client.tsx`: убрать `rowGrouping={...}` prop из `DataTable`.
2. Добавить `Toggle` (shadcn) в toolbar `DataTable` — рядом с search. State через `useSearchParams`.
3. Filter rows локально или на server (recommended — local, т.к. список не большой и `actionStatusSet` уже клиентский).
4. Удалить связанный код в `procurement-distribution/api/server-queries.ts:150,187` если он отрабатывал под прежнюю логику (или адаптировать toggle-aware).

---

### Row 61 — поле «Информация для распределения заявки»

**Tester request (РОП + МОП):**
> «Нет поля 21.05.2026»

**Browser verify (2026-05-24, prod, admin):** поле УЖЕ есть в коде —
`transfer-dialog.tsx:368-376` (id=`checklist-distribution-comment`,
label «Комментарий для распределения», placeholder «Опционально: уточнения для МОЛ/МОТ»).

**Гипотеза почему тестер не видит:**
1. **Discoverability:** modal `sm:max-w-md` (~448px) — 4 checkbox'а + radio + длинная обязательная textarea «Что это за оборудование...» перед distribution_comment. Тестер не доскроллил.
2. **Permanence:** после отправки в закупки modal недоступен, и нет surface для МОП чтобы добавить/исправить comment позже.

**Решение:**
- **Promote** distribution_comment в визуально заметное место + сделать always-editable:
  - Добавить inline-блок «Комментарий для распределения» **поверх позиций** на sales-step (рядом с действиями) — текстовое поле, autosave on blur (debounce 500ms).
  - Modal в `transfer-dialog.tsx` остаётся как есть (back-compat для МОПов которые уже привыкли там видеть).
  - Synced state: оба места пишут в один и тот же путь `quotes.sales_checklist.distribution_comment` через server action.
- После отправки → блок виден на context-panel (уже работает через `sales-checklist-block.tsx`) + becomes **editable** для МОП/РОП.

**Реализация (для batch 23B):**
1. New component `<DistributionCommentInline>` в `frontend/src/features/quotes/ui/sales-step/`.
2. Position: между header-card и items-grid на sales-step page.
3. Server action `updateDistributionComment(quoteId, comment)` (или reuse existing `submitToProcurementWithChecklist` с partial update).
4. Editable также в `context-panel/sales-checklist-block.tsx` — добавить edit-button и inline edit для МОП/РОП.
5. Sync: form state в transfer-dialog читает initial value из quote.sales_checklist.distribution_comment если есть (already does).

---

## Group C — Большие фичи (калькулятор переработка)

### Row 36 / 45 / 46 / 48 — переработка calculation-step

**Tester quotes:**
- **Row 36 (РОП + МОП):** «Не тянет Цену в валюте КП, Сумму в валюте КП. На этапе расчета необходимо выводить инфморацию о пошлинах и сертификации. Чтобы МОП ориентировался в КП»
- **Row 45 (РОП + МОП):** «Выбор типа сделки присутствует»
- **Row 46 (РОП + МОП):** «На данный момент, мы предоставляем любые условия оплаты - 30/70, 70/30, 50/50 и тд. Также есть комбинированные 20/30/50 и тд. На каждый сегмент указать сроки оплаты в календарных днях. Важно выделить - Срок оплаты Аванса Клиентом, Срок оплаты Клиентом после отгрузки Товара»
- **Row 48 (РОП + МОП):** «Данных нет»

**Текущее состояние calc-form (`calculation-form.tsx`):**
Тип сделки → Инкотермс → Валюта КП → Наценка % → Аванс клиента → До аванса → До расчёта → Тип → Сумма.

**Constraint:** `calculation_engine.py` + models + mapper — **LOCKED** (CLAUDE.md). Любые новые поля проходят через `build_calculation_inputs()` mapping.

**Частичные решения:**
- **Row 45 — Тип сделки:** переезжает в «Контрольный список» modal (рядом с is_estimate / is_tender). Field на calc-step становится read-only / убирается.
- **Row 48 — Стоимость логистики:** auto-pull из logistics-step (Σ `main_cost_rub` сегментов). Read-only на calc. Если logistics пуста — «Данных нет из логистики».

**Отложено (Row 46 — сегментация платежей):**
- Слишком большая тема. Уходит в отдельный spec session с design pass:
  - Свободная vs preset сегментация
  - % + дни + тип (Аванс/После отгрузки)
  - Validation: sum = 100%
  - Storage shape (`payment_segments` JSONB?)
  - Связь с Row 69 (% аванса в КПП-таблице) — единый источник?
- См. отдельный батч **23C-2** ниже.

**Row 36 — пошлины + сертификация на calc:** дополнительные read-only output поля. Источник:
- Пошлины — из customs-step (`customs_item.duty_rate * purchase_price`?). Sum в валюте КП.
- Сертификация — Σ cost из customs-certificates (после Row 73 — с валютой).
- Показать рядом с Total в результатах.

**Реализация (для batch 23C-1 — только Row 36, 45, 48):**
1. Migration: `quotes.deal_type` уже есть, переместить ввод в `transfer-dialog.tsx` (Контрольный список modal).
2. `calculation-form.tsx`: убрать FormRow "Тип сделки" (line 49). Сделать read-only display.
3. `calculation-results.tsx`: добавить read-only поля:
   - «Стоимость логистики (Σ из logistics)»
   - «Пошлины (Σ из customs)»
   - «Сертификация (Σ из customs)»
4. Server fetch: aggregate query — `logistics_route_segments.main_cost_rub` + `customs_items.*` + `customs_certificates.cost_*`.
5. Golden master suite: run после любого изменения mapping в `build_calculation_inputs()` — гарантируем что добавление input-полей не ломает существующий расчёт.

**Batch 23C-2 (отложено):**
- Row 46 (сегментация платежей) + Row 69 (КПП-таблица % аванса) — связаны. Отдельная сессия с design pass.

---

## Group D — Прочее

### Row 69 — % аванса + Условия оплаты в КПП-таблице

**Tester request (РОЗ + СтМОЗ + МОЗ, 21.05.2026):**
> «нет ячеек»

**Verify:**
- PR #190 (2026-05-20) добавил колонки `advance_to_supplier_percent` («% аванса», 60px) + `supplier_payment_terms` («Условия оплаты», 160px) в `procurement-handsontable.tsx:1110-1126`.
- Тестер логировал на следующий день после deploy — скорее всего кеш браузера.

**Решение — UX полировка:**
- Колонки уже есть, но «% аванса» = 60px — заголовок «% аванса» wrap'ается / тесно для 3-х значного числа (100). Расширить до 90px.
- Добавить tooltip-help на column header («Процент авансового платежа поставщику, 0-100») — для онбординга новых МОЗ.
- В tester-note (для следующего round): «Проверьте после hard refresh — колонки добавлены 20.05».

**Реализация (для batch 23A — minor polish):**
1. `procurement-handsontable.tsx:1163`: `width: 60` → `width: 90` для advance.
2. Опционально добавить header tooltip — но Handsontable v17 не имеет built-in header tooltips, придётся custom cellProperties.afterRenderer на header row. Возможно skip — слишком много для polish.

**Note про Row 46 связь:**
- Когда landed Row 46 (сегментация платежей клиента) — может потребоваться рефактор `advance_to_supplier_percent` (поставщик) в аналогичную структуру. Открытый вопрос: одинарное % vs сегментированное? Решим в batch 23C-2.

---

## Batches plan (финал, 2026-05-24)

### Batch 23A — Quick decisions + polish (параллельные worktrees)

| Row | Что | Сложность | Risk |
|---|---|---|---|
| 38p2 | Роль «Новичок» (newbie): migration + RLS + sidebar/routes guard + /admin/users role-assign allowlist | M | DB schema change |
| 64+65+66 | `<FilterBar>` shared component (5 фильтров для logistics/customs + 5 для procurement), URL-persistent state | L | Side-effects на queue fetching |
| 73 | Cert types: 5 вместо 10, add currency field в cert + expense forms, migration `cost_rub` → `cost_original` + `cost_currency` | M | Calc engine FX mapping |
| 69 | Polish: width 60→90 для % аванса column | S | None |

### Batch 23B — Workflow decisions (sequential)

| Row | Что | Сложность | Risk |
|---|---|---|---|
| 43 | Disable auto-distribute logistics/customs + change deadline source to `procurement_completed_at` + backfill migration | M | Trigger logic, existing data backfill |
| 74 | Substate `paused` (5-я колонка в kanban): enum, board column, drag-and-drop | S | None |
| 19 | Replace `rowGrouping` на toolbar toggle «Только требует действия» (URL param) | S | Removes UI element 8 testers complained about |
| 61 | Inline `<DistributionCommentInline>` блок на sales-step + edit-button в context-panel | S | Sync state с transfer-dialog |

### Batch 23C-1 — Calc partial (не блокируется design pass'ом)

| Row | Что | Сложность | Risk |
|---|---|---|---|
| 45 | Переезд «Тип сделки» в transfer-dialog modal | S | Remove from calc form |
| 48 | Auto-pull стоимости логистики на calc-results (read-only Σ из logistics) | M | New query |
| 36 | Auto-pull пошлин + сертификации на calc-results (read-only Σ из customs) | M | New query |

### Batch 23C-2 — Calc redesign (отдельная сессия, требует design pass)

| Row | Что | Сложность | Risk |
|---|---|---|---|
| 46 | Сегментация платежей клиента (свободная / preset, % + дни + тип Аванс/После отгрузки) | XL | Calc engine input mapping |
| 69 (рефактор) | Возможно перевести `advance_to_supplier_percent` в аналогичную сегментацию | L | Schema migration |

**Wireframe / design tasks для 23C-2:**
- Storage shape (`payment_segments JSONB` vs separate table)
- Validation: sum=100%, days non-negative
- Связь с КПП-таблицей (Row 69) — единый источник или две стороны
- UI placement: на calc или в context-panel

### Row 70 (XLS upload) — отложено целиком

Большая фича — match-key dilemma + column mapping UI. Возвращаемся позже отдельным батчем.

---

## Сводка

- **9 рядов закрыто решениями**: 38p2, 64-66, 73, 19, 43, 74, 61, 36, 45, 48, 69 (Group D)
- **1 ряд отложен**: 70 (XLS upload)
- **1 ряд в большой sessions**: 46 (сегментация платежей) — Batch 23C-2

**Total ship-able PRs в batches 23A + 23B + 23C-1:** ~10 PRs.
