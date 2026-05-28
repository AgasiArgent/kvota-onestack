# Testing 2 → tester feedback triage (25.05.2026)

Тестер: Денис Рогачёв + role-testers (РОП/МОП/РОЗ/СтМОЗ/МОЗ/РОЛ/МОЛ/МВЭД).
Sheet: https://docs.google.com/spreadsheets/d/12rpec26N8jXGjfGBuCgxGYL4d3xSMhp9FfJFYft-KYE/
Fetched as: /tmp/testing2-2026-05-25.csv (392 rows)

## P0 FATAL — drop everything

| ID | Что | Источник | Действие |
|----|----|---------|----------|
| **P0-CALC** | Перевод КП на этап «расчёт» — не грузятся позиции, кнопка «Рассчитать» не работает | Дениса chat msg [04:12]. URL: `/quotes/ec48c1fc-2408-4555-9327-30edc8b66723?step=calculation` | Agent диагностирует, потом fix |
| **P0-NEWBIE** | Роль «Новичок» — белая страница, нет logout, нет надписи | Дениса chat msg [04:12]. Row 38 в sheet | Agent дёрнут — добавить logout button + «Ожидайте распределение» |

## P1 — tester PRIORITY-флаг в sheet

| Row | Где | Что | Источник |
|-----|----|-----|----------|
| 58 | `/quotes/{id}/logistics`, кнопка «Шаблон маршрута» | Страница прыгает вверх | tester МОЛ, PRIORITY |
| 67 | `/procurement/kanban` карточка | Комментарий не тянет в карточку канбана | tester РОЗ + СтМОЗ, PRIORITY |
| 71 | Таможня, таблица грузки | Стоимость каждой позиции (ед и сумм) не выводится | РОЛ + МВЭД, PRIORITY |
| 82 | `/customers` (юр лица) главная | Нет кнопки (вероятно "создать клиента") | РОЗ, PRIORITY |
| 83 | `/procurement` главная | Данные скрыты | РОЗ + СтМОЗ + МОЗ, PRIORITY |

## P2 — direct feedback от Дениса в chat [05:32 + 06:12]

| Тема | Что | Ответ Дениса | Действие |
|------|-----|---------------|----------|
| **Row 19** — split table | done ✅ | «(done)» | Закрыто. Sheet ещё содержит старый текст 25.05.2026 — у тестера cache, попросим Ctrl+Shift+R и перепроверить |
| **Row 38p2** — newbie role | Что входит в права + когда назначается? | «выше ответил» (= белая страница нужна с logout — см. P0-NEWBIE) | См. P0-NEWBIE |
| **Row 43** — auto-distribute + timer | «Таймер МОТ и МОЛ от даты поступления сделки на ЭТАП» — но в sheet продолжают писать «сделка автоматически распределилась» | Уже сделано m325 (timer from stage entry). Но auto-distribute жалобы могут означать pre-#230 observation (21.05.2026 = до нашего deploy). VERIFY на проде после refresh |
| **Row 46** — payment segments | «Сомнительная реализация… могут быть иные условия… Может лучше сделать, как в сертификатах?» (creatable combobox) | REDESIGN: dropdown с preset'ами + кастомные комбинации (как cert types были до Row 73 коллапса). Сейчас 5 anchors фиксированных — добавить «+ Добавить сегмент» с произвольным label. |
| **Row 61** — distribution comment | «не тянет в канбан» + новый вопрос: «Комментарий для распределения МОТ/МОЛ - это отдельно для мот/мол или ошибка при комментарии для МОЗ?» | BUG: distribution comment (Row 61 fix) не отображается в карточке канбана закупок (Row 67 in sheet). И — на странице quote есть 2 поля distribution comment? VERIFY (URL `/quotes/b2a22d6e-026e-491f-a229-d37d1194ae8d`) |
| **Row 66** — filters | «те, что ты добавил пока хватит, **но добавить поисковую строку для IDN**» | ADD: search box по IDN/номеру КП в FilterBar (procurement + logistics + customs queues). + тестер пишет «нет фильтров» 25.05.2026 — возможно cache, попросить refresh |
| **Row 69** — % аванса в КПП-таблице | «неверно, не для каждой позиции, а для **КПП в целом**» | REDESIGN: убрать колонки `% аванса` + `Условия оплаты` из per-row таблицы → поставить как single field над таблицей рядом с валютой/НДС (UI-level + DB-shape — может быть `procurement_orders.advance_pct/payment_terms` ИЛИ агрегат из items). PRIORITY от тестера |
| **Row 70** — XLS upload в КПП | «шаблон из того, что мы качаем 'Скачать XLS'. определяем по артикулу» | UNBLOCKED — match-key = артикул. Можно проектировать. |
| **Row 73** — cert types | «пока хватит, потом поменяем если что» | Closed for now. Но дополнительно: «Дать возможность изменения валюты и в **сертификации, и в расходах**». Currency на cert уже есть (PR #224). На расходах — нет. Добавить currency на kvota.expense_items / similar. |
| **Row 74** — pause stage | «pause/unpause - на усмотрение моз, но **нужно добавить обязательный комментарий**» | ADD: на drag-to-paused или click-to-pause появляется modal с required text «Почему на паузу?» → сохраняется в paused_reason поле (новая column). |

## P3 — other 25.05.2026 feedback из sheet (не упомянуто в chat)

| Row | Где | Что |
|-----|----|-----|
| 44 | `/quotes/{id}/logistics` первый сегмент | «Такой возможности нет» — что именно не работает? UNCLEAR. Спросить у тестера или browser-reproduce. |
| 47 | Расчёт, наценка | Можно ставить наценку ниже 5% (сейчас минимум 5%) — поменять валидацию |
| 62, 63 | Очередь логистики/таможни | Страница прокручивается вверх при нажатии "Назначить"/"Переназначить" — scroll jump bug |
| 68 | Таблица КПП | «Позиции перемешиваются» при копировании из «Позиции заявки» в КПП — ordering bug (ORDER BY clause где-то?) |
| 72 | Таможня, таблица | Десятичные числа округляются в столбце % пошлины при копировании — paste-handler precision bug |
| 75 | Канбан закупок | Добавить кнопку «Переназначить» |
| 76 | Логист, этап логистики | «не работает» — БЕЗ деталей. Browser-reproduce. |
| 77 | Локации главная | Удалить локацию можно только если не используется в КП — добавить FK guard |
| 78 | Локации главная | Не отражаются распределённые КП — joined data missing |
| 79 | Карточка КПП, инф-панель «Участники» | Не указывает дату/время распределения — добавить поле |

## P4 — deferred (batch 23C-1, отдельная сессия)

| Row | Что |
|-----|-----|
| 36 | Calc-step — не тянет цену/сумму в валюте КП. Выводить пошлины/сертификацию для МОП |
| 45 | Calc — убрать выбор типа сделки |
| 48 | Calc — стоимость+сроки логистики на сегмент (не отражая поставщика); реструктура верхней панели |

## P5 — нужно verify на проде после refresh (cache?)

| Row | Что | Подозрение |
|-----|----|------------|
| 19 | Split table обратно? | Cache — попросить тестера Ctrl+Shift+R. Денис уже подтвердил «done». |
| 43 | Auto-distribute продолжается? | Cache OR regression. Verify browser-test. |
| 64, 65, 66 | «нет фильтров» 25.05.2026 | Cache — Денис подтвердил что фильтры есть. Verify. |

## Action plan — батчи

```
P0 (now, parallel):
  - CALC: agent диагностирует → fix → deploy ASAP
  - NEWBIE: agent уже фиксит logout + waiting message

P1 (next batch — 24B):
  - Row 58: scroll jump на «Шаблон маршрута»
  - Row 67: distribution comment в карточку канбана (= Row 61 + 67 combined)
  - Row 71: стоимость per-position в customs cargo table
  - Row 82: missing button on /customers
  - Row 83: «Данные скрыты» на /procurement (вероятно RLS/role gate)

P2 (batch 24C — design changes):
  - Row 46: redesign payment segments → creatable preset combobox (как cert types)
  - Row 66: add IDN search in FilterBar
  - Row 69: % аванса как KPP-level field (UI + DB redesign)
  - Row 73: currency на расходах (extension)
  - Row 74: mandatory pause reason comment

P3 (batch 24D — polish & validation):
  - Row 47: min наценка validation
  - Row 62, 63: scroll preservation на assign
  - Row 68: ordering при копировании в КПП
  - Row 72: decimals paste precision
  - Row 75: reassign button на канбане
  - Row 77, 78, 79: locations + info panel
  - Row 44, 76: BLOCKED — нужны репродукции

P4 (batch 24E):
  - Row 70: XLS upload в КПП с match-key=артикул (можно проектировать)

P5 (verify-only — без кода):
  - browser test: rows 19, 43, 64, 65, 66 на проде с force-refresh

Defer:
  - Row 36/45/48 → batch 23C-1 (отдельная сессия, big spec)
```
