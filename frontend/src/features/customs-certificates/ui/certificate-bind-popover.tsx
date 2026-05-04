"use client";

/**
 * CertificateBindPopover — Phase B Wave 3 Task 7d (REQ-8).
 *
 * Anchored popover (~360px wide) that lets a customs specialist link the
 * current per-item dialog's `quote_item` to a certificate that already
 * exists in the same quote — without opening the full
 * `<CertificateModal>`.
 *
 * Behaviour summary (per design.md §4.8.4 + §5.2 + REQ-8 AC#1..#11):
 *   - Header «Привязать позицию №{N} «{item.name}» к сертификату»
 *     (точная копия из мокапа line 948).
 *   - Search input filtering candidates case-insensitively against
 *     `type` and `number` (REQ-8 AC#6 — searchable pattern, LD-5).
 *   - Radio list showing only same-quote certs; expired ones disabled
 *     with tooltip «Сертификат истёк {DD.MM.YYYY}» (REQ-4 AC#3).
 *   - Empty state when `existingCerts` is empty (REQ-8 AC#10) — link
 *     fires `onCreateNew` so the parent can open the modal.
 *   - After-attach preview (info-blue card) appears once a radio is
 *     selected — pure-frontend `splitCostBatch` recomputation; current
 *     item highlighted amber per мокап line 974 (REQ-8 AC#7).
 *   - Footer «Отмена» (ghost) + «Привязать» (default, disabled until
 *     selection) (REQ-8 AC#8).
 *   - Submit: optimistic local append → POST `/items` → on success
 *     close + onAttached(updatedCert); on error rollback + toast
 *     (REQ-8 AC#9).
 *
 * Pure helpers (`filterCertsBySearch`, `isCertExpired`,
 * `computeAfterAttachPreview`) are exported so the workspace's no-jsdom
 * vitest setup can unit-test the math/filter logic without a browser.
 *
 * Compliance (LD-13): shadcn `<Button>` only, design tokens only, no
 * inline `style=` for colors/fonts/spacing, no `transition: all`, no
 * `transform: translateY()`. Date formatting via `formatDateRussian`
 * from the customs-history feature (project-wide helper, LD-11).
 */

import { useMemo, useState, type ReactNode } from "react";
import { Search, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import { formatDateRussian } from "@/features/customs-history/lib/format-date";

import { attachCertificateItem } from "../api/certificates";
import { splitCostBatch } from "../lib/cost-split";
import { formatRub } from "../lib/format-rub";
import type { Certificate, QuoteItemForSelect } from "../model/types";

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit testing without a DOM environment.
// ---------------------------------------------------------------------------

/**
 * Case-insensitive substring filter against `type` and `number`.
 *
 *  - Empty / whitespace-only query → returns the full list untouched.
 *  - `null` `number` is tolerated — only `type` is matched.
 *
 * Pure — never mutates the input array.
 */
export function filterCertsBySearch(
  certs: readonly Certificate[],
  query: string,
): readonly Certificate[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return certs;
  return certs.filter((cert) => {
    const type = cert.type?.toLowerCase() ?? "";
    const number = cert.number?.toLowerCase() ?? "";
    return type.includes(needle) || number.includes(needle);
  });
}

/**
 * `valid_until` decision — `<= today` means expired (REQ-4 AC#3).
 *
 *  - `null` → never expired (perpetual cert per REQ-4 AC#1).
 *  - The `today` arg defaults to the current ISO-day; tests pass a fixed
 *    string for determinism.
 *
 * Both sides are compared as `YYYY-MM-DD` ISO strings — lexicographic
 * compare is correct for this format and avoids timezone drift.
 */
export function isCertExpired(
  validUntil: string | null,
  today: string = new Date().toISOString().slice(0, 10),
): boolean {
  if (!validUntil) return false;
  return validUntil <= today;
}

/**
 * One row in the after-attach preview block — shape consumed by JSX.
 *
 * `isCurrent=true` for the row matching `currentItem` (highlighted amber
 * per мокап line 974). Other rows render in neutral text.
 */
export interface AfterAttachPreviewRow {
  /** UUID of the `quote_items` row this row refers to. */
  item_id: string;
  /** 1-based ordinal within the quote — rendered as «№N». */
  position: number;
  /** Display name of the position. */
  name: string;
  /** Per-item RUB cost basis (numerator in the split formula). */
  item_basis: number;
  /** Sum of all RUB cost bases in the projected attachment set. */
  total_basis: number;
  /** Kopek-exact share assigned to this row by `splitCostBatch`. */
  share_rub: number;
  /** True when this row corresponds to `currentItem` (UI highlight). */
  isCurrent: boolean;
}

/**
 * Optimistic frame for the cert when `currentItemId` is about to be
 * attached — the helper that the component calls before the network
 * round-trip lands.
 *
 *  - If `currentItemId` is already in `cert.attached_items[]` → return
 *    `cert` unchanged (no double-attach; server would 409).
 *  - Otherwise → return a new cert with `currentItemId` appended at the
 *    END of `attached_items[]` (matches server-side `created_at ASC`
 *    ordering used by `split_cost_batch`). The placeholder `share_rub` /
 *    `share_percent` are zeroed out — the parent should NOT trust them
 *    until the authoritative `onAttached(serverCert)` arrives.
 *
 * Pure — never mutates inputs.
 */
export function optimisticAttachUpdate(
  cert: Certificate,
  currentItemId: string,
): Certificate {
  const already = cert.attached_items.some(
    (a) => a.item_id === currentItemId,
  );
  if (already) return cert;
  return {
    ...cert,
    attached_items: [
      ...cert.attached_items,
      { item_id: currentItemId, share_rub: 0, share_percent: 0 },
    ],
  };
}

/**
 * Compute the «после привязки» distribution preview.
 *
 *  - Combines `cert.attached_items[]` (existing) with `currentItem.id`
 *    (about to be attached) into a single deterministic ordering — the
 *    new item lands at the END so the preview renders in the same order
 *    the server will see after the POST commits (the server orders
 *    attachments by `created_at ASC`).
 *  - Resolves each `attached_items[].item_id` against the parent-supplied
 *    `allItems[]` to get position / name / `rub_basis`. Items that the
 *    parent did not pass through (orphaned attachments) are silently
 *    skipped — the preview is informational and we'd rather render a
 *    smaller table than crash on a stale cert payload.
 *  - Skips currentItem from the existing list if it happens to already
 *    appear (defensive — server rejects duplicates with 409 anyway).
 *  - Empty inputs → `[]` (UI hides the preview block).
 *
 * Pure — never mutates inputs.
 */
export function computeAfterAttachPreview(
  cert: Certificate,
  allItems: readonly QuoteItemForSelect[],
  currentItem: QuoteItemForSelect,
): AfterAttachPreviewRow[] {
  const byId = new Map(allItems.map((i) => [i.id, i]));

  // Resolve existing attached items, dropping unknowns and the current
  // item (we add it ourselves at the end).
  const existing: QuoteItemForSelect[] = [];
  for (const att of cert.attached_items) {
    if (att.item_id === currentItem.id) continue;
    const found = byId.get(att.item_id);
    if (found) existing.push(found);
  }

  const projected: QuoteItemForSelect[] = [...existing, currentItem];

  if (projected.length === 0) {
    return [];
  }

  const itemValues = projected.map((it) => it.rub_basis);
  const shares = splitCostBatch(itemValues, cert.cost_rub);
  const total = itemValues.reduce((sum, v) => sum + v, 0);

  return projected.map((it, idx) => ({
    item_id: it.id,
    position: it.position,
    name: it.name,
    item_basis: it.rub_basis,
    total_basis: total,
    share_rub: shares[idx] ?? 0,
    isCurrent: it.id === currentItem.id,
  }));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface CertificateBindPopoverProps {
  /**
   * Element that opens the popover. The component wraps it in a
   * `<PopoverTrigger>` so the parent stays in control of the visual
   * trigger (button, link, icon) without imposing a particular shape.
   */
  trigger: ReactNode;
  /** Position the popover is binding ("текущая позиция" в мокапе). */
  currentItem: QuoteItemForSelect;
  /**
   * Full list of selectable positions in the current quote — used to
   * resolve `cert.attached_items[].item_id` for the after-attach preview
   * (the parent already has the lookup, so we pass it down rather than
   * re-fetch).
   */
  allItems: QuoteItemForSelect[];
  /**
   * Same-quote candidates available for binding. The parent is expected
   * to filter `quote_id === currentItem.quote_id` — this component only
   * operates on what it receives.
   */
  existingCerts: Certificate[];
  /**
   * Optional callback fired after a successful POST `/items` — passes
   * the freshly-returned cert with recomputed `attached_items[]` so the
   * parent can refresh its coverage list / section state.
   */
  onAttached?: (cert: Certificate) => void;
  /**
   * Optional callback fired when the empty-state link is clicked. The
   * parent should open the full `<CertificateModal mode="create">` so
   * the user can add the first cert without closing the dialog.
   */
  onCreateNew?: () => void;
}

export function CertificateBindPopover({
  trigger,
  currentItem,
  allItems,
  existingCerts,
  onAttached,
  onCreateNew,
}: CertificateBindPopoverProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedCertId, setSelectedCertId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Stable `today` snapshot — recomputed only when the popover opens
  // (the user closing/reopening picks up a new day if midnight rolls
  // over while the dialog is in the background).
  const today = useMemo(
    () => new Date().toISOString().slice(0, 10),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [open],
  );

  const filtered = useMemo(
    () => filterCertsBySearch(existingCerts, search),
    [existingCerts, search],
  );

  const selectedCert = useMemo(
    () => existingCerts.find((c) => c.id === selectedCertId) ?? null,
    [existingCerts, selectedCertId],
  );

  const previewRows = useMemo(() => {
    if (!selectedCert) return [];
    return computeAfterAttachPreview(selectedCert, allItems, currentItem);
  }, [selectedCert, allItems, currentItem]);

  function reset() {
    setSearch("");
    setSelectedCertId(null);
    setSubmitting(false);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    setOpen(next);
  }

  async function handleAttach() {
    if (!selectedCert || submitting) return;
    setSubmitting(true);

    // Optimistic: locally append the current item to the selected cert's
    // attached_items so a parent that watches this prop can react
    // immediately. We only wire a single optimistic mutation — the
    // authoritative state (recomputed shares) arrives via onAttached.
    const optimisticCert = optimisticAttachUpdate(selectedCert, currentItem.id);
    onAttached?.(optimisticCert);

    try {
      const res = await attachCertificateItem(selectedCert.id, currentItem.id);
      if (!res.success || !res.data) {
        // Rollback the optimistic update by handing the parent the
        // pre-attach cert again. Parent decides whether to keep the
        // optimistic frame; we provide an authoritative rollback target.
        onAttached?.(selectedCert);
        const message =
          res.error?.message ?? "Не удалось привязать сертификат";
        toast.error(message);
        return;
      }
      // Authoritative — parent replaces the optimistic frame.
      onAttached?.(res.data);
      handleOpenChange(false);
    } catch (err) {
      // Network / unexpected error — rollback + toast.
      onAttached?.(selectedCert);
      const message =
        err instanceof Error ? err.message : "Не удалось привязать сертификат";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  const headerLabel =
    `Привязать позицию №${currentItem.position} «${currentItem.name}» к сертификату`;
  const isEmpty = existingCerts.length === 0;

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger render={trigger as never} />
      <PopoverContent
        align="start"
        side="bottom"
        className="w-[360px] p-3"
        data-testid="certificate-bind-popover"
      >
        <div className="flex flex-col gap-3">
          <div
            className="text-sm font-medium"
            data-testid="certificate-bind-popover-header"
          >
            {headerLabel}
          </div>

          {isEmpty ? (
            <div
              className="rounded-md border border-border bg-muted/30 px-3 py-4 text-xs text-muted-foreground"
              data-testid="certificate-bind-popover-empty"
            >
              <div>В этом КП ещё нет сертификатов. Создайте новый.</div>
              {onCreateNew && (
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => {
                    handleOpenChange(false);
                    onCreateNew();
                  }}
                  className="mt-1 h-auto p-0 text-xs"
                  data-testid="certificate-bind-popover-create-new"
                >
                  Создать новый
                </Button>
              )}
            </div>
          ) : (
            <>
              <div className="relative">
                <Search
                  className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                  size={14}
                />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Поиск по типу/номеру"
                  className="h-7 pl-7 text-xs"
                  aria-label="Поиск сертификатов"
                  data-testid="certificate-bind-popover-search"
                />
                {search.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setSearch("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    aria-label="Очистить поиск"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>

              <div
                className="flex max-h-64 flex-col gap-1 overflow-y-auto"
                data-testid="certificate-bind-popover-list"
              >
                {filtered.length === 0 ? (
                  <div className="px-2 py-4 text-center text-xs text-muted-foreground">
                    Ничего не найдено
                  </div>
                ) : (
                  filtered.map((cert) => {
                    const expired = isCertExpired(cert.valid_until, today);
                    const expiredLabel = expired
                      ? `Сертификат истёк ${formatDateRussian(cert.valid_until)}`
                      : "";
                    const checked = cert.id === selectedCertId;
                    const attachedCount = cert.attached_items.length;
                    const headline =
                      cert.number && cert.number.length > 0
                        ? `${cert.type} ${cert.number}`
                        : cert.type;
                    return (
                      <label
                        key={cert.id}
                        className={cn(
                          "flex items-start gap-2 rounded-md border px-2 py-1.5 text-xs",
                          expired
                            ? "cursor-not-allowed border-border opacity-60"
                            : "cursor-pointer border-border hover:bg-muted/40",
                          checked && !expired && "border-primary bg-primary/5",
                        )}
                        data-slot="certificate-bind-popover-row"
                        data-cert-id={cert.id}
                        data-expired={expired ? "true" : "false"}
                        data-selected={checked ? "true" : "false"}
                        title={expiredLabel || undefined}
                      >
                        <input
                          type="radio"
                          name="certificate-bind-popover-radio"
                          value={cert.id}
                          checked={checked}
                          disabled={expired}
                          onChange={() => setSelectedCertId(cert.id)}
                          aria-label={headline}
                          className="mt-0.5"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-foreground">
                            {headline}
                          </div>
                          {cert.number && (
                            <div className="font-mono text-[11px] text-muted-foreground truncate">
                              {cert.number}
                            </div>
                          )}
                          <div className="text-[10px] text-muted-foreground">
                            {`${formatRub(cert.cost_rub)} · уже на ${attachedCount} позициях`}
                          </div>
                          {expired && (
                            <div className="text-[10px] text-destructive">
                              {expiredLabel}
                            </div>
                          )}
                        </div>
                      </label>
                    );
                  })
                )}
              </div>

              {selectedCert && previewRows.length > 0 && (
                <div
                  className="rounded-md border border-blue-900 bg-blue-950/20 p-2 text-[11px]"
                  data-testid="certificate-bind-popover-preview"
                >
                  <div className="text-foreground/90">
                    {`После привязки к ${selectedCert.type} (выбрано):`}
                  </div>
                  <div className="text-muted-foreground">
                    {`Стоимость распределится на ${previewRows.length} позиций по новой пропорции:`}
                  </div>
                  <div className="mt-1 flex flex-col">
                    {previewRows.map((row) => (
                      <div
                        key={row.item_id}
                        className={cn(
                          "flex items-baseline justify-between gap-2",
                          row.isCurrent && "text-amber-400",
                        )}
                        data-slot="certificate-bind-popover-preview-row"
                        data-item-id={row.item_id}
                        data-current={row.isCurrent ? "true" : "false"}
                      >
                        <span>
                          <span className="font-medium">№{row.position}</span>
                          <span className="text-muted-foreground">
                            {" "}
                            ({formatRub(row.item_basis)} / {formatRub(row.total_basis)})
                          </span>
                        </span>
                        <span className="font-mono">
                          → {formatRub(row.share_rub)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          <div className="flex justify-end gap-2 border-t border-border pt-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => handleOpenChange(false)}
              disabled={submitting}
              data-testid="certificate-bind-popover-cancel"
            >
              Отмена
            </Button>
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleAttach}
              disabled={!selectedCert || submitting || isEmpty}
              data-testid="certificate-bind-popover-submit"
            >
              Привязать
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
