# Testing 2 — Bug Triage (2026-05-22)

**Source:** Google Sheets "Testing 2" tab (`/tmp/testing2-20260522.csv`, 302 lines)
**Sheet last update visible:** 21.05.2026 stamps in row 19/40/41/42/57/61
**Previous triage:** [2026-05-13-testing2-bugs.md](./2026-05-13-testing2-bugs.md)
**Previous tester note:** [2026-05-14-tester-note.md](./2026-05-14-tester-note.md), [2026-05-21-tester-note.md](./2026-05-21-tester-note.md)

## Status of 13.05 triage

Closed (per 14.05 tester note): rows 1–18 (customs/locations/cargo/kanban), 20, 22, 23, 25, 26, 27.
Punted to data/clarification (per 14.05): rows 12 (МОЛ assign), 24 (Q-202605-0008 address dropdown), 28, 29.
Product decision (not a bug): row 19 (split table). **Re-flagged 21.05 by tester with new stamps — needs revisit.**

## New since last triage

31 actionable rows. Categorized below.

---

## A. Quick UI fixes (recommended first batch — small risk, visible wins)

| Row | Page | What | Roles | Notes |
|---|---|---|---|---|
| 40 | `/workspace/logistics` | "Исполнитель" col shows email → show ФИО | РОЛ, МОЛ | Display-only |
| 41 | `/workspace/customs` | same as row 40 (customs queue) | РОЛ, МВЭД | Shared component |
| 31 | `/quotes/{id}?step=sales` Таблица | Dropdown в Ед.изм. шириной с ячейку, видно микро | РОП, МОП | Probably Radix `Select` width prop |
| 32 | `/messages` загрузка файла | `.xlsm` (macroenabled Excel) blocked at mime check | **ALL 8 ROLES** | Add `application/vnd.ms-excel.sheet.macroenabled.12` to allowlist |
| 58 | `/quotes/{id}` editor маршрута | "При введении данных страница обновляется" | МОЛ | **PROBABLY FIXED** by `fb84a056` (PR #186) — ask tester to Ctrl+Shift+R |

## B. Backend bugs (need investigation)

| Row | Page | What | Roles |
|---|---|---|---|
| 42 | `/quotes` главная | "Сумма КП на этапе расчета тянется" — value showing where shouldn't | ALL 8 |
| 57 | `/quotes/{id}?step=procurement` | "Завершил закупку — этап не перешел на логистику/таможню" | РОЗ, СтМОЗ |
| 47 | `/quotes/{id}?step=calculation` Наценка | Validation: markup <5% allowed | РОП, МОП |
| 79 | `/quotes/{id}` Закупки Q-202605-0021 Уч-ки | Дата/время распределения не отображаются | РОЗ, СтМОЗ, МОЗ |
| 72 | `/quotes/{id}?step=customs` Таможня | "Десятичные округляются при копировании % пошлины" | РОЛ, МВЭД |
| 68 | `/quotes/{id}?step=procurement` КПП | "Позиции перемешиваются" при переносе из позиций заявки | РОЗ, СтМОЗ, МОЗ |
| 76+78 | logist access | МОЛ "нет доступа к распределенной заявке" + "не отражаются распределенные КП" | МОЛ |
| 62+63 | очереди логистики/таможни | "Страница прокручивается вверх" при клике на Назначить | РОЛ, МОЛ, МВЭД |

## C. Feature requests (need product input — defer or split out)

| Row | Page | Ask | Roles |
|---|---|---|---|
| 19 | `/quotes` | Re-iterate: убрать разделение таблицы (8 testers continue to flag) | ALL 8 — needs product re-decision |
| 36 | `/quotes/{id}?step=calculation` | "Не тянет Цену/Сумму в валюте КП" + добавить пошлины/сертификация | РОП, МОП |
| 38 | `/admin/users` | Новая роль "Новичок" (0 прав) + убрать Алёну/Лиану с таможни | РОП |
| 44 | logistics 1st сегмент | Опция: поставщик везёт за свой счёт | РОЛ, МОЛ, МВЭД |
| 45 | calc Компания | Убрать выбор типа сделки — он должен быть на создании КП | РОП, МОП |
| 46 | calc Условия оплаты | Сегментация (30/70/50/etc.) + сроки в днях per segment + аванс/после отгрузки | РОП, МОП |
| 48 | calc главная | Поле "стоимость логистики" + сроки поставки/логистики | РОП, МОП |
| 61 | Контрольный список | Поле "Информация для распределения заявки" | РОП, МОП |
| 64+65+66 | очереди + канбан | Добавить фильтры | РОЛ/МОЛ/МВЭД + РОЗ/СтМОЗ/МОЗ |
| 67 | канбан карточка | На карточке: комментарий, тег Тендер, дата распределения | РОЗ, СтМОЗ |
| 69 | КПП ячейки | Добавить % аванса + Условия оплаты | РОЗ, СтМОЗ, МОЗ |
| 70 | КПП XLS upload | Кнопка "Загрузить xls" с мэппингом колонок | РОЗ, СтМОЗ, МОЗ |
| 71 | Таможня cargo | "Данных нет" — Валюта КПП, Стоимость, Кол-во, Ед.изм. | РОЛ, МВЭД |
| 73 | Customs cert модалка | Упростить типы сертификатов + currency choice | РОЛ, МВЭД |
| 74 | канбан стадии | Добавить стадию "пауза" | РОЗ, СтМОЗ, МОЗ |
| 75 | канбан | Кнопка переназначения | РОЗ, СтМОЗ, МОЗ |
| 77 | locations | Удаление/изменение только если не используется в КП | РОЛ, МОЛ, МВЭД |
| 43 | workflow | Распределение МОЛ/МОТ должно быть ручным + таймер с этапа отправки, не с распределения | РОЛ, МОЛ, МВЭД |

## D. Data / admin tasks (manual, not code)

| Row | What | Action |
|---|---|---|
| 37 | "Удалить клиентов без ИНН" | SQL cleanup on `kvota.customers` |
| 38 (part 2) | "Убрать Алёну/Лиану с роли таможни" | DELETE from `kvota.user_roles` |

## E. Cross-references with today's wins (envelope refactor + m319)

None of these new bugs touch the envelope refactor surfaces (no `[object Object]` reports in this wave). The 21.05 tester-note fixes still need browser-verification.

---

## Recommended next batch (BATCH-22A)

**5 quick-win items, all proddable today, mix of frontend/backend:**

1. **Row 32** — `.xlsm` mime allowlist (8 ROLES BLOCKED) — `urgent`
2. **Row 40+41** — email → ФИО in logistics/customs queue table (shared component fix)
3. **Row 31** — dropdown width on sales table (likely 1-line CSS/prop)
4. **Row 47** — markup <5% validation
5. **Row 58** — verify fix already shipped (PR #186), just communicate to tester

**Stretch / next session:**
- Row 42 (KP sum display) — needs spec clarification first
- Row 57 (workflow stuck) — needs reproduce
- Row 62+63 (scroll-to-top) — DOM event bug
- Row 76+78 (МОЛ access) — RLS investigation

**For product (NOT for this batch):**
- Row 19 — split table re-decision
- Row 36/45/46/48 — calculation page restructuring (large)
- Row 38 — Новичок role design
