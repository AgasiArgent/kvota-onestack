# Bug & UX Analysis Report

**Generated:** 2026-03-10
**Sources:** denis.r@masterbearing.ru (78 items), lliubov.d@masterbearing.ru (14 items)
**Total:** 92 items (76 new, 16 resolved)
**Focus:** UX/UI items first, then functional bugs/suggestions

---

## Summary

| Category | New | Resolved | Total |
|----------|-----|----------|-------|
| UX/UI (design, layout, fonts) | 14 | 0 | 14 |
| Bug (functional) | 20 | 16 | 36 |
| Suggestion (new features) | 24 | 0 | 24 |
| **Total** | **76** | **16** | **92** |

---

## Batch Plan

| Batch | Area | Items | Priority | Status |
|-------|------|-------|----------|--------|
| 0 | Design system foundation | 2 | DONE | ✅ Completed (commits e6e3634, 122dea1, c81a043) |
| A | Customer pages | 18 | HIGH | 🔄 In progress (list: b0eaf94, detail tabs: 96f860f, general: cc45dd9) |
| B | Quote pages | 18 | HIGH | 🔄 In progress (list: 33a9837/e65b64c, summary: 96f860f, overview: 266482d, new form: cc45dd9) |
| C | General pages (dashboard, tasks, changelog, training) | 10 | MEDIUM | ✅ Triaged 2026-03-19: 8 resolved, 1 obsolete, 1 backlog |
| D | Calls | 4 | MEDIUM | ✅ Triaged 2026-03-19: 3 resolved (15e07d9), 1 obsolete |
| E | Logistics / Customs / Procurement | 8 | LOW | 🔄 Triaged 2026-03-19: 1 resolved, 3 duplicates merged, 4 unique open |
| F | Other (telegram, settings, chat) | 5 | LOW | ✅ Triaged 2026-03-19: all resolved (chat: 6906770, telegram: 368f817) |
| G | New feedback (2026-03-16) | 5 | MEDIUM | ⬜ New — added 2026-03-19 |

---

## Batch 0: Design System Foundation ✅ DONE

Global CSS changes applied project-wide:
- Font: Manrope → Inter
- Removed all `transition: all` (39 instances)
- Removed all hover `translateY` lifts (cards, nav, stat-cards, buttons)
- Flattened all badge gradients to flat backgrounds
- Primary buttons: gray → blue (#3b82f6)
- Headings: added Inter font-family rule
- All button gradients → flat blue

---

## Batch A: Customer Pages (18 items)

### A1. Customer List `/customers` — UX overhaul

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 1 | FB-260310195138 | ux_ui | 1-убрать ненужные блоки (занимают место) 2-перенести в одну линию 3-удалить кнопку поиска (сделать фильтр при вводе) 4-перенести в линию 5-добавить кнопку проверки контрагента (pop-up) 6-удалить кнопки (название кликабельно) 7-изменить колонки (Наименование, ИНН, Менеджер, Статус) 8-сводку по компаниям над таблицей мелким шрифтом | ✅ Points 1,6,7,8 done. Point 5 (контрагент popup) deferred |
| 2 | FB-260310092200 | suggestion | Сделать таблицу меньше (по примеру КП), добавить столбик МОП | ✅ Done (b0eaf94) |
| 3 | FB-260224091454 | suggestion | Выровнять блоки. Таблица: Название, ИНН, Статус, ФИО МОП. Добавить проверку по ИНН | ✅ Done (b0eaf94) |
| 4 | FB-260310112031 | suggestion | Фильтрация клиентов по менеджерам/группам (lliubov) | ⬜ |
| 5 | FB-260225063421 | bug | Добавлял Санофи Восток, но не отображается | ⬜ |
| 6 | FB-260227105552 | bug | Не вижу заведенного клиента (ИНН 2367010021) — отображать клиентов направления (lliubov) | ⬜ |

### A2. Customer Detail `/customers/{id}` — General tab

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 7 | FB-260310200403 | ux_ui | 1-проверить отступы+шрифты 2-цвет/размер кнопки (единый дизайн с КП) 3-удалить/заполнить блок 4-шрифт меньше (Дата, IDN, Статус), проверить переводы статусов 5-=//= | ✅ Compact fonts, accent links (cc45dd9) |
| 8 | FB-260310110954 | suggestion | Добавить ручное добавление ссылки на rusprofile.ru | ⬜ |
| 9 | FB-260310094251 | suggestion | Добавить сферу клиента (торг.орг/производство/лаборатория/ТО/гос/учебное) | ⬜ |
| 10 | FB-260310104018 | suggestion | Добавить резидент/нерезидент или страну компании | ⬜ |
| 11 | FB-260310093853 | suggestion | Холдинг, вкладка Compliance, Категория клиента | ⬜ |
| 12 | FB-260225103127 | suggestion | Добавить ответственного МОП по клиенту | ⬜ |
| 13 | FB-260227105317 | suggestion | Закрепление нескольких ответственных (lliubov) | ⬜ |
| 14 | FB-260310111855 | suggestion | Закрепление нескольких менеджеров за клиентом (lliubov) | ⬜ |
| 15 | FB-260310111937 | suggestion | Взаимосвязь между компаниями (единые владельцы/закупки) (lliubov) | ⬜ |

### A3. Customer Detail — Tabs

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 16 | FB-260310200808 | ux_ui | Контакты: уменьшить шрифт, текст съезжает, нельзя удалить контакт? | ✅ Font 13px (96f860f) |
| 17 | FB-260310200929 | ux_ui | Запрашиваемые позиции: уменьшить шрифт, статус не тянет? | ✅ Font 13px (96f860f) |
| 18 | FB-260310201027 | ux_ui | Звонки: дублируется текст | ✅ Fixed (96f860f) |
| 19 | FB-260310201205 | bug | КП: дату первой колонкой, переводы статусов | ✅ Done (96f860f) |
| 20 | FB-260310200614 | bug | Адреса: разделить — Блок1 (Юр,Факт,Почтовый), Блок2 (склады). Отступы/шрифты | ✅ Done (029f6b6) |
| 21 | FB-260310112718 | bug | Адреса: не могу руками добавить юр лицо, не сохраняет | ⬜ |
| 22 | FB-260310091406 | suggestion | Контакты: уменьшить таблицу | ⬜ |
| 23 | FB-260302074402 | suggestion | Звонки: открыть звонок для чтения комментов, увеличить текст | ⬜ |

### A4. Customer Contacts

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 24 | FB-260310094345 | bug | Форма нового контакта: поправить отображение | ⬜ |
| 25 | FB-260310091220 | bug | Задвоило добавление контакта | ✅ Duplicate check by name+customer_id (b5b96ec) |
| 26 | FB-260310112224 | bug | Нет контроля дублей контактов (lliubov) | ✅ Fixed with #25 (b5b96ec) |
| 27 | FB-260310112145 | bug | Нет взаимосвязи одинаковых контактов в разных юрлицах (lliubov) | ⬜ |
| 28 | FB-260310111328 | suggestion | Загрузка контактов списком из Excel (lliubov) | ⬜ |
| 29 | FB-260310111712 | suggestion | Добавление нескольких телефонов (lliubov) | ⬜ |
| 30 | FB-260310104505 | suggestion | Отдельно рабочий и мобильный телефон | ⬜ |

---

## Batch B: Quote Pages (18 items)

### B1. Quote List `/quotes`

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 1 | FB-260310193054 | ux_ui | 1-поиск по менеджеру 2-выровнять кнопку "Новая КП" (зеленый) 3-убрать кнопки (IDN кликабельный) 4-шире колонку 5-кликабельный текст не выделен 6-единый шрифт 7-добавить ФИО менеджера | ✅ Points 1,3,5,7 done (33a9837). Points 2,4,6 minor |
| 2 | FB-260225063350 | bug | Было 2 КП, отобразилось только 1 (filter status=approved) | ⬜ |

### B2. New Quote `/quotes/new`

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 3 | FB-260310185431 | ux_ui | 1-убрать тултип → выпадающий список 2-единый блок: Часть1 (Клиент+Контакт, кнопка добавить popup), Часть2 (Страна,Город,Адрес,Способ) 3-единый шрифт/размер полей | ✅ Two-section form layout (cc45dd9) |
| 4 | FB-260306080709 | bug | Поиск клиента по наименованию/ИНН (lliubov) | ⬜ |
| 5 | FB-260227103441 | suggestion | Поиск по ИНН, обязательное поле Контактное лицо | ⬜ |
| 6 | FB-260305104413 | bug | Ошибка duplicate key IDN при создании КП | ⬜ |

### B3. Quote Detail — Overview `/quotes/{id}?tab=overview`

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 7 | FB-260310202322 | ux_ui | 2 итога на странице — оставить один. Объединить обзор и позиции. Проверить шрифты/отступы | ✅ Merged subtabs (266482d) |
| 8 | FB-260306074237 | bug | Маржа точно ли правильная? | ✅ Formula aligned: margin=profit÷revenue_no_vat, markup=profit÷COGS (b5b96ec) |
| 9 | FB-260226060145 | bug | Маржа не та (настоящее 22%) | ✅ Fixed (b5b96ec) |
| 10 | FB-260224112206 | bug | Маржа не та что в расчете | ✅ Fixed (b5b96ec) |
| 11 | FB-260306074322 | suggestion | Выводить мин. срок = Закупка + Логистика | ⬜ |
| 12 | FB-260306074720 | suggestion | При скачивании указывать IDN КП в названии файла | ⬜ |

### B4. Quote Detail — Summary `/quotes/{id}?tab=summary`

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 13 | FB-260310202117 | ux_ui | Убрать кнопку "Отправить", перенести "Скачать" под все блоки | ✅ Done (96f860f) |

### B5. Quote Detail — PHMB tab

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 14 | FB-260306080258 | bug | Наценка/маржа с пороговыми значениями — шаг только 0.5 (lliubov) | ⬜ |
| 15 | FB-260306080500 | suggestion | Вывести средний срок поставки в строке PHMB (lliubov) | ⬜ |

### B6. Quote Detail — Other

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 16 | FB-260306073012 | suggestion | Админу/руководителю убирать курсовую разницу (если закуп и продажа в одной валюте) | ⬜ |
| 17 | FB-260224102539 | suggestion | "Информация от отдела продаж": Проценка? Тендер? Прямой запрос? Конкуренты? Описание. Файлы | ⬜ |
| 18 | FB-260227121949 | bug | Логика изменения количества после согласования | ⬜ |
| 19 | FB-260306100840 | suggestion | Добавить кнопку "Валидация Excel" (quote-control) | ⬜ |
| 20 | FB-260226060133 | bug | Маржа не та (duplicate of B3 items) | ✅ Fixed with B3 #8-10 (b5b96ec) |

---

## Batch C: General Pages (10 items) — Triaged 2026-03-19

### C1. Dashboard `/dashboard`

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 1 | FB-260310183315 | ux_ui | Сделать sales главной страницей. Метрики кликабельны. Убрать ФИО/компанию/должность блок. Мои задачи + Обзор → одна страница. Выровнять блоки | ✅ Dashboard redirects to /quotes (7cf08f1). No separate profile block |
| 2 | FB-260310141333 | bug | Убрать уведомления (оставить только в настройках) | ✅ No notifications in Next.js dashboard (page is redirect to /quotes) |

### C2. Tasks `/tasks`

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 3 | FB-260310195547 | ux_ui | Убрать эффект всплытия блока (hover lift) — жрет мощности | ✅ Done in Batch 0 |
| 4 | FB-260302074057 | suggestion | Отдельно кнопка "Выйти", отдельно вход в профиль | ✅ Next.js sidebar has separate Выйти + Profile link |
| 5 | FB-260224094403 | suggestion | Отобразить какие этапы КП пройдены (в таблице) | ❌ OBSOLETE — tasks consolidated into /quotes page, no separate tasks table |

### C3. Changelog `/changelog`

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 6 | FB-260310183352 | ux_ui | Поправить по ширине экрана | ✅ Done (dd8b073) |
| 7 | FB-260310134355 | bug | Заполнять страницу при отдалении (responsive width) | ✅ Done (dd8b073) |

### C4. Training `/training`

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 8 | FB-260310201337 | ux_ui | Нет отступов сверху | ✅ Done (dd8b073 + migrated to Next.js: 12f683a) |

### C5. Specifications

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 9 | FB-260227110353 | suggestion | Добавить отношение договора к спецификации (несколько договоров) | ⬜ Feature request — backlog |

---

## Batch D: Calls (4 items) — Triaged 2026-03-19

> Note: Standalone `/calls` registry removed from sidebar (adf2173 — Mango not integrated).
> Items below apply to **customer calls tab** which remains active.

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 1 | FB-260310105655 | bug | Перенести запланированный звонок в звонок (кнопка). "Продолжить общение" | ✅ "Завершить встречу" in expanded row (15e07d9) |
| 2 | FB-260310105146 | suggestion | Исправить расположение кнопок. Добавить "Добавить звонок" с выбором компании/контакта | ✅ Button kept as-is, contact selection in modal works (pre-existing) |
| 3 | FB-260310115140 | suggestion | Руководителям видеть все звонки подчинённых | ❌ OBSOLETE — standalone calls registry dropped (adf2173) |
| 4 | FB-260302074436 | suggestion | Добавить возможность раскрыть звонок (полный комментарий, заметки) | ✅ Expandable rows with full details (15e07d9) |

---

## Batch E: Logistics / Customs / Procurement (5 items) — Triaged 2026-03-19, design notes added

### E1. Logistics — SVH + Additional Expenses (3 reports consolidated)

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 1 | FB-260310081358 + FB-260310083213 + FB-260224103929 | bug+suggestion | Перенести расходы СВХ из Таможни в Логистику, добавить графу "Дополнительные расходы" | ⏸️ Design note for Next.js migration |

> **Design note (E1):** СВХ должен быть категорией расходов в logistics stages (не в customs). Добавить generic "Доп. расходы" в logistics. Потребует новую DB категорию + миграцию существующих данных customs→logistics.

### E2. Procurement

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 2 | FB-260310202407 | bug | Таблицы стали черными | ✅ RESOLVED — Handsontable CSS v17 fix (935be1c) |
| 3 | FB-260306071028 + FB-260227120839 | bug | Файл/скан загружен, но не отобразился как загруженный | ⏸️ Design note for Next.js migration |
| 4 | FB-260224080017 | suggestion | Добавить столбцы: Вес кг, Ставка НДС % | ⏸️ Design note for Next.js migration |

> **Design note (E3):** `supplier_invoices.invoice_file_url` колонка есть, таблица пуста (0 записей). При миграции: upload → Supabase Storage → URL в `invoice_file_url`, отображать статус загрузки.
>
> **Design note (E4):** `quote_items.weight_in_kg` есть. `vat_rate` (ставка %) нет — нужна новая колонка. `weight_kg` дублирует `weight_in_kg` — унифицировать. Подтверждено FB-260316-111518.

### E3. Customs

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 5 | FB-260224093431 | suggestion | Расширяющийся размер таблицы "Таможня по позициям" | ⏸️ Design note for Next.js migration |

> **Design note (E5):** Responsive table с горизонтальным скроллом или collapsible columns.

---

## Batch F: Other (5 items) — ✅ ALL RESOLVED (Triaged 2026-03-19)

### F1. Chat

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 1 | FB-260310083243 | bug | Править чат сделки | ✅ Chat implemented (6906770) + empty state fixed (60728d3) |
| 2 | FB-260310082744 | bug | Править чат сделки (duplicate) | ✅ Same fix |
| 3 | FB-260303133417 | bug | Беды с чатом | ✅ Same fix |

### F2. Telegram / Settings

| # | ID | Type | Description | Status |
|---|-----|------|-------------|--------|
| 4 | FB-260310083630 | bug | Telegram: не удалось | ✅ Simplified to one-click deep link (368f817) |
| 5 | FB-260310083600 | bug | Не дает подключить телеграм | ✅ Same fix |

---

## Batch G: New Feedback (2026-03-16) — Triaged 2026-03-19

| # | ID | Type | Page | Description | Status |
|---|-----|------|------|-------------|--------|
| 1 | FB-260316-063243 | suggestion | customer documents | Добавить договоры | ✅ Already implemented — tab-documents.tsx has Договоры CRUD |
| 2 | FB-260316-065611 | suggestion | customer CRM | Добавить редактируемость CRM записей | ✅ Full edit via modal (2e3f573) |
| 3 | FB-260316-065755 | bug | customer positions | IDN-SKU label wrong — вывести отдельно артикул | ✅ Already fixed — tab-positions.tsx has separate Артикул + IDN-SKU columns |
| 4 | FB-260316-065839 | suggestion | customer positions | Responsive scaling при уменьшении экрана | ✅ Already has ScrollableTable wrapper |
| 5 | FB-260316-111518 | suggestion | procurement | Мега-фидбек: (1) таблица закупок redesign, (2) IDN-SKU убрать, (3) чат на все страницы, (4) подсветка артикулов, (5) маршрутизация ✅, (6) ОС по отклонённым, (7) реестр позиций | 🔄 1/7 done. Design notes saved → `.kiro/specs/procurement-logistics-redesign-notes.md` |

---

## Already Resolved (16 + 7 newly resolved items)

| ID | Description | Page |
|----|-------------|------|
| FB-260224101205 | Некорректная валюта и статус | customer detail general |
| FB-260224081535 | Не сохраняет данные компании | seller-companies edit |
| FB-260224091049 | МОП должен видеть только своих клиентов | customers |
| FB-260224095317 | Убрать дублирующуюся кнопку снизу | quote overview |
| FB-260224090731 | В закупках не отображаются юрлица | tasks |
| FB-260224094259 | Логистический/Таможенный менеджер не отразился | quote detail |
| FB-260224074941 | Ошибка при расчете до получения цен | calculate |
| FB-260224092925 | Обзор должен быть у каждого пользователя | dashboard overview |
| FB-260224101126 | Некорректная валюта | customer quotes tab |
| FB-260224101101 | Некорректная валюта | customer requested_items |
| FB-260224095209 | Перевести на русский | calculate |
| FB-260224095426 | Некорректная валюта | tasks |
| FB-260224101506 | Кнопка скачать до проверки | quote summary |
| FB-260224102826 | Инвойс требует 2 раза выбрать файл | procurement |
| FB-260224093259 | Заменить Объем на Габариты | procurement |
| FB-260224094444 | Менеджеры не отразились | quote detail |

---

## Cross-cutting observations (updated 2026-03-19)

1. **Margin/markup discrepancy** — ✅ RESOLVED (b5b96ec). Formula aligned: margin=profit÷revenue_no_vat, markup=profit÷COGS.

2. **Multiple managers per customer** — 3 items (FB-260225103127, FB-260227105317, FB-260310111855) request multi-manager support. Currently single manager_id on customers table. **Still open.**

3. **Contact deduplication** — Duplicate check added (b5b96ec). Cross-company contact linking still open (FB-260310112145).

4. **SVH/additional expenses in logistics** — 3 reports consolidated into E1.1. **Still open.**

5. **Chat** — ✅ RESOLVED. Chat tab implemented (6906770), empty state fixed (60728d3). New request: extend chat to all department pages (FB-260316-111518).

6. **Telegram connection** — ✅ RESOLVED. Simplified to one-click deep link (368f817).

7. **Font/spacing consistency** — addressed globally in Batch 0, page-specific tweaks done for customers + quotes.

8. **Procurement table redesign** — NEW. FB-260316-111518 requests comprehensive column changes (бренд, артикул запроса/производителя, наименование, цена, готовность, вес, габариты мм, НДС, инвойс). Remove IDN-SKU. Highlight article mismatches.

9. **Cancelled/rejected deals feedback** — NEW. FB-260316-111518 requests ОС by reason: (a) cancelled — why client refused, (b) rejected — why team can't supply.

10. **Positions registry with prices** — NEW. FB-260316-111518 requests table with filters (бренд, МОЗ, дата), columns (дата, статус, бренд, артикул, наименование, цена+валюта, МОЗ, инвойс/офер).

---

## Recommended Execution Order (updated 2026-03-19)

**Done (Phase 1 UX quick wins):** ✅ C3 changelog, C4 training, C2.3 hover lift, A3.16-18 fonts, B1.1 columns

**In progress:**
- **Batch A** (Customer pages) — 🔄 list + detail tabs done, contacts/addresses partial
- **Batch B** (Quote pages) — 🔄 list + overview + summary done, PHMB/other partial

**Next up:**
1. **Admin routing** (separate spec) — combines new functionality with existing brands/groups migration
2. **C1** Dashboard redesign — address during Next.js migration
3. **D** Customer calls tab UX (3 items) — after customer detail migration stabilizes
4. **E** Logistics SVH + procurement file upload (4 unique items)
5. **G5** Procurement table redesign (comprehensive — from FB-260316-111518)

**Backlog (feature requests):**
- Multi-manager per customer (A2.12-14)
- Contract management (G1)
- Cancelled/rejected deals feedback loop (G5.6)
- Positions registry with prices (G5.7)
- Spec-contract relationships (C5.9)
- Contact Excel import (A4.28)
- Cross-company contact linking (A4.27)
