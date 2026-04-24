"use client";

/**
 * Sidebar "Пути" panel — lists every non-archived curated flow, grouped by
 * persona role (Req 18.3). Clicking a flow navigates to `/journey/flows/:slug`,
 * which ships in Task 29; until then the destination resolves to a 404.
 *
 * The component is intentionally thin — the non-trivial logic lives in two
 * pure helpers (`groupFlowsByRole`, `sortFlowsByDisplayOrder`) that are
 * covered by the sibling unit test without touching the DOM.
 *
 * FSD boundary: `features/journey/ui/flows/` may import from
 * `entities/journey/` + `shared/` only.
 */

import Link from "next/link";
import type { JourneyFlow, RoleSlug } from "@/entities/journey";

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit tests.
// ---------------------------------------------------------------------------

/**
 * Groups flows by their `role` slug. Roles with zero flows are absent from
 * the returned object (caller doesn't need to render empty sections).
 *
 * Returns a `Partial<Record<RoleSlug, readonly JourneyFlow[]>>` — `Partial`
 * because only roles with at least one flow are present as keys.
 */
export function groupFlowsByRole(
  flows: readonly JourneyFlow[]
): Partial<Record<RoleSlug, readonly JourneyFlow[]>> {
  const out: Partial<Record<RoleSlug, JourneyFlow[]>> = {};
  for (const flow of flows) {
    const bucket = out[flow.role] ?? [];
    bucket.push(flow);
    out[flow.role] = bucket;
  }
  return out;
}

/**
 * Returns a new array sorted by `display_order` ascending. Input is not
 * mutated (Array.prototype.sort mutates — we copy first). Sort is stable
 * per the ES2019 spec, so ties preserve input order.
 */
export function sortFlowsByDisplayOrder(
  flows: readonly JourneyFlow[]
): readonly JourneyFlow[] {
  return [...flows].sort((a, b) => a.display_order - b.display_order);
}

// ---------------------------------------------------------------------------
// Role-slug → display label. Matches `.kiro/steering/access-control.md`.
// ---------------------------------------------------------------------------

const ROLE_LABELS: Record<RoleSlug, string> = {
  admin: "Администратор",
  top_manager: "Топ-менеджер",
  head_of_sales: "Руководитель продаж",
  head_of_procurement: "Руководитель закупок",
  head_of_logistics: "Руководитель логистики",
  sales: "Продажи",
  quote_controller: "Контроль КП",
  spec_controller: "Контроль спецификаций",
  finance: "Финансы",
  procurement: "Закупки",
  procurement_senior: "Старший закупщик",
  logistics: "Логистика",
  customs: "Таможня",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  readonly flows: readonly JourneyFlow[];
}

/**
 * Renders the "Пути" panel. Groups flows by role, sorts each group by
 * display_order, and emits a `<Link>`-wrapped card per flow.
 */
export function FlowList({ flows }: Props) {
  if (flows.length === 0) {
    return (
      <p
        data-testid="journey-flow-list-empty"
        className="text-xs text-text-subtle"
      >
        Пока нет ни одного пути.
      </p>
    );
  }

  const grouped = groupFlowsByRole(flows);
  const roles = Object.keys(grouped) as RoleSlug[];

  return (
    <div data-testid="journey-flow-list" className="flex flex-col gap-3">
      {roles.map((role) => {
        const bucket = sortFlowsByDisplayOrder(grouped[role] ?? []);
        return (
          <div key={role} className="flex flex-col gap-1.5">
            <div className="text-[11px] font-medium uppercase tracking-wide text-text-subtle">
              {ROLE_LABELS[role] ?? role}
            </div>
            <ul className="flex flex-col gap-1.5">
              {bucket.map((flow) => (
                <li key={flow.id}>
                  <Link
                    href={`/journey/flows/${flow.slug}`}
                    data-testid={`journey-flow-card-${flow.slug}`}
                    className="flex flex-col gap-0.5 rounded-md border border-border-light bg-background px-3 py-2 text-left transition-colors hover:border-border-strong"
                  >
                    <span className="text-sm font-semibold text-text-default">
                      {flow.title}
                    </span>
                    <span className="text-xs text-text-subtle">
                      {flow.persona}
                    </span>
                    <span className="mt-1 inline-flex w-fit rounded-sm bg-surface-muted px-1.5 py-0.5 text-[10px] font-medium text-text-subtle">
                      ~{flow.est_minutes} мин
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
