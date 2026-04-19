"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies";
import { mergeInvoiceItems } from "@/entities/quote/mutations";

/**
 * Phase 5c Task 13 — MergeModal.
 *
 * Consolidates N ≥ 2 quote_items (currently 1:1-covered in THIS invoice)
 * into one merged invoice_item plus N coverage rows (all ratio=1). The
 * merge is local to the calling invoice — coverage in other invoices for
 * the same quote_items is untouched.
 *
 * Chain-merge is prevented by only accepting candidates that are already
 * 1:1 in this invoice (the caller filters these in invoice-card.tsx).
 */

export interface MergeQuoteItemCandidate {
  id: string;
  product_name: string;
  quantity: number;
}

export interface MergeFormState {
  product_name: string;
  supplier_sku: string;
  brand: string;
  quantity: string;
  purchase_price_original: string;
  purchase_currency: string;
  weight_in_kg: string;
  customs_code: string;
}

interface MergeModalProps {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  /** Source candidates = quote_items currently 1:1-covered in this invoice. */
  candidates: MergeQuoteItemCandidate[];
  /**
   * Currency inherited from the parent invoice. Pre-fills the merged row's
   * `purchase_currency` field.
   */
  defaultCurrency: string;
}

export function defaultMergeQuantity(
  sources: MergeQuoteItemCandidate[]
): number {
  if (sources.length === 0) return 0;
  return sources.reduce((max, s) => Math.max(max, s.quantity), 0);
}

export function isMergeFormValid(form: {
  selectedQuoteItemIds: Set<string>;
  merged: MergeFormState;
}): boolean {
  if (form.selectedQuoteItemIds.size < 2) return false;
  if (!form.merged.product_name.trim()) return false;
  const qty = parseFloat(form.merged.quantity);
  if (!Number.isFinite(qty) || qty <= 0) return false;
  const price = parseFloat(form.merged.purchase_price_original);
  if (!Number.isFinite(price) || price <= 0) return false;
  if (!form.merged.purchase_currency) return false;
  return true;
}

function makeEmptyMerged(defaultCurrency: string): MergeFormState {
  return {
    product_name: "",
    supplier_sku: "",
    brand: "",
    quantity: "",
    purchase_price_original: "",
    purchase_currency: defaultCurrency,
    weight_in_kg: "",
    customs_code: "",
  };
}

/**
 * Pure form body — extracted from MergeModal so it can be rendered without
 * a Dialog portal (the @base-ui/react Dialog uses a React Portal which is
 * omitted during SSR). Tests mount this body directly; production use
 * wraps it in a Dialog via MergeModal.
 */
interface MergeModalBodyProps {
  candidates: MergeQuoteItemCandidate[];
  selectedQuoteItemIds: Set<string>;
  onToggle: (id: string) => void;
  merged: MergeFormState;
  onMergedChange: (field: keyof MergeFormState, value: string) => void;
}

export function MergeModalBody({
  candidates,
  selectedQuoteItemIds,
  onToggle,
  merged,
  onMergedChange,
}: MergeModalBodyProps) {
  return (
    <div className="space-y-4 max-h-[60vh] overflow-y-auto">
      <div className="space-y-1.5">
        <Label>
          Исходные позиции заявки{" "}
          <span className="text-destructive">*</span>
        </Label>
        <p className="text-xs text-muted-foreground">
          Выберите не менее 2 позиций. В списке только те, что покрыты 1:1 в
          этом КП (без текущих разделений/объединений).
        </p>
        {candidates.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Нет подходящих позиций для объединения.
          </p>
        ) : (
          <div className="rounded-md border border-border bg-muted/20 p-2 space-y-1 max-h-48 overflow-y-auto">
            {candidates.map((c) => (
              <label
                key={c.id}
                className="flex items-center gap-2 text-sm cursor-pointer hover:bg-muted/40 rounded px-1 py-0.5"
              >
                <Checkbox
                  checked={selectedQuoteItemIds.has(c.id)}
                  onCheckedChange={() => onToggle(c.id)}
                />
                <span className="flex-1 truncate">{c.product_name}</span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {c.quantity} шт.
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-md border border-border bg-muted/20 p-3 space-y-2">
        <span className="text-xs font-medium text-muted-foreground">
          Объединённая позиция
        </span>

        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2 space-y-1">
            <Label className="text-xs">
              Наименование <span className="text-destructive">*</span>
            </Label>
            <Input
              className="h-8 text-sm"
              placeholder="Наименование"
              value={merged.product_name}
              onChange={(e) => onMergedChange("product_name", e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Артикул поставщика</Label>
            <Input
              className="h-8 text-sm"
              placeholder="Артикул"
              value={merged.supplier_sku}
              onChange={(e) => onMergedChange("supplier_sku", e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Бренд</Label>
            <Input
              className="h-8 text-sm"
              placeholder="Бренд"
              value={merged.brand}
              onChange={(e) => onMergedChange("brand", e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">
              Кол-во <span className="text-destructive">*</span>
            </Label>
            <Input
              type="number"
              step="0.001"
              min="0"
              className="h-8 text-sm tabular-nums"
              placeholder="0"
              value={merged.quantity}
              onChange={(e) => onMergedChange("quantity", e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">
              Цена закупки <span className="text-destructive">*</span>
            </Label>
            <Input
              type="number"
              step="0.01"
              min="0"
              className="h-8 text-sm tabular-nums"
              placeholder="0.00"
              value={merged.purchase_price_original}
              onChange={(e) =>
                onMergedChange("purchase_price_original", e.target.value)
              }
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Валюта</Label>
            <select
              value={merged.purchase_currency}
              onChange={(e) =>
                onMergedChange("purchase_currency", e.target.value)
              }
              className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            >
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Вес, кг</Label>
            <Input
              type="number"
              step="0.001"
              min="0"
              className="h-8 text-sm tabular-nums"
              placeholder="0"
              value={merged.weight_in_kg}
              onChange={(e) => onMergedChange("weight_in_kg", e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Код ТНВЭД</Label>
            <Input
              className="h-8 text-sm"
              placeholder="Код"
              value={merged.customs_code}
              onChange={(e) => onMergedChange("customs_code", e.target.value)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function MergeModal({
  open,
  onClose,
  invoiceId,
  candidates,
  defaultCurrency,
}: MergeModalProps) {
  const router = useRouter();
  const [selectedQuoteItemIds, setSelectedQuoteItemIds] = useState<Set<string>>(
    new Set()
  );
  const [merged, setMerged] = useState<MergeFormState>(() =>
    makeEmptyMerged(defaultCurrency)
  );
  const [submitting, setSubmitting] = useState(false);

  // Sync default quantity from max of selected sources whenever selection
  // changes and user hasn't typed a manual value yet.
  useEffect(() => {
    if (merged.quantity.trim() !== "") return;
    const selected = candidates.filter((c) =>
      selectedQuoteItemIds.has(c.id)
    );
    const defQty = defaultMergeQuantity(selected);
    if (defQty > 0) {
      setMerged((prev) => ({ ...prev, quantity: String(defQty) }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedQuoteItemIds]);

  function resetForm() {
    setSelectedQuoteItemIds(new Set());
    setMerged(makeEmptyMerged(defaultCurrency));
  }

  function handleClose() {
    if (submitting) return;
    resetForm();
    onClose();
  }

  function toggleQuoteItem(id: string) {
    setSelectedQuoteItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function updateMerged(field: keyof MergeFormState, value: string) {
    setMerged((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit() {
    if (!isMergeFormValid({ selectedQuoteItemIds, merged })) return;
    setSubmitting(true);
    try {
      await mergeInvoiceItems(invoiceId, Array.from(selectedQuoteItemIds), {
        product_name: merged.product_name.trim(),
        supplier_sku: merged.supplier_sku.trim() || null,
        brand: merged.brand.trim() || null,
        quantity: parseFloat(merged.quantity),
        purchase_price_original: parseFloat(merged.purchase_price_original),
        purchase_currency: merged.purchase_currency,
        weight_in_kg: merged.weight_in_kg.trim()
          ? parseFloat(merged.weight_in_kg)
          : null,
        customs_code: merged.customs_code.trim() || null,
      });
      toast.success(
        `${selectedQuoteItemIds.size} поз. объединены`
      );
      resetForm();
      onClose();
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось объединить позиции"
      );
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    !submitting && isMergeFormValid({ selectedQuoteItemIds, merged });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) handleClose();
      }}
    >
      <DialogContent
        className="sm:max-w-2xl z-[200]"
        showCloseButton={false}
      >
        <DialogHeader>
          <DialogTitle>Объединить позиции</DialogTitle>
          <DialogDescription>
            Выберите две или более позиции заявки, которые поставщик
            предлагает одной строкой. Все выбранные позиции будут объединены
            в одну позицию этого КП (с коэффициентом 1 для каждой).
          </DialogDescription>
        </DialogHeader>

        <MergeModalBody
          candidates={candidates}
          selectedQuoteItemIds={selectedQuoteItemIds}
          onToggle={toggleQuoteItem}
          merged={merged}
          onMergedChange={updateMerged}
        />

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={submitting}
          >
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
