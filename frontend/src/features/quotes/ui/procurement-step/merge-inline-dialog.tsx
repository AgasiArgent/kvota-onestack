"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { extractErrorMessage } from "@/shared/lib/errors";
import { mergeInvoiceItems } from "@/entities/quote/mutations";

/**
 * Inline merge UX (mirror of the inline split shipped this session).
 *
 * Triggered per-row from the procurement handsontable. The clicked row is
 * the "initiator". The dialog lists OTHER 1:1 candidates in this invoice
 * with checkboxes — user picks ≥1 — plus a 4-field form for the resulting
 * merged row. Currency is inherited from the parent КП (no picker).
 *
 * Other supplier-side fields (вес, габариты, артикул производителя, MOQ,
 * срок поставки, etc.) are filled inline in the handsontable AFTER merge,
 * keeping this dialog focused on the structural action.
 */

export interface MergeCandidate {
  invoice_item_id: string;
  source_quote_item_id: string;
  brand: string;
  supplier_sku: string;
  product_name: string;
  quantity: number;
}

export interface MergeFormState {
  product_name: string;
  brand: string;
  supplier_sku: string;
  purchase_price_original: string;
  selectedPartnerIds: Set<string>;
}

export function isPartnerSelected(
  state: MergeFormState,
  invoiceItemId: string
): boolean {
  return state.selectedPartnerIds.has(invoiceItemId);
}

export function isValidMergeForm(state: MergeFormState): boolean {
  if (state.selectedPartnerIds.size < 1) return false;
  if (!state.product_name.trim()) return false;
  if (!state.brand.trim()) return false;
  if (!state.supplier_sku.trim()) return false;
  const price = parseFloat(state.purchase_price_original);
  if (!Number.isFinite(price) || price <= 0) return false;
  return true;
}

interface MergeInlineDialogProps {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  initiatorInvoiceItemId: string;
  initiatorSourceQuoteItemId: string;
  /** Initiator's source-quote-item quantity — used to seed the merged-row qty. */
  initiatorQuantity: number;
  /** OTHER 1:1 candidates in this invoice (excluding the initiator). */
  candidates: MergeCandidate[];
  /** Currency inherited from the parent invoice. */
  currency: string;
  /** Initiator-row defaults pre-filled into the merged-row form. */
  defaults: {
    product_name: string;
    brand: string;
    supplier_sku: string;
    purchase_price_original: number | null;
  };
}

function makeInitialState(
  defaults: MergeInlineDialogProps["defaults"]
): MergeFormState {
  return {
    product_name: defaults.product_name ?? "",
    brand: defaults.brand ?? "",
    supplier_sku: defaults.supplier_sku ?? "",
    purchase_price_original:
      defaults.purchase_price_original != null
        ? defaults.purchase_price_original.toString()
        : "",
    selectedPartnerIds: new Set<string>(),
  };
}

export function MergeInlineDialog({
  open,
  onClose,
  invoiceId,
  initiatorInvoiceItemId,
  initiatorSourceQuoteItemId,
  initiatorQuantity,
  candidates,
  currency,
  defaults,
}: MergeInlineDialogProps) {
  const router = useRouter();
  const [state, setState] = useState<MergeFormState>(() =>
    makeInitialState(defaults)
  );
  const [submitting, setSubmitting] = useState(false);

  // Reset on every fresh open against a different initiator.
  useEffect(() => {
    if (!open) return;
    setState(makeInitialState(defaults));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initiatorInvoiceItemId]);

  function handleClose() {
    if (submitting) return;
    onClose();
  }

  function togglePartner(invoiceItemId: string) {
    setState((prev) => {
      const next = new Set(prev.selectedPartnerIds);
      if (next.has(invoiceItemId)) next.delete(invoiceItemId);
      else next.add(invoiceItemId);
      return { ...prev, selectedPartnerIds: next };
    });
  }

  function setField<K extends keyof Omit<MergeFormState, "selectedPartnerIds">>(
    field: K,
    value: MergeFormState[K]
  ) {
    setState((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit() {
    if (!isValidMergeForm(state)) return;
    setSubmitting(true);
    try {
      // Map selected invoice_item_ids back to their source quote_item_ids.
      // The mutation expects quote_item_ids (the qi side of the M:N coverage).
      const selectedPartners = candidates.filter((c) =>
        state.selectedPartnerIds.has(c.invoice_item_id)
      );
      const sourceQuoteItemIds = [
        initiatorSourceQuoteItemId,
        ...selectedPartners.map((c) => c.source_quote_item_id),
      ];

      // Merged-row quantity is the MAX of selected sources' quantities —
      // matches the legacy MergeModal default. The user can adjust later
      // by editing the row inline if the heuristic guesses wrong.
      const mergedQuantity = Math.max(
        initiatorQuantity,
        ...selectedPartners.map((c) => c.quantity)
      );

      await mergeInvoiceItems(invoiceId, sourceQuoteItemIds, {
        product_name: state.product_name.trim(),
        brand: state.brand.trim() || null,
        supplier_sku: state.supplier_sku.trim() || null,
        quantity: mergedQuantity,
        purchase_price_original: parseFloat(state.purchase_price_original),
        purchase_currency: currency,
        // Filled inline in the handsontable after merge — not part of this
        // structural action.
        weight_in_kg: null,
        customs_code: null,
      });

      toast.success("Позиции объединены");
      onClose();
      router.refresh();
    } catch (err) {
      console.error("[merge-inline-dialog] submit failed:", err);
      toast.error(
        extractErrorMessage(err) ?? "Не удалось объединить позиции"
      );
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = !submitting && isValidMergeForm(state);
  const selectedCount = state.selectedPartnerIds.size;

  return (
    <Dialog open={open} onOpenChange={(next) => !next && handleClose()}>
      <DialogContent className="sm:max-w-xl z-[200]" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Объединить позиции</DialogTitle>
          <DialogDescription>
            «{defaults.product_name}» + выбранные позиции ниже сольются в одну
            строку. Остальные поля (вес, габариты, артикул производителя,
            срок и др.) заполните в таблице после объединения.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">
              Объединить с (выбрано: {selectedCount})
            </Label>
            {candidates.length === 0 ? (
              <p className="text-xs text-muted-foreground italic">
                Нет позиций, с которыми можно объединить.
              </p>
            ) : (
              <div className="rounded-md border border-border divide-y divide-border max-h-48 overflow-y-auto">
                {candidates.map((c) => (
                  <label
                    key={c.invoice_item_id}
                    className="flex items-center gap-3 px-3 py-2 hover:bg-muted/40 cursor-pointer text-sm"
                  >
                    <input
                      type="checkbox"
                      className="size-4"
                      checked={state.selectedPartnerIds.has(c.invoice_item_id)}
                      onChange={() => togglePartner(c.invoice_item_id)}
                    />
                    <span className="font-medium truncate max-w-24">
                      {c.brand || "—"}
                    </span>
                    <span className="font-mono text-xs text-muted-foreground truncate max-w-28">
                      {c.supplier_sku || "—"}
                    </span>
                    <span className="truncate flex-1">{c.product_name}</span>
                    <span className="font-mono shrink-0 tabular-nums">
                      {c.quantity}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-md border border-border bg-muted/20 p-3 space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              Объединённая позиция
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="col-span-2 space-y-1">
                <Label className="text-xs">
                  Наименование <span className="text-destructive">*</span>
                </Label>
                <Input
                  className="h-8 text-sm"
                  placeholder="Наименование"
                  value={state.product_name}
                  onChange={(e) => setField("product_name", e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <Label className="text-xs">
                  Бренд <span className="text-destructive">*</span>
                </Label>
                <Input
                  className="h-8 text-sm"
                  placeholder="Бренд"
                  value={state.brand}
                  onChange={(e) => setField("brand", e.target.value)}
                />
              </div>

              <div className="space-y-1">
                <Label className="text-xs">
                  Артикул поставщика <span className="text-destructive">*</span>
                </Label>
                <Input
                  className="h-8 text-sm"
                  placeholder="Артикул"
                  value={state.supplier_sku}
                  onChange={(e) => setField("supplier_sku", e.target.value)}
                />
              </div>

              <div className="col-span-2 space-y-1">
                <Label className="text-xs">
                  Цена закупки ({currency}){" "}
                  <span className="text-destructive">*</span>
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  className="h-8 text-sm tabular-nums"
                  placeholder="0.00"
                  value={state.purchase_price_original}
                  onChange={(e) =>
                    setField("purchase_price_original", e.target.value)
                  }
                />
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={submitting}>
            Отмена
          </Button>
          <Button
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Объединить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
