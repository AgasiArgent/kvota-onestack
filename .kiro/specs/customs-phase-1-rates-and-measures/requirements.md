# Requirements Document

## Introduction

Phase 1 интеграции OneStack с Alta-Soft XML API заменяет ручной workflow таможенников МастерБэринг (поиск кодов ТН ВЭД и переписывание ставок с alta.ru) на in-app автоподбор. Архитектура **Alta-only (H1)** — единый провайдер, без TKS, без LLM-слоя в MVP. Phase 1 покрывает Проблему 1 целиком (ставки пошлин/акциза/НДС × страна × дата + меры нетарифного регулирования) и подготавливает инфраструктуру для Phase 2 (классификатор товар→код через Alta Express + АПУ).

**Scope reference:** `docs/plans/2026-04-22-customs-ved-integration-handoff.md` (актуализирован 2026-04-24)
**Phase 0 reference implementation:** `/Users/andreynovikov/workspace/tech/projects/kvota/onestack-customs-phase0/scripts/phase0_eval_alta_express.py` (MD5 signer, XML builder, response parser, AltaApiError class — переиспользуем при имплементации `services/alta_client.py`)
**Architecture:** Alta-only XML API + smart cache (live-fetch + 30-day TTL + weekly revalidation cron)

**Key terminology used in requirements below:**
- **Quote Item** — строка в `kvota.quote_items`
- **Rate** — ставка пошлины/акциза/НДС, строка в `kvota.tnved_rates` с 3-слотовой моделью значения
- **Country/Areal** — страна (OKSM числовой) или экономический ареал (ЕАЭС, FTA-VN, UNFRIENDLY и т.п.); хранится в `tnved_rates.country_or_areal` префиксом `C:156` или `A:EAEU`
- **Resolver** — `services/rate_resolver.py`, обходит приоритет `страна → ареал → базовая (NULL)` и lazy-fetch'ит из Alta при cache miss
- **Alta Такса** — endpoint `/tnved/xml/` для ставок; **Alta xml_nodes** — endpoint `/tnved/xml_nodes/` для мер нетарифного регулирования (тарифицируется отдельно)
- **AltaClient** — новый модуль `services/alta_client.py`, единая точка входа во все 4 Alta API
- **Customs roles** — `_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}` (для авторизации новых endpoints)

**Locked decisions (resolved open questions):** см. секцию «Locked decisions» ниже после Requirements.

---

## Requirements

### Requirement 1: Foundation Database Schema (Migration 296)

**Objective:** Как разработчик, я хочу создать миграцию `296_tnved_foundation.sql` с полным набором справочных и операционных таблиц, чтобы все последующие компоненты Phase 1 могли работать с консистентной схемой данных.

#### Acceptance Criteria

1. Миграция `migrations/296_tnved_foundation.sql` shall создать в schema `kvota` следующие таблицы: `countries`, `areals`, `country_areals`, `tnved_codes`, `payment_types`, `tnved_rates`, `tnved_non_tariff_measures`, `tnved_apu_cache`, `tnved_classification_log` — со структурой, точно соответствующей разделу «Target State → New tables» handoff-документа.
2. Миграция shall расширить `kvota.quote_items` колонками: `country_of_origin_oksm SMALLINT REFERENCES kvota.countries(oksm_digital)`, `has_origin_certificate BOOLEAN DEFAULT FALSE`, `has_fta_certificate BOOLEAN DEFAULT FALSE`, `customs_rates_snapshot JSONB`, `customs_rates_snapshot_date DATE` — все через `ADD COLUMN IF NOT EXISTS`.
3. Миграция shall выполнить seed следующих данных: `payment_types` (8 строк: IMP, EXP, NDS, AKC, IMPCOMP, IMPDEMP, IMPTMP, IMPDOP с корректными `depends_on_country`/`depends_on_certificate` флагами), `countries` (импорт CSV ОКСМ Росстандарта, ~250 строк), `areals` (EAEU, CIS, FTA-VN, FTA-IR, FTA-SRB, LRC, UNFRIENDLY — manual insert), `country_areals` (привязки стран к ареалам).
4. Миграция shall пометить недружественные страны (`countries.is_unfriendly = TRUE`) на основе разового lookup ПП РФ № 430-р от pravo.gov.ru — список фиксируется на дату миграции, дальнейшие изменения вносятся вручную.
5. Миграция shall создать индексы: `idx_rates_lookup` на `tnved_rates(tnved_code, payment_type, valid_from DESC)`, `idx_rates_country` на `tnved_rates(country_or_areal) WHERE country_or_areal IS NOT NULL`, `idx_apu_cache_last_used` на `tnved_apu_cache(last_used_at DESC)`.
6. Миграция shall использовать UNIQUE constraint `(tnved_code, payment_type, country_or_areal, valid_from, certificate_required, sp_certificate_required)` на `tnved_rates` — для безопасного upsert при cache-revalidate.
7. Миграция shall использовать ровно номер `296` (текущая последняя — 295: `sla_notifications_dedupe.sql`); если на момент применения номер занят, shall переименовываться на следующий свободный.
8. Миграция shall быть применима через `scripts/apply-migrations.sh` без ручных правок и shall быть идемпотентной (повторный запуск не падает на CREATE TABLE / ADD COLUMN).
9. Где `tnved_codes.parent_code` REFERENCES `tnved_codes(code)` создаёт self-FK, миграция shall обеспечить bootstrapping: парент-коды (2-знаки → 4-знаки → … → 10-знаки) могут быть вставлены в правильном порядке либо FK shall быть DEFERRABLE INITIALLY DEFERRED для batch-insert.
10. Где Phase 1 не использует TKS, миграция shall **не** создавать колонок `tks_priznak_flags`, `tks_*_id` и аналогов — handoff scope явно исключает TKS-specific поля.

---

### Requirement 2: Alta XML API Client (`services/alta_client.py`)

**Objective:** Как разработчик OneStack, я хочу единый async-клиент для всех 4 Alta endpoint'ов с правильной MD5-подписью и обработкой ошибок, чтобы вышестоящие сервисы (rate_resolver, classifier) могли вызывать Alta без знания протокольных деталей.

#### Acceptance Criteria

1. `services/alta_client.py` shall экспортировать класс `AltaClient` с async-методами для всех 4 endpoint'ов:
   - `get_rates(tncode, country, date, certificate, sp_certificate)` → Такса `/tnved/xml/`
   - `get_non_tariff_measures(tncode, country, mode='import')` → `/tnved/xml_nodes/`
   - `apu_suggest(query, limit)` + `apu_codes(payload_id, limit)` → АПУ stage 1 + stage 2
   - `classify_batch(items, request_id)` → Express `/tools/autotnved/v2/`
2. Конструктор `AltaClient(login: str, password: str)` shall кэшировать `md5(password)` один раз; password в plaintext shall существовать только в области видимости конструктора, не в атрибутах инстанса.
3. Метод `_sign(param: str)` shall вычислять подпись точно как `md5(f"{param}:{login}:{md5(password)}".encode("utf-8")).hexdigest()` — параметры передаются в **исходных UTF-8 строках**, БЕЗ URL-encoding (gotcha #1 handoff). URL-encoding применяется отдельно при сборке GET-параметров.
4. Where Alta Такса возвращает XML с `encoding="windows-1251"` (gotcha #2), парсер shall детектировать кодировку через response charset header или XML declaration и декодировать explicitly; UTF-8 ответы (Express) парсятся напрямую.
5. Where Alta API возвращает документированный код ошибки (100 = auth, 110 = limit, 120 = tariff, 140 = insufficient funds, 201 = request not found), клиент shall raise `AltaApiError(code: int, message: str)` с распознаваемым кодом.
6. Where Alta возвращает `handled=false` с числовым кодом, не входящим в документированный набор, клиент shall raise `AltaApiError(code, "undocumented Alta error code: {message}")` — undocumented numeric codes никогда не должны silent retry.
7. Where Alta Express возвращает `handled=false` с пустым/нечисловым `<message>` (queue-pending state), клиент shall poll до `POLL_MAX_ATTEMPTS = 6` (1 initial + 5 retries) с `POLL_DELAY_SECONDS = 2.0` между попытками, переиспользуя тот же `request_id` (Express идемпотентен по requestid).
8. Where polling timeout reached без `handled=true`, клиент shall raise `RuntimeError` с last_message и request_id в сообщении, чтобы debugging real-run failures не терял контекст.
9. Метод `classify_batch` shall **не передавать** XML-атрибут `group=` (Phase 1 MVP decision); параметр `group_hint` принимается в API ради forward-compatibility, но в XML-payload игнорируется и должен явно логировать предупреждение если передан.
10. Где Alta Express response содержит `<packet><item>` с `left_count`, клиент shall логировать `left_count` после каждого вызова и emit warning при `left_count < 100` (packet limits — gotcha #9).
11. `AltaClient` shall читать credentials только через DI (передача в конструктор) — модуль не должен делать `os.environ` lookup внутри. Credentials никогда не появляются в логах, exception messages, repr дата-классов, и URL query strings.
12. Timeouts: HTTP timeout `30.0` секунд per request. Retries на network errors (connect timeout, read timeout): max 2 attempts с exponential backoff (1s, 2s).

---

### Requirement 3: Rate Resolver (`services/rate_resolver.py`)

**Objective:** Как customs-эндпоинт OneStack, я хочу единую функцию `resolve_rate()`, которая возвращает актуальную ставку с учётом приоритета «конкретная страна → ареал → базовая» и автоматически lazy-fetch'ит из Alta при cache miss/stale, чтобы customs-юзер не ждал минут на live-запрос для частых пар.

#### Acceptance Criteria

1. Функция `resolve_rate(db, tnved_code: str, payment_type: str, country_oksm: int, date: date, has_certificate: bool = False) -> Optional[Rate]` shall искать rate в `tnved_rates` в следующем приоритете и возвращать **первое найденное**:
   1. exact country: `country_or_areal = 'C:{country_oksm}'`
   2. areal-level: для каждого areal в `country_areals` где `country_oksm = $1` — пробовать `country_or_areal = 'A:{areal_code}'`
   3. base rate: `country_or_areal IS NULL`
2. Where rate в кэше но `source_fetched_at < now() - interval '30 days'` (stale), resolver shall считать запись отсутствующей и lazy-fetch live из Alta Такса.
3. Where все три tier'а dry (cache miss или stale), resolver shall вызвать `AltaClient.get_rates(tncode, country, date, certificate)` и upsert ответ в `tnved_rates` с `source = 'alta-live'`, `source_fetched_at = now()`. После upsert повторно вызвать lookup из Step 1.
4. Where Alta вернула comprehensive response (несколько payment_types за один запрос — IMP+NDS+AKC+IMPCOMP), resolver shall upsert все возвращённые rate'ы за одну транзакцию (минимизирует round-trips для последующих lookups).
5. Where 2 запроса к одному `(tnved_code, country_oksm, date)` приходят конкурентно, resolver shall использовать UNIQUE constraint `tnved_rates` для idempotent upsert (`ON CONFLICT DO UPDATE`); race не должен приводить к duplicate rows.
6. Where Alta API недоступна (network error, 5xx), resolver shall не падать на cache miss — возвращает `None` и логирует ERROR. UI должен показать «Не удалось получить ставку» с кнопкой retry, но не падать страницей.
7. Resolver shall обновлять `last_used_at` на rate row при успешном lookup (для weekly revalidation cron — он re-fetch'ит top-N most-used).
8. Where resolver вызывается с `date` в прошлом (retroactive calc), shall сначала искать в `customs_rates_snapshot` соответствующего `quote_item` (если контекст известен) — иначе fallback на standard live-resolve по дате.
9. Resolver shall быть thread-safe (никаких module-level mutable state) и использовать переданное `db` подключение без global pool lookups.
10. **`countries.is_unfriendly` flag НЕ участвует в lookup-логике** (gotcha #11) — повышенные пошлины для недружественных стран уже зашиты в Alta-ответах автоматически. Resolver не фильтрует и не модифицирует ставки на основе этого флага.

---

### Requirement 4: Customs Duty Calculator (`services/customs_calc.py`)

**Objective:** Как customs-аналитик, я хочу детерминированный расчёт итоговой суммы пошлины из ставки + таможенной стоимости + параметров товара, чтобы UI показывал rouble-выраженную сумму одинаково для всех типов ставок (адвалорная / специфическая / комбинированная).

#### Acceptance Criteria

1. `calculate_duty(rate: Rate, customs_value_rub: Decimal, weight_kg: Decimal, currency_rates: dict[str, Decimal]) -> Decimal` shall корректно обрабатывать три типа ставок:
   - **Адвалорная** (`value_1_unit = 'percent'`): `customs_value_rub × value_1_number / 100`
   - **Специфическая** (`value_1_unit ∈ {'166', '111', ...}` — код единицы измерения): `quantity × value_1_number × currency_rates[value_1_currency]`, где `quantity` — масса/объём из `weight_kg` или соответствующего поля
   - **Комбинированная** (`value_1` адвалорная + `value_2` специфическая, `sign_1 = '>'`): `max(адвалорная, специфическая)` (gotcha #3 handoff). При `sign_1 = '+'`: `адвалорная + специфическая`.
2. `calculate_customs_fee(customs_value_rub: Decimal) -> Decimal` shall реализовать step-функцию ПП РФ № 342 от 26.03.2020 с актуальными бэндами на дату миграции (verify: `≤ 200 000 → 775`, `≤ 450 000 → 1550`, … полный список на pravo.gov.ru).
3. `calculate_util_fee(tnved_code: str, engine_volume_cc: int, vehicle_age_years: int) -> Decimal` shall реализовать формулу ПП РФ № 81 **только** если `tnved_code` начинается с `87` (автомобили). Для остальных групп — return `Decimal('0')` без вызова формулы.
4. Where `rate` имеет некорректные/несовместимые поля (например, `value_1_unit = 'percent'` но `value_1_currency != NULL`), функция shall raise `ValueError` с указанием конкретного поля и значения, не silently игнорировать.
5. Все денежные операции shall использовать `Decimal` (не `float`); rounding до 2 знаков после запятой только в финальном ответе, промежуточные расчёты — full precision.
6. Where ставка использует unit code из `tnved_codes.prim` (например `'166'` — кг, `'111'` — литр, `'796'` — штук), функция shall иметь whitelist поддерживаемых unit codes; неизвестный unit code → `ValueError`. Документация по unit codes — в Alta Таксе.
7. **Calculator не должен модифицировать `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`** (project rule). Интеграция с существующей calc engine — через расширение `build_calculation_inputs()` (адаптер-слой).
8. Calculator shall быть pure-functional: никаких side effects (DB-запросов, network calls, file I/O). Вход — ставка + контекст; выход — Decimal. Это упрощает unit-тесты и ускоряет batch-расчёт.

---

### Requirement 5: API Endpoints (`api/customs.py`)

**Objective:** Как Next.js frontend и AI-агент через MCP, я хочу REST endpoint'ы для resolve-rates, non-tariff-measures, и расширенного autofill, чтобы получать customs-данные через единый JSON-протокол с правильной авторизацией.

#### Acceptance Criteria

1. `POST /api/customs/resolve-rates` shall принимать JSON body `{tnved_code: str, country_oksm: int, date?: str (ISO), certificate?: bool, sp_certificate?: bool, quote_item_id?: int}` и возвращать `{success: true, data: {rates: [{payment_type, value_1_*, ..., raw_value_string, calculated_amount_rub}, ...], total_rub, source, fetched_at}}`.
2. `POST /api/customs/non-tariff-measures` shall принимать `{tnved_code: str, country_oksm: int, mode?: 'import' | 'export'}` и возвращать `{success: true, data: {measures: [{measure_type, name, description, document_basis, document_link, ...}], source, fetched_at}}`. Endpoint вызывается **только** когда UI явно запрашивает меры (gotcha #5: тарифицируется отдельно 3₽/запрос).
3. Существующий endpoint autofill (в `api/customs.py`) shall быть расширен: при отсутствии исторических данных или `force_live=true` в request — вызывать `rate_resolver` и возвращать актуальные ставки. **Сигнатура existing autofill НЕ меняется** (backwards-compat — frontend ждёт текущий response shape; новые поля добавляются опционально).
4. Все три endpoint'а shall использовать dual-auth: проверять `request.state.api_user` (JWT через `ApiAuthMiddleware`) ИЛИ legacy `session` cookie. Если ни одно из них не valid → `401 Unauthorized` (response envelope `{success: false, error: {code: 'UNAUTHORIZED', message: ...}}`).
5. Авторизация: endpoint shall разрешать только пользователей с ролями из `_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}`. Иначе `403 Forbidden` (envelope `{success: false, error: {code: 'FORBIDDEN', ...}}`).
6. Каждый endpoint shall иметь structured docstring (формат api-first.md): `Path:`, `Params:`, `Returns:`, `Side Effects:`, `Roles:` — для будущей OpenAPI/MCP-генерации.
7. Where `quote_item_id` передан в `resolve-rates`, endpoint shall обновить `quote_items.country_of_origin_oksm`, `customs_duty`, `customs_duty_percent` (и связанные computed-поля) после успешного resolve. Это side-effect, явно указанный в docstring.
8. Where Alta API недоступна и cache пуст, endpoint shall вернуть `503 Service Unavailable` с body `{success: false, error: {code: 'ALTA_UNAVAILABLE', message: 'Alta API недоступен, попробуйте позже'}}`. UI показывает retry button, не падает страницей.
9. Все endpoint'ы shall логировать `(user_id, tnved_code, country_oksm, source, latency_ms, cache_hit: bool)` для observability и cost-tracking. Credentials и polling internals не логируются.
10. Endpoints shall возвращать единый response envelope `{success, data?, error?, meta?}` (project api-design.md convention).

---

### Requirement 6: Weekly Cache Revalidation Cron

**Objective:** Как платформа, я хочу еженедельный фоновый процесс, который обновляет кэш `tnved_rates` для самых используемых пар «code × country», чтобы users не видели lazy-fetch latency на горячих lookup'ах.

#### Acceptance Criteria

1. `api/cron.py` shall добавить endpoint `POST /api/cron/revalidate-rates` (existing cron-router pattern), вызываемый внешним cron на VPS (раз в неделю по subj timeline).
2. Endpoint shall выполнять SQL: `SELECT tnved_code, country_or_areal FROM kvota.tnved_rates WHERE source_fetched_at < now() - interval '7 days' GROUP BY tnved_code, country_or_areal ORDER BY MAX(last_used_at) DESC NULLS LAST LIMIT 1000` — топ-1000 наиболее свежих использований среди stale записей.
3. Для каждой пары: вызвать `AltaClient.get_rates(...)`, upsert ответ в `tnved_rates` с `source = 'alta-revalidate'`, `source_fetched_at = now()`. Старые row'ы НЕ удалять — устанавливать `valid_to = now()` если ставка изменилась (история сохраняется).
4. Endpoint shall логировать: total processed, cache hits (rate не изменился — same values, продлили `source_fetched_at`), updates (rate изменился — closed old + inserted new), failures (Alta вернула ошибку), packet_left на каждом 100-м запросе.
5. Where Alta возвращает `AltaApiError(140, ...)` (insufficient funds) или packet_left < 50, endpoint shall немедленно прервать batch и emit ALERT через configured channel (Telegram bot / email — uses existing alerting infrastructure).
6. Endpoint shall быть idempotent: повторный запуск в течение 7 дней — no-op (записи уже свежие). Это разрешает retry на cron failure.
7. Endpoint shall иметь timeout 30 минут (long-running 1000 запросов × ~100ms каждый ≈ 1.5 минуты, но network jitter учитывается).
8. Cron infrastructure: VPS-side crontab entry **не часть этого спека** — Andrey добавляет вручную через `(crontab -l; echo "0 4 * * 1 curl -X POST .../api/cron/revalidate-rates -H 'Authorization: ...'") | crontab -` (см. memory `reference_vps_cron_endpoints.md`). Ответственность спека — только endpoint.

---

### Requirement 7: Frontend UI (Next.js — Quote Item Edit)

**Objective:** Как customs-юзер, я хочу на странице редактирования quote_item видеть поля «Страна происхождения» + сертификаты, кнопку «Автоподбор ставок», и breakdown с мерами нетарифного, чтобы за один клик заполнить все customs-related поля без копипаста с alta.ru.

#### Acceptance Criteria

1. На существующем UI редактирования `quote_item` (`frontend/src/app/quotes/[id]/...` или соответствующий route) shall быть добавлены input-элементы:
   - **Страна происхождения** — searchable select с автокомплитом по `countries.name_ru` (memory `feedback_searchable_select.md` — все entity-pickers через searchable Input+dropdown, не plain Select); value bind to `country_of_origin_oksm`
   - **Чекбоксы:** `has_origin_certificate` (Сертификат происхождения) + `has_fta_certificate` (Сертификат FTA)
2. Where страна происхождения помечена `is_unfriendly = TRUE`, UI shall отображать badge «⚠️ Недружественная страна (ПП 430-р)» рядом со значением — это UI-only сигнал (gotcha #11), не влияет на расчёт.
3. Кнопка **«Автоподбор ставок»** shall вызывать `POST /api/customs/resolve-rates` с текущими `tnved_code`, `country_of_origin_oksm`, `date = today`, `has_certificate`, `has_fta_certificate`. После успеха — заполнить `customs_duty`, `customs_duty_percent`, `customs_excise`, `customs_eco_fee`, `customs_extra_cost` в форме (без перезагрузки).
4. После автоподбора UI shall показывать **breakdown**: «пошлина X% + НДС 20% + (акциз Y если ≠0) → итого N₽» — с raw_value_string для каждой ставки в tooltip («10%, но не менее 0.04 евро/кг»).
5. UI shall показывать timestamp `source_fetched_at` рядом с breakdown («Обновлено 5 минут назад»). Кнопка **«Обновить ставки»** force-вызывает endpoint с `force_live=true`, минуя cache.
6. Кнопка **«Показать меры нетарифного регулирования»** (отдельная — оплата 3₽ за вызов, gotcha #5 + handoff explicitly) shall вызывать `POST /api/customs/non-tariff-measures` и показывать список мер с `name`, `document_basis`, `document_link` (ссылка на pravo.gov.ru или аналог).
7. Where Alta API недоступна (503 от backend), UI shall показать non-blocking error toast «Alta API недоступен, попробуйте позже» + retry button. Существующие данные quote_item остаются доступными (form не падает).
8. Validation UX (memory `feedback_validation_ux.md`): если автоподбор fail из-за невалидных входов (например, `tnved_code` не 10 цифр) — UI shall выделить конкретное поле + показать сообщение «Код ТН ВЭД должен быть 10 цифр», не silent fail.
9. Frontend code shall находиться **только** в `frontend/src/` (Next.js 15 App Router + shadcn/ui + Tailwind + FSD architecture). Modifications в `legacy-fasthtml/` запрещены.
10. Supabase JS client (если используется direct read для countries dropdown) shall быть инициализирован с `db: { schema: 'kvota' }`. Бизнес-логика (resolve-rates) идёт через Python API, не direct DB.

---

### Requirement 8: Freeze Behavior (Snapshot for Retroactive Calc)

**Objective:** Как пользователь, выгрузивший finalized quote в PDF/Excel несколько месяцев назад, я хочу чтобы повторное открытие этого quote показывало те же customs-значения, что были на момент freeze, чтобы расчёты не «плавали» при изменении ставок ЕЭК.

#### Acceptance Criteria

1. При `quote.status = 'frozen'` (или соответствующий freeze-event), системa shall сохранить в `quote_items.customs_rates_snapshot` JSONB-объект содержащий все resolved ставки + меры на момент freeze: `{rates: [{payment_type, value_1_*, ..., calculated_amount_rub}, ...], measures: [...], frozen_at: ISO_timestamp, source_at_freeze: 'alta-live' | 'alta-revalidate'}`.
2. Поле `quote_items.customs_rates_snapshot_date` shall быть установлено в дату freeze.
3. Where `customs_rates_snapshot IS NOT NULL`, последующие чтения quote_item для отображения customs-полей shall использовать **snapshot**, а не live-resolve. Это garantees что PDF, отправленный клиенту 3 месяца назад, остаётся consistent.
4. Where юзер явно нажал **«Пересчитать по текущим ставкам»** на frozen quote, UI shall запросить confirm («Это перезапишет snapshot. Продолжить?») и затем re-resolve через `rate_resolver`. Старый snapshot копируется в audit log (или новая таблица `quote_items_history` если она существует — не создавать новой в Phase 1).
5. Where freeze-операция вызвана но Alta API недоступна, freeze shall fail gracefully: либо abort с message «Не удалось получить актуальные ставки для freeze, попробуйте позже», либо использовать last-known cache values с явным флагом `source_at_freeze: 'cache-stale'` в snapshot. Behaviour — запросить выбор у Andrey на этапе spec-design.
6. Snapshot shall содержать достаточно данных для полного re-render PDF без single Alta-запроса; если в JSONB что-то отсутствует — это bug.

---

## Locked decisions (resolved open questions)

| Решение | Источник | Применение в Requirements |
|---|---|---|
| `countries.is_unfriendly` — UI-only flag | handoff Q11 gotcha | REQ-3 AC#10, REQ-7 AC#2 |
| Не backfill legacy `quote_items.hs_code` | handoff Open Q5 | (вне scope этого спека — отдельный legacy-tag job) |
| Alta Express login = main Alta login | handoff Open Q6 | REQ-2 AC#11, ENV: `ALTA_LOGIN` / `ALTA_PASSWORD` единые |
| НЕТ `group` hint в Express MVP | user 2026-04-28 | REQ-2 AC#9 |
| Migration 296 (не 294) | git log проверка | REQ-1 AC#7 |
| Меры нетарифного в Phase 1 | user 2026-04-28 | REQ-1, REQ-2, REQ-5, REQ-7 |
| Manual seed `is_unfriendly` | handoff Q2 | REQ-1 AC#4, weekly cron-reminder вне spec scope |

## Critical project rules (NOT negotiable)

- НЕ модифицировать `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` — обернуть в `build_calculation_inputs()` (REQ-4 AC#7)
- Schema = `kvota`, role column = `r.slug` (REQ-1, REQ-7 AC#10)
- Auth: dual JWT/session (REQ-5 AC#4)
- Customs roles: `_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}` (REQ-5 AC#5)
- Backwards-compat existing autofill: расширять response, не менять signature (REQ-5 AC#3)
- Frontend в `frontend/src/`, никогда `legacy-fasthtml/` (REQ-7 AC#9)
- Supabase JS client: `db: { schema: 'kvota' }` (REQ-7 AC#10)

## Out of scope (deferred)

| Feature | Phase | Reasoning |
|---|---|---|
| Alta Express batch classifier UI integration | Phase 2 | Express **client** существует с Phase 1 (REQ-2), но UI surface — Phase 2 |
| АПУ interactive picker UI | Phase 2 | Same as Express |
| `POST /api/customs/classify-batch` endpoint | Phase 2 | Зависит от UI Phase 2 |
| Eval-gate measurement (Phase 0 dry-run with real МастерБэринг data) | Phase 3 | Throwaway script готов в `onestack-customs-phase0` worktree, прогон при поступлении real-data |
| LLM fallback (OpenRouter A/B) | Phase 4A | Только если Phase 3 eval показывает 60-75% accuracy |
| Revisit TKS / full LLM pipeline | Phase 4B | Только если Phase 3 eval < 60% accuracy |
| `tnved_codes.parent_code` дерево UI (drill-down picker) | Phase 2/3 | Заполняется органически из Alta Такса response в Phase 1, навигационный UI — позже |
| Backfill legacy `quote_items` snapshot | Never | Locked decision: legacy-rows остаются как есть |

---

## Next step

Run `/kiro:validate-gap customs-phase-1-rates-and-measures` (рекомендуется — brownfield project) для анализа existing code и integration points, затем `/kiro:spec-design customs-phase-1-rates-and-measures -y`.

Альтернатива: если gap-анализ не нужен — сразу `/kiro:spec-design customs-phase-1-rates-and-measures -y`.
