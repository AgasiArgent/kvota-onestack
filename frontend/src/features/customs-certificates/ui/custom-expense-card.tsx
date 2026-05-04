"use client";

/**
 * CustomExpenseCard — Phase B Wave 3 Task 7a (REQ-6 AC#5 + REQ-10).
 *
 * Section-level tile for `kvota.quote_certificates` rows where
 * `is_custom_expense=true`. Sibling of `CertificateCard` — chosen by the
 * parent section based on the `is_custom_expense` flag (REQ-10 AC#5).
 *
 * Visual rules:
 *   - Gray-tinted border + bg (neutral token) — visually distinct from the
 *     emerald cert card so users can tell certs apart from arbitrary fees
 *     (e.g. «Услуги декларанта»).
 *   - NO `valid_until` row, NO `type` badge with a cert number, NO
 *     `legal_doc` reference — these fields stay `NULL` for custom-expense
 *     rows (REQ-10 AC#3) and rendering them would expose an empty UI.
 *   - Custom-expense rows do NOT have an "expired" state — `valid_until`
 *     is always `NULL` for them, so we never render the destructive border.
 *
 * Behaviour:
 *   - Same role-gated `onEdit`/`onDelete` contract as `CertificateCard`.
 *   - The «Расход» badge uses `secondary` variant — neutral gray — so the
 *     distinction from the emerald cert badge is unambiguous.
 *
 * Compliance (LD-13): shadcn `<Button>`, `<Badge>` only; no inline `style=`;
 * no `transition: all`; no `transform: translateY()`.
 */

import { Pencil, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { formatRub } from "../lib/format-rub";
import type { Certificate } from "../model/types";

export interface CustomExpenseCardProps {
  /**
   * Certificate row to render. Must satisfy `is_custom_expense=true` —
   * the parent section routes by the flag (REQ-10 AC#5). The shape stays
   * `Certificate` (single table) so `display_name`/`cost_rub` come straight
   * from the same row the cert card consumes.
   */
  expense: Certificate;
  /**
   * Total number of `quote_items` for the parent quote — drives the
   * «{N} из {M}» coverage counter (REQ-6 AC#5).
   */
  totalQuoteItems: number;
  /** Edit-callback — only invoked when `canEdit=true`. */
  onEdit?: () => void;
  /** Delete-callback — only invoked when `canEdit=true`. */
  onDelete?: () => void;
  /**
   * Role gate (REQ-9 AC#6). When `false`, footer action buttons are not
   * rendered.
   */
  canEdit: boolean;
}

export function CustomExpenseCard({
  expense,
  totalQuoteItems,
  onEdit,
  onDelete,
  canEdit,
}: CustomExpenseCardProps) {
  const attachedCount = expense.attached_items.length;
  // Defensive default — NOT NULL on DB for custom expenses, but if upstream
  // serialization ever omits it we render the empty string rather than the
  // literal "null" — keeps the UI from leaking implementation details.
  const displayName = expense.display_name ?? "";

  return (
    <div
      className="rounded-md border border-slate-700 bg-slate-950/10 p-3"
      data-testid="custom-expense-card"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="secondary"
              data-testid="custom-expense-card-badge"
            >
              Расход
            </Badge>
            <span
              className="text-sm font-medium text-foreground/90"
              data-testid="custom-expense-card-display-name"
            >
              {displayName}
            </span>
          </div>

          <div className="mt-2 text-xs text-muted-foreground">
            <span data-testid="custom-expense-card-counter">
              {`${attachedCount} из ${totalQuoteItems} позиций`}
            </span>
            <span className="mx-2">·</span>
            <span data-testid="custom-expense-card-total">
              {`распределено ${formatRub(expense.cost_rub)}`}
            </span>
          </div>
        </div>

        <div className="text-right shrink-0">
          <div
            className="text-sm font-semibold"
            data-testid="custom-expense-card-cost"
          >
            {formatRub(expense.cost_rub)}
          </div>

          {canEdit && (
            <div className="flex gap-1 mt-2 justify-end">
              <Button
                size="xs"
                variant="ghost"
                onClick={onEdit}
                data-testid="custom-expense-card-edit"
                aria-label="Редактировать расход"
              >
                <Pencil />
                Редактировать
              </Button>
              <Button
                size="icon-xs"
                variant="ghost"
                onClick={onDelete}
                data-testid="custom-expense-card-delete"
                aria-label="Удалить расход"
              >
                <Trash2 />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
