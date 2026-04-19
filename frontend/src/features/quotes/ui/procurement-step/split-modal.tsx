"use client";

import { useState } from "react";
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
import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies";
import { splitInvoiceItem } from "@/entities/quote/mutations";

/**
 * Phase 5c Task 12 — SplitModal.
 *
 * Decomposes one source quote_item (currently 1:1 covered in this invoice)
 * into N ≥ 2 invoice_items with individual ratios. The split is local to
 * the calling invoice: other invoices that cover the same quote_item are
 * left alone.
 *
 * Ratio semantics: `ratio = invoice_item_units per quote_item_unit`.
 * Display: «сколько штук этого на 1 штуку того».
 * Invariant: `invoice_item.quantity = source_quote_item.quantity × ratio`.
 */

export interface SplitQuoteItemCandidate {
  id: string;
  product_name: string;
  quantity: number;
}

export interface SplitChildFormState {
  product_name: string;
  supplier_sku: string;
  brand: string;
  quantity_ratio: string;
  purchase_price_original: string;
  purchase_currency: string;
  weight_in_kg: string;
  customs_code: string;
}

export interface SplitFormState {
  sourceQuoteItemId: string;
  children: SplitChildFormState[];
}

interface SplitModalProps {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  /** Source candidates = quote_items currently 1:1-covered in this invoice. */
  candidates: SplitQuoteItemCandidate[];
  /**
   * Currency inherited from the parent invoice. Pre-fills each child's
   * `purchase_currency` field.
   */
  defaultCurrency: string;
}

export function computeChildQuantity(
  sourceQuantity: number,
  ratio: number
): number {
  if (!Number.isFinite(ratio) || ratio <= 0) return 0;
  return sourceQuantity * ratio;
}

function isValidChild(child: SplitChildFormState): boolean {
  if (!child.product_name.trim()) return false;
  const ratio = parseFloat(child.quantity_ratio);
  if (!Number.isFinite(ratio) || ratio <= 0) return false;
  const price = parseFloat(child.purchase_price_original);
  if (!Number.isFinite(price) || price <= 0) return false;
  if (!child.purchase_currency) return false;
  return true;
}

export function isSplitFormValid(form: SplitFormState): boolean {
  if (!form.sourceQuoteItemId) return false;
  if (form.children.length < 2) return false;
  return form.children.every(isValidChild);
}

function makeEmptyChild(defaultCurrency: string): SplitChildFormState {
  return {
    product_name: "",
    supplier_sku: "",
    brand: "",
    quantity_ratio: "1",
    purchase_price_original: "",
    purchase_currency: defaultCurrency,
    weight_in_kg: "",
    customs_code: "",
  };
}

/**
 * Pure form body — extracted from SplitModal so it can be rendered without
 * a Dialog portal (the @base-ui/react Dialog uses a React Portal which is
 * omitted during SSR). Tests mount this body directly; production use
 * wraps it in a Dialog via SplitModal.
 *
 * Named `childRows` (not `children`) to avoid React's special prop name —
 * passing a non-React-node array as `children` trips the
 * `react/no-children-prop` lint rule.
 */
interface SplitModalBodyProps {
  candidates: SplitQuoteItemCandidate[];
  defaultCurrency: string;
  sourceQuoteItemId: string;
  onSourceChange: (id: string) => void;
  childRows: SplitChildFormState[];
  onChildUpdate: (
    idx: number,
    field: keyof SplitChildFormState,
    value: string
  ) => void;
  onAddChild: () => void;
  onRemoveChild: (idx: number) => void;
}

export function SplitModalBody({
  candidates,
  defaultCurrency,
  sourceQuoteItemId,
  onSourceChange,
  childRows,
  onChildUpdate,
  onAddChild,
  onRemoveChild,
}: SplitModalBodyProps) {
  void defaultCurrency; // per-child currency; parent seeds defaults.
  const source = candidates.find((c) => c.id === sourceQuoteItemId) ?? null;
  return (
    <div className="space-y-4 max-h-[60vh] overflow-y-auto">
      <div className="space-y-1.5">
        <Label>
          Исходная позиция заявки{" "}
          <span className="text-destructive">*</span>
        </Label>
        <select
          value={sourceQuoteItemId}
          onChange={(e) => onSourceChange(e.target.value)}
          className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
        >
          <option value="">Выберите позицию</option>
          {candidates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.product_name} ({c.quantity} шт.)
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Части ({childRows.length})</Label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-xs"
            onClick={onAddChild}
          >
            <Plus size={14} />
            Добавить часть
          </Button>
        </div>

        {childRows.map((child, idx) => {
          const ratio = parseFloat(child.quantity_ratio);
          const computedQty = source
            ? computeChildQuantity(source.quantity, ratio)
            : 0;
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
                  onClick={() => onRemoveChild(idx)}
                  disabled={childRows.length <= 2}
                  title="Удалить часть"
                >
                  <Trash2 size={12} />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="col-span-2 space-y-1">
                  <Label className="text-xs">
                    Наименование{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    className="h-8 text-sm"
                    placeholder="Наименование"
                    value={child.product_name}
                    onChange={(e) =>
                      onChildUpdate(idx, "product_name", e.target.value)
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Артикул поставщика</Label>
                  <Input
                    className="h-8 text-sm"
                    placeholder="Артикул"
                    value={child.supplier_sku}
                    onChange={(e) =>
                      onChildUpdate(idx, "supplier_sku", e.target.value)
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Бренд</Label>
                  <Input
                    className="h-8 text-sm"
                    placeholder="Бренд"
                    value={child.brand}
                    onChange={(e) =>
                      onChildUpdate(idx, "brand", e.target.value)
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">
                    Коэфф. (шт. на 1 шт.){" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    type="number"
                    step="0.001"
                    min="0"
                    className="h-8 text-sm tabular-nums"
                    placeholder="1"
                    value={child.quantity_ratio}
                    onChange={(e) =>
                      onChildUpdate(idx, "quantity_ratio", e.target.value)
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Кол-во (расчёт)</Label>
                  <Input
                    readOnly
                    disabled
                    className="h-8 text-sm tabular-nums bg-muted"
                    value={source ? computedQty.toString() : "—"}
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">
                    Цена закупки{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    className="h-8 text-sm tabular-nums"
                    placeholder="0.00"
                    value={child.purchase_price_original}
                    onChange={(e) =>
                      onChildUpdate(
                        idx,
                        "purchase_price_original",
                        e.target.value
                      )
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Валюта</Label>
                  <select
                    value={child.purchase_currency}
                    onChange={(e) =>
                      onChildUpdate(idx, "purchase_currency", e.target.value)
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
                    value={child.weight_in_kg}
                    onChange={(e) =>
                      onChildUpdate(idx, "weight_in_kg", e.target.value)
                    }
                  />
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Код ТНВЭД</Label>
                  <Input
                    className="h-8 text-sm"
                    placeholder="Код"
                    value={child.customs_code}
                    onChange={(e) =>
                      onChildUpdate(idx, "customs_code", e.target.value)
                    }
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function SplitModal({
  open,
  onClose,
  invoiceId,
  candidates,
  defaultCurrency,
}: SplitModalProps) {
  const router = useRouter();
  const [sourceQuoteItemId, setSourceQuoteItemId] = useState("");
  const [childrenState, setChildrenState] = useState<SplitChildFormState[]>(
    () => [makeEmptyChild(defaultCurrency), makeEmptyChild(defaultCurrency)]
  );
  const [submitting, setSubmitting] = useState(false);

  function resetForm() {
    setSourceQuoteItemId("");
    setChildrenState([
      makeEmptyChild(defaultCurrency),
      makeEmptyChild(defaultCurrency),
    ]);
  }

  function handleClose() {
    if (submitting) return;
    resetForm();
    onClose();
  }

  function updateChild(
    idx: number,
    field: keyof SplitChildFormState,
    value: string
  ) {
    setChildrenState((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, [field]: value } : c))
    );
  }

  function addChild() {
    setChildrenState((prev) => [...prev, makeEmptyChild(defaultCurrency)]);
  }

  function removeChild(idx: number) {
    setChildrenState((prev) =>
      prev.length <= 2 ? prev : prev.filter((_, i) => i !== idx)
    );
  }

  async function handleSubmit() {
    if (!isSplitFormValid({ sourceQuoteItemId, children: childrenState })) {
      return;
    }
    setSubmitting(true);
    try {
      await splitInvoiceItem(
        invoiceId,
        sourceQuoteItemId,
        childrenState.map((c) => ({
          product_name: c.product_name.trim(),
          supplier_sku: c.supplier_sku.trim() || null,
          brand: c.brand.trim() || null,
          quantity_ratio: parseFloat(c.quantity_ratio),
          purchase_price_original: parseFloat(c.purchase_price_original),
          purchase_currency: c.purchase_currency,
          weight_in_kg: c.weight_in_kg.trim()
            ? parseFloat(c.weight_in_kg)
            : null,
          customs_code: c.customs_code.trim() || null,
        }))
      );
      toast.success(`Позиция разделена на ${childrenState.length} частей`);
      resetForm();
      onClose();
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось разделить позицию"
      );
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    !submitting &&
    isSplitFormValid({ sourceQuoteItemId, children: childrenState });

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
          <DialogTitle>Разделить позицию</DialogTitle>
          <DialogDescription>
            Одна позиция заявки поставщика может поставлять несколько товаров
            из одной строки заявки покупателя. Укажите, сколько штук каждой
            части приходится на 1 штуку исходной позиции (коэффициент).
          </DialogDescription>
        </DialogHeader>

        <SplitModalBody
          candidates={candidates}
          defaultCurrency={defaultCurrency}
          sourceQuoteItemId={sourceQuoteItemId}
          onSourceChange={setSourceQuoteItemId}
          childRows={childrenState}
          onChildUpdate={updateChild}
          onAddChild={addChild}
          onRemoveChild={removeChild}
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
            Разделить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
