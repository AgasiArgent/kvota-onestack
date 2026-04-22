# Prompt: Claude Design — Logistics & Customs UI Implementation

**Usage:**
1. Attach `/tmp/claude-design-context.tar.gz` to the Claude Design chat (or all 12 files individually if tar not supported by your platform).
2. Copy the block below from `## PROMPT START` to `## PROMPT END` into the chat.
3. Work iteratively — Claude Design pauses after each feature, you approve before next.

**Context for this prompt:** The main project repository (`onestack`) is **not public on GitHub** — Claude Design cannot access it via repo connector. All necessary context is provided **as attachments**. The only related public repo is `kvotaflow-design-system` (design-system preview), which may contain an older version of `design-system.md` — use the one from attachments instead.

---

## PROMPT START

Ты — frontend designer/engineer для OneStack (Kvota Quotation Management System). Делаем редизайн stages **"Логистика"** и **"Таможня"** в рамках quote → deal pipeline.

### Критично: контекст в attachments, репо недоступен

Главный репозиторий OneStack **не публичный** — у тебя нет прямого file access к нему. Весь нужный контекст прикреплён к этому сообщению (12 файлов + папка `wireframes/`). **Не пытайся резолвить пути вида `frontend/src/...` через file read — используй только attachments.**

Если всплывёт необходимость в файле, которого нет в attachments — **спроси**, и я приложу. Не угадывай структуру.

### Stack (из `frontend-package.json`)

- **Next.js 16.1.6** (App Router)
- **React 19.2.3**
- **Tailwind CSS v4** + `tw-animate-css`
- **shadcn/ui** (последний релиз), `@base-ui/react 1.3.0`
- **Font:** Plus Jakarta Sans (импорт в `globals.css`)
- **Handsontable 17.0** + `@handsontable/react 16.2` — сохраняем для customs, не заменяем на AG Grid (AG Grid НЕ в dependencies)
- **Drag & Drop:** `@dnd-kit/core 6.3.1` + `@dnd-kit/sortable 10.0.0` — используй для Route Constructor
- **React Table:** `@tanstack/react-table 8.21.3` — для обычных таблиц (workspace list, admin routing patterns)
- **Icons:** `lucide-react 0.577.0` (не эмодзи, кроме флагов стран)
- **Toasts:** `sonner 2.0.7` — `toast.success()`, `toast.error()`
- **Supabase:** `@supabase/ssr 0.9.0` + `@supabase/supabase-js 2.99.1`
- **Testing:** `vitest 4.1.3` (не jest), tests в `__tests__/` рядом с компонентом

### Architecture (FSD, hybrid с shadcn)

Репо уже использует FSD. Твоя задача — **следовать**, не мигрировать:

```
frontend/src/
├── app/                    — Next.js App Router
│   └── (app)/              — route group с shared layout (уже есть, кладём новые pages сюда)
│       ├── quotes/page.tsx              — ПРИЛОЖЕН как reference (REFERENCE-quotes-page.tsx)
│       ├── admin/routing/page.tsx       — ПРИЛОЖЕН как reference (REFERENCE-admin-routing-page.tsx)
│       └── workspace/                   — НЕТ, создаём
├── features/               — per-user-story UI blocks
│   ├── quotes/ui/customs-step/customs-handsontable.tsx  — ПРИЛОЖЕН (EXISTING-customs-handsontable.tsx)
│   ├── quotes/ui/logistics-step/                         — существует, реорганизуем под новый Route Constructor
│   └── admin-routing/                                    — существует (для procurement), добавляем Logistics tab
├── entities/               — domain objects (customer, quote, invoice, supplier, user, table-view, ...)
│   └── user/               — ПРИЛОЖЕН целиком (get-session-user.ts + index.ts + types.ts)
├── shared/ui/              — cross-feature reusables (НЕ shadcn, а проектные wrappers)
│   └── pagination.tsx, scrollable-table.tsx, data-table/  — существуют
├── widgets/                — composite widgets (пока минимально используется)
├── components/ui/          — **stock shadcn primitives** (Button, Card, Tabs, Dialog, Sheet, ...)
│                             НЕ трогаем и НЕ дублируем в shared/
├── lib/                    — lib/utils.ts → cn() helper (ПРИЛОЖЕН, lib-utils.ts)
│                             Import: `import { cn } from "@/lib/utils"`
└── pages/                  — legacy, минимально
```

**FSD правила (жёстко):**
- Top-down imports: `app → widgets → features → entities → shared/components`
- No horizontal: feature A не импортит feature B напрямую — композиция через widgets/pages
- Public API: import only from slice root (e.g. `@/features/workspace-logistics`), не из `@/features/workspace-logistics/ui/inner.tsx`
- `components/ui/` (shadcn) — import as-is: `import { Button } from "@/components/ui/button"`

### Что читать в attachments (обязательно, до начала работы)

1. **`design-system.md`** — SOURCE OF TRUTH для цветов/шрифтов/spacing/компонентов. Все визуальные решения должны соответствовать. Если wireframe расходится с design-system → приоритет у design-system.
2. **`SPEC.md`** — architectural spec. Прочитай целиком, особенно:
   - §3 Design Decisions — почему такие решения
   - §7 UI Structure — FSD расположение
   - §11 Open UX Items — 3 нюанса, где ты можешь предложить свой вариант
3. **`wireframes/01-04.html`** — reference layouts. Открой каждый в браузере, они стили­зованы под проект (Plus Jakarta Sans + slate+copper palette + правильные radius/spacing).
4. **`globals.css`** — Tailwind v4 `@theme inline` с CSS vars. Все цвета — через эти vars, не hex.
5. **`frontend-package.json`** — версии и зависимости.
6. **`REFERENCE-quotes-page.tsx`** — pattern для новой `/workspace/logistics/page.tsx`. Скопируй структуру (server component, getSessionUser → redirect if no orgId → fetch parallel с Promise.all → pass props to client feature).
7. **`REFERENCE-admin-routing-page.tsx`** — в него extending'ишь новые tabs Logistics + Customs.
8. **`EXISTING-customs-handsontable.tsx`** — 420 строк, текущий customs handsontable. Твой scope — рефактор этого файла (не переписывание):
   - Удалить колонки `customs_ds_sgr`, `customs_marking`
   - Rename `customs_psn_pts` → `customs_psm_pts`
   - Composite column "Пошлина" (% / ₽/кг / ₽/шт chip + value)
   - **Сохранить** Handsontable internals: `hotRef`, `afterChange` handler, `cellsCallback`, pendingOps lock pattern
   - Новые компоненты **вокруг** таблицы (не внутри): AutofillBanner, TableViewsDropdown, BulkAcceptModal, QuoteCustomsExpenses, ItemCustomsExpenses, row-action `↗` Dialog
9. **`get-session-user.ts`** + **`user-index.ts`** + **`user-types.ts`** — готовый helper:
   ```typescript
   import { getSessionUser } from "@/entities/user";
   const user = await getSessionUser();
   // SessionUser | null with {id, email, orgId, orgName, roles: string[]}
   ```
10. **`lib-utils.ts`** — стандартный `cn(...inputs)` через `clsx + tailwind-merge`.

### Задача — 4 реализации

Конвертировать 4 wireframe'а (в папке `wireframes/`) в production tsx:

| # | Wireframe | Целевой путь в репо | Тип |
|---|-----------|---------------------|-----|
| 1 | `01-workspace.html` | `frontend/src/app/(app)/workspace/logistics/page.tsx` + `frontend/src/app/(app)/workspace/customs/page.tsx` + `frontend/src/features/workspace-logistics/` | New routes + new feature |
| 2 | `02-route-constructor.html` | `frontend/src/features/route-constructor/` (new client feature с `@dnd-kit`) + интеграция в существующий `frontend/src/features/quotes/ui/logistics-step/` | New feature + integration |
| 3 | `03-customs-table.html` | Рефактор `EXISTING-customs-handsontable.tsx` + новые компоненты: `AutofillBanner`, `TableViewsDropdown`, `BulkAcceptModal`, `QuoteCustomsExpenses`, `ItemCustomsExpenses` | Refactor + new siblings |
| 4 | `04-admin-routing.html` | Добавить Logistics tab в `REFERENCE-admin-routing-page.tsx` + `frontend/src/features/admin-routing-logistics/` | Extend + new feature |

### Обязательные переиспользуемые компоненты

Элементы встречаются на 2+ экранах — **оформи как shared/entity компоненты**:

| Component | Где встречается | Путь в репо |
|-----------|-----------------|-------------|
| `LocationChip` (с типом: supplier/hub/customs/warehouse/client) | Workspace, Route Constructor, Admin Routing | `frontend/src/entities/location/ui/location-chip.tsx` |
| `SlaTimerBadge` (green/yellow/red по deadline_at) | Workspace, Route Constructor | `frontend/src/shared/ui/sla-timer-badge.tsx` |
| `SegmentCard` / `SegmentNode` | Route Constructor | `frontend/src/features/route-constructor/ui/` |
| `AutofillSparkle` (✨ icon + tooltip "Из Q-…") | Customs table | `frontend/src/features/customs-autofill/ui/` |
| `EntityNotesPanel` (notes section with role-based visibility) | Route Constructor side-panel, Customer detail (later) | `frontend/src/entities/entity-note/ui/entity-notes-panel.tsx` |
| `InvoiceTabs` (per-invoice selector) | Logistics step, Customs step | `frontend/src/features/quotes/ui/invoice-tabs.tsx` |
| `TableViewsDropdown` (saved column views) | Customs table, потом другие | `frontend/src/features/table-views/ui/` |
| `RoleBasedTabs` (показывает больше tabs для head) | Workspace logistics, workspace customs, admin routing | `frontend/src/shared/ui/role-based-tabs.tsx` |
| `UserAvatarChip` (avatar + name + email in patterns table) | Admin routing | `frontend/src/entities/user/ui/user-avatar-chip.tsx` |

### Constraints (жёсткие)

**Design system compliance:**
- Все цвета через CSS vars (`var(--accent)`, `text-foreground`, `bg-card`, `text-muted-foreground`) или Tailwind tokens (`bg-primary`, `text-accent-foreground`).
- **Запрещено:** `text-[#hex]`, `bg-[rgba(...)]`, `style={{ color: ... }}` для цвета. Exception — tabular/inline для dynamic values.
- Font: Plus Jakarta Sans уже в `globals.css`, не импортируй повторно.
- Radius: **только** `rounded-sm` (6px) / `rounded-md` (8px) / `rounded-lg` (12px). `rounded-full` — только avatar/dots.
- Spacing: Tailwind scale (1/2/3/4/6/8/12/16). Arbitrary `gap-[13px]` — **нет**.
- Density: comfortable (48-56px row), не compact.

**Иконки:**
- Lucide React: `import { X } from "lucide-react"`. Не inline SVG из wireframes.
- Emoji — **только** флаги стран (🇨🇳 🇷🇺 🇹🇷 🇮🇳) как content.

**Анимации (anti-patterns из design-system.md):**
- `transition-colors`, `transition-[opacity,transform]` — OK
- `transition-all` — **запрещено**
- `hover:translate-y-*`, `hover:scale-*` на кнопках/карточках — **запрещено**. Только color/shadow change.

**TypeScript:**
- Props interface для каждого компонента.
- `any` запрещён. `unknown` + type guards для dynamic.
- API response типы — рядом с query/mutation функцией.

**Не трогать:**
- Handsontable internals в `customs-handsontable.tsx` (hotRef, afterChange, cellsCallback, pendingOps)
- Calc engine — бэкенд, не твой scope
- Workflow transitions — через API endpoints (список в SPEC §6)

### Expected deliverables

Отвечай **итеративно**, не дампи всё в один ответ:

**Round 1 — Plan (сейчас):**
1. Layout Map — иерархия компонентов для каждого из 4 экранов (дерево tsx-файлов, какой в какой кладётся)
2. Component Inventory — таблица: component name, path в репо, props interface (signature), какие shadcn primitives использует
3. "What I'd change from wireframes" — разделы для каждого экрана: что в wireframe было compromise, как ты это улучшишь (intent, accessibility, responsive)
4. Questions — если что-то в SPEC неясно или противоречит design-system, спроси **до** начала кодинга

**Round 2+ — Implementation (после approve plan'а):**
- Per feature → tsx files готовые к коммиту
- Short JSDoc header в каждом файле (что делает, data source)
- Named exports + `index.ts` на уровне feature/entity (public API)
- `"use client"` где нужен интерактив
- Pause после каждого feature для моего approve

**Round final — Summary doc:**
- `frontend/docs/components/logistics-customs-redesign.md` с деревом компонентов, data flow (API endpoints из SPEC §6), notes по §11 UX items (какой вариант взял из моих recommendations, обоснование)

### §11 Open UX items — напомню контекст

Три нюанса, где мои recommendations в SPEC, но ты можешь предложить лучше:

1. **Customs "Пошлина" column composition** — my recommendation: single column, composite UI (chip `% / ₽/кг / ₽/шт` + value). Storage: `customs_duty` (pct) OR `customs_duty_per_kg` (decimal) — UI выбирает по chip.
2. **`customs_item_expenses`** — my recommendation: отдельная таблица (не JSON в quote_items).
3. **Row "expand" modal** — my recommendation: per-row `↗` icon → `<Dialog>` со всеми полями (включая скрытые table view columns + item-level expenses).

Согласен с моими? Если иначе — скажи до кодинга соответствующего куска.

### Start here

1. Распакуй tar (если приложен архивом) или проверь что видишь все 12 файлов + папку `wireframes/` в attachments.
2. Прочитай `SPEC.md` целиком, все 4 HTML wireframes, `design-system.md`, `EXISTING-customs-handsontable.tsx`.
3. Отдай Round 1 deliverables (Layout Map + Component Inventory + "what I'd change" + questions).
4. Ждёшь approve, потом Round 2 per feature.

## PROMPT END

---

## Подготовка attachments (команды)

```bash
# Из корня onestack репо:

# Вариант 1 — tar архив одним файлом (если платформа Claude Design поддерживает)
# Уже подготовлен по /tmp/claude-design-context.tar.gz (запусти только если нужно переподготовить)
rm -rf /tmp/claude-design-context /tmp/claude-design-context.tar.gz
mkdir -p /tmp/claude-design-context
cp design-system.md /tmp/claude-design-context/
cp docs/superpowers/specs/2026-04-22-logistics-customs-redesign-design.md /tmp/claude-design-context/SPEC.md
cp -r docs/superpowers/wireframes/2026-04-22-logistics-customs/ /tmp/claude-design-context/wireframes
cp frontend/package.json /tmp/claude-design-context/frontend-package.json
cp frontend/src/app/globals.css /tmp/claude-design-context/globals.css
cp 'frontend/src/app/(app)/quotes/page.tsx' /tmp/claude-design-context/REFERENCE-quotes-page.tsx
cp 'frontend/src/app/(app)/admin/routing/page.tsx' /tmp/claude-design-context/REFERENCE-admin-routing-page.tsx
cp frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx /tmp/claude-design-context/EXISTING-customs-handsontable.tsx
cp frontend/src/entities/user/get-session-user.ts /tmp/claude-design-context/
cp frontend/src/entities/user/index.ts /tmp/claude-design-context/user-index.ts
cp frontend/src/entities/user/types.ts /tmp/claude-design-context/user-types.ts
cp frontend/src/lib/utils.ts /tmp/claude-design-context/lib-utils.ts
cd /tmp && tar -czf claude-design-context.tar.gz claude-design-context/
```

**Файл готов:** `/tmp/claude-design-context.tar.gz` (60 KB, 12 файлов + 4 wireframes)

## Fallback — если платформа не принимает tar

Загрузить файлы по одному (все из `/tmp/claude-design-context/`):
- `design-system.md`
- `SPEC.md`
- `wireframes/01-workspace.html`
- `wireframes/02-route-constructor.html`
- `wireframes/03-customs-table.html`
- `wireframes/04-admin-routing.html`
- `frontend-package.json`
- `globals.css`
- `REFERENCE-quotes-page.tsx`
- `REFERENCE-admin-routing-page.tsx`
- `EXISTING-customs-handsontable.tsx`
- `get-session-user.ts`
- `user-index.ts`
- `user-types.ts`
- `lib-utils.ts`
