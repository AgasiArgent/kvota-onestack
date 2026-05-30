# План реализации — control-spec-workspace

Задачи выровнены с 4 PR из `design.md`. `(P)` = можно делать параллельно с соседями
своего блока. `*` = опциональное тестовое покрытие (можно отложить пост-MVP).
Трассировка — к числовым REQ-ID из `requirements.md`.

> Реализация — через `/lean-tdd` (тест → реализация → lint/tsc). Между мержами PR ~90s
> (docker race). Перед каждой задачей — чистый контекст (`/kiro:spec-impl <id>`).

---

## PR 1 — Миграция + проводка типов + роли (foundation)

- [x] 1. Foundation: схема, типы, роли
- [x] 1.1 Подтвердить номер миграции на VPS и написать аддитивную миграцию
  - На VPS свериться с `kvota.schema_migrations` (CLAUDE.md=283 vs `migrations/`=318/319) — взять истинный следующий номер
  - `migrations/<NEXT>_control_spec_signing_fx_and_seller_fk.sql`: `BEGIN; ALTER TABLE kvota.specifications ADD signing_fx_mode VARCHAR(32) CHECK(...), ADD signing_fx_rate DECIMAL(15,6), ADD seller_company_id UUID REFERENCES kvota.seller_companies(id) ON DELETE SET NULL; COMMIT;`
  - Идемпотентность (`IF NOT EXISTS`), `information_schema` guard (если есть) фильтрует `table_schema='kvota'`
  - _Requirements: 4.5, 8.1, 8.2, 8.3, 8.5_
- [x] 1.2 Применить миграцию на VPS и перегенерировать типы
  - `git pull` + `scripts/apply-migrations.sh` (НЕ scp); проверить схему пост-факт
  - `cd frontend && npm run db:types`; `tsc` зелёный; `tools/check_select_columns.py`
  - Reset `/root/onestack` на main после применения с ветки
  - _Requirements: 8.3, 8.4_
- [x] 1.3 (P) Хелперы ролей контролёров в `shared/lib/roles.ts`
  - `isQuoteController`, `isSpecController`, `canSeeControlBoard` (admin/top_manager→оба), `canEditSpecControl` (spec_controller||admin); fail-closed на неизвестную роль
  - _Requirements: 11.1, 11.3, 11.5_
- [x] 1.4 (P) Read-only enforcement для top_manager/контролёров
  - Расширить `ROLE_EDITABLE_STEPS` (`entities/quote/types.ts`): `top_manager: []`, контролёрам — только их control-шаг; через существующую `isReadOnly`-машинерию
  - _Requirements: 11.2, 11.3_
- [x] 1.5 Расширить `SpecificationRow` + оба SELECT call-site + сериализацию
  - Widen SELECT в `specification-step.tsx` И `specification-step/queries.ts` + тип `SpecificationRow` (держать в синхроне); добавить новые + «мёртвые» колонки реквизитов
  - Проверить, что `services/specification_service.py` сериализует новые поля
  - _Requirements: 1.1, 2.1, 3.1, 12.1_
- [x]* 1.6 Unit-тесты хелперов ролей (чистые функции)
  - _Requirements: 11.1, 11.3, 11.5_

## PR 2 — Экран контроля спецификации (4 блока)

- [x] 2. Экран контроля спеца, фаза «На контроле»
- [x] 2.1 (P) Блок «Из расчёта» (read-only)
  - Читать из prop `quote`: `total_quote_currency`, `total_with_vat_quote`, `total_profit_usd`, `currency`, `exchange_rate_to_usd` (НЕ `total_amount_quote` — удалён); markup из calc-summary; пометка «нет данных расчёта» при отсутствии
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
- [x] 2.2 (P) Promote `entities/seller-company` (тип + `fetchSellerCompanies(orgId)`)
  - Вынести из `features/companies` в `entities/`, чтобы spec-step не cross-import-ил соседнюю feature
  - _Requirements: 2.3_
- [x] 2.3 Блок «Реквизиты» (searchable-дропдауны)
  - Наше юрлицо → `SearchableCombobox<SellerCompany>`, persist FK `seller_company_id` + dual-write имени в `our_legal_entity` (совместимость экспорта)
  - Договор → `SearchableCombobox` из `customer_contracts` клиента; заменить plain `<Select>`; сохранить inline-create
  - Страны → `SearchableCombobox` из distinct `locations.country`, persist строкой в `*_country`
  - Юрлицо клиента → read-only (один набор)
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_
- [x] 2.4 (P) Блок «Условия спецификации» (ввод)
  - `sign_date`, `validity_period`, `readiness_period`, `logistics_period`, `cargo_type`, `delivery_city_russia`; read-only при отсутствии edit-права
  - _Requirements: 3.1, 3.2, 3.3, 3.4_
- [x] 2.5 Блок «Контроль» + selector курса на подписание
  - Режим `cbr_on_payment_day` (default) | `fixed` + ввод значения; ответственный = текущий юзер (показ); Дата контроля — при «Отправить на подписание»
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
- [x] 2.6 Расширить insert/update payload + `created_by` + edit-gate
  - `handleCreate`/`handleSave`: писать новые + реквизитные колонки + `created_by`; обернуть блоки `canEditSpecControl`
  - _Requirements: 2.7, 3.3, 11.3_
- [x]* 2.7 DOM-тесты экрана (рендер блоков, read-only по роли, дропдауны)
  - _Requirements: 1.2, 2.2, 11.2, 11.3_

## PR 3 — Workflow «Отправить на подписание» + сверка + handoff

- [ ] 3. Двухфазный переход контроля спеца
- [ ] 3.1 Действие «Отправить на подписание» (реактивация `pending_signature`)
  - Кнопка → `callWorkflowTransition(quoteId, { to_status: 'pending_signature' })`; валидация обязательных реквизитов (договор, наше юрлицо) — блок + назвать/подсветить недостающие; проставить Дату контроля + ответственного
  - _Requirements: 4.1, 4.2, 5.1, 5.2, 5.3, 5.4_
- [ ] 3.2 `ReconciliationStrip` — структурная сверка (ручной чек-лист)
  - Клон shape `useControlChecks` → `ReconCheck[]`; сайд-бай-сайд (скан слева / система справа); пункты: scan_uploaded, spec_number, contract, parties, totals, dates, signatory; контролёр подтверждает; ПОКА не все + нет скана — «Пометить подписанной» disabled; фиксировать кто/когда
  - дописать `uploaded_by` на documents-строку скана
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
- [ ] 3.3 «Пометить подписанной» → создание сделки + handoff через workflow_service
  - Вызов существующего `confirmSignatureAndCreateDeal`; роутить `quote → 'deal'` через `workflow_service.transition_quote_status(pending_signature → deal)` вместо прямой записи `api/deals.py:251`; читать `total_quote_currency` (флаг 19); при ошибке — остаться в `pending_signature`
  - _Requirements: 7.1, 7.2, 7.3, 7.4_
- [ ]* 3.4 Тесты перехода + гейта сверки
  - _Requirements: 5.3, 6.3, 7.4_

## PR 4 — Воркспейс /workspace/control (два канбана)

- [ ] 4. Воркспейс контроля
- [ ] 4.1 Параметризовать `KANBAN_COLUMNS` → column-config prop
  - Вынести hard-coded const (`kanban-board.tsx`, `model/types.ts`) в prop; **regress-тест logistics/customs** (не сломать существующие board)
  - _Requirements: 9.1_
- [ ] 4.2 (P) `ControlKanbanCard` type + `fetchControlBoard(domain, user)` в `entities`
  - calc: quotes в `pending_quote_control`/`pending_approval`; spec: quotes в `pending_spec_control` (На контроле) / `pending_signature` (На подписании); org-scoped
  - _Requirements: 9.2, 9.3, 9.5, 9.6_
- [ ] 4.3 `ControlCard` renderer + two-board shell + переключатель
  - Кликабельные карточки (без drag); клик → `/quotes/{id}?step=control` (calc) / `?step=specification` (spec)
  - _Requirements: 9.1, 10.1, 10.2_
- [ ] 4.4 Страница `app/(app)/workspace/control/page.tsx` (server) + fail-closed гард
  - Зеркало `workspace/logistics/page.tsx`: orgId redirect, role-guard по `canSeeControlBoard`, `Promise.all` двух board; **fail-closed** (redirect/notFound для неавторизованных)
  - _Requirements: 9.1, 11.1, 11.4, 11.5_
- [ ] 4.5 (P) Пункт «Контроль» в сайдбаре
  - `widgets/sidebar/sidebar-menu.ts` → `/workspace/control`, гейт `hasRole('quote_controller','spec_controller','top_manager')` + isAdmin
  - _Requirements: 9.4_
- [ ]* 4.6 Тесты column-config (logistics/customs regress) + control-board фетчера
  - _Requirements: 9.1, 9.2, 9.3_

## PR 5 — Интеграция и верификация

- [ ] 5. Сквозная проверка
- [ ] 5.1 Браузер-проверка на localhost (Next.js) + prod-Supabase
  - Прогон обеих фаз контроля спеца + воркспейс с двумя канбанами + навигация карточка→таб; роли: `spec_controller`, `quote_controller`, `top_manager` (read-only), `admin`
  - _Requirements: 5.1, 6.1, 7.1, 9.1, 10.1, 11.1, 11.2_
- [ ] 5.2 Контроль непролома: `control-step` (Контроль расчёта) не изменён; экспорт DOCX/PDF работает с FK-юрлицом (dual-write snapshot); калькулятор не затронут
  - _Requirements: 10.3, 12.2, 12.4_
