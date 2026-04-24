"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { createClient } from "@/shared/lib/supabase/client";
import { extractErrorMessage } from "@/shared/lib/errors";
import { assignItemsToInvoice } from "@/entities/quote/mutations";

/**
 * Task 73 — Requirement 7 AC#3: add positions into an empty КП поставщику.
 *
 * Opened from InvoiceCard's `isEmpty` branch ("+ Добавить позиции"). The
 * user cancelled or never had items when the КП was created; this modal
 * lets them pick from the quote's candidate items to assign into THIS
 * invoice.
 *
 * Phase 5b REQ-1 AC#1: overlapping КП coverage is allowed. Items already
 * covered by another invoice are shown with a subtle "в КП …" badge but
 * remain selectable. The server-side `assignItemsToInvoice` handles the
 * idempotent upsert of invoice_item_coverage rows.
 */

interface CandidateItem {
  id: string;
  product_name: string;
  supplier_sku: string | null;
  brand: string | null;
  quantity: number;
  /** Invoice numbers the item is already covered by (may be empty). */
  existing_invoice_numbers: string[];
}

interface AddPositionsModalProps {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  quoteId: string;
}

const qtyFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/**
 * Pure body — extracted so tests can render without a Portal (the
 * @base-ui Dialog uses a React Portal omitted during SSR). Production
 * wraps it in a Dialog via AddPositionsModal.
 */
interface AddPositionsModalBodyProps {
  loading: boolean;
  candidates: CandidateItem[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: () => void;
}

export function AddPositionsModalBody({
  loading,
  candidates,
  selectedIds,
  onToggle,
  onToggleAll,
}: AddPositionsModalBodyProps) {
  if (loading) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        <Loader2 size={16} className="animate-spin inline-block mr-2" />
        Загрузка позиций…
      </div>
    );
  }

  if (candidates.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        В заявке нет позиций для добавления.
      </div>
    );
  }

  const allSelected = selectedIds.size === candidates.length;

  return (
    <div className="max-h-[50vh] overflow-y-auto rounded-md border border-input">
      <div className="sticky top-0 bg-muted/60 border-b border-input px-3 py-2 flex items-center gap-2">
        <Checkbox
          checked={allSelected}
          onCheckedChange={onToggleAll}
          aria-label="Выбрать все"
        />
        <span className="text-xs font-medium">
          Выбрать все ({candidates.length})
        </span>
        <span className="ml-auto text-xs text-muted-foreground">
          Выбрано: {selectedIds.size}
        </span>
      </div>
      <ul className="divide-y divide-border">
        {candidates.map((item) => {
          const checked = selectedIds.has(item.id);
          const isCovered = item.existing_invoice_numbers.length > 0;
          return (
            <li
              key={item.id}
              className={`px-3 py-2 flex items-center gap-2 ${
                checked ? "bg-muted/40" : ""
              }`}
            >
              <Checkbox
                checked={checked}
                onCheckedChange={() => onToggle(item.id)}
                aria-label={`Выбрать ${item.product_name}`}
              />
              <span className="text-sm font-medium truncate max-w-48">
                {item.product_name}
              </span>
              {item.brand && (
                <span className="text-xs text-muted-foreground truncate max-w-20">
                  {item.brand}
                </span>
              )}
              {item.supplier_sku && (
                <span className="text-xs font-mono text-muted-foreground truncate max-w-24">
                  {item.supplier_sku}
                </span>
              )}
              {isCovered && (
                <Badge
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 h-5"
                  title="Уже в другом КП — выбор разрешён"
                >
                  в {item.existing_invoice_numbers.join(", ")}
                </Badge>
              )}
              <span className="ml-auto text-xs font-mono tabular-nums shrink-0">
                {qtyFmt.format(item.quantity)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function AddPositionsModal({
  open,
  onClose,
  invoiceId,
  quoteId,
}: AddPositionsModalProps) {
  const router = useRouter();
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Fetch candidate quote_items + their existing coverage when modal opens.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setSelectedIds(new Set());

    void (async () => {
      const supabase = createClient();

      const { data: items, error: itemsErr } = await supabase
        .from("quote_items")
        .select("id, product_name, supplier_sku, brand, quantity")
        .eq("quote_id", quoteId)
        .order("position", { ascending: true });

      if (cancelled) return;
      if (itemsErr || !items) {
        setCandidates([]);
        setLoading(false);
        return;
      }

      // Phase 5b REQ-1 AC#1: overlapping coverage allowed — we DO NOT
      // exclude items already in another КП. Instead annotate them with
      // the covering invoice numbers as a subtle badge.
      const qiIds = items.map((i) => i.id);
      const { data: coverage } = qiIds.length
        ? await supabase
            .from("invoice_item_coverage")
            .select(
              "quote_item_id, invoice_items!inner(invoice_id, invoices!inner(id, invoice_number))"
            )
            .in("quote_item_id", qiIds)
        : { data: [] };

      if (cancelled) return;

      const coverageByQi = new Map<string, Set<string>>();
      for (const row of (coverage ?? []) as unknown as Array<{
        quote_item_id: string;
        invoice_items: {
          invoice_id: string;
          invoices: { id: string; invoice_number: string };
        };
      }>) {
        const inv = row.invoice_items?.invoices;
        if (!inv) continue;
        // Exclude the current (empty) invoice — it has no coverage yet,
        // but belt-and-suspenders: never annotate "this invoice covers
        // this item" because we're about to add coverage to it.
        if (inv.id === invoiceId) continue;
        const set = coverageByQi.get(row.quote_item_id) ?? new Set<string>();
        set.add(inv.invoice_number);
        coverageByQi.set(row.quote_item_id, set);
      }

      setCandidates(
        items.map((i) => ({
          id: i.id,
          product_name: i.product_name ?? "",
          supplier_sku: i.supplier_sku ?? null,
          brand: i.brand ?? null,
          quantity: Number(i.quantity ?? 0),
          existing_invoice_numbers: Array.from(
            coverageByQi.get(i.id) ?? []
          ).sort(),
        }))
      );
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [open, quoteId, invoiceId]);

  function toggleItem(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleAll() {
    setSelectedIds((prev) => {
      if (prev.size === candidates.length) {
        return new Set();
      }
      return new Set(candidates.map((c) => c.id));
    });
  }

  async function handleSubmit() {
    if (selectedIds.size === 0) return;
    setSubmitting(true);
    try {
      await assignItemsToInvoice(Array.from(selectedIds), invoiceId);
      toast.success(`${selectedIds.size} поз. добавлено в КП`);
      onClose();
      router.refresh();
    } catch (err) {
      console.error("[add-positions-modal] assign failed:", err);
      toast.error(
        extractErrorMessage(err) ?? "Не удалось добавить позиции в КП"
      );
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = selectedIds.size > 0 && !submitting;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next && !submitting) onClose(); }}>
      <DialogContent className="sm:max-w-lg z-[200]">
        <DialogHeader>
          <DialogTitle>Добавить позиции в КП</DialogTitle>
          <DialogDescription>
            Выберите позиции заявки для добавления в это КП поставщику.
            Позиции, уже находящиеся в других КП, также доступны для выбора.
          </DialogDescription>
        </DialogHeader>

        <AddPositionsModalBody
          loading={loading}
          candidates={candidates}
          selectedIds={selectedIds}
          onToggle={toggleItem}
          onToggleAll={toggleAll}
        />

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Отмена
          </Button>
          <Button
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {submitting && <Loader2 size={14} className="animate-spin mr-1" />}
            Добавить выбранные
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
