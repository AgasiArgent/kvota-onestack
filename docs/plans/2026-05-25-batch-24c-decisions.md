# Batch 24C — product decisions (25.05.2026)

Ответы пользователя на 7 кластеров вопросов после tester feedback на batches 23A/23B/23C-2.

## Q1 — Row 67 + Row 61 (distribution comment в карточке канбана) — DEFERRED

**Тестер:**
- Sheet Row 67: «Комментарий не тянет PRIORITY» (в карточке канбана procurement)
- Chat: «Комментарий для распределения МОТ/МОЛ — это отдельно для мот/мол или ошибка при комментарии для МОЗ?»

**Решение:** «Не знаю, спрошу позже».

**Default-стратегия:** предположение что Денис видит одно поле distribution comment (от МОП) и UI-лейбл его сбил с толку. План — вытянуть это поле в карточку канбана + переименовать лейбл если надо. До ответа Дениса работу не начинаем.

## Q2 — Row 46 (payment segments redesign) — KEEP AS IS

**Тестер:** «Сомнительная реализация… Может лучше сделать, как в сертификатах?» (creatable combobox)

**Решение:** «Оставить 5 фиксированных anchor events, как в excel. Мудрить не будем».

**Scope:** опционально — UX-полиш labels если найдём проблему на проде, без structural rework.

## Q3 — Row 47 (наценка минимум) — HARD STOP 5%

**Тестер:** «Можно поставить ниже. В дальнейшем сделаем функционал согласования, но сейчас не ниже 5%»

**Решение:** «Hard stop 5%, ниже Рассчитать не работает».

**Scope:** добавить frontend validation на input «Наценка %» — < 5% → disable кнопка «Рассчитать» + inline ошибка. Backend validation в `/api/calculate` — отвергать 400 с code `MARKUP_TOO_LOW`.

## Q4 — Row 69 (% аванса + условия оплаты в КПП) — PER-INVOICE

**Тестер:**
- Sheet: «УБРАТЬ %АВАНСА И УСЛОВИЯ ИЗ ТАБЛИЦЫ. И ОСТАВИТЬ ЯЧЕЙКУ НАД ТАБЛИЦЕЙ В ПОЛЕ, ГДЕ НАХОДИТСЯ ВАЛЮТА И НДС. **PRIORITY**»
- Chat: «не для каждой позиции, а для КПП в целом»

**Решение:** «Per-supplier и per-invoice. Два разных инвойса от одного суплаера могут иметь разные цены из-за разных условий оплаты».

**Scope:**
- DB: переместить `advance_pct` + `payment_terms` с position-level (kvota.procurement_items или similar) на invoice-level (kvota.invoices). Migration с backfill — первое значение из items группы.
- UI: per-invoice header-блок над каждой группой позиций в КПП-таблице (рядом с currency / VAT — те поля уже per-invoice).
- API: обновить endpoint /api/procurement/invoices/{id} — добавить advance_pct + payment_terms в payload.
- Tests: backfill correctness, multi-invoice case, UI re-render at invoice header.

## Q5 — Row 70 (XLS upload в КПП) — UNBLOCKED

**Тестер:** Match-key = артикул от МОП. Шаблон = тот же что «Скачать XLS».

**Решение по 4 edge case'ам:**

| Case | Behavior |
|------|----------|
| Новый артикул (в XLS, не в КПП) | **Skip + warning toast** «N артикулов не найдены в КПП: [list]» |
| Удалённый артикул (в КПП, не в XLS) | **Оставить как есть** (preserve existing values) |
| Дубликат артикула в XLS | **Reject upload + error** «Дубликаты артикулов: [list]» |
| Поля для update | **Все** из шаблона (цена, qty, страна, condition, и т.д.) |

**Scope:**
- Frontend: «Загрузить XLS» button на КПП-table, file picker, парсинг via xlsx lib.
- Backend: новый endpoint `/api/procurement/{quote_id}/import-xls` — принимает FormData с файлом, возвращает 200 с `{updated, skipped[]}` или 400 с `{error: "DUPLICATES", duplicates[]}`.
- Tests: все 4 edge cases + happy path.

## Q6 — Row 74 (mandatory pause reason) — ACTIVITY LOG + INLINE LAST + ALL

**Тестер:** «pause/unpause - на усмотрение моз, но нужно добавить обязательный комментарий почему на этот этап кидаем»

**Решение:**

| Параметр | Решение |
|----------|---------|
| Хранение | **Activity log** — история всех пауз с датами + comment |
| После unpause | **Inline display** — последний reason виден в карточке/info-panel без открытия модалки |
| Видимость | **Все procurement** (РОЗ + СтМОЗ + МОЗ + admin) |

**Scope:**
- DB: новая таблица `kvota.procurement_pause_log` (или extend существующего activity log) — columns: quote_id, paused_at, paused_by, reason, unpaused_at, unpaused_by.
- UI: при drag-to-paused или click-to-pause — modal с required textarea «Почему на паузу?». При unpause — auto-clear modal не нужен, просто запись unpaused_at.
- Inline display: в карточке канбана для квот в «На паузе» — показать последний reason + кто поставил.
- Tests: pause requires reason, history persists across multiple pause/unpause cycles, visibility for all procurement roles.

## Q7 — Row 36 + Row 48 (calc-step main page redesign)

**Тестер:**
- Row 36: «На этапе расчета необходимо выводить инфморацию о пошлинах и сертификации»
- Row 48: «Необходимо указать стоимость логистики для данного заказа»

**Решение:**

| Параметр | Решение |
|----------|---------|
| Расположение | **(a) Info card** сверху таблицы позиций |
| Поля | **Логистика per-invoice** + пошлины + сертификаты + similar (per-item где применимо) |
| Логистика source | **Auto-pull** из логистического этапа. «Не может быть не заполнено» = error state, требует заполнение в логистике |

**Scope:**
- Frontend: новый компонент `<CalcStepInfoCard>` сверху таблицы позиций на calc-step.
- Поля для display:
  - Per-invoice: стоимость логистики (auto-pull)
  - Per-quote или per-item: % пошлины, код ТН ВЭД, тип сертификата(ов), стоимость сертификата
- API: расширить endpoint /api/quotes/{id}/calculation-data — вернуть logistics_cost_per_invoice, customs_duties, certifications.
- Edge case: если логистика не заполнена → не блокировать UI calc-step, но показать предупреждение «Стоимость логистики не указана — заполните на логистическом этапе».
- Tests: info card renders correctly, pulls from logistics stage, handles empty state gracefully.

## Q8 (bonus) — Row 75 (procurement reassign permissions) — DEFERRED

**Контекст:** PR #217 уже даёт reassign на procurement kanban (admin / РОЗ / СтМОЗ). Тестер написал «добавить кнопку» — нужно ли расширить на регулярных МОЗ?

**Решение:** не задавали, defer.

**Default-стратегия:** оставить как есть в PR #217 (admin/РОЗ/СтМОЗ). Если тестер пожалуется что МОЗ не может — open follow-up.

---

## Action plan для batch 24C — redesigns

### Phase 1 (ready to dispatch — после /compact):
1. **Row 47** — hard stop 5% валидация (small, 1-2 файла)
2. **Row 70** — XLS upload в КПП (medium, new endpoint + UI)
3. **Row 74** — mandatory pause reason + activity log (medium, new table + UI flow)

### Phase 2 (нужна DB migration):
4. **Row 69** — % аванса per-invoice (DB migration + backfill + UI restructure) — m327
5. **Row 36+48** — calc-step info card (API extension + UI component)

### Phase 3 (нужен ответ Дениса):
- **Row 67/61** — distribution comment в карточке канбана (waiting for screenshot/clarification)
- **Row 46** — UX polish if needed (waiting for problem report)

### NO-OP (уже сделано, попросить тестера refresh):
- Row 75 (PR #217)
- Row 68 (PR #214)
- Row 19 (PR #229 = done per Денис)

### Полишинг unambiguous (in flight as PR #236, #237, #238, #239)
- Row 45 — remove deal type → #237
- Row 66 — IDN search → #239
- Row 79 — distribution date label → #238
- #118 overflow regression → #236
