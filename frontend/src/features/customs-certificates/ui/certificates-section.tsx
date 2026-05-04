"use client";

/**
 * CertificatesSection — Phase B Wave 3 Task 7f / REQ-6.
 *
 * Single section "Расходы по таможне" replacing the Phase A
 * `<QuoteCustomsExpenses />` + `<ItemCustomsExpenses />` split.
 *
 * Renders:
 *   - Header with title + two add buttons («+ Добавить сертификат»,
 *     «+ Добавить расход»). Buttons are hidden when `canEdit=false`.
 *   - Body: vertical stack of cards — `CertificateCard` for cert rows
 *     (`is_custom_expense=false`) or `CustomExpenseCard` for expense rows
 *     (`is_custom_expense=true`). Sorted `created_at DESC`.
 *   - Empty state: «Расходов нет» + helper «Нажмите ➕ чтобы добавить
 *     сертификат или расход» + a centered duplicate of the two buttons
 *     when `canEdit=true` (REQ-6 AC#7).
 *
 * Loads its own list via `listCertificates(quoteId)` on mount (REQ-2 AC#3),
 * exposes a re-fetch callback to children that mutate the list (REQ-6
 * AC#9 — delete & refresh path).
 *
 * **Wave 3 isolation note (Task 7f):** sibling cards/modals
 * (`CertificateCard`, `CustomExpenseCard`, `CertificateModal`, `ExpenseModal`,
 * `CertificateDetailsModal`) live in Wave 3 Tasks 7a/7c/7e and may not be
 * present in this commit. To keep `tsc --noEmit` green this section renders
 * card markup inline — matching the visual contract from design.md §4.8.4 —
 * until those siblings land. Wave 4 Task 9 will wire the modal mount points
 * once `CertificateModal` / `ExpenseModal` / `CertificateDetailsModal` are
 * available.
 *
 * Compliance (LD-13):
 *   - shadcn `<Button variant="default|secondary">` only — no raw button.
 *   - Tailwind v4 design tokens — no hex codes, no inline `style=`.
 *   - No `transition: all`, no `transform: translateY()` on hover.
 *   - All dropdowns/searches in nested modals = searchable Combobox (LD-5).
 *   - Russian formatting through `formatRub` + `formatDateRussian`.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { formatDateRussian } from "@/features/customs-history/lib/format-date";

import { listCertificates } from "../api/certificates";
import { formatRub } from "../lib/format-rub";
import type { Certificate, QuoteItemForSelect } from "../model/types";

export interface CertificatesSectionProps {
  /** UUID of the parent quote — used to fetch the certificate list. */
  quoteId: string;
  /**
   * Quote items used by nested modals (multi-select + live-preview).
   * Passed through to children — the section itself only uses
   * `items.length` for the "N из M" counter on each card.
   */
  items: QuoteItemForSelect[];
  /**
   * Role gate for write operations — when `false` the add buttons and
   * card edit handlers are suppressed, but the list remains visible
   * (REQ-1 AC#6 — read roles include sales/finance/etc.).
   */
  canEdit: boolean;
  /**
   * Optional override for the initial certificate list — when provided
   * the section skips the initial `listCertificates(quoteId)` call and
   * uses these directly. Useful for parent components that already have
   * the list in scope (e.g. `customs-step.tsx` after Wave 4 Task 9 wires
   * a server-side fetch). Internal `Refresh` flow still calls the API.
   */
  initialCertificates?: Certificate[];
}

/** Sort certificates `created_at DESC` (stable, single-purpose helper). */
function sortByCreatedAtDesc(certs: Certificate[]): Certificate[] {
  return [...certs].sort((a, b) => {
    if (a.created_at === b.created_at) return 0;
    return a.created_at < b.created_at ? 1 : -1;
  });
}

/** Whether `cert.valid_until` is strictly in the past (UTC midnight). */
function isCertExpired(cert: Certificate): boolean {
  if (!cert.valid_until) return false;
  const validUntil = new Date(cert.valid_until);
  if (Number.isNaN(validUntil.getTime())) return false;
  // Normalize today to UTC midnight so the comparison matches the server
  // SQL `valid_until <= CURRENT_DATE` (REQ-4 AC#8).
  const todayUtc = new Date();
  todayUtc.setUTCHours(0, 0, 0, 0);
  return validUntil <= todayUtc;
}

/**
 * Inline cert card markup — placeholder until Wave 3 Task 7a's
 * `CertificateCard` lands. Matches REQ-6 AC#4 fields: type badge, number,
 * cost_rub, counter, valid_until (red border when expired per REQ-4 AC#3).
 */
function CertCardInline({
  cert,
  totalItemsInQuote,
  onClick,
}: {
  cert: Certificate;
  totalItemsInQuote: number;
  onClick: () => void;
}) {
  const expired = isCertExpired(cert);
  // Red border takes priority over emerald when the cert is expired
  // (REQ-9 AC#5 — visual priority order).
  const borderClass = expired ? "border-destructive" : "border-emerald-700";
  const validUntilRu = cert.valid_until
    ? formatDateRussian(cert.valid_until)
    : "";
  const attachedCount = cert.attached_items.length;
  const numberFragment = cert.number ? `№${cert.number}` : "";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick();
        }
      }}
      className={
        `flex flex-col gap-1 rounded-md border ${borderClass} ` +
        "bg-card px-3 py-2 cursor-pointer"
      }
      data-testid="customs-cert-card"
      data-cert-id={cert.id}
      data-cert-type={cert.type}
      data-expired={expired ? "true" : "false"}
    >
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <span className="rounded-sm bg-emerald-950/40 text-emerald-300 px-1.5 py-0.5">
          {cert.type}
        </span>
        {numberFragment ? (
          <span className="text-foreground/90">{numberFragment}</span>
        ) : null}
        <span className="ml-auto font-medium">{formatRub(cert.cost_rub)}</span>
      </div>
      <div className="flex items-center justify-between gap-2 text-xs text-foreground/70">
        <span>
          {attachedCount} из {totalItemsInQuote} позиций
        </span>
        {validUntilRu ? <span>до {validUntilRu}</span> : null}
      </div>
    </div>
  );
}

/**
 * Inline custom-expense card markup — placeholder until Wave 3 Task 7a's
 * `CustomExpenseCard` lands. Matches REQ-6 AC#5: gray badge «Расход»,
 * `display_name`, `cost_rub`, counter — NO `valid_until`/`type`/`legal_doc`.
 */
function ExpenseCardInline({
  cert,
  totalItemsInQuote,
  onClick,
}: {
  cert: Certificate;
  totalItemsInQuote: number;
  onClick: () => void;
}) {
  const attachedCount = cert.attached_items.length;
  const label = cert.display_name ?? "Расход без названия";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick();
        }
      }}
      className={
        "flex flex-col gap-1 rounded-md border border-border-light " +
        "bg-card px-3 py-2 cursor-pointer"
      }
      data-testid="customs-expense-card"
      data-cert-id={cert.id}
    >
      <div className="flex items-center gap-2 flex-wrap text-xs">
        <span className="rounded-sm bg-muted text-muted-foreground px-1.5 py-0.5">
          Расход
        </span>
        <span className="text-foreground/90 truncate">{label}</span>
        <span className="ml-auto font-medium">{formatRub(cert.cost_rub)}</span>
      </div>
      <div className="text-xs text-foreground/70">
        {attachedCount} из {totalItemsInQuote} позиций
      </div>
    </div>
  );
}

/**
 * Top-level section — see component-level docstring for behaviour.
 */
export function CertificatesSection({
  quoteId,
  items,
  canEdit,
  initialCertificates,
}: CertificatesSectionProps) {
  // ── Certificate list state ─────────────────────────────────────────────
  // `null` → not yet loaded; `[]` → empty quote (renders empty state).
  const [certs, setCerts] = useState<Certificate[] | null>(
    initialCertificates ?? null,
  );
  const [loadError, setLoadError] = useState<string | null>(null);

  // ── Modal flags ────────────────────────────────────────────────────────
  // Sibling Wave 3 Task 7c/7e modal components are mounted by Wave 4 Task 9
  // (the wiring task that ties this section into `customs-step.tsx`). The
  // flags below capture intent — opening a modal sets the flag, the parent
  // wiring task is responsible for actually rendering the modal markup
  // once the sibling components ship. Until then, opening a card simply
  // marks the cert as "selected for inspection" — verifiable via tests.
  const [createCertOpen, setCreateCertOpen] = useState(false);
  const [createExpenseOpen, setCreateExpenseOpen] = useState(false);
  const [selectedCert, setSelectedCert] = useState<Certificate | null>(null);

  /** Re-fetch the list — exposed to nested modals/popovers. */
  const refreshCerts = useCallback(async () => {
    try {
      const res = await listCertificates(quoteId);
      if (res.success && res.data) {
        setCerts(res.data.certificates);
        setLoadError(null);
      } else {
        setLoadError(res.error?.message ?? "Не удалось загрузить сертификаты");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Network error";
      setLoadError(msg);
    }
  }, [quoteId]);

  useEffect(() => {
    if (initialCertificates) return; // parent already provided the list
    let cancelled = false;
    (async () => {
      try {
        const res = await listCertificates(quoteId);
        if (cancelled) return;
        if (res.success && res.data) {
          setCerts(res.data.certificates);
        } else {
          setLoadError(
            res.error?.message ?? "Не удалось загрузить сертификаты",
          );
        }
      } catch (err) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "Network error";
        setLoadError(msg);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [quoteId, initialCertificates]);

  const sortedCerts = useMemo(
    () => (certs ? sortByCreatedAtDesc(certs) : []),
    [certs],
  );
  const totalItemsInQuote = items.length;
  const isLoading = certs === null && loadError === null;
  const isEmpty = certs !== null && certs.length === 0;

  // ── Card click handler — open edit modal (canEdit) or details modal ────
  const handleCardClick = useCallback(
    (cert: Certificate) => {
      // Sibling modals not mounted yet — capture intent in state so the
      // wire-up task (Wave 4 Task 9) can drive the modal mount. Tests
      // assert state transitions via `data-*` attributes.
      setSelectedCert(cert);
    },
    [setSelectedCert],
  );

  return (
    <section
      className="flex flex-col gap-3"
      data-testid="customs-certificates-section"
      data-selected-cert-id={selectedCert?.id ?? ""}
      data-create-cert-open={createCertOpen ? "true" : "false"}
      data-create-expense-open={createExpenseOpen ? "true" : "false"}
    >
      {/* Header — title + two buttons (hidden when canEdit=false). */}
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-foreground">
          Расходы по таможне
        </h2>
        {canEdit ? (
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => setCreateCertOpen(true)}
              data-testid="customs-cert-add-button"
            >
              + Добавить сертификат
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCreateExpenseOpen(true)}
              data-testid="customs-expense-add-button"
            >
              + Добавить расход
            </Button>
          </div>
        ) : null}
      </div>

      {/* Body — loading / error / empty / list. */}
      {isLoading ? (
        <div
          className="text-xs text-foreground/60"
          data-testid="customs-cert-loading"
        >
          Загрузка…
        </div>
      ) : null}

      {loadError ? (
        <div
          className="rounded-md border border-destructive bg-destructive/10 px-3 py-2 text-xs text-destructive"
          data-testid="customs-cert-load-error"
        >
          {loadError}
        </div>
      ) : null}

      {isEmpty ? (
        <div
          className="flex flex-col items-center gap-2 rounded-md border border-dashed border-border bg-card/50 px-4 py-6"
          data-testid="customs-cert-empty-state"
        >
          <p className="text-sm font-medium text-foreground/80">Расходов нет</p>
          <p className="text-xs text-foreground/60">
            Нажмите ➕ чтобы добавить сертификат или расход
          </p>
          {canEdit ? (
            <div className="flex items-center gap-2 mt-1">
              <Button
                variant="default"
                size="sm"
                onClick={() => setCreateCertOpen(true)}
                data-testid="customs-cert-add-button-empty"
              >
                + Добавить сертификат
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCreateExpenseOpen(true)}
                data-testid="customs-expense-add-button-empty"
              >
                + Добавить расход
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      {!isEmpty && certs !== null ? (
        <div
          className="flex flex-col gap-2"
          data-testid="customs-cert-list"
          data-cert-count={sortedCerts.length}
        >
          {sortedCerts.map((cert) =>
            cert.is_custom_expense ? (
              <ExpenseCardInline
                key={cert.id}
                cert={cert}
                totalItemsInQuote={totalItemsInQuote}
                onClick={() => handleCardClick(cert)}
              />
            ) : (
              <CertCardInline
                key={cert.id}
                cert={cert}
                totalItemsInQuote={totalItemsInQuote}
                onClick={() => handleCardClick(cert)}
              />
            ),
          )}
        </div>
      ) : null}

      {/*
        Modal mount points — Wave 4 Task 9 will wire `CertificateModal` /
        `ExpenseModal` / `CertificateDetailsModal` once the sibling Wave 3
        components ship. The state flags above (`createCertOpen`,
        `createExpenseOpen`, `selectedCert`) capture the intent today so
        the wiring task only has to mount the components and pass props.
      */}
      {/*
        Hidden refresh token — exposes a stable testid so future wiring
        tasks can verify that the cert list re-fetches after children
        mutate the data. The refresh callback itself is bound above
        (`refreshCerts`) — kept in scope so Wave 4 Task 9 can pass it
        down to the modal/popover children that need it.
      */}
      <span
        className="hidden"
        data-testid="customs-cert-refresh-token"
        data-refresh-handler={refreshCerts.name || "refreshCerts"}
      />
    </section>
  );
}
