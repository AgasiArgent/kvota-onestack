# Triage 2026-05-07 — Multi-tab Test Sweep (5 tabs, sales/procurement/logistics)

**Source tabs:** РОЗ тест 06, МОП тест 06, МОЗ тест 07, СтМоз Тест 06, РОЛ Тест 07
**Source file:** `mcp-claude_ai_Google_Drive-read_file_content-1778145847855.txt` (single Google Sheet export, all 5 tabs concatenated, 1124 lines)
**Scope:** bugs only (UI/UX suggestions filtered out)
**Dedup baseline:** `2026-05-01-moz-test-triage.md`, `2026-05-03-roz-test-triage.md`, `2026-05-03-mop-rop-test-triage.md` + PRs #77–#90

---

## Tab → table mapping (resolved from file content)

| Tab (user-stated)   | Tester                | Lines       | Format         | Notes                                                |
|---------------------|-----------------------|-------------|----------------|------------------------------------------------------|
| РОЗ тест 06         | chislova.e            | 565–757     | URL columns    | 159 rows; **fully matches** prior 05-03 RОЗ triage   |
| МОП тест 06         | bokov.a               | 920–940     | sub-table      | 19 rows, КП registry only; matches 05-03 МОП triage  |
| МОЗ тест 07         | МОЗ procurement       | 764–918     | URL columns    | 146 rows; mostly overlaps prior 05-01 МОЗ triage     |
| СтМоз Тест 06 (NEW) | Senior Procurement    | 1063–1104   | sub-tables     | 36 rows across 2 sub-tables (Customers + KP)         |
| РОЛ Тест 07 (NEW)   | Head of Logistics?    | 1105–1123 ? | sidebar only   | **PROBABLY MISSING from export** — see Open #3       |

Mid-tables 942–1062 (4 sub-tables, kravtsova @ L962 = РОП marker) belong to the РОП Тест tab from 05-03 mop-rop triage. Found 2 new failures here.

---

## Summary

| Tab            | Total rows | Failed | Notes | Not Run | Already fixed | New bugs | Suggestions filtered |
|----------------|-----------:|-------:|------:|--------:|--------------:|---------:|--------------------:|
| РОЗ Тест 06    |        159 |     17 |     8 |      13 |          ~17  |       0  |                  ~3 |
| МОП Тест 06    |         19 |      0 |     2 |       0 |           2   |       0  |                   0 |
| МОЗ Тест 07    |        146 |     22 |     7 |      12 |          ~18  |       3  |                  ~5 |
| СтМоз Тест 06  |         36 |      1 |     2 |       0 |           0   |       3  |                   0 |
| РОП Тест (cross-ref) | 94   |      2 |     4 |       1 |           4   |       2  |                   0 |
| РОЛ Тест 07    |          ? |     ?  |    ?  |      ?  |           ?   |       ?  |                   ? |

**Total NEW bugs in scope:** 8 (across МОЗ Тест 07, СтМоз Тест 06, РОП re-test).

---

## РОЗ Тест 06 — Head of Procurement (chislova.e)

**Verdict:** No new bugs. All 17 Failed already covered.

### Already fixed (cross-ref to 05-03 РОЗ triage)

All 17 Failed and 8 Passed-with-Notes from this tab map 1:1 to the 05-03 triage. PRs that closed them:

| РОЗ # | Brief                                              | Closed by                |
|-------|----------------------------------------------------|--------------------------|
| 39    | Должность РОЗ не переведена в чате                 | PR #79                   |
| 49    | Распределение показывает забаненную Бармину А.     | tracks B from РОЗ batch  |
| 52    | Dropdown «Назначить МОЗ» — те же активные/неактивные | track B                |
| 57    | Sidebar badge ≠ /procurement/distribution header   | track F (P3)             |
| 58    | Канбан закупок — false-positive (now works)        | already done before test |
| 60    | `/suppliers` пустой — `isProcurementOnly` фикс     | track A (PR + 05-03 file) |
| 69    | Профиль — не отражается руководитель               | PR #78 (МОЗ #56)         |
| 80    | «Закрыть документы» возвращает на «Заявку»         | track C                  |
| 83    | Кнопка удалить документ                            | PR #77                   |
| 84    | Кнопка скачать открывает вместо качает             | PR #79                   |
| 87    | КПП modal — отсутствуют доп. поля                  | already done             |
| 89/91 | Поиск в Поставщик/Компания-покупатель              | PR #82                   |
| 95    | Авто-НДС в КПП modal                               | track D (procurement-bugs-fix) |
| 101   | Бренд не полностью + ед.изм                        | PR #78                   |
| 104   | Назначить позиции — reload required                | PR #78                   |
| 107/108 | Header данные дублируются                        | UX deferred              |
| 111   | XLS всегда RU                                      | PR #79                   |
| 117   | Письмо — данные не тянутся                         | PR #81                   |
| 158   | «Редактировать с одобрением» — отправлено куда-то  | track D                  |
| 159   | «Завершить закупку» — этап не переносится          | track D                  |

**Conclusion:** No new triage rows. RОЗ tab is 100% reconciled with prior triage.

---

## МОП Тест 06 — Sales Manager (bokov.a)

**Verdict:** No new bugs. Both Notes already addressed.

### Already fixed (cross-ref to 05-03 МОП/РОП triage)

| МОП # | Brief                                                       | Closed by |
|-------|-------------------------------------------------------------|-----------|
| 6     | Таблица КП — ВЕРСИЯ/СУММА/ПРИБЫЛЬ — нет возможности проверить | data-readiness, not bug — РОЛЬ-aware columns; deferred |
| 19    | «Дает создать кп для клиента другого пользователя»          | PR #87 Track A (searchCustomers leak) |

---

## МОЗ Тест 07 — Procurement Manager (NEW round)

**Verdict:** Mostly re-test of resolved МОЗ items. **3 new bugs** identified.

### Already fixed (cross-ref to 05-01 МОЗ triage + PRs #77–#82, #87–#90)

All status duplicates collapsed. Items below are confirmed already resolved:

| МОЗ#07 | Brief                                                         | Closed by         |
|--------|---------------------------------------------------------------|-------------------|
| 35     | Должности «unknown» в чатах                                   | PR #79            |
| 45     | Канбан закупок — отражаются все КП                            | confirmed working before test (РОЗ R1) |
| 47     | Реестр КП — этапы вместо стадий                               | МОЗ #47 (05-01) — UX semantics task |
| 60     | Блок «Финансы» в КП profile — «удалить»                       | already removed (track from РОЗ batch) |
| 74     | КПП modal — добавить адрес/комментарий/контакт                | МОЗ #74 (05-01) — done before test |
| 75     | КПП modal — Поставщик: видны ВСЕ поставщики                   | track A (РОЗ #60 fix; supplier list scoped to org) |
| 76     | Поиск в dropdown Поставщик                                    | PR #82            |
| 78     | Поиск в dropdown Компания-покупатель                          | PR #82            |
| 82     | Авто-НДС не тянет                                             | track D (procurement-bugs-fix REQ-3) |
| 91     | Назначение позиций — reload required                          | PR #78            |
| 96     | Грузовые места — нет возможности изменения                    | track E (РОЗ R2 cargo edit) — verified by РОЗ batch |
| 98     | Скачать XLS RU/ENG — всегда RU                                | PR #79            |
| 104    | Подготовить письмо — данные не тянутся                        | PR #81            |
| 108    | Крестик «удалить позицию из КПП»                              | МОЗ #108 (05-01)  |
| 109–114 | «Прыгает при выборе ячейки» (Handsontable)                   | Track H deferred (05-03 mop-rop)  |
| 145    | «Редактировать с одобрением» — Not Run                        | track D (РОЗ #158) |
| 146    | «Завершить закупку» — этап не переносится                     | track D (РОЗ #159) |
| 16, 26, 49–53, 57, 63, 101, 145 | All Not Run (training, registries, telegram, etc.) | not actual bugs |

### New bugs

| #   | P  | Description                                                         | Repro                                                    | Expected                                | Actual                                       | Notes                                              |
|-----|----|---------------------------------------------------------------------|----------------------------------------------------------|-----------------------------------------|----------------------------------------------|----------------------------------------------------|
| 58  | P3 | Контакт в блоке «Информации о КП» — МОЗ может **изменить** контакт МОПа | Профиль КП → блок «Клиент» → Контакт                | Контакт read-only для МОЗ              | МОЗ может выбрать иные контакты или убрать выставленный МОП | RLS/permission scope: МОЗ should not edit sales-side fields |
| 93  | P3 | «Создать КПП» modal — открывается слишком широко, кнопки недоступны | Таблица позиций → Назначить → Создать КП поставщику      | Modal стандартной ширины                | Modal слишком широкий, кнопки create/cancel недоступны | UI bug — likely viewport/overflow CSS issue       |
| 94  | P4 | Header КПП — данные дублируются ниже, часть не читается             | Таблица КПП → header                                      | Данные не дублируются                  | Часть не возможно прочесть                  | Repeats РОЗ #107/108 — confirm if same root cause |

---

## СтМоз Тест 06 — Senior Procurement (NEW)

**Verdict:** 3 new bugs (1 Failed + 2 Notes), all permission/visibility-related.

### New bugs

| #   | P  | Description                                                                 | Repro                                                                | Expected                                                | Actual                                                                                | Notes                                                       |
|-----|----|-----------------------------------------------------------------------------|----------------------------------------------------------------------|---------------------------------------------------------|----------------------------------------------------------------------------------------|-------------------------------------------------------------|
| C3  | P4 | Customers list — фильтр «Все статусы» ничего не делает для СтМоз            | `/customers` → выпадающий «Все статусы»                              | Фильтр меняет содержимое таблицы                        | «не могу проверить, так как не могу изменить статус»                                  | Status-change permission missing OR dropdown read-only for procurement_senior |
| C9  | P4 | Customers «Подробно» вид — КП/Посл.КП/Статус/Выручка/Спец/Прибыль = «нет возможности проверить» | `/customers` toggle Подробно                  | Все колонки отображают данные                           | Только наименование/ИНН/дата видны                                                    | Likely RLS on quotes/specs filters out for senior procurement role |
| Q6  | P3 | КП registry — ВЕРСИЯ/СУММА/ПРИБЫЛЬ для СтМоз = «нет возможности проверить»  | `/quotes`                                                            | Все колонки видны                                       | 3 колонки empty                                                                       | Mirror C9 — visibility scope for procurement_senior         |

**Pattern:** All 3 bugs share root cause — `procurement_senior` role missing from visibility/edit policies on customers/quotes/specifications.

### Suggestions filtered (not bugs)

- C16/C17 — отсутствуют фильтры на странице (UX request, not regression)
- C19 — «Дает создать кп для клиента другого пользователя» (Passed, not failed) — confirms Track A fix works for this role too

---

## РОП Тест (cross-ref re-scan from same export)

The 4 sub-tables 942–1062 belong to `kravtsova.e` (РОП = head_of_sales) per Profile marker at L962. Re-scanned for items missed in 05-03 mop-rop triage.

### Already fixed

| #          | Brief                                          | Closed by                                                                |
|------------|------------------------------------------------|--------------------------------------------------------------------------|
| Cust #3    | «Все статусы» dropdown не работает (Not Run)   | head_of_sales status visibility — same as СтМоз C3 (group cluster)       |
| Cust #9    | Подробно view: Статус/Выручка/Спец = empty     | data-readiness, deferred                                                 |
| Msg #3     | Большие ФИО показывает не полностью            | track F (PR #87)                                                         |
| Msg #4     | unknown в Должности                            | PR #79                                                                   |

### New bugs

| #         | P  | Description                                                                                  | Repro                                                                                           | Expected                                                            | Actual                                                                                                       | Notes                                                                                                        |
|-----------|----|----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| KP #24    | P5 | РОП не может «Отправить в закупку» когда КП клиента подчинённого                             | КП подчинённого МОПа → Кнопка «Отправить в закупку»                                              | РОП может отправить (он группа-leader)                              | `Ошибка перехода: You don't have permission to perform this transition. Required roles: sales, admin`        | Workflow transition role-check excludes `head_of_sales`. **Repro from CSV:** L1009 in source. **P5: blocks РОП-driven sales workflow.** |
| Cust #1   | P4 | РОП не может войти в профиль клиента подчинённого                                            | `/customers` → клик по клиенту подчинённого МОПа                                                 | РОП открывает профиль (group-scoped visibility)                     | «РОП не может войти в клиента подчиненного» (Failed, P5 в CSV)                                                | Check `customer_select_policy` for `head_of_sales` — should allow group + own. **L1023 in source.**          |
| KP #22    | P3 | Таблица позиций — выпадающий «ед» открывается «багано» при 2-3 позициях                      | КП → Таблица позиций → ячейка «ед.»                                                              | Dropdown открывается стандартно                                     | «багано открывается выпадающий список при 2-3 позициях»                                                       | Already noted as Track H in 05-03 mop-rop, **deferred** — same Handsontable issue                            |

---

## РОЛ Тест 07 — Head of Logistics (NEW)

**Verdict:** **TAB CONTENT NOT IDENTIFIED in export.**

The only candidate table (Mid-10, lines 1105–1123) is a generic sidebar nav boilerplate test with NO status column and ALL «Соответствует ожидаемому» — does not appear to be a real role-specific test sheet.

There is **no logistics module test data** (no `/logistics`, `/customs`, `/customs-declarations` URLs anywhere in the export beyond РОЗ #65 / МОЗ #53 which are Not Run links).

**Action item:** verify with user (see Open Question #3).

---

## Cross-cutting clusters

### Cluster 1 — `head_of_sales` workflow & visibility gaps (NEW, P5)

Two РОП findings + one suggestion of system-wide pattern:

- **РОП KP #24** (P5): `head_of_sales` missing from workflow transition allowed-roles for sales→procurement → blocks subordinate KP escalation
- **РОП Cust #1** (P4): `customers` table policy may be missing the manager_id-of-subordinate path for `head_of_sales`
- 05-03 РОП triage already had C16/C17 customer-create fixed via PR #76 — but **transitions and customer-profile-entry** are separate flows that weren't tested then.

**Recommended single fix:** audit all `Required roles` workflow guards + customer/quote/spec RLS policies for `head_of_sales`. One sweep.

### Cluster 2 — `procurement_senior` visibility scope (NEW, P4)

СтМоз C3, C9 + Q6 all show same symptom: «нет возможности проверить» columns/dropdowns. Likely missing role grants on:
- `customers_select_policy` extended fields (status, revenue, profit)
- `quotes_select_policy` extended fields (sum, profit, version)
- Customer status-change action

**Recommended single fix:** mirror `procurement` role policies onto `procurement_senior` where they currently differ.

### Cluster 3 — KPP modal/header sizing (P3-P4)

МОЗ #93 (modal too wide, buttons unreachable) + МОЗ #94 / РОЗ #107/108 (header data duplicates below). Possibly same CSS root cause for КПП-related dialogs/headers.

---

## Open questions

1. **РОЛ Тест 07 — does this tab actually exist in the source spreadsheet?** Mid-10 (lines 1105-1123) appears to be sidebar nav boilerplate without a status column. Either (a) the tab wasn't filled in by the РОЛ tester yet, (b) it was filtered out by the Drive export, or (c) the table I'm seeing IS it but it's all-passing. **Need user to confirm** whether to expect failures here at all.

2. **РОП #24 — is `head_of_sales` *supposed* to escalate KPs to procurement?** Required-roles error says only `sales, admin`. Confirm whether РОП escalating subordinate's KP is in-scope, or if it's expected to be MOP-only.

3. **МОЗ #58 — should МОЗ be able to edit the Контакт field in КП «Клиент» block?** This was set by МОП. If МОЗ is read-only for sales-side fields, that's a permission tightening; if MOZ has legit reasons to override, this isn't a bug.

4. **СтМоз cluster — is `procurement_senior` distinct from `procurement` in role design?** If StMoz should see everything procurement sees plus subordinate visibility, then C9/Q6 are real gaps. If StMoz is only an admin-tier role, the role contract differs.
