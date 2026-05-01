"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus, Trash2 } from "lucide-react";
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
import { splitInvoiceItem } from "@/entities/quote/mutations";

/**
 * Inline split UX (replaces top-level SplitModal flow).
 *
 * Triggered from a single invoice_item row in the procurement handsontable
 * — the source quote_item is already known, so this dialog only collects
 * the per-child fields the user has to enter at split time:
 *   наименование, бренд, артикул поставщика, коэффициент, цена закупки.
 *
 * Other fields (currency, MOQ, срок, вес, габариты, артикул/наименование
 * производителя) are filled inline in the handsontable AFTER the split —
 * keeping this dialog small. Currency is inherited from the parent КП.
 */

export interface SplitChildFormState {
  product_name: string;
  brand: string;
  supplier_sku: string;
  quantity_ratio: string;
  purchase_price_original: string;
}

export function computeChildQuantity(
  sourceQuantity: number,
  ratio: number
): number {
  if (!Number.isFinite(ratio) || ratio <= 0) return 0;
  return sourceQuantity * ratio;
}

export function isValidSplitChild(child: SplitChildFormState): boolean {
  if (!child.product_name.trim()) return false;
  if (!child.brand.trim()) return false;
  if (!child.supplier_sku.trim()) return false;
  const ratio = parseFloat(child.quantity_ratio);
  if (!Number.isFinite(ratio) || ratio <= 0) return false;
  const price = parseFloat(child.purchase_price_original);
  if (!Number.isFinite(price) || price <= 0) return false;
  return true;
}

export function isSplitFormValid(children: SplitChildFormState[]): boolean {
  if (children.length < 2) return false;
  return children.every(isValidSplitChild);
}

function makeEmptyChild(seed: Partial<SplitChildFormState> = {}): SplitChildFormState {
  return {
    product_name: seed.product_name ?? "",
    brand: seed.brand ?? "",
    supplier_sku: seed.supplier_sku ?? "",
    quantity_ratio: seed.quantity_ratio ?? "1",
    purchase_price_original: seed.purchase_price_original ?? "",
  };
}

interface SplitInlineDialogProps {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  /** Quote_item the row is 1:1-covered against (resolved upstream). */
  sourceQuoteItemId: string;
  /** Source quote_item.quantity — drives the live computed-qty preview. */
  sourceQuantity: number;
  /** Product name shown in dialog header for context. */
  sourceProductName: string;
  /** Currency inherited from the parent invoice; not user-editable here. */
  currency: string;
  /** Defaults seeded into each fresh child row from the clicked invoice_item. */
  defaults?: {
    product_name?: string;
    brand?: string;
    supplier_sku?: string;
    purchase_price_original?: number | null;
  };
}

export function SplitInlineDialog({
  open,
  onClose,
  invoiceId,
  sourceQuoteItemId,
  sourceQuantity,
  sourceProductName,
  currency,
  defaults,
}: SplitInlineDialogProps) {
  const router = useRouter();
  const [children, setChildren] = useState<SplitChildFormState[]>(() => [
    makeEmptyChild(seedFromDefaults(defaults)),
    makeEmptyChild(seedFromDefaults(defaults)),
  ]);
  const [submitting, setSubmitting] = useState(false);

  // Reset children whenever the dialog re-opens against a fresh source row.
  // Without this, switching from one row to another carries over stale input
  // (state survives across openings as long as the component is mounted).
  useEffect(() => {
    if (!open) return;
    setChildren([
      makeEmptyChild(seedFromDefaults(defaults)),
      makeEmptyChild(seedFromDefaults(defaults)),
    ]);
    // We deliberately reset only on dialog open events; subsequent default
    // changes mid-session would otherwise wipe user input.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, sourceQuoteItemId]);

  function handleClose() {
    if (submitting) return;
    onClose();
  }

  function addChild() {
    setChildren((prev) => [
      ...prev,
      makeEmptyChild(seedFromDefaults(defaults)),
    ]);
  }

  function updateChild<K extends keyof SplitChildFormState>(
    idx: number,
    field: K,
    value: SplitChildFormState[K]
  ) {
    setChildren((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, [field]: value } : c))
    );
  }

  function removeChild(idx: number) {
    setChildren((prev) => (prev.length <= 2 ? prev : prev.filter((_, i) => i !== idx)));
  }

  async function handleSubmit() {
    if (!isSplitFormValid(children)) return;
    setSubmitting(true);
    try {
      await splitInvoiceItem(
        invoiceId,
        sourceQuoteItemId,
        children.map((c) => ({
          product_name: c.product_name.trim(),
          supplier_sku: c.supplier_sku.trim(),
          brand: c.brand.trim(),
          quantity_ratio: parseFloat(c.quantity_ratio),
          purchase_price_original: parseFloat(c.purchase_price_original),
          purchase_currency: currency,
          // Weight, customs_code, MOQ, dimensions, manufacturer fields —
          // edited inline in the handsontable after the split lands.
          weight_in_kg: null,
          customs_code: null,
        }))
      );
      toast.success(`Позиция разделена на ${children.length} ${children.length === 2 ? "части" : "частей"}`);
      onClose();
      router.refresh();
    } catch (err) {
      console.error("[split-inline-dialog] submit failed:", err);
      toast.error(extractErrorMessage(err) ?? "Не удалось разделить позицию");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = !submitting && isSplitFormValid(children);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && handleClose()}>
      <DialogContent className="sm:max-w-xl z-[200]" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Разделить позицию</DialogTitle>
          <DialogDescription>
            «{sourceProductName}» ({sourceQuantity} шт.). Добавьте сколько
            угодно частей; коэффициент — сколько штук дочерней позиции
            приходится на 1 штуку исходной. Остальные поля (вес, габариты,
            артикул производителя и т. д.) заполните прямо в таблице после
            разделения.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label className="text-xs text-muted-foreground">
              Частей: {children.length}
            </Label>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={addChild}
            >
              <Plus size={14} />
              Добавить часть
            </Button>
          </div>

          <div className="space-y-2">
            {children.map((child, idx) => {
              const ratio = parseFloat(child.quantity_ratio);
              const computedQty = computeChildQuantity(sourceQuantity, ratio);
              return (
                <div
                  key={idx}
                  className="rounded-md border border-border bg-muted/20 p-3 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-muted-foreground">
                      Часть {idx + 1}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeChild(idx)}
                      disabled={children.length <= 2}
                      title="Удалить часть"
                    >
                      <Trash2 size={12} />
                    </Button>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="col-span-2 space-y-1">
                      <Label className="text-xs">
                        Наименование <span className="text-destructive">*</span>
                      </Label>
                      <Input
                        className="h-8 text-sm"
                        placeholder="Наименование"
                        value={child.product_name}
                        onChange={(e) => updateChild(idx, "product_name", e.target.value)}
                      />
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs">
                        Бренд <span className="text-destructive">*</span>
                      </Label>
                      <Input
                        className="h-8 text-sm"
                        placeholder="Бренд"
                        value={child.brand}
                        onChange={(e) => updateChild(idx, "brand", e.target.value)}
                      />
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs">
                        Артикул поставщика <span className="text-destructive">*</span>
                      </Label>
                      <Input
                        className="h-8 text-sm"
                        placeholder="Артикул"
                        value={child.supplier_sku}
                        onChange={(e) => updateChild(idx, "supplier_sku", e.target.value)}
                      />
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs">
                        Коэфф. (шт. на 1 шт.) <span className="text-destructive">*</span>
                      </Label>
                      <Input
                        type="number"
                        step="0.001"
                        min="0"
                        className="h-8 text-sm tabular-nums"
                        placeholder="1"
                        value={child.quantity_ratio}
                        onChange={(e) => updateChild(idx, "quantity_ratio", e.target.value)}
                      />
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs">Кол-во (расчёт)</Label>
                      <Input
                        readOnly
                        disabled
                        className="h-8 text-sm tabular-nums bg-muted"
                        value={ratio > 0 ? computedQty.toString() : "—"}
                      />
                    </div>

                    <div className="col-span-2 space-y-1">
                      <Label className="text-xs">
                        Цена закупки ({currency}) <span className="text-destructive">*</span>
                      </Label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        className="h-8 text-sm tabular-nums"
                        placeholder="0.00"
                        value={child.purchase_price_original}
                        onChange={(e) =>
                          updateChild(idx, "purchase_price_original", e.target.value)
                        }
                      />
                    </div>
                  </div>
                </div>
              );
            })}
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
            Разделить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function seedFromDefaults(
  defaults: SplitInlineDialogProps["defaults"]
): Partial<SplitChildFormState> {
  if (!defaults) return {};
  return {
    product_name: defaults.product_name ?? "",
    brand: defaults.brand ?? "",
    supplier_sku: defaults.supplier_sku ?? "",
    purchase_price_original:
      defaults.purchase_price_original != null
        ? defaults.purchase_price_original.toString()
        : "",
  };
}
