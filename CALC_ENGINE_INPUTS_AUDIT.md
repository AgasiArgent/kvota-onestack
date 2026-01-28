# Calculation Engine Inputs Audit

## Правило: Храним в оригинальной валюте, конвертируем в USD только перед расчётом

**Важно (2026-01-28):** Brokerage и DM Fee хранятся в ОРИГИНАЛЬНОЙ валюте, которую ввёл пользователь.
Конвертация в USD происходит ТОЛЬКО в `build_calculation_inputs()` непосредственно перед передачей в Calculation Engine.

Это упрощает код и исключает ошибки округления при двойной конвертации.

---

## 1. ДЕНЕЖНЫЕ ЗНАЧЕНИЯ (требуют конвертации в USD)

### 1.1 Цена закупки (per-item)
| Поле | Источник | Валюта хранения | Конвертация | Статус |
|------|----------|-----------------|-------------|--------|
| `base_price_vat` | quote_items.purchase_price_original | Валюта поставщика (purchase_currency) | Через `exchange_rate` в Phase 1 (R16=P16/rate) | ✅ OK |

### 1.2 Логистика (quote-level, агрегируется из инвойсов)
| Поле | Источник | Валюта хранения | Конвертация | Статус |
|------|----------|-----------------|-------------|--------|
| `logistics_supplier_hub` | invoices (aggregated) | Разные валюты в инвойсах | ✅ Конвертируется в USD при агрегации | ✅ OK |
| `logistics_hub_customs` | invoices (aggregated) | Разные валюты в инвойсах | ✅ Конвертируется в USD при агрегации | ✅ OK |
| `logistics_customs_client` | invoices (aggregated) | Разные валюты в инвойсах | ✅ Конвертируется в USD при агрегации | ✅ OK |

### 1.3 Брокерские услуги (quote-level, вводятся на странице таможни)
| Поле | Источник | Валюта хранения | Конвертация | Статус |
|------|----------|-----------------|-------------|--------|
| `brokerage_hub` | Form input (customs page) | С указанием валюты (brokerage_hub_currency) | ✅ Конвертируется в USD перед Calculation Engine | ✅ OK (после фикса) |
| `brokerage_customs` | Form input | С указанием валюты (brokerage_customs_currency) | ✅ Конвертируется в USD перед Calculation Engine | ✅ OK (после фикса) |
| `warehousing_at_customs` | Form input | С указанием валюты (warehousing_at_customs_currency) | ✅ Конвертируется в USD перед Calculation Engine | ✅ OK (после фикса) |
| `customs_documentation` | Form input | С указанием валюты (customs_documentation_currency) | ✅ Конвертируется в USD перед Calculation Engine | ✅ OK (после фикса) |
| `brokerage_extra` | Form input | С указанием валюты (brokerage_extra_currency) | ✅ Конвертируется в USD перед Calculation Engine | ✅ OK (после фикса) |

### 1.4 DM Fee (вознаграждение ЛПР)
| Поле | Источник | Валюта хранения | Конвертация | Статус |
|------|----------|-----------------|-------------|--------|
| `dm_fee_value` (fixed) | Form input | С указанием валюты (dm_fee_currency) | ✅ Конвертируется в USD в POST handler | ✅ OK (после фикса) |

---

## 2. ПРОЦЕНТНЫЕ ЗНАЧЕНИЯ (не требуют конвертации)

| Поле | Описание | Статус |
|------|----------|--------|
| `supplier_discount` | Скидка поставщика (%) | ✅ OK |
| `markup` | Наценка (%) | ✅ OK |
| `rate_forex_risk` | Резерв на курсовую разницу (%) | ✅ OK |
| `import_tariff` | Таможенная пошлина (%) | ✅ OK |
| `excise_tax` | Акциз (%) | ✅ OK |
| `advance_from_client` | Аванс от клиента (%) | ✅ OK |
| `advance_to_supplier` | Аванс поставщику (%) | ✅ OK |
| `rate_fin_comm` | Финансовая комиссия (%) | ✅ OK |
| `rate_loan_interest_annual` | Годовая ставка (%) | ✅ OK |
| `rate_insurance` | Ставка страхования (%) | ✅ OK |

---

## 3. ВРЕМЕННЫЕ ЗНАЧЕНИЯ (дни, не требуют конвертации)

| Поле | Описание | Статус |
|------|----------|--------|
| `delivery_time` | Срок поставки (дни) | ✅ OK |
| `time_to_advance` | Дни до аванса | ✅ OK |
| `time_to_advance_loading` | Дни до аванса на погрузке | ✅ OK |
| `time_to_advance_on_receiving` | Дни до оплаты после получения | ✅ OK |
| `customs_logistics_pmt_due` | Дни оплаты таможни/логистики | ✅ OK |

---

## 4. ENUM/STRING ЗНАЧЕНИЯ (не требуют конвертации)

| Поле | Описание | Статус |
|------|----------|--------|
| `supplier_country` | Страна поставщика | ✅ OK |
| `offer_incoterms` | Условия поставки (DDP, EXW, etc.) | ✅ OK |
| `currency_of_base_price` | Валюта закупки | ✅ OK |
| `currency_of_quote` | Валюта КП | ✅ OK |
| `seller_company` | Компания-продавец | ✅ OK |
| `offer_sale_type` | Тип сделки (поставка, транзит) | ✅ OK |
| `dm_fee_type` | Тип вознаграждения (Фикс, %) | ✅ OK |

---

## 5. EXCHANGE RATE

| Поле | Описание | Статус |
|------|----------|--------|
| `exchange_rate` | Курс purchase_currency → quote_currency | ✅ Рассчитывается per-item в build_calculation_inputs |

---

## ИСПРАВЛЕННЫЕ ПРОБЛЕМЫ

### ✅ Проблема 1: Brokerage без указания валюты (ИСПРАВЛЕНО)
**Поля:** brokerage_hub, brokerage_customs, warehousing_at_customs, customs_documentation, brokerage_extra

**Было:** Пользователь вводил числа без указания валюты. Система не знала, в какой валюте введены значения.

**Исправлено:**
- Добавлены селекторы валюты для каждого brokerage поля на странице таможни
- Валюты хранятся в JSONB: `brokerage_hub_currency`, `brokerage_customs_currency`, etc.
- Конвертация в USD выполняется перед передачей в Calculation Engine
- По умолчанию валюта = RUB (как указал пользователь)

### ✅ Проблема 2: DM Fee конвертировался в quote_currency, не USD (ИСПРАВЛЕНО)
**Поле:** dm_fee_value

**Было:** В build_calculation_inputs конвертировался в quote_currency.

**Исправлено:** Конвертация теперь выполняется в USD в POST handler перед вызовом build_calculation_inputs.

---

## ТЕКУЩЕЕ СОСТОЯНИЕ

Все денежные значения теперь корректно конвертируются в USD перед передачей в Calculation Engine:

| Категория | Значения | Конвертация | Статус |
|-----------|----------|-------------|--------|
| Цена закупки | base_price_vat | purchase_currency → USD через exchange_rate | ✅ |
| Логистика | logistics_* (3 поля) | Разные валюты → USD при агрегации из invoices | ✅ |
| Брокерские | brokerage_* (5 полей) | *_currency → USD в POST handler | ✅ |
| DM Fee | dm_fee_value | dm_fee_currency → USD в POST handler | ✅ |

---

## VALIDATION EXPORT (export_validation_service.py)

### Правило: API_Inputs должен содержать USD значения

Excel-шаблон ожидает:
- Колонка C: значение в USD
- Колонка D: конвертация USD → валюта КП через формулу `=C*$E$2`

**Исправлено (2026-01-28):**
- `create_validation_excel()` теперь конвертирует brokerage и DM fee из оригинальной валюты в USD
- `import_tariff` читается из поля `customs_duty` (заполняется таможней), с fallback на `import_tariff`

| Поле в API_Inputs | Источник | Конвертация |
|-------------------|----------|-------------|
| W5 brokerage_hub | variables + *_currency | original → USD |
| W6 brokerage_customs | variables + *_currency | original → USD |
| W7 warehousing | variables + *_currency | original → USD |
| W8 documentation | variables + *_currency | original → USD |
| W9 other_costs | variables + *_currency | original → USD |
| AG4/AG6 dm_fee_value | variables + dm_fee_currency | original → USD |
| X16 import_tariff | item.customs_duty or item.import_tariff | passthrough (%) |

---

*Audit date: 2026-01-28*
*Updated: 2026-01-28 (validation export fixed)*
