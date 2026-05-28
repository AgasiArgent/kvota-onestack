# Testing 2 — Red Cells Triage (Round 5)

**Date:** 2026-05-26
**Source:** Google Sheets XLSX export (preserves cell colors) — 14 unique tester rows red-flagged
**Scope:** Cross-reference against 24 PRs (#233–#257) shipped in rounds 22–24.

---

## Bucket A — Already shipped (REFRESH or RE-VERIFY)

These 4 rows map to PRs that landed on prod. First action: ask tester to **Ctrl+Shift+R** + retest. If still red after refresh, treat as scope-extension / regression.

| Row | Page | Tester comment (verbatim) | PR shipped | Action |
|-----|------|---------------------------|------------|--------|
| **36** | `/quotes/.../?step=calculation` — Расчет | «Не тянет Цену в валюте КП, Сумму в валюте КП. На этапе расчета необходимо выводить информацию о пошлинах и сертификации. Чтобы МОП ориентировался в КП» | #129 (calc-step info card: logistics + customs + certs) | **VERIFY** — info card lives in different DOM node than price columns. Tester may still be missing the **per-item currency/sum columns** which our info card didn't add. Check live, then either close (refresh) or open new PR for column visibility. |
| **48** | `/quotes/.../?step=calculation` — Расчет | «Сроки и стоимость на каждый сегмент, но не отражать имя поставщика. Компания и условия: выбор нашей орган…» (extended) | #129 (calc-step info card) | **EXTEND** — original ask was «show logistics + customs + certs». Tester now adds: per-segment cost+time, hide supplier name, our-company picker + terms. New scope = new PR. |
| **58** | `/quotes/{id}?invoice={uuid}` — Логистика | «страница прыгает вверх PRIORITY» (кнопка шаблон маршрута) | #130 (logistics scroll preservation) | **REFRESH** — exact ask we fixed. Almost certainly stale cache. |
| **83** | `/quotes/.../?step=procurement` — Закупки | «Данные скрыты PRIORITY» (при завершенной закупке) | #132 (procurement role gate — РОЗ/СтМОЗ/МОЗ see data after completion) | **REFRESH** — exact ask. Verify the test quote `311d9173` actually has procurement_completed_at set. If not, this is a different bug. |

**Recommended action for Bucket A:** **Manual verify in browser** (one quick walkthrough), then split: refresh-bucket → tester ping; extend-bucket → new PRs.

---

## Bucket B — Wrong target page (1 row)

| Row | Page | Tester comment | Previously shipped | Action |
|-----|------|----------------|--------------------|--------|
| **82** | `/companies?tab=buyer` — Юр лица | «нет кнопки PRIORITY» (добавить юр. лицо и изменить) | #131 (Row 82) — we added button on **/customers** | **NEW WORK** — same UX, different page. Add Создать/Редактировать buttons to `/companies?tab=buyer` (РОЗ role). Reuse component from /customers if possible. |

---

## Bucket C — New work (9 rows)

| # | Row | Page | Roles | Tester comment | Priority | Size |
|---|-----|------|-------|----------------|----------|------|
| 1 | **80** | `/quotes/.../?step=logistics` | РОЛ, МОЛ | «Логистика не завершается пока не проценятся все КПП» | P1 — gate | S |
| 2 | **81** | `/quotes/{id}` — Логистика | РОЛ, МОЛ | «Дополнительные расходы — выделить кнопку Добавить» | P2 — polish | XS |
| 3 | **84** | `/suppliers` | РОЗ, СтМОЗ, МОЗ | Columns redesign: Наименование, Страна, МОЗ, Дата последнего КПП, Сумма КПП, Статус. Убрать Код. | P1 — UX | M |
| 4 | **85** | `/quotes/.../?step=procurement` | **ALL 9 ROLES** | «При введении MOQ — он отображается и калькулируется на следующих этапах PRIORITY» | **P0** | M |
| 5 | **86** | `/quotes/.../?step=customs` | РОЛ | «Полностью переделать модальное окно. Нет возможности редактирования. Автор — пишет id. Расчет по позициям непонятный» | P1 — redesign | L |
| 6 | **87** | `/quotes/.../?step=calculation` | РОП, МОП | «Выводит ошибку. Без цены: Китайский бренд — Миксер пневматический PM-3/TJ3. + позиции не было в КПП (отказались МОП и МОЗ). + позицию запретили к ввозу на этапе таможни. PRIORITY» | **P0** — bug | M |
| 7 | **88** | `/quotes/{id}` — Закупки → Скачать XLS | РОЗ, СтМОЗ, МОЗ | «Арт. запрошенный — выводит IDN-SKU, а не артикул. Ед. изм. — не выводит» | P1 — bug | S |
| 8 | **89** | `/quotes/.../?step=procurement` | РОЗ, СтМОЗ, МОЗ | «Добавить ячейку с дедлайном КПП в тело КПП» | P2 — feature | S |
| 9 | **90** | `/quotes/.../?step=calculation` | РОП, МОП | «Позиции должны идти по порядку из запроса. Дать возможность не выбирать поставщика вообще» | P1 — UX | M |

---

## Recommended Phase Plan

### Phase 0 (5 min) — Cache sanity
1. Open Row 58, 83 in browser as tester role → confirm fixes live → ping tester to hard-refresh.

### Phase 1 — P0 quick wins (parallel dispatch)
- **Row 87** — calc-step crash on disallowed-import items (РОП/МОП can't open calc step for affected quotes).
- **Row 85** — MOQ propagation (high-value, touches calc engine inputs — careful, calc_engine itself is LOCKED).

### Phase 2 — P1 fixes (parallel dispatch)
- **Row 82** — `/companies?tab=buyer` add buttons (reuse customers pattern).
- **Row 80** — logistics completion gate (block завершение until all КПП processed).
- **Row 84** — suppliers table columns redesign.
- **Row 88** — XLS template column fix (IDN-SKU → Артикул, add Ед. изм).
- **Row 90** — calc step position order + optional supplier.

### Phase 3 — P1 redesign + Bucket A extend (sequential)
- **Row 86** — customs certificate modal full redesign.
- **Row 48 extend** — calc-step segment-level logistics card + company picker.

### Phase 4 — Polish (parallel after Phase 1–3 land)
- **Row 81** — visible "Add" button for logistics extras.
- **Row 89** — KPP deadline cell in body.

---

## Critical constraints reminder

- ✅ Local main locked in worktree `onestack-customs-phase1` → all branches `git checkout -b <br> origin/main`.
- ✅ `gh pr create` always `--head <branch> --base main`.
- ✅ Calc engine LOCKED: `calculation_engine.py` / `calculation_models.py` / `calculation_mapper.py` — Row 85 MUST adapt input via `build_calculation_inputs()` only.
- ✅ Developer agents use `isolation:"worktree"` + path-discipline block.
- ✅ Migrations: SSH → `cd /root/onestack && git pull && bash scripts/apply-migrations.sh`. Wrap multi-statement in BEGIN/COMMIT.
- ✅ Next migration = m331.
- ✅ 90s between merges (or `gh pr merge --auto`).
