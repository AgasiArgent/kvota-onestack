"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Save, ShieldCheck, MoreVertical, RefreshCw, FileText, FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { CurrencyInvoiceDetail, CompanyOption } from "@/entities/currency-invoice/types";
import {
  SEGMENT_COLORS,
  STATUS_LABELS,
  STATUS_COLORS,
  canManageCurrencyInvoices,
} from "@/entities/currency-invoice/types";
import { saveCurrencyInvoice, verifyCurrencyInvoice } from "@/entities/currency-invoice/mutations";

interface CIDetailProps {
  invoice: CurrencyInvoiceDetail;
  sellers: CompanyOption[];
  buyers: CompanyOption[];
  userRoles: string[];
  orgId: string;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatDecimal(value: number | null, decimals: number = 2): string {
  if (value === null || value === undefined) return "\u2014";
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

function formatCurrency(amount: number | null, currency: string): string {
  if (amount === null || amount === undefined) return "\u2014";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

const NONE_VALUE = "__none__";

export function CIDetail({ invoice, sellers, buyers, userRoles, orgId }: CIDetailProps) {
  const router = useRouter();
  const canManage = canManageCurrencyInvoices(userRoles);
  const isEditable = invoice.status === "draft";

  const [sellerEntityId, setSellerEntityId] = useState(invoice.seller_entity_id ?? "");
  const [buyerEntityId, setBuyerEntityId] = useState(invoice.buyer_entity_id ?? "");
  const [markupPercent, setMarkupPercent] = useState(String(invoice.markup_percent));
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const canVerify = isEditable && sellerEntityId && buyerEntityId;

  async function handleSave() {
    setSaving(true);
    try {
      const markup = parseFloat(markupPercent);
      const sellerOption = sellers.find((s) => s.id === sellerEntityId);
      const buyerOption = buyers.find((b) => b.id === buyerEntityId);
      await saveCurrencyInvoice(invoice.id, orgId, {
        seller_entity_type: sellerOption?.type ?? null,
        seller_entity_id: sellerEntityId || null,
        buyer_entity_type: buyerOption?.type ?? null,
        buyer_entity_id: buyerEntityId || null,
        markup_percent: isNaN(markup) ? invoice.markup_percent : markup,
      });
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  async function handleVerify() {
    if (!confirm("Подтвердить инвойс? После подтверждения редактирование будет невозможно.")) return;
    setVerifying(true);
    try {
      await verifyCurrencyInvoice(invoice.id, orgId);
      router.refresh();
    } finally {
      setVerifying(false);
    }
  }

  async function handleRegenerate() {
    if (!confirm("Пересоздать инвойс из источника? Текущие позиции будут заменены.")) return;
    setRegenerating(true);
    try {
      const res = await fetch(
        `https://kvotaflow.ru/currency-invoices/${invoice.id}/regenerate`,
        { method: "POST", credentials: "include" }
      );
      if (!res.ok) {
        throw new Error(`Regenerate failed: ${res.status}`);
      }
      router.refresh();
    } finally {
      setRegenerating(false);
    }
  }

  // Compute totals from items
  const totalBasePrice = invoice.items.reduce((sum, item) => sum + item.total, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{invoice.invoice_number}</h1>
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                SEGMENT_COLORS[invoice.segment] ?? "bg-slate-100 text-slate-700"
              }`}
            >
              {invoice.segment}
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                STATUS_COLORS[invoice.status] ?? "bg-slate-100 text-slate-700"
              }`}
            >
              {STATUS_LABELS[invoice.status] ?? invoice.status}
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>{formatDate(invoice.created_at)}</span>
            <span>{invoice.currency}</span>
            {invoice.quote_idn && <span>КП: {invoice.quote_idn}</span>}
            {invoice.customer_name && <span>Клиент: {invoice.customer_name}</span>}
          </div>
        </div>
        {invoice.deal_number && (
          <Link
            href={`https://kvotaflow.ru/deals/${invoice.deal_id}`}
            className="text-sm text-accent hover:underline flex items-center gap-1 shrink-0"
          >
            <ArrowLeft size={14} />
            Сделка {invoice.deal_number}
          </Link>
        )}
      </div>

      {/* Company selectors + Markup */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-muted/30 rounded-lg border">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Продавец</label>
          <Select
            value={sellerEntityId || NONE_VALUE}
            onValueChange={(v) => setSellerEntityId(!v || v === NONE_VALUE ? "" : v)}
            disabled={!isEditable}
          >
            <SelectTrigger>
              <span className="truncate">
                {sellerEntityId ? (sellers.find((s) => s.id === sellerEntityId)?.name ?? "Выберите продавца") : "Не выбрано"}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>Не выбрано</SelectItem>
              {sellers.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Покупатель</label>
          <Select
            value={buyerEntityId || NONE_VALUE}
            onValueChange={(v) => setBuyerEntityId(!v || v === NONE_VALUE ? "" : v)}
            disabled={!isEditable}
          >
            <SelectTrigger>
              <span className="truncate">
                {buyerEntityId ? (buyers.find((b) => b.id === buyerEntityId)?.name ?? "Выберите покупателя") : "Не выбрано"}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>Не выбрано</SelectItem>
              {buyers.map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Наценка, %</label>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              step="0.01"
              min="0"
              max="100"
              value={markupPercent}
              onChange={(e) => setMarkupPercent(e.target.value)}
              disabled={!isEditable}
              className="w-24"
            />
            <span className="text-xs text-muted-foreground">
              Пересчёт цен при сохранении
            </span>
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        {isEditable && (
          <>
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              <Save size={16} className="mr-1.5" />
              {saving ? "Сохранение..." : "Сохранить"}
            </Button>
            <Button
              variant="outline"
              onClick={handleVerify}
              disabled={verifying || !canVerify}
              title={!canVerify ? "Выберите продавца и покупателя" : ""}
            >
              <ShieldCheck size={16} className="mr-1.5" />
              {verifying ? "Подтверждение..." : "Подтвердить"}
            </Button>
          </>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="outline" size="icon" />}
          >
            <MoreVertical size={16} />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-[220px]">
            {canManage && (
              <DropdownMenuItem
                onClick={handleRegenerate}
                disabled={regenerating}
              >
                <RefreshCw size={14} className="mr-2" />
                {regenerating ? "Пересоздание..." : "Пересоздать из источника"}
              </DropdownMenuItem>
            )}
            <DropdownMenuItem
              render={
                <a
                  href={`https://kvotaflow.ru/currency-invoices/${invoice.id}/download-docx`}
                  target="_blank"
                  rel="noopener noreferrer"
                />
              }
            >
              <FileText size={14} className="mr-2" />
              Экспорт DOCX
            </DropdownMenuItem>
            <DropdownMenuItem
              render={
                <a
                  href={`https://kvotaflow.ru/currency-invoices/${invoice.id}/download-pdf`}
                  target="_blank"
                  rel="noopener noreferrer"
                />
              }
            >
              <FileDown size={14} className="mr-2" />
              Экспорт PDF
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Positions table */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Позиции</h2>
        <div className="border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40px] text-center">#</TableHead>
                <TableHead className="min-w-[200px]">Наименование</TableHead>
                <TableHead className="w-[100px]">SKU</TableHead>
                <TableHead className="w-[100px]">IDN-SKU</TableHead>
                <TableHead className="w-[120px]">Производитель</TableHead>
                <TableHead className="w-[70px] text-right">Кол-во</TableHead>
                <TableHead className="w-[50px]">Ед.</TableHead>
                <TableHead className="w-[90px]">HS Code</TableHead>
                <TableHead className="w-[100px] text-right">Баз. цена</TableHead>
                <TableHead className="w-[100px] text-right">Цена</TableHead>
                <TableHead className="w-[110px] text-right">Итого</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoice.items.map((item, idx) => (
                <TableRow key={item.id}>
                  <TableCell className="text-center text-muted-foreground tabular-nums">
                    {idx + 1}
                  </TableCell>
                  <TableCell className="font-medium" title={item.product_name}>
                    {item.product_name}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs" title={item.sku ?? ""}>
                    {item.sku ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs" title={item.idn_sku ?? ""}>
                    {item.idn_sku ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs truncate" title={item.manufacturer ?? ""}>
                    {item.manufacturer ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatDecimal(item.quantity, 0)}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">
                    {item.unit ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">
                    {item.hs_code ?? "\u2014"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatDecimal(item.base_price)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatDecimal(item.price)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums font-medium">
                    {formatDecimal(item.total)}
                  </TableCell>
                </TableRow>
              ))}
              {invoice.items.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={11}
                    className="text-center py-8 text-muted-foreground"
                  >
                    Нет позиций
                  </TableCell>
                </TableRow>
              )}
              {/* Total row */}
              {invoice.items.length > 0 && (
                <TableRow className="bg-muted/30 font-semibold">
                  <TableCell colSpan={10} className="text-right">
                    Итого:
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatCurrency(totalBasePrice, invoice.currency)}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
