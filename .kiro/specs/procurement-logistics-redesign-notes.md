# Procurement / Logistics / Customs — Design Notes for Next.js Migration

**Source:** User feedback FB-260316-111518 + Batch E triage (2026-03-19)
**Use when:** UX audit before migrating procurement, logistics, or customs pages to Next.js

---

## Procurement Table Redesign (FB-260316-111518)

Requested columns for procurement table:
1. Бренд
2. Артикул из запроса (от клиента)
3. Артикул производителя (от поставщика)
4. Наименование из запроса
5. Наименование производителя
6. Количество (ед. товара)
7. Цена (+ валюта)
8. Готовность к отгрузке
9. Вес, КГ (`quote_items.weight_in_kg` — exists)
10. Габариты, мм (NOT объём — нужны dimensions, не volume)
11. НДС % (`vat_rate` — **new column needed**, currently only `price_includes_vat` boolean)
12. Инвойс

**Remove:** IDN-SKU из таблицы закупок (не нужен МОЗ, только артикулы)

## Article Mismatch Highlighting

Подсвечивать отличающиеся артикулы для МОЗ и причины отличия для МОП:
- Если артикул производителя ≠ артикул из запроса → visual highlight
- МОП видит причину замены (поле "причина отличия" или комментарий от МОЗ)

## Chat on All Department Pages

Вынести чат (comments tab) на все страницы отделов, не только quote detail.
- Procurement page — чат по позициям
- Logistics page — чат по отгрузке
- Customs page — чат по декларации

## Cancelled/Rejected Deals Feedback (ОС)

Два типа обратной связи:
1. **Отменённые** (клиент отказался) — info от МОП: почему клиент отказался / проиграли тендер
2. **Отклонённые** (не можем дать цены) — info от МОЗ/МОТ/МОЛ: почему не можем дать цены или привезти

Нужны:
- Поле `cancellation_reason` на quotes (или отдельная таблица feedback)
- UI: модалка при смене статуса на "отменена"/"отклонена" с обязательным комментарием
- Dashboard: агрегация причин отмен/отклонений по периодам

## Positions Registry with Prices

Отдельный реестр позиций на которые дали цены:
- Фильтры: бренд, МОЗ, дата
- Колонки: дата, статус, бренд, артикул производителя, наименование, цена (+валюта), МОЗ, инвойс/офер
- Статусы: в работе у МОЗ, цены даны, покупай (клиент согласовал + оплата)

## Logistics — SVH + Additional Expenses (Batch E1)

- СВХ (склад временного хранения) переносим из "Таможня" в "Логистика"
- Добавить generic "Дополнительные расходы" в logistics stages
- Потребует новую DB категорию + миграцию существующих данных

## File Upload Indicator (Batch E3)

- `supplier_invoices.invoice_file_url` — колонка есть, данных 0
- При миграции: upload → Supabase Storage → URL сохраняется → UI показывает статус

## Weight Column Dedup (Batch E4)

- `quote_items.weight_in_kg` и `quote_items.weight_kg` — дублируют друг друга
- Унифицировать при миграции (оставить одну колонку)
- Добавить `vat_rate` (decimal) для ставки НДС %
