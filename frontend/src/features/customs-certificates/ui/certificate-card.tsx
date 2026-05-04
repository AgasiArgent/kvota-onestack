"use client";

/**
 * CertificateCard — Phase B Wave 3 Task 7a (REQ-6 AC#4 + REQ-4 AC#3).
 *
 * Section-level tile rendered inside «Расходы по таможне» (REQ-6) for every
 * row of `kvota.quote_certificates` where `is_custom_expense=false`. Mirrors
 * the design layout from `docs/mockups/customs-after-phases.html` lines
 * 340-400 and the cert-only branch of design.md §4.8.4.
 *
 * Visual rules:
 *   - Default: emerald-tinted border + bg (success token).
 *   - Expired (`cert.valid_until <= today`): RED border replaces emerald
 *     (REQ-4 AC#3 — design-system token, never hex). Visual priority:
 *     destructive > emerald.
 *
 * Behaviour:
 *   - When `canEdit=true`, `onEdit` and `onDelete` callbacks are wired to
 *     footer buttons; when `false`, both buttons are hidden so the read-only
 *     consumer surface stays clean (REQ-9 AC#6 — role-gated controls).
 *   - Counter «N из M» derives from `cert.attached_items.length` and the
 *     parent-supplied `totalQuoteItems` (cert ≠ owns the universe of
 *     positions, so we receive M from the quote-step parent).
 *
 * Compliance (LD-13): shadcn `<Button>`, `<Badge>` only; no inline `style=`;
 * no `transition: all`; no `transform: translateY()`. Date strings pass
 * through `formatDateRussian` (REQ-4 AC#7 — REUSE only).
 */

import { Pencil, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { formatDateRussian } from "@/features/customs-history/lib/format-date";

import { formatRub } from "../lib/format-rub";
import type { Certificate } from "../model/types";

export interface CertificateCardProps {
  /**
   * Certificate row to render. Must satisfy `is_custom_expense=false`
   * (CustomExpenseCard handles the inverse branch); we don't enforce it
   * structurally — the section component branches on the flag and routes
   * the row to the correct card.
   */
  cert: Certificate;
  /**
   * Total number of `quote_items` for the parent quote — drives the
   * «{N} из {M}» coverage counter. Provided by the parent so the card stays
   * decoupled from the quote-step data fetcher.
   */
  totalQuoteItems: number;
  /** Edit-callback — only invoked when `canEdit=true`. */
  onEdit?: () => void;
  /** Delete-callback — only invoked when `canEdit=true`. */
  onDelete?: () => void;
  /**
   * Role gate (REQ-9 AC#6). When `false`, footer action buttons are not
   * rendered — read-only consumers (sales, finance, etc.) see the data but
   * cannot mutate it. Mutating endpoints are also gated server-side.
   */
  canEdit: boolean;
}

/**
 * Decide whether `valid_until` has lapsed. NULL is treated as «бессрочный»
 * per REQ-4 AC#1 — never expired. Comparison uses `YYYY-MM-DD` string
 * compare which is safe because both sides are ISO-formatted date strings
 * (no time component) — avoids timezone drift between the user's locale
 * and the server's `CURRENT_DATE`.
 */
function isExpired(validUntil: string | null): boolean {
  if (!validUntil) return false;
  const today = new Date().toISOString().slice(0, 10);
  return validUntil <= today;
}

export function CertificateCard({
  cert,
  totalQuoteItems,
  onEdit,
  onDelete,
  canEdit,
}: CertificateCardProps) {
  const expired = isExpired(cert.valid_until);
  const attachedCount = cert.attached_items.length;

  // Border + bg priority: destructive (red) > emerald, per REQ-4 AC#3.
  const containerClass = expired
    ? "rounded-md border border-destructive bg-destructive/5 p-3"
    : "rounded-md border border-emerald-900 bg-emerald-950/10 p-3";

  return (
    <div className={containerClass} data-testid="certificate-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="default" data-testid="certificate-card-type">
              {cert.type}
            </Badge>
            {cert.number && (
              <span className="text-sm font-mono text-foreground/90">
                {`№${cert.number}`}
              </span>
            )}
          </div>

          <div className="mt-2 text-xs text-muted-foreground">
            <span data-testid="certificate-card-counter">
              {`${attachedCount} из ${totalQuoteItems} позиций`}
            </span>
            <span className="mx-2">·</span>
            <span data-testid="certificate-card-total">
              {`распределено ${formatRub(cert.cost_rub)}`}
            </span>
          </div>

          {cert.valid_until && (
            <div
              className="mt-1 text-xs text-muted-foreground"
              data-testid="certificate-card-valid-until"
            >
              {`Срок действия: ${formatDateRussian(cert.valid_until)}`}
              {expired && (
                <span className="ml-1 text-destructive">(истёк)</span>
              )}
            </div>
          )}
        </div>

        <div className="text-right shrink-0">
          <div
            className="text-sm font-semibold"
            data-testid="certificate-card-cost"
          >
            {formatRub(cert.cost_rub)}
          </div>

          {canEdit && (
            <div className="flex gap-1 mt-2 justify-end">
              <Button
                size="xs"
                variant="ghost"
                onClick={onEdit}
                data-testid="certificate-card-edit"
                aria-label="Редактировать сертификат"
              >
                <Pencil />
                Редактировать
              </Button>
              <Button
                size="icon-xs"
                variant="ghost"
                onClick={onDelete}
                data-testid="certificate-card-delete"
                aria-label="Удалить сертификат"
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
