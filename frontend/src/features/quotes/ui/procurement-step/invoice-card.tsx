"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Download, Loader2, Mail, Package, Paperclip, Trash2, Undo2, Weight } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ProcurementItemsEditor } from "./procurement-items-editor";
import { SendHistoryPanel } from "./send-history-panel";
import { EditApprovalButton } from "./edit-approval-button";
import { LetterDraftComposer } from "./letter-draft-composer";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";
import { deleteInvoice, fetchCargoPlaces } from "@/entities/quote/mutations";
import { downloadInvoiceXls } from "@/entities/invoice/mutations";
import { findCountryByCode } from "@/shared/ui/geo";

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
  userRoles?: string[];
}

export function InvoiceCard({
  invoice,
  items,
  defaultExpanded = false,
  procurementCompleted,
  userRoles = [],
}: InvoiceCardProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [unassigning, setUnassigning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [downloadingXls, setDownloadingXls] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [cargoPlaces, setCargoPlaces] = useState<
    Array<{ position: number; weight_kg: number; length_mm: number; width_mm: number; height_mm: number }>
  >([]);
  const [weightKg, setWeightKg] = useState(invoice.total_weight_kg?.toString() ?? "");
  const [volumeM3, setVolumeM3] = useState(invoice.total_volume_m3?.toString() ?? "");
  const isEmpty = items.length === 0;
  const isSent = invoice.sent_at != null;
  const canSend =
    items.length > 0 &&
    (userRoles.includes("admin") ||
      userRoles.includes("procurement") ||
      userRoles.includes("head_of_procurement") ||
      userRoles.includes("procurement_senior"));

  useEffect(() => {
    fetchCargoPlaces(invoice.id).then(setCargoPlaces);
  }, [invoice.id]);

  const supplierName =
    (invoice.supplier as { name: string } | null)?.name ?? "\u2014";
  const buyerName =
    (invoice.buyer_company as { name: string; company_code: string } | null)?.name ?? null;
  const pickupCity = invoice.pickup_city ?? null;
  const pickupCountryCode = invoice.pickup_country_code ?? null;
  const pickupCountryRu = pickupCountryCode
    ? findCountryByCode(pickupCountryCode)?.nameRu ?? null
    : null;
  const pickupLocationLabel =
    pickupCity && pickupCountryRu && pickupCountryCode
      ? `${pickupCity}, ${pickupCountryRu} (${pickupCountryCode})`
      : pickupCity ??
        (pickupCountryRu && pickupCountryCode
          ? `${pickupCountryRu} (${pickupCountryCode})`
          : null);
  const supplierIncoterms = invoice.supplier_incoterms ?? null;
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

  const hasInvoiceWeight = invoice.total_weight_kg != null || invoice.total_volume_m3 != null;

  async function handleSaveField(field: "total_weight_kg" | "total_volume_m3", raw: string) {
    const value = raw.trim() === "" ? null : Number(raw);
    if (value !== null && isNaN(value)) return;
    try {
      const supabase = (await import("@/shared/lib/supabase/client")).createClient();
      const { error } = await supabase
        .from("invoices")
        .update({ [field]: value })
        .eq("id", invoice.id);
      if (error) throw error;
      toast.success("Сохранено");
      router.refresh();
    } catch {
      toast.error("Не удалось сохранить");
    }
  }

  async function handleDownloadXls() {
    setDownloadingXls(true);
    try {
      await downloadInvoiceXls(invoice.id);
      toast.success("XLS скачан");
      router.refresh();
    } catch {
      toast.error("Не удалось скачать XLS");
    } finally {
      setDownloadingXls(false);
    }
  }

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
      toast.error("Не удалось убрать позиции из КП");
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
      toast.error("Не удалось удалить КП");
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

          {pickupLocationLabel && (
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
              {pickupLocationLabel}
            </span>
          )}

          {supplierIncoterms && (
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
              Условия: {supplierIncoterms}
            </span>
          )}

          {hasInvoiceWeight && (
            <span className="text-xs text-muted-foreground tabular-nums shrink-0 hidden sm:inline">
              {invoice.total_weight_kg != null && <>{numberFmt.format(invoice.total_weight_kg)}&nbsp;кг</>}
              {invoice.total_weight_kg != null && invoice.total_volume_m3 != null && " · "}
              {invoice.total_volume_m3 != null && <>{numberFmt.format(invoice.total_volume_m3)}&nbsp;м&sup3;</>}
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

          {isSent && (
            <Badge variant="default" className="shrink-0 text-xs bg-green-600">
              Отправлено {new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" }).format(new Date(invoice.sent_at!))}
            </Badge>
          )}

          {hasFile && (
            <Paperclip size={14} className="shrink-0 text-muted-foreground" />
          )}
        </button>

        {isSent ? (
          <div className="mr-2">
            <EditApprovalButton invoiceId={invoice.id} />
          </div>
        ) : isEmpty ? (
          <Button
            variant="ghost"
            size="sm"
            className="mr-2 text-muted-foreground hover:text-destructive"
            onClick={handleDelete}
            disabled={deleting}
            title="Удалить пустое КП поставщику"
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
          {!procurementCompleted ? (
            <div className="px-4 py-2 bg-muted/30 border-b border-border">
              <div className="flex items-center gap-2 mb-1">
                <Weight size={14} className="text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">
                  Вес и габариты
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="Вес"
                    value={weightKg}
                    onChange={(e) => setWeightKg(e.target.value)}
                    onBlur={() => handleSaveField("total_weight_kg", weightKg)}
                    className="h-7 w-24 text-xs tabular-nums"
                  />
                  <span className="text-xs text-muted-foreground">кг</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="Объём"
                    value={volumeM3}
                    onChange={(e) => setVolumeM3(e.target.value)}
                    onBlur={() => handleSaveField("total_volume_m3", volumeM3)}
                    className="h-7 w-24 text-xs tabular-nums"
                  />
                  <span className="text-xs text-muted-foreground">м³</span>
                </div>
              </div>
            </div>
          ) : hasInvoiceWeight ? (
            <div className="px-4 py-2 bg-muted/30 border-b border-border">
              <div className="flex items-center gap-2">
                <Weight size={14} className="text-muted-foreground" />
                <span className="text-xs text-muted-foreground tabular-nums">
                  {invoice.total_weight_kg != null && <>{numberFmt.format(invoice.total_weight_kg)} кг</>}
                  {invoice.total_weight_kg != null && invoice.total_volume_m3 != null && " · "}
                  {invoice.total_volume_m3 != null && <>{numberFmt.format(invoice.total_volume_m3)} м³</>}
                </span>
              </div>
            </div>
          ) : null}
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
          {canSend && (
            <div className="px-4 py-2 bg-muted/30 border-b border-border">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={handleDownloadXls}
                  disabled={downloadingXls}
                >
                  {downloadingXls ? (
                    <Loader2 size={14} className="animate-spin mr-1" />
                  ) : (
                    <Download size={14} className="mr-1" />
                  )}
                  Скачать XLS
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => setComposerOpen(true)}
                >
                  <Mail size={14} className="mr-1" />
                  Подготовить письмо
                </Button>
              </div>
            </div>
          )}

          <SendHistoryPanel invoiceId={invoice.id} />

          <div className="overflow-x-auto">
            <ProcurementItemsEditor items={items} invoiceId={invoice.id} procurementCompleted={procurementCompleted} />
          </div>
        </div>
      )}

      <LetterDraftComposer
        open={composerOpen}
        onClose={() => {
          setComposerOpen(false);
          router.refresh();
        }}
        invoiceId={invoice.id}
        supplierName={supplierName}
        supplierEmail={(invoice.supplier as { email?: string } | null)?.email ?? null}
        items={items}
        currency={currency}
        incoterms={supplierIncoterms}
        pickupCountry={pickupCountryRu}
      />
    </Card>
  );
}
