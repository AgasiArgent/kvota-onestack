"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  createQuoteItem,
  updateQuoteItem,
  deleteQuoteItem,
} from "@/entities/quote/mutations";
import type { QuoteItemRow } from "@/entities/quote/queries";

interface SalesItemsEditorProps {
  quoteId: string;
  items: QuoteItemRow[];
  currency: string;
}

export function SalesItemsEditor({
  quoteId,
  items,
  currency,
}: SalesItemsEditorProps) {
  const router = useRouter();
  const [adding, setAdding] = useState(false);

  async function handleAddRow() {
    setAdding(true);
    try {
      await createQuoteItem(quoteId, {
        product_name: "",
        quantity: 1,
      });
      router.refresh();
    } catch {
      toast.error("Не удалось добавить позицию");
    } finally {
      setAdding(false);
    }
  }

  async function handleDeleteRow(itemId: string) {
    try {
      await deleteQuoteItem(itemId);
      toast.success("Позиция удалена");
      router.refresh();
    } catch {
      toast.error("Не удалось удалить позицию");
    }
  }

  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10 text-center">#</TableHead>
            <TableHead className="w-28">Бренд</TableHead>
            <TableHead className="w-32">Артикул</TableHead>
            <TableHead>Наименование</TableHead>
            <TableHead className="w-20 text-right">Кол-во</TableHead>
            <TableHead className="w-16">Ед.</TableHead>
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item, idx) => (
            <EditableItemRow
              key={item.id}
              item={item}
              index={idx}
              onDelete={() => handleDeleteRow(item.id)}
            />
          ))}

          {items.length === 0 && (
            <TableRow>
              <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                Нет позиций. Нажмите &laquo;Добавить позицию&raquo; чтобы начать.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <div className="px-4 py-3 border-t border-border">
        <Button
          variant="outline"
          size="sm"
          onClick={handleAddRow}
          disabled={adding}
        >
          {adding ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Plus size={14} />
          )}
          Добавить позицию
        </Button>
      </div>
    </div>
  );
}

function EditableItemRow({
  item,
  index,
  onDelete,
}: {
  item: QuoteItemRow;
  index: number;
  onDelete: () => void;
}) {
  const router = useRouter();
  const [brand, setBrand] = useState(item.brand ?? "");
  const [sku, setSku] = useState(item.idn_sku ?? "");
  const [name, setName] = useState(item.product_name);
  const [quantity, setQuantity] = useState(String(item.quantity));
  const [unit, setUnit] = useState(item.unit ?? "");
  const [deleting, setDeleting] = useState(false);

  const saveField = useCallback(
    async (field: string, rawValue: string) => {
      let value: unknown;
      if (field === "quantity") {
        const parsed = parseFloat(rawValue);
        value = isNaN(parsed) || parsed <= 0 ? 1 : parsed;
      } else {
        value = rawValue || null;
      }

      try {
        await updateQuoteItem(item.id, { [field]: value });
        router.refresh();
      } catch {
        toast.error("Не удалось сохранить");
      }
    },
    [item.id, router]
  );

  async function handleDelete() {
    setDeleting(true);
    await onDelete();
    setDeleting(false);
  }

  const inputClass =
    "w-full h-7 px-1.5 text-sm border border-transparent rounded bg-transparent hover:border-border focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring/50";

  return (
    <TableRow>
      <TableCell className="text-center text-muted-foreground">
        {index + 1}
      </TableCell>
      <TableCell>
        <input
          type="text"
          className={inputClass}
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
          onBlur={() => saveField("brand", brand)}
          placeholder="Бренд"
        />
      </TableCell>
      <TableCell>
        <input
          type="text"
          className={`${inputClass} font-mono text-xs`}
          value={sku}
          onChange={(e) => setSku(e.target.value)}
          onBlur={() => saveField("idn_sku", sku)}
          placeholder="Артикул"
        />
      </TableCell>
      <TableCell>
        <input
          type="text"
          className={inputClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => saveField("product_name", name)}
          placeholder="Наименование"
        />
      </TableCell>
      <TableCell>
        <input
          type="number"
          step="0.01"
          min="0"
          className={`${inputClass} text-right font-mono [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none`}
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          onBlur={() => saveField("quantity", quantity)}
          placeholder="1"
        />
      </TableCell>
      <TableCell>
        <input
          type="text"
          className={`${inputClass} text-xs`}
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          onBlur={() => saveField("unit", unit)}
          placeholder="шт"
        />
      </TableCell>
      <TableCell>
        <button
          type="button"
          className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
          onClick={handleDelete}
          disabled={deleting}
          aria-label="Удалить позицию"
        >
          {deleting ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Trash2 size={14} />
          )}
        </button>
      </TableCell>
    </TableRow>
  );
}
