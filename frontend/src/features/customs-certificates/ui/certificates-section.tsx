"use client";

/**
 * CertificatesSection — Phase B Wave 3 Task 7f / REQ-6 + Wave 4 Task 9.
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
 * **Wave 4 Task 9 wiring:** mounts the sibling cards
 * (`CertificateCard`, `CustomExpenseCard`) plus three modals
 * (`CertificateModal`, `ExpenseModal`, `CertificateDetailsModal`):
 *   - «+ Добавить сертификат» → `CertificateModal` (create flow).
 *   - «+ Добавить расход» → `ExpenseModal` (custom-expense create flow).
 *   - Card click / edit button → `CertificateDetailsModal` (read-only
 *     details for now; an explicit edit form is out of Phase B scope —
 *     REQ-9 AC#7).
 *   - Card delete button → confirm + `deleteCertificate` API + refresh.
 *
 * Compliance (LD-13):
 *   - shadcn `<Button variant="default|secondary">` only — no raw button.
 *   - Tailwind v4 design tokens — no hex codes, no inline `style=`.
 *   - No `transition: all`, no `transform: translateY()` on hover.
 *   - All dropdowns/searches in nested modals = searchable Combobox (LD-5).
 *   - Russian formatting through `formatRub` + `formatDateRussian`.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

import { deleteCertificate, listCertificates } from "../api/certificates";
import type { Certificate, QuoteItemForSelect } from "../model/types";
import { CertificateCard } from "./certificate-card";
import { CertificateDetailsModal } from "./certificate-details-modal";
import { CertificateModal } from "./certificate-modal";
import { CustomExpenseCard } from "./custom-expense-card";
import { ExpenseModal } from "./expense-modal";

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
  // `selectedCertForDetails` drives the read-only `CertificateDetailsModal`
  // open state — open when not null, closed when null (REQ-9 AC#7).
  const [createCertOpen, setCreateCertOpen] = useState(false);
  const [createExpenseOpen, setCreateExpenseOpen] = useState(false);
  const [selectedCertForDetails, setSelectedCertForDetails] =
    useState<Certificate | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  // ── Mutating handlers ──────────────────────────────────────────────────

  /**
   * Append the freshly-created cert/expense to the local list and trigger
   * a server refresh. Optimistic append keeps the UI responsive while the
   * server response cycles in via `refreshCerts()` — both shouldn't drift
   * because `createCertificate` returns the same row shape.
   */
  const handleCreated = useCallback(
    (cert: Certificate) => {
      setCerts((prev) => {
        if (!prev) return [cert];
        // Defensive de-dup in case the refresh races and the cert is
        // already present from the network refresh below.
        if (prev.some((c) => c.id === cert.id)) return prev;
        return [cert, ...prev];
      });
      // Network refresh to pick up server-computed share_rub / share_percent
      // for any pre-existing certs whose attached_items[] may have shifted.
      void refreshCerts();
    },
    [refreshCerts],
  );

  /**
   * Card edit click → open the read-only details modal. Phase B scope
   * does not include an inline edit form (REQ-9 AC#7); when one ships we
   * can swap this for an editable variant without changing the cards.
   */
  const handleEditCert = useCallback((cert: Certificate) => {
    setSelectedCertForDetails(cert);
  }, []);

  /**
   * Confirm + delete + refresh. The `confirm()` prompt is intentional —
   * destructive actions get an explicit gate per project UX policy.
   */
  const handleDeleteCert = useCallback(
    async (cert: Certificate) => {
      const label = cert.is_custom_expense
        ? cert.display_name || "расход"
        : `сертификат «${cert.type}»`;
      const ok =
        typeof window === "undefined"
          ? true
          : window.confirm(`Удалить ${label}?`);
      if (!ok) return;

      setDeletingId(cert.id);
      try {
        const res = await deleteCertificate(cert.id);
        if (!res.success) {
          toast.error(res.error?.message ?? "Не удалось удалить");
          return;
        }
        // Optimistic removal + server refresh for absolute parity.
        setCerts((prev) =>
          prev ? prev.filter((c) => c.id !== cert.id) : prev,
        );
        await refreshCerts();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Network error";
        toast.error(msg);
      } finally {
        setDeletingId(null);
      }
    },
    [refreshCerts],
  );

  return (
    <section
      className="flex flex-col gap-3"
      data-testid="customs-certificates-section"
      data-selected-cert-id={selectedCertForDetails?.id ?? ""}
      data-create-cert-open={createCertOpen ? "true" : "false"}
      data-create-expense-open={createExpenseOpen ? "true" : "false"}
      data-deleting-id={deletingId ?? ""}
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
              <CustomExpenseCard
                key={cert.id}
                expense={cert}
                totalQuoteItems={totalItemsInQuote}
                canEdit={canEdit}
                onEdit={() => handleEditCert(cert)}
                onDelete={() => handleDeleteCert(cert)}
              />
            ) : (
              <CertificateCard
                key={cert.id}
                cert={cert}
                totalQuoteItems={totalItemsInQuote}
                canEdit={canEdit}
                onEdit={() => handleEditCert(cert)}
                onDelete={() => handleDeleteCert(cert)}
              />
            ),
          )}
        </div>
      ) : null}

      {/* ── Modals ──────────────────────────────────────────────────────── */}

      <CertificateModal
        open={createCertOpen}
        onOpenChange={setCreateCertOpen}
        quoteId={quoteId}
        items={items}
        onCreated={handleCreated}
      />

      <ExpenseModal
        open={createExpenseOpen}
        onOpenChange={setCreateExpenseOpen}
        quoteId={quoteId}
        items={items}
        onCreated={handleCreated}
      />

      {selectedCertForDetails ? (
        <CertificateDetailsModal
          open={selectedCertForDetails !== null}
          onOpenChange={(open) => {
            if (!open) setSelectedCertForDetails(null);
          }}
          cert={selectedCertForDetails}
          items={items}
        />
      ) : null}
    </section>
  );
}
