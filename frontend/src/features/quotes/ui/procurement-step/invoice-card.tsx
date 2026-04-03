"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Paperclip, Undo2, Loader2, Trash2, Package } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProcurementItemsEditor } from "./procurement-items-editor";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";
import { deleteInvoice, fetchCargoPlaces } from "@/entities/quote/mutations";

type InvoiceExtras = {
  invoice_file_url?: string | null;
};

function ext<T>(row: unknown): T {
  return row as T;
}

const numberFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const INVOICE_STATUS_LABELS: Record<string, string> = {
  pending_procurement: "Ожидает закупки",
  pending_logistics: "Ожидает логистики",
  pending_customs: "Ожидает таможни",
  completed: "Завершён",
};

interface InvoiceCardProps {
  invoice: QuoteInvoiceRow;
  items: QuoteItemRow[];
  defaultExpanded?: boolean;
  procurementCompleted: boolean;
}

export function InvoiceCard({
  invoice,
  items,
  defaultExpanded = false,
  procurementCompleted,
}: InvoiceCardProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [unassigning, setUnassigning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [cargoPlaces, setCargoPlaces] = useState<
    Array<{ position: number; weight_kg: number; length_mm: number; width_mm: number; height_mm: number }>
  >([]);
  const isEmpty = items.length === 0;

  useEffect(() => {
    fetchCargoPlaces(invoice.id).then(setCargoPlaces);
  }, [invoice.id]);

  const supplierName =
    (invoice.supplier as { name: string } | null)?.name ?? "\u2014";
  const buyerName =
    (invoice.buyer_company as { name: string; company_code: string } | null)?.name ?? null;
  const pickupCity = invoice.pickup_city ?? null;
  const totalAmount = items.reduce((sum, item) => {
    const price = item.purchase_price_original ?? 0;
    return sum + price * item.quantity;
  }, 0);
  const currency = invoice.currency ?? "USD";
  const hasFile = ext<InvoiceExtras>(invoice).invoice_file_url != null;

  const cargoWeight = cargoPlaces.reduce((sum, cp) => sum + cp.weight_kg, 0);
  const cargoVolume = cargoPlaces.reduce(
    (sum, cp) => sum + (cp.length_mm * cp.width_mm * cp.height_mm) / 1e9,
    0
  );
  const hasCargoPlaces = cargoPlaces.length > 0;

  async function handleUnassignAll() {
    setUnassigning(true);
    try {
      // Set invoice_id to null for all items in this invoice
      const supabase = (await import("@/shared/lib/supabase/client")).createClient();
      const { error } = await supabase
        .from("quote_items")
        .update({ invoice_id: null })
        .in("id", items.map((i) => i.id));
      if (error) throw error;
      toast.success(`${items.length} поз. возвращены в нераспределённые`);
      router.refresh();
    } catch {
      toast.error("Не удалось убрать позиции из инвойса");
    } finally {
      setUnassigning(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteInvoice(invoice.id);
      toast.success(`Инвойс ${invoice.invoice_number} удалён`);
      router.refresh();
    } catch {
      toast.error("Не удалось удалить инвойс");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="flex-1 px-4 py-3 flex items-center gap-3 text-left hover:bg-muted/50 transition-colors"
        >
          {expanded ? (
            <ChevronDown size={16} className="shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight size={16} className="shrink-0 text-muted-foreground" />
          )}

          <span className="font-medium text-sm truncate">
            {invoice.invoice_number}
          </span>

          <span className="text-sm text-muted-foreground truncate">
            {supplierName}
          </span>

          {buyerName && (
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
              → {buyerName}
            </span>
          )}

          {pickupCity && (
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
              {pickupCity}
            </span>
          )}

          {hasCargoPlaces && (
            <span className="text-xs text-muted-foreground tabular-nums shrink-0 hidden sm:inline">
              {cargoPlaces.length} мест &middot; {numberFmt.format(cargoWeight)} кг &middot; {cargoVolume.toFixed(2)} м&sup3;
            </span>
          )}

          <Badge variant="secondary" className="ml-auto shrink-0">
            {items.length} поз.
          </Badge>

          <span className="text-sm font-mono tabular-nums shrink-0">
            {numberFmt.format(totalAmount)} {currency}
          </span>

          {invoice.status && (
            <Badge variant="outline" className="shrink-0">
              {INVOICE_STATUS_LABELS[invoice.status] ?? invoice.status}
            </Badge>
          )}

          {hasFile && (
            <Paperclip size={14} className="shrink-0 text-muted-foreground" />
          )}
        </button>

        {isEmpty ? (
          <Button
            variant="ghost"
            size="sm"
            className="mr-2 text-muted-foreground hover:text-destructive"
            onClick={handleDelete}
            disabled={deleting}
            title="Удалить пустой инвойс"
          >
            {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="mr-2 text-muted-foreground hover:text-destructive"
            onClick={handleUnassignAll}
            disabled={unassigning}
            title="Вернуть все позиции в нераспределённые"
          >
            {unassigning ? <Loader2 size={14} className="animate-spin" /> : <Undo2 size={14} />}
          </Button>
        )}
      </div>

      {expanded && (
        <div className="border-t border-border">
          {hasCargoPlaces && (
            <div className="px-4 py-2 bg-muted/30 border-b border-border">
              <div className="flex items-center gap-2 mb-1">
                <Package size={14} className="text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">
                  Грузовые места ({cargoPlaces.length})
                </span>
              </div>
              <div className="space-y-0.5">
                {cargoPlaces.map((cp) => (
                  <div key={cp.position} className="text-xs text-muted-foreground tabular-nums">
                    Место {cp.position}: {numberFmt.format(cp.weight_kg)} кг, {cp.length_mm}&times;{cp.width_mm}&times;{cp.height_mm} мм
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="overflow-x-auto">
            <ProcurementItemsEditor items={items} invoiceId={invoice.id} invoiceCurrency={currency} procurementCompleted={procurementCompleted} />
          </div>
        </div>
      )}
    </Card>
  );
}
