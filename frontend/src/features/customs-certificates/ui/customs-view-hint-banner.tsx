"use client";

/**
 * CustomsViewHintBanner — Phase B Wave 4 Task 8 / REQ-11 AC#9-#11.
 *
 * Renders a small hint card above the customs Handsontable when the user
 * has activated a non-default system view (e.g. «Тарифы и НДС»,
 * «Документы и сертификаты», «Только идентификация»). The banner explains
 * which columns are currently hidden so the user does not get confused
 * by a "missing" column they expected to see.
 *
 * Rendering rules (REQ-11 AC#9):
 *   - `currentView === null`        → returns `null` (no markup).
 *   - `currentView.id === 'system:all'` → returns `null` (default view,
 *     nothing hidden).
 *   - Otherwise renders the banner with:
 *       «💡 Сейчас активен вид «{label}» — скрыты колонки: {hidden_list}.»
 *     where `hidden_list` is a comma-separated list of the Russian labels
 *     of every column NOT in `currentView.visibleColumnIds`, in the order
 *     they appear in `allColumns`.
 *
 * The banner also includes a disabled CTA link «Создать свой вид: Колонки →
 * Сохранить как...» (REQ-11 AC#10) — wrapped in a tooltip carrying the copy
 * «Доступно в следующей фазе» — because user-editable views land in Phase C
 * (REQ-11 AC#11). The link is rendered as a span with `aria-disabled` so it
 * stays focus-visible without firing a navigation.
 *
 * Compliance (LD-13):
 *   - shadcn `<Tooltip>` from `@/components/ui/tooltip` — no raw popover.
 *   - Tailwind utility classes mapped to design tokens (info-blue palette
 *     re-using the same `border-blue-900` / `bg-blue-950/20` combo as
 *     `HistoryBanner` apply variant for visual continuity).
 *   - Inline emoji 💡 (no SVG icon import) per design.md §4.12.
 *   - No `style=` for colors/fonts/spacing.
 *   - No `transition: all`, no `transform: translateY()` on hover.
 */

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import { getHiddenColumnLabels } from "@/features/quotes/ui/customs-step/customs-views";

import type { SystemView } from "../model/types";

export interface CustomsViewHintBannerProps {
  /**
   * The currently-active system view, or `null` when no view is resolved
   * (e.g. URL param missing or pointing at a UUID row). The banner is
   * rendered ONLY for non-default system views (REQ-11 AC#9 — `system:all`
   * also collapses to `null` markup).
   */
  currentView: SystemView | null;
  /**
   * Full column registry — pass `CUSTOMS_AVAILABLE_COLUMNS` from the
   * customs-step. Injected so the banner stays decoupled from the
   * customs-columns module path during testing.
   */
  allColumns: ReadonlyArray<{ key: string; label: string }>;
}

export function CustomsViewHintBanner({
  currentView,
  allColumns,
}: CustomsViewHintBannerProps) {
  // No view resolved or default «Все колонки» — nothing to hint about.
  if (!currentView || currentView.id === "system:all") return null;

  const hiddenLabels = getHiddenColumnLabels(currentView, allColumns);
  const hiddenList = hiddenLabels.join(", ");

  return (
    <div
      className="flex items-center justify-between gap-2 rounded-md border border-blue-900 bg-blue-950/20 px-3 py-2 mb-3"
      data-testid="customs-view-hint-banner"
      data-view-id={currentView.id}
    >
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <span className="shrink-0" aria-hidden="true">
          💡
        </span>
        <div className="text-xs text-foreground/90">
          {`Сейчас активен вид «${currentView.label}» — скрыты колонки: ${hiddenList}.`}
        </div>
      </div>
      <div className="shrink-0">
        <TooltipProvider delay={150}>
          <Tooltip>
            <TooltipTrigger
              render={<span className="inline-block" />}
            >
              <span
                className="text-xs text-muted-foreground underline decoration-dotted cursor-not-allowed opacity-60"
                aria-disabled="true"
                data-testid="customs-view-hint-cta"
              >
                Создать свой вид: Колонки → Сохранить как...
              </span>
            </TooltipTrigger>
            <TooltipContent>Доступно в следующей фазе</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  );
}
