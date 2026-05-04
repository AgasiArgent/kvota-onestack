"use client";

/**
 * CertificateDetailsModal — Phase B Task 7e / REQ-9 AC#7.
 *
 * Read-only modal that surfaces the full row of a `kvota.quote_certificates`
 * record together with the per-item attachment table. Mounted from
 * `CertificateCoverageList` (cert card → «Открыть сертификат» / «Подробнее»)
 * inside the per-item dialog.
 *
 * Two surface modes — the title and field set switch on
 * `cert.is_custom_expense`:
 *
 *   • cert (`is_custom_expense=false`) — title is `cert.type` (e.g. «ДС ТР
 *     ТС»). Field grid: type, number, issuer, legal_doc, issued_at,
 *     valid_until, cost_rub, notes, created_at, created_by.
 *
 *   • custom expense (`is_custom_expense=true`) — title is «Расход».
 *     Field grid drops `type`/`number`/`issuer`/`legal_doc`/`issued_at`/
 *     `valid_until` and adds `display_name` (those columns are NULL on
 *     custom-expense rows by REQ-10 AC#3).
 *
 * Below the field grid: «Прикреплено к {N} позициям» table — one row per
 * `cert.attached_items[]` entry with `№{position} {name} → {share_rub}
 * ({share_percent}%)`. The position label is resolved against the
 * caller-supplied `items` prop (so we can render «№3 Cabel A12» instead of
 * an opaque UUID).
 *
 * NO edit form (REQ-9 AC#7). Footer is a single «Закрыть» (`<Button
 * variant="ghost">`).
 *
 * Date strings render via `formatDateRussian` (LD-11). RUB values render
 * via `formatRub`.
 *
 * **Testability note** — the body content lives in `CertificateDetailsBody`,
 * which is exported separately so SSR-only test harnesses (no jsdom in
 * this repo, see `city-combobox.test.tsx`) can assert markup without
 * having to render through `@base-ui/react`'s portal-backed Dialog. The
 * top-level `CertificateDetailsModal` simply wraps the body in the shadcn
 * Dialog shell.
 */

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

import { formatDateRussian } from "@/features/customs-history/lib/format-date";

import { formatRub } from "../lib/format-rub";
import type { Certificate, QuoteItemForSelect } from "../model/types";

export interface CertificateDetailsModalProps {
  /** Controlled open flag. */
  open: boolean;
  /** Called whenever the modal toggles open state (X icon, ESC, footer). */
  onOpenChange: (open: boolean) => void;
  /** Full certificate row, including its `attached_items[]` payload. */
  cert: Certificate;
  /**
   * Quote items lookup table — used to resolve `attached_items[].item_id`
   * to a human label («№3 Cabel A12»). Optional: when omitted the modal
   * falls back to truncated UUIDs.
   */
  items?: QuoteItemForSelect[];
  /**
   * Optional resolver for `created_by` UUID → display string (e.g. email).
   * When omitted we render the raw UUID (or «—» on null).
   */
  resolveCreatedBy?: (userId: string | null) => string | null;
}

export interface CertificateDetailsBodyProps {
  cert: Certificate;
  items?: QuoteItemForSelect[];
  resolveCreatedBy?: (userId: string | null) => string | null;
  /** Called when the user clicks «Закрыть». Wired by the modal wrapper. */
  onClose: () => void;
}

/** Render a labelled field row, omitting empty/null values gracefully. */
function FieldRow({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  const display =
    value === null || value === undefined || value === ""
      ? "—"
      : String(value);
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs uppercase text-neutral-500">{label}</span>
      <span className="text-sm">{display}</span>
    </div>
  );
}

/**
 * Format an ISO date string `YYYY-MM-DD` directly without going through
 * `new Date()` (which would shift by the host timezone offset). Returns
 * `null` for inputs that don't match the date-only shape — callers should
 * fall back to `formatDateRussian` for full timestamps.
 */
function formatIsoDateOnly(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const [, year, month, day] = match;
  return `${day}.${month}.${year}`;
}

/** Format any cert date string — try date-only first, then full timestamp. */
function formatCertDate(iso: string | null | undefined): string | null {
  return formatIsoDateOnly(iso) ?? (iso ? formatDateRussian(iso) : null);
}

/**
 * Read-only body — exported so SSR-only tests can assert on markup
 * without paying the cost of base-ui's Portal-backed Dialog shell. The
 * body is identical between the modal and standalone rendering.
 */
export function CertificateDetailsBody({
  cert,
  items,
  resolveCreatedBy,
  onClose,
}: CertificateDetailsBodyProps) {
  const isExpense = cert.is_custom_expense;

  // Build a fast lookup so the attachment table can show «№N {name}».
  const itemsById = new Map<string, QuoteItemForSelect>();
  if (items) {
    for (const it of items) {
      itemsById.set(it.id, it);
    }
  }

  const createdByDisplay =
    resolveCreatedBy?.(cert.created_by) ?? cert.created_by ?? null;

  return (
    <div
      className="flex flex-col gap-4"
      data-testid="certificate-details-modal"
    >
      <div data-testid="cert-details-title" className="text-base font-medium">
        {isExpense ? "Расход" : cert.type}
      </div>

      {/* ---------- Field grid (read-only) ---------- */}
      <div
        className="grid grid-cols-2 gap-3"
        data-testid="cert-details-fields"
      >
        {isExpense ? (
          <>
            <FieldRow label="Название" value={cert.display_name} />
            <FieldRow
              label="Сумма, ₽"
              value={formatRub(cert.cost_rub)}
            />
          </>
        ) : (
          <>
            <FieldRow label="Тип" value={cert.type} />
            <FieldRow label="Номер" value={cert.number} />
            <FieldRow label="Орган выдачи" value={cert.issuer} />
            <FieldRow label="Регламент" value={cert.legal_doc} />
            <FieldRow
              label="Дата выдачи"
              value={formatCertDate(cert.issued_at)}
            />
            <FieldRow
              label="Действует до"
              value={formatCertDate(cert.valid_until)}
            />
            <FieldRow
              label="Стоимость, ₽"
              value={formatRub(cert.cost_rub)}
            />
          </>
        )}
      </div>

      {cert.notes ? (
        <div
          className="flex flex-col gap-0.5"
          data-testid="cert-details-notes"
        >
          <span className="text-xs uppercase text-neutral-500">
            Примечание
          </span>
          <span className="text-sm whitespace-pre-wrap">{cert.notes}</span>
        </div>
      ) : null}

      {/* ---------- Audit row ---------- */}
      <div
        className="grid grid-cols-2 gap-3 border-t pt-3"
        data-testid="cert-details-audit"
      >
        <FieldRow
          label="Создано"
          value={formatDateRussian(cert.created_at) || cert.created_at}
        />
        <FieldRow label="Автор" value={createdByDisplay} />
      </div>

      {/* ---------- Attachment table ---------- */}
      <div className="flex flex-col gap-2" data-testid="cert-details-table">
        <div className="text-xs uppercase text-neutral-500">
          {`Прикреплено к ${cert.attached_items.length} позициям`}
        </div>
        {cert.attached_items.length === 0 ? (
          <div className="text-sm text-neutral-500">
            Нет привязанных позиций.
          </div>
        ) : (
          <ul className="flex flex-col gap-1">
            {cert.attached_items.map((att) => {
              const it = itemsById.get(att.item_id);
              const label = it ? `№${it.position} ${it.name}` : att.item_id;
              return (
                <li
                  key={att.item_id}
                  className="text-sm flex items-center justify-between gap-2"
                  data-testid="cert-details-row"
                >
                  <span className="truncate">{label}</span>
                  <span className="text-amber-400 shrink-0">
                    {`${formatRub(att.share_rub)} (${att.share_percent}%)`}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* ---------- Footer ---------- */}
      <div className="flex justify-end pt-2">
        <Button
          variant="ghost"
          onClick={onClose}
          data-testid="cert-details-close"
        >
          Закрыть
        </Button>
      </div>
    </div>
  );
}

export function CertificateDetailsModal({
  open,
  onOpenChange,
  cert,
  items,
  resolveCreatedBy,
}: CertificateDetailsModalProps) {
  const isExpense = cert.is_custom_expense;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isExpense ? "Расход" : cert.type}</DialogTitle>
        </DialogHeader>

        <CertificateDetailsBody
          cert={cert}
          items={items}
          resolveCreatedBy={resolveCreatedBy}
          onClose={() => onOpenChange(false)}
        />

        <DialogFooter>
          {/*
            Footer button is intentionally rendered inside the body too —
            keeping it in the body lets SSR tests assert presence; the
            DialogFooter copy below offers the sticky-bottom layout users
            expect on tall content.
          */}
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            data-testid="cert-details-close-footer"
          >
            Закрыть
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
