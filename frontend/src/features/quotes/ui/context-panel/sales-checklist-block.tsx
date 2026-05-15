"use client";

import { Badge } from "@/components/ui/badge";
import { ClipboardList } from "lucide-react";

/**
 * Shape of the JSONB `kvota.quotes.sales_checklist` payload written by the
 * МОП «Передать в закупки» dialog (`transfer-dialog.tsx::handleSubmit` via
 * `submitToProcurementWithChecklist`).
 *
 * Testing 2 row 29 (FB-260514-220805-be23): МОП fills these fields when
 * transferring a quote to procurement; the procurement-side roles (МОЗ /
 * РОЗ / СтМОЗ) were seeing «Данных нет» because the rendering was orphaned
 * during the April 2026 context-panel merge (see commit 35ea2e44). The
 * fetch in `queries.ts::fetchQuoteContextData` was kept; this component is
 * the missing render surface, now wired back into `ContextPanel` so the
 * checklist is visible from procurement-onward without re-opening the
 * sales-step dialog.
 */
export interface SalesChecklist {
  is_estimate: boolean;
  is_tender: boolean;
  direct_request: boolean;
  trading_org_request: boolean;
  equipment_description: string;
  completed_at: string | null;
  completed_by: string | null;
}

interface SalesChecklistBlockProps {
  checklist: SalesChecklist | null;
}

const REQUEST_TYPE_BADGES: {
  key: keyof Pick<
    SalesChecklist,
    "is_estimate" | "is_tender" | "direct_request" | "trading_org_request"
  >;
  label: string;
}[] = [
  { key: "is_estimate", label: "Проценка" },
  { key: "is_tender", label: "Тендер" },
  { key: "direct_request", label: "Прямой запрос" },
  { key: "trading_org_request", label: "Через торгующих" },
];

/**
 * Returns true if the checklist carries any user-entered content. Used to
 * hide the entire block when the quote came through a path that never
 * populated `sales_checklist` (e.g., legacy quotes pre-dating the dialog).
 *
 * Tester edge case (Testing 2 row 29): "if all fields null → hide block".
 */
export function hasSalesChecklistContent(
  checklist: SalesChecklist | null,
): checklist is SalesChecklist {
  if (!checklist) return false;
  if (
    checklist.is_estimate ||
    checklist.is_tender ||
    checklist.direct_request ||
    checklist.trading_org_request
  ) {
    return true;
  }
  return checklist.equipment_description?.trim().length > 0;
}

export function SalesChecklistBlock({ checklist }: SalesChecklistBlockProps) {
  if (!hasSalesChecklistContent(checklist)) return null;

  const activeBadges = REQUEST_TYPE_BADGES.filter((b) => checklist[b.key]);
  const description = checklist.equipment_description?.trim();

  return (
    <div
      className="space-y-2 min-w-0"
      data-testid="context-panel-sales-checklist"
    >
      <div className="flex items-center gap-2 mb-2">
        <ClipboardList size={14} className="text-muted-foreground" />
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          От МОП
        </h4>
      </div>

      {activeBadges.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {activeBadges.map((b) => (
            <Badge
              key={b.key}
              variant="secondary"
              className="bg-amber-100 text-amber-700"
            >
              {b.label}
            </Badge>
          ))}
        </div>
      )}

      {description && (
        <div className="space-y-1">
          <span className="text-xs text-muted-foreground">
            Описание оборудования
          </span>
          <div className="rounded-md bg-muted/30 px-3 py-2 text-sm text-foreground whitespace-pre-wrap break-words">
            {description}
          </div>
        </div>
      )}
    </div>
  );
}
