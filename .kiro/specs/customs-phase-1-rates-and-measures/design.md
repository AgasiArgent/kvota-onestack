# Technical Design — customs-phase-1-rates-and-measures

**Date:** 2026-05-01
**Architecture:** Alta-only (H1)
**Decisions resolved:** see `decisions.md`
**Gap analysis:** see `gap-analysis.md`
**Research log:** see `research.md`

---

## Architecture Decision

Phase 1 расширяет existing customs-инфраструктуру OneStack, не строит с нуля. Основная задача — заменить ручной workflow таможенников (alta.ru → копипаст в quote) автоматическим resolve через единый `services/alta_client.py`. Архитектурно это **четыре новых сервисных модуля + расширение existing API + новый frontend feature**, plus **integration в существующий quote_versions snapshot pattern** для freeze-семантики.

Calc-engine (`calculation_engine.py`/`calculation_models.py`/`calculation_mapper.py`) — **LOCKED**, не модифицируется. Новый `customs_calc.py` подключается через `build_calculation_inputs()` адаптер-слой; switch между legacy и новой формулой — по полю `rate.source`. Snapshot для freeze — **extend** existing `quote_versions.input_variables` (Q7 finding), а не новые JSONB-колонки на quote_items.

---

## Requirements Traceability

| REQ | Title | Component(s) | New/Touched |
|-----|-------|--------------|-------------|
| REQ-1 | Migration 298 (foundation) | `migrations/298_tnved_foundation.sql` | NEW |
| REQ-2 | Alta XML API client | `services/alta_client.py` | NEW |
| REQ-3 | Rate resolver | `services/rate_resolver.py` | NEW |
| REQ-4 | Customs duty calculator | `services/customs_calc.py` + `services/calculation_helpers.py` (адаптер) | NEW + TOUCH |
| REQ-5 | API endpoints | `api/customs.py` + `api/routers/customs.py` | EXTEND |
| REQ-6 | Weekly cache revalidation cron | `api/cron.py` + `api/routers/cron.py` + `api/auth.py` | EXTEND |
| REQ-7 | Frontend UI | `frontend/src/features/quotes/ui/customs-step/` + new feature folders | EXTEND + NEW |
| REQ-8 | Freeze snapshot behavior | `services/customs_freeze_service.py` + hook в `services/workflow_service.py` + reuse `services/quote_version_service.py` + `services/changelog_service.py` | NEW + TOUCH |

---

## Data Model — Migration 298

**Filename:** `migrations/298_tnved_foundation.sql`

**Decision changes from REQ-1 (Q7 simplification):**
- ❌ DROP from migration: `quote_items.customs_rates_snapshot JSONB` and `customs_rates_snapshot_date DATE` columns. Snapshot lives in `quote_versions.input_variables.customs_rates` instead.
- ✅ ADD to `tnved_rates`: `last_used_at TIMESTAMPTZ NOT NULL DEFAULT now()` (Q3 decision).
- ✅ KEEP from REQ-1: all 9 new tables, 3 quote_items columns (`country_of_origin_oksm`, `has_origin_certificate`, `has_fta_certificate`), 4 seeds, 3 indexes.

### New tables (schema `kvota`)

```sql
-- 1. Countries (~250 rows from ОКСМ Росстандарта)
CREATE TABLE IF NOT EXISTS kvota.countries (
    oksm_digital   SMALLINT     PRIMARY KEY,             -- 643 (Russia), 156 (China), ...
    iso_alpha2     CHAR(2)      NOT NULL UNIQUE,
    iso_alpha3     CHAR(3)      NOT NULL UNIQUE,
    name_ru        VARCHAR(200) NOT NULL,
    name_en        VARCHAR(200) NOT NULL,
    is_unfriendly  BOOLEAN      NOT NULL DEFAULT FALSE,  -- ПП 430-р, manual seed
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 2. Areals (economic zones)
CREATE TABLE IF NOT EXISTS kvota.areals (
    code        VARCHAR(20)  PRIMARY KEY,                -- EAEU, CIS, FTA-VN, FTA-IR, FTA-SRB, LRC, UNFRIENDLY
    name_ru     VARCHAR(200) NOT NULL,
    description TEXT
);

-- 3. Country ↔ Areal mapping (many-to-many)
CREATE TABLE IF NOT EXISTS kvota.country_areals (
    country_oksm SMALLINT     NOT NULL REFERENCES kvota.countries(oksm_digital) ON DELETE CASCADE,
    areal_code   VARCHAR(20)  NOT NULL REFERENCES kvota.areals(code) ON DELETE CASCADE,
    PRIMARY KEY (country_oksm, areal_code)
);

-- 4. ТН ВЭД codes (hierarchy: 2 → 4 → 6 → 8 → 10 digit)
CREATE TABLE IF NOT EXISTS kvota.tnved_codes (
    code         VARCHAR(10)  PRIMARY KEY,
    parent_code  VARCHAR(10)  REFERENCES kvota.tnved_codes(code) DEFERRABLE INITIALLY DEFERRED,
    description  TEXT         NOT NULL,
    prim         VARCHAR(10),                            -- Primary unit (166=kg, 111=l, 796=шт)
    fetched_from VARCHAR(20)  NOT NULL DEFAULT 'alta',   -- 'alta' | 'manual'
    fetched_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 5. Payment types (8 strict rows)
CREATE TABLE IF NOT EXISTS kvota.payment_types (
    code                  VARCHAR(20) PRIMARY KEY,       -- IMP, EXP, NDS, AKC, IMPCOMP, IMPDEMP, IMPTMP, IMPDOP
    name_ru               VARCHAR(200) NOT NULL,
    depends_on_country    BOOLEAN NOT NULL DEFAULT FALSE,
    depends_on_certificate BOOLEAN NOT NULL DEFAULT FALSE
);

-- 6. Rates (3-slot model, supports ad-valorem + specific + combined)
CREATE TABLE IF NOT EXISTS kvota.tnved_rates (
    id                       BIGSERIAL    PRIMARY KEY,
    tnved_code               VARCHAR(10)  NOT NULL REFERENCES kvota.tnved_codes(code),
    payment_type             VARCHAR(20)  NOT NULL REFERENCES kvota.payment_types(code),
    country_or_areal         VARCHAR(30),                -- 'C:643' | 'A:EAEU' | NULL (base)
    valid_from               DATE         NOT NULL,
    valid_to                 DATE,                       -- NULL = current

    -- Slot 1 (always present)
    value_1_number           DECIMAL(20, 6),
    value_1_unit             VARCHAR(20),                -- 'percent' | '166' | '111' | '796' | ...
    value_1_currency         VARCHAR(3),                 -- NULL for percent

    -- Slot 2 (combined rates)
    value_2_number           DECIMAL(20, 6),
    value_2_unit             VARCHAR(20),
    value_2_currency         VARCHAR(3),
    sign_1                   VARCHAR(2),                 -- '+' | '>' | NULL — relation between slot1 and slot2

    -- Slot 3 (rare — third-component rates)
    value_3_number           DECIMAL(20, 6),
    value_3_unit             VARCHAR(20),
    value_3_currency         VARCHAR(3),
    sign_2                   VARCHAR(2),

    raw_value_string         TEXT,                       -- Human-readable: "10%, но не менее 0.04 евро/кг"

    certificate_required     BOOLEAN NOT NULL DEFAULT FALSE,
    sp_certificate_required  BOOLEAN NOT NULL DEFAULT FALSE,

    source                   VARCHAR(20) NOT NULL,       -- 'alta-live' | 'alta-revalidate' | 'manual'
    source_fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at             TIMESTAMPTZ NOT NULL DEFAULT now(),  -- Q3 decision

    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_tnved_rates UNIQUE (
        tnved_code, payment_type, country_or_areal, valid_from,
        certificate_required, sp_certificate_required
    )
);

-- 7. Non-tariff measures (certifications, bans, licenses)
CREATE TABLE IF NOT EXISTS kvota.tnved_non_tariff_measures (
    id              BIGSERIAL    PRIMARY KEY,
    tnved_code      VARCHAR(10)  NOT NULL REFERENCES kvota.tnved_codes(code),
    country_or_areal VARCHAR(30),
    measure_type    VARCHAR(50)  NOT NULL,               -- 'certification' | 'ban' | 'license' | ...
    name            VARCHAR(500) NOT NULL,
    description     TEXT,
    document_basis  TEXT,
    document_link   TEXT,
    valid_from      DATE,
    valid_to        DATE,
    source          VARCHAR(20)  NOT NULL,
    source_fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. АПУ classifier cache (Phase 2 surface, but client exists Phase 1)
CREATE TABLE IF NOT EXISTS kvota.tnved_apu_cache (
    id                BIGSERIAL    PRIMARY KEY,
    query_text        TEXT         NOT NULL,
    payload_id        VARCHAR(100),
    response_json     JSONB        NOT NULL,
    last_used_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 9. Classification log (audit trail of Express/АПУ calls)
CREATE TABLE IF NOT EXISTS kvota.tnved_classification_log (
    id              BIGSERIAL    PRIMARY KEY,
    quote_item_id   BIGINT,
    method          VARCHAR(20)  NOT NULL,               -- 'express' | 'apu' | 'manual' | 'history'
    input_text      TEXT         NOT NULL,
    suggested_codes JSONB        NOT NULL,
    chosen_code     VARCHAR(10),
    user_id         UUID,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

### ALTER quote_items (3 columns, NOT 5)

```sql
ALTER TABLE kvota.quote_items
    ADD COLUMN IF NOT EXISTS country_of_origin_oksm SMALLINT REFERENCES kvota.countries(oksm_digital),
    ADD COLUMN IF NOT EXISTS has_origin_certificate BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS has_fta_certificate    BOOLEAN NOT NULL DEFAULT FALSE;
-- ❌ DROPPED from REQ-1 (Q7): customs_rates_snapshot JSONB, customs_rates_snapshot_date DATE
```

### Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_rates_lookup
    ON kvota.tnved_rates(tnved_code, payment_type, valid_from DESC);

CREATE INDEX IF NOT EXISTS idx_rates_country
    ON kvota.tnved_rates(country_or_areal)
    WHERE country_or_areal IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rates_last_used
    ON kvota.tnved_rates(last_used_at DESC);              -- For Q3 cron lookup

CREATE INDEX IF NOT EXISTS idx_apu_cache_last_used
    ON kvota.tnved_apu_cache(last_used_at DESC);
```

### Seed data

| Table | Source | Rows |
|-------|--------|------|
| `payment_types` | Inline SQL — 8 hardcoded rows with correct flags | 8 |
| `countries` | Росстандарт ОКСМ — separate file `migrations/298_seed_oksm_countries.csv` imported via `\copy` | ~250 |
| `areals` | Inline SQL — 7 hardcoded rows (EAEU, CIS, FTA-VN, FTA-IR, FTA-SRB, LRC, UNFRIENDLY) | 7 |
| `country_areals` | Inline SQL — derived mapping | ~80 |
| `countries.is_unfriendly` | Inline UPDATE per ПП 430-р lookup at migration date (~50 countries) | UPDATE |

**Idempotency:** All `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `ON CONFLICT DO NOTHING` for seeds.

**Bootstrap для self-FK:** `parent_code` FK declared `DEFERRABLE INITIALLY DEFERRED` — позволяет insert hierarchy в одном transaction блоке. Phase 1 миграция вставляет только 99 двузначных корневых кодов; остальное приходит органически из Alta Такса при первом resolve.

---

## Service Layer

### `services/alta_client.py` (REQ-2, ~600 lines)

**Public API:**

```python
class AltaApiError(Exception):
    code: int
    message: str

class AltaClient:
    def __init__(self, login: str, password: str): ...

    async def get_rates(self, tncode: str, country: int, date: date,
                       certificate: bool = False, sp_certificate: bool = False) -> list[Rate]: ...

    async def get_non_tariff_measures(self, tncode: str, country: int,
                                     mode: Literal['import', 'export'] = 'import') -> list[Measure]: ...

    async def apu_suggest(self, query: str, limit: int = 10) -> ApuSuggestResponse: ...
    async def apu_codes(self, payload_id: str, limit: int = 10) -> list[ApuCode]: ...

    async def classify_batch(self, items: list[ExpressItem],
                            request_id: str) -> ExpressBatchResponse: ...

# DI factory
def get_alta_client() -> AltaClient: ...   # Q6: FastAPI Depends, lazy singleton from env
```

**Internal architecture:**
- `_sign(param: str) -> str` — MD5 двойной hash, `param` в **исходных UTF-8 строках** (gotcha #1)
- `_decode_xml(resp: httpx.Response) -> str` — windows-1251/UTF-8 detection через response charset header → fallback на XML declaration → fallback на `windows-1251` для Такса (gotcha #2)
- `_parse_response(xml: str) -> ParsedResult` — error code recognition (100/110/120/140/201) + undocumented code handling (REQ-2 AC#6)
- `_poll_express(request_id: str)` — `POLL_MAX_ATTEMPTS = 6`, `POLL_DELAY_SECONDS = 2.0`
- `_log_packet_left(left_count: int)` — emit warning at < 100, throttled 1/hour through `services/telegram_service.notify_admin()` (Q2)

**Phase 0 lift:** `sign_request()`, `build_request_xml()`, `parse_response()`, `AltaApiError` переносятся как-есть из `phase0_eval_alta_express.py`. Sync→async обёртка через `httpx.AsyncClient`.

**Credentials handling (Q6 = FastAPI Depends):**
- Module-level lazy singleton:
  ```python
  _client_singleton: AltaClient | None = None

  def get_alta_client() -> AltaClient:
      global _client_singleton
      if _client_singleton is None:
          login = os.environ['ALTA_LOGIN']
          password = os.environ['ALTA_PASSWORD']
          _client_singleton = AltaClient(login, password)
      return _client_singleton
  ```
- Endpoint usage: `client: AltaClient = Depends(get_alta_client)`
- Test override: `app.dependency_overrides[get_alta_client] = lambda: MockAltaClient()`
- Plaintext password живёт только в области конструктора, в attribute хранится `_password_md5` (REQ-2 AC#2)

**Timeouts/retries:** 30.0s HTTP timeout, 2 max retries on network errors with backoff (1s, 2s).

---

### `services/rate_resolver.py` (REQ-3, ~250 lines)

**Public API:**

```python
async def resolve_rate(
    db: AsyncConnection,
    tnved_code: str,
    payment_type: str,
    country_oksm: int,
    date: date,
    has_certificate: bool = False,
    *,
    alta_client: AltaClient,
    quote_item_id: int | None = None,  # For retroactive snapshot lookup
) -> Rate | None: ...
```

**Algorithm:**

```
1. If quote_item_id provided AND quote.status >= APPROVED:
     Read snapshot from quote_versions.input_variables.customs_rates[quote_item_id]
     Return rate from snapshot (REQ-3 AC#8 with Q7 simplification)

2. Tier-1 lookup: exact country
     SELECT FROM tnved_rates
     WHERE tnved_code = $1 AND payment_type = $2
       AND country_or_areal = 'C:' || $3
       AND valid_from <= $4 AND (valid_to IS NULL OR valid_to > $4)
       AND source_fetched_at >= now() - interval '30 days'  -- TTL
     ORDER BY valid_from DESC LIMIT 1

3. Tier-2 lookup: areals (loop over country_areals)
     For each areal in country_areals[country_oksm]:
         SELECT ... AND country_or_areal = 'A:' || areal_code

4. Tier-3 lookup: base
     SELECT ... AND country_or_areal IS NULL

5. If all dry → call alta_client.get_rates(...) → upsert all returned rows
     Re-run Tier 1-3 lookup

6. UPDATE last_used_at = now() on returned row (fire-and-forget, не блокирует response)

7. Return Rate | None (None if Alta failed or returned empty)
```

**Race-safe upsert:** Use `INSERT ... ON CONFLICT (tnved_code, payment_type, country_or_areal, valid_from, certificate_required, sp_certificate_required) DO UPDATE SET source_fetched_at = EXCLUDED.source_fetched_at, last_used_at = EXCLUDED.last_used_at`.

**Comprehensive response handling (REQ-3 AC#4):** Alta returns multiple payment_types (IMP+NDS+AKC) per single request — upsert all in single transaction.

**`is_unfriendly` not used in lookup** (REQ-3 AC#10) — Alta encodes effects in rate response automatically.

---

### `services/customs_calc.py` (REQ-4, ~200 lines)

**Public API:**

```python
def calculate_duty(
    rate: Rate,
    customs_value_rub: Decimal,
    weight_kg: Decimal,
    quantity: Decimal,
    currency_rates: dict[str, Decimal],  # {'EUR': Decimal('100.5'), ...}
) -> Decimal: ...

def calculate_customs_fee(customs_value_rub: Decimal) -> Decimal: ...   # ПП 342 step-function

def calculate_util_fee(
    tnved_code: str,
    engine_volume_cc: int,
    vehicle_age_years: int,
) -> Decimal: ...   # Returns 0 if not 87xxxx
```

**Combined rate semantics (Q1 = Option B, parallel formulas):**

```python
def calculate_duty(rate: Rate, ...) -> Decimal:
    # Three rate types
    if rate.value_1_unit == 'percent' and rate.value_2_number is None:
        # Pure ad-valorem
        return customs_value_rub * rate.value_1_number / 100

    if rate.value_1_unit != 'percent' and rate.value_2_number is None:
        # Pure specific
        unit_quantity = _resolve_unit_quantity(rate.value_1_unit, weight_kg, quantity)
        currency_rate = currency_rates[rate.value_1_currency]
        return unit_quantity * rate.value_1_number * currency_rate

    if rate.value_1_unit == 'percent' and rate.value_2_number is not None:
        # Combined
        ad_valorem = customs_value_rub * rate.value_1_number / 100
        unit_quantity = _resolve_unit_quantity(rate.value_2_unit, weight_kg, quantity)
        currency_rate = currency_rates[rate.value_2_currency]
        specific = unit_quantity * rate.value_2_number * currency_rate

        if rate.sign_1 == '>':
            return max(ad_valorem, specific)   # gotcha #3
        elif rate.sign_1 == '+':
            return ad_valorem + specific
        else:
            raise ValueError(f"Unknown sign_1 in combined rate: {rate.sign_1!r}")

    raise ValueError(f"Unsupported rate shape: {rate!r}")
```

**Pure-functional, no side effects** (REQ-4 AC#8): no DB queries, no network, no I/O. All inputs explicit; output is `Decimal`.

**Calc-engine adapter (REQ-4 AC#7 — ABSOLUTE LOCK):**

`calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` — **NEVER touched**. Integration через `services/calculation_helpers.py:build_calculation_inputs()`:

```python
# In build_calculation_inputs() — adapter layer, NOT calc_engine
def build_calculation_inputs(item: dict, ...) -> CalculationInputs:
    ...
    # Switch logic for combined rate (Q1 Option B)
    customs_rate = _load_resolved_rate_for_item(item)  # Optional[Rate]

    if customs_rate is not None and customs_rate.source in ('alta-live', 'alta-revalidate'):
        # New formula via customs_calc
        from services.customs_calc import calculate_duty
        duty_rub = calculate_duty(customs_rate, ...)
        # Convert to engine-expected fields
        inputs['customs_duty'] = duty_rub
        inputs['customs_duty_per_kg'] = Decimal('0')  # signal: don't apply legacy formula
    else:
        # Legacy combined formula in calculation_helpers.py:269+
        # SUNSET when all quote_items migrated to Alta-resolved (Phase 5+)
        inputs['customs_duty'] = item.get('customs_duty')
        inputs['customs_duty_per_kg'] = item.get('customs_duty_per_kg')

    return inputs
```

**Documented technical debt:** legacy formula path помечается комментарием `# legacy combined-rate, sunset при переводе всех quote_items на Alta-resolved (Phase 5+)`.

**ПП 342 step-function:** hardcoded bands as constant, comment `# verified 2026-05-01, проверять раз в год`.

---

### `services/customs_freeze_service.py` (REQ-8, NEW, ~150 lines)

**Public API:**

```python
@dataclass
class FreezeSnapshotResult:
    status: Literal['ok', 'cache-stale', 'abort']
    items: dict[int, ItemSnapshot]   # quote_item_id → snapshot
    source_at_freeze: Literal['alta-live', 'cache-stale', 'abort']
    warnings: list[str]
    message: str | None              # Set when status == 'abort'

async def build_snapshot(
    db: AsyncConnection,
    quote_id: int,
    *,
    alta_client: AltaClient,
) -> FreezeSnapshotResult: ...
```

**Three-tier graceful degradation (Q4 = Option C + notifications):**

```
For each quote_item in quote:
    Tier 1 — Live Alta call (preferred):
        try resolve_rate(... force_live=True ...)
            success → status = 'ok', source_at_freeze = 'alta-live'
            failure → fall to Tier 2

    Tier 2 — Cache fallback (Alta API down):
        SELECT FROM tnved_rates WHERE source_fetched_at >= now() - interval '30 days'
            found → status = 'cache-stale' (warning)
                    source_at_freeze = 'cache-stale'
                    add to warnings: "{tnved_code}/{country}: использован кэш от {fetched_at}"
            empty/stale > 30 days → fall to Tier 3

    Tier 3 — Abort:
        status = 'abort'
        message = "Не удалось получить актуальные ставки для freeze. Попробуйте через несколько минут."
        emit Telegram alert via telegram_service.notify_admin(...)
```

### Hook integration in `services/workflow_service.py`

**Hook point:** `transition_quote_status()` lines 1343-1352 (после status update commit), **trigger:** `to_status == WorkflowStatus.APPROVED`.

```python
# In services/workflow_service.py:transition_quote_status()
if to_status == WorkflowStatus.APPROVED:
    snapshot_result = await customs_freeze_service.build_snapshot(
        db, quote_id, alta_client=alta_client
    )

    if snapshot_result.status == 'abort':
        # Q4 Tier 3 — block transition + admin Telegram alert (already sent in build_snapshot)
        raise FreezeAbortedError(snapshot_result.message)

    # Extend existing quote_version creation (Q7 simplification)
    await quote_version_service.create_quote_version(
        quote_id,
        calculated_vars=existing_calculated_vars,
        # Phase 1 NEW key extending input_variables JSONB
        customs_rates=snapshot_result.items,
        source_at_freeze=snapshot_result.source_at_freeze,
    )

    # Q4 Tier 2 — non-blocking warning to UI
    if snapshot_result.status == 'cache-stale':
        # Caller (API endpoint) reads warnings + propagates to response
        return TransitionResult(success=True, warnings=snapshot_result.warnings)
```

**Re-freeze endpoint:** `POST /api/quotes/{quote_id}/refresh-customs-snapshot` (in `api/customs.py`):

```python
async def refresh_customs_snapshot(quote_id: int, request: Request, alta_client: AltaClient = Depends(get_alta_client)):
    # 1. Auth (dual JWT/session, _CUSTOMS_ROLES)
    # 2. Build new snapshot (same three-tier logic)
    # 3. Create new quote_versions row (NOT update — history saved automatically)
    new_version = await quote_version_service.create_quote_version(...)
    # 4. Audit log via existing changelog_service (Q5 = Option B)
    await changelog_service.log_event(
        event_type='customs_rates_snapshot_replaced',
        payload={
            'quote_id': quote_id,
            'old_version_id': previous_version_id,
            'new_version_id': new_version.id,
            'replaced_by_user_id': user.id,
            'reason': request_body.get('reason', 'manual_refresh'),
            'replaced_at': now,
        }
    )
    return {'success': True, 'data': {'new_version_id': new_version.id, 'warnings': snapshot_result.warnings}}
```

**Snapshot shape extending `quote_versions.input_variables`:**

```json
{
  "products": [...],
  "calculated_vars": {...},
  "customs_rates": {
    "12345": {
      "rates": [
        {"payment_type": "IMP", "value_1_number": 10, "value_1_unit": "percent",
         "calculated_amount_rub": 50000, "raw_value_string": "10%, но не менее 0.04 евро/кг"}
      ],
      "measures": [{"measure_type": "certification", "name": "...", "document_link": "..."}],
      "fetched_at": "2026-05-01T12:34:56+00:00",
      "source_at_freeze": "alta-live"
    }
  }
}
```

---

## API Layer (REQ-5)

### Handler split (existing pattern)

**`api/customs.py`** — handlers (extends existing 606-line module):

```python
async def resolve_rates_handler(
    request: Request,
    body: ResolveRatesRequest,
    alta_client: AltaClient = Depends(get_alta_client),
): ...

async def non_tariff_measures_handler(
    request: Request,
    body: NonTariffMeasuresRequest,
    alta_client: AltaClient = Depends(get_alta_client),
): ...

async def refresh_customs_snapshot_handler(
    request: Request,
    quote_id: int,
    body: RefreshSnapshotRequest,
    alta_client: AltaClient = Depends(get_alta_client),
): ...

# EXISTING — extend with optional force_live param + additive response fields
async def autofill_handler(...): ...
```

**`api/routers/customs.py`** — thin router (additive):

```python
@router.post('/resolve-rates')
async def resolve_rates(request: Request, body: ResolveRatesRequest, ...):
    return await api.customs.resolve_rates_handler(request, body, ...)

@router.post('/non-tariff-measures')
async def non_tariff_measures(request: Request, body: NonTariffMeasuresRequest, ...):
    return await api.customs.non_tariff_measures_handler(request, body, ...)
```

Re-freeze endpoint mounted under `/api/quotes/{quote_id}/refresh-customs-snapshot` — defined in `api/routers/quotes.py` if it exists, else stays in `api/routers/customs.py` with quote_id path param.

### Auth pattern (REQ-5 AC#4-5)

```python
async def resolve_rates_handler(request: Request, body, alta_client = Depends(get_alta_client)):
    """Resolve customs rates for a tnved+country+date.

    Path: POST /api/customs/resolve-rates
    Params:
        tnved_code: str — 10-digit ТН ВЭД code
        country_oksm: int — ОКСМ digital code
        date: str (ISO, optional) — defaults to today
        certificate: bool (optional)
        sp_certificate: bool (optional)
        quote_item_id: int (optional) — if set, updates quote_items.country_of_origin_oksm/customs_*
        force_live: bool (optional) — bypass cache, force Alta call
    Returns:
        {success: true, data: {rates: [Rate], total_rub, source, fetched_at}}
    Side Effects:
        - On quote_item_id: UPDATE quote_items SET country_of_origin_oksm, customs_duty, ...
        - UPDATE tnved_rates SET last_used_at = now()
    Roles: customs, admin, head_of_customs
    """
    user = _resolve_dual_auth(request)  # JWT or session, returns user with role
    if user.role not in _CUSTOMS_ROLES:
        return JSONResponse({'success': False, 'error': {'code': 'FORBIDDEN', ...}}, status_code=403)

    rate = await rate_resolver.resolve_rate(...)
    if rate is None:
        return JSONResponse(
            {'success': False, 'error': {'code': 'ALTA_UNAVAILABLE', 'message': 'Alta API недоступен, попробуйте позже'}},
            status_code=503
        )

    # Optional side effect
    if body.quote_item_id:
        await db.execute("UPDATE kvota.quote_items SET country_of_origin_oksm = $1, ...")

    # Structured logging (REQ-5 AC#9)
    logger.info('customs_resolve_rates', extra={'user_id': user.id, 'tnved_code': ..., 'cache_hit': cache_hit, 'latency_ms': ...})

    return {'success': True, 'data': {'rates': [...], 'total_rub': ..., 'source': ..., 'fetched_at': ...}}
```

### Response envelope (project convention)

```typescript
// All endpoints
{ success: true, data: T, meta?: ... }
{ success: false, error: { code: 'UNAUTHORIZED' | 'FORBIDDEN' | 'BAD_REQUEST' | 'ALTA_UNAVAILABLE' | 'INVALID_TNVED_CODE' | 'INVALID_OKSM' | 'FREEZE_ABORTED', message: string } }
```

### Backwards-compat for `_AUTOFILL_FIELDS` (REQ-5 AC#3)

Existing tuple in `api/customs.py:36`:
```python
_AUTOFILL_FIELDS = ('hs_code', 'customs_duty', 'customs_duty_per_kg', ...)
```

**Phase 1 changes — STRICTLY ADDITIVE:**
- ✅ Append: `country_of_origin_oksm`, `has_origin_certificate`, `has_fta_certificate`, `customs_rates_source`, `customs_rates_fetched_at`
- ❌ NEVER rename/remove existing fields
- ❌ NEVER change semantics of existing fields
- TS interface `frontend/src/features/customs-autofill/types.ts:CustomsAutofillSuggestion` — все новые поля **optional**

---

## Cron Layer (REQ-6)

### `api/cron.py` — new handler `cron_revalidate_rates`

```python
async def cron_revalidate_rates(
    request: Request,
    alta_client: AltaClient = Depends(get_alta_client),
):
    """Weekly revalidation of top-1000 most-used rates.

    Path: POST /api/cron/revalidate-rates
    Auth: X-Cron-Secret header
    Returns: {success: true, data: {processed, hits, updates, failures}}
    """
    _validate_cron_secret(request)

    # Top-1000 most-used stale rates (Q3: ORDER BY last_used_at DESC)
    rows = await db.fetch("""
        SELECT DISTINCT tnved_code, country_or_areal
        FROM kvota.tnved_rates
        WHERE source_fetched_at < now() - interval '7 days'
        ORDER BY MAX(last_used_at) DESC NULLS LAST
        LIMIT 1000
    """)

    stats = {'processed': 0, 'hits': 0, 'updates': 0, 'failures': 0}
    for code, country in rows:
        try:
            new_rates = await alta_client.get_rates(code, country, date.today())
            await _upsert_rates(new_rates, source='alta-revalidate')
            stats['processed'] += 1
            # ... update hits/updates based on whether values changed
        except AltaApiError as e:
            stats['failures'] += 1
            if e.code == 140:  # Insufficient funds
                await telegram_service.notify_admin(f'Cron revalidate-rates aborted: AltaApiError 140')
                break
            # ... handle packet_left < 50

    return {'success': True, 'data': stats}
```

### `api/routers/cron.py` — mount route

```python
@router.post('/revalidate-rates')
async def revalidate_rates(request: Request, ...):
    return await api.cron.cron_revalidate_rates(request, ...)
```

### `api/auth.py` — extend `PUBLIC_API_PATHS`

```python
PUBLIC_API_PATHS = [
    '/api/cron/check-overdue',
    '/api/cron/sla-check',
    '/api/cron/revalidate-rates',   # NEW
]
```

### VPS crontab (out of spec)

`(crontab -l; echo "0 4 * * 1 curl -X POST https://kvotaflow.ru/api/cron/revalidate-rates -H 'X-Cron-Secret: $CRON_SECRET'") | crontab -`

---

## Frontend Layer (REQ-7)

### Existing surfaces (extend, don't replace)

- `frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx` — per-item edit dialog, **extend** with country dropdown + checkboxes + auto-resolve button
- `frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx` — bulk grid editor, **extend** with `country_of_origin_oksm` column (read-only or via dropdown cell type)
- `frontend/src/features/customs-autofill/` — existing autofill feature, **extend** types

### New feature folders (FSD architecture)

```
frontend/src/features/customs-rate-resolve/
├── ui/
│   ├── auto-resolve-button.tsx         # "Автоподбор ставок" button
│   ├── rate-breakdown.tsx              # Display: пошлина X% + НДС 20% + (акциз) → итого N₽
│   └── source-timestamp.tsx            # "Обновлено 5 минут назад" + Refresh button
├── api/
│   └── resolve-rates.ts                # POST /api/customs/resolve-rates wrapper
├── model/
│   └── types.ts                        # Rate, BreakdownItem types
└── index.ts

frontend/src/features/customs-non-tariff-measures/
├── ui/
│   └── measures-list.tsx               # Pull-trigger button (3₽ aware) + measures list
├── api/
│   └── fetch-measures.ts               # POST /api/customs/non-tariff-measures
└── index.ts
```

### Country dropdown — searchable (project standard)

**Following `feedback_searchable_select.md` mandate** — ALL dropdowns must be searchable, no exceptions.

```tsx
// frontend/src/features/quotes/ui/customs-step/country-dropdown.tsx
import { Combobox, Command } from '@/shared/ui/combobox';   // shadcn pattern

export function CountryDropdown({ value, onChange }: Props) {
  const { data: countries } = useCountries();   // Reads kvota.countries via Supabase JS

  return (
    <Combobox
      options={countries.map(c => ({
        value: c.oksm_digital,
        label: c.name_ru,
        badge: c.is_unfriendly ? '⚠️ Недружественная (ПП 430-р)' : null,
      }))}
      value={value}
      onChange={onChange}
      placeholder="Выберите страну происхождения"
      searchPlaceholder="Поиск по названию..."
      filterFn={substringMatchCaseInsensitive}
      emptyMessage="Не найдено"
    />
  );
}
```

**Reference:** `features/customers/ui/tab-assignees.tsx` (existing searchable pattern from `feedback_searchable_select.md`).

### Supabase JS direct read (countries lookup)

Countries — relatively static reference data, OK to read directly:

```ts
const { data } = await supabase
  .schema('kvota')                       // CRITICAL: kvota schema
  .from('countries')
  .select('oksm_digital, name_ru, is_unfriendly')
  .order('name_ru');
```

Business logic (resolve-rates, freeze) — **always через Python API**, никогда direct DB.

### Type generation pipeline

After migration 298 deploy:
```bash
cd frontend && npm run db:types
```
Updates `frontend/src/shared/types/database.types.ts` with new tables/columns. Critical — без этого TS не знает про новые поля (memory `feedback_regen_types_before_schema_drop.md`).

### Q4 freeze warnings UI

- **Tier 1 (live success):** silent
- **Tier 2 (cache fallback):** non-blocking toast — `⚠️ Используется кэш ставок от {fetched_at}, Alta API временно недоступна. Snapshot создан, но проверьте актуальность ставок.`
- **Tier 3 (abort):** modal — `🛑 Не удалось зафиксировать ставки. Попробуйте через несколько минут. Если проблема повторяется — обратитесь к администратору.`

UI handler reads `warnings[]` and `error.code === 'FREEZE_ABORTED'` from API response to discriminate tiers.

---

## Cross-cutting Concerns

### Telegram alerting (Q2)

All packet warnings + cron failures + freeze aborts → `services/telegram_service.notify_admin(message)`. Throttle: max 1 packet-warning per hour (avoid spam if cron triggers every 10 min). Reuses existing admin-channel ID from overdue/SLA notifications.

### Changelog audit (Q5)

Re-freeze events logged via `services/changelog_service.log_event('customs_rates_snapshot_replaced', payload)`. Existing changelog UI (admin panel) automatically renders new event type.

### Type safety pipeline

```
Migration 298 deployed → npm run db:types → TS sees new columns →
implementation in frontend/src/ compiles cleanly →
localhost:3000 testing (memory reference_localhost_browser_test.md) →
git push → CI → production deploy
```

---

## Test Strategy

### Service-level (TDD per /lean-tdd workflow)

| Module | File | Coverage |
|--------|------|----------|
| `services/alta_client.py` | `tests/services/test_alta_client.py` | MD5 sign correctness, XML parse (windows-1251 + UTF-8), error code recognition (100/110/120/140/201), undocumented codes, polling timeout, packet warning logic |
| `services/rate_resolver.py` | `tests/services/test_rate_resolver.py` | Three-tier priority lookup, TTL stale detection, race-safe upsert via `ON CONFLICT`, `last_used_at` update, snapshot lookup for frozen quotes |
| `services/customs_calc.py` | `tests/services/test_customs_calc.py` | Ad-valorem, specific, combined (`max` + `+`), ПП 342 bands, ПП 81 (87xxxx only), Decimal precision, ValueError on bad shapes |
| `services/customs_freeze_service.py` | `tests/services/test_customs_freeze.py` | Tier 1/2/3 fallback flow, snapshot shape, FreezeAbortedError raised on Tier 3 |

**Mocking:** `app.dependency_overrides[get_alta_client] = lambda: MockAltaClient(canned_responses)` (Q6 testability).

### API-level

| Endpoint | File | Coverage |
|----------|------|----------|
| `POST /api/customs/resolve-rates` | `tests/api/test_customs_api.py` | Auth (JWT + session), role gate, 503 on Alta down, side-effect on quote_item_id, response envelope |
| `POST /api/customs/non-tariff-measures` | same | Auth, response shape |
| `POST /api/quotes/{id}/refresh-customs-snapshot` | `tests/api/test_refresh_snapshot.py` | New version row created, changelog event logged, three-tier fallback propagated to response |
| `POST /api/cron/revalidate-rates` | `tests/api/test_cron_revalidate.py` | X-Cron-Secret validation, top-1000 selection, packet_left alerting, idempotent re-run |

### Migration test

`tests/migrations/test_298_tnved_foundation.py` — apply on empty test DB → assert all 9 tables exist with expected schema, indexes present, seed counts (~250 countries, 8 payment_types, 7 areals).

### Frontend (manual + Playwright manifest)

Per /lean-tdd Phase 5e — generate test manifest from REQs, run on localhost:3000 with prod Supabase. Critical paths:
1. Open quote_item edit dialog → fill country dropdown (verify search works) → check certificates → click "Автоподбор ставок" → verify breakdown displayed
2. Click "Показать меры нетарифного" → verify list rendered
3. Approve quote → verify quote_versions row created with customs_rates JSONB key
4. Re-freeze: click "Пересчитать по текущим ставкам" → confirm modal → verify new version row + changelog event
5. Tier 2 simulation (mock Alta down): verify cache-stale warning toast
6. Tier 3 simulation (cache empty + Alta down): verify abort modal

---

## Risk Mitigation Summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Migration 298 conflict with parallel PRs | Med | Verify `ls migrations/` immediately before merge; bumping номера тривиально |
| Alta API outage during freeze (legal-critical workflow) | High | Q4 three-tier graceful degradation + Telegram admin alert + UI modal |
| Packet exhaustion on Alta Express | Med | Q2 Telegram alerts at `left_count < 100`, throttle 1/hour, log every call |
| Combined-rate formula divergence (legacy vs new path) | High | Q1 explicit switch by `rate.source` field; legacy quote_items remain on legacy formula until Phase 5+ sunset |
| windows-1251 XML decoding | Low | Detect via response charset / XML declaration → explicit `decode('windows-1251')` fallback |
| `_AUTOFILL_FIELDS` backwards-compat | Med | Strict additive-only changes; never rename/change semantics of existing fields; TS interface fields all optional |
| Calc engine accidentally modified | Critical | Pre-merge check: `git diff calculation_engine.py calculation_models.py calculation_mapper.py` MUST be empty |
| Race on concurrent rate upsert | Low | UNIQUE constraint + `ON CONFLICT DO UPDATE` |
| Type drift after migration | Med | `npm run db:types` mandatory before frontend implementation |

---

## Parallelization Plan (informs spec-tasks phase)

```
Wave 1 (parallel): Migration 298 + types regen ║ AltaClient skeleton
Wave 2 (parallel): rate_resolver ║ customs_calc
Wave 3 (sequential, depends on services): API endpoints (resolve-rates, non-tariff-measures, refresh-snapshot)
Wave 4 (parallel with Wave 3 backend done): Frontend components ║ Cron revalidate endpoint
Wave 5 (sequential): customs_freeze_service ║ workflow_service hook integration
```

Estimated: ~3 weeks at 1 developer (matches handoff).

---

## Готовность к tasks phase

✅ All 8 REQs mapped to concrete file changes
✅ Q7 architectural simplification baked in (drop snapshot columns from quote_items, extend quote_versions)
✅ Calc engine lock prominent в REQ-4 design + risk register
✅ All 7 design questions resolved (per decisions.md)
✅ Existing customs infrastructure reuse documented per REQ
✅ Test strategy spans unit/api/migration/frontend layers
✅ Parallelization plan ready for spec-tasks decomposition

**Next:** `/kiro:spec-tasks customs-phase-1-rates-and-measures -y`
