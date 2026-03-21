"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "\u20AC",
  USD: "$",
  CNY: "\u00A5",
  RUB: "\u20BD",
};

interface DealSummaryPanelProps {
  dealType: string | null;
  incoterms: string | null;
  currency: string;
  markup: number;
  itemCount: number;
  clientPrepayment: number | null;
  supplierAdvance: number | null;
  totalAmount: number | null;
  financingAmount: number | null;
  importVat: number | null;
}

const DEAL_TYPE_LABELS: Record<string, string> = {
  supply: "Поставка",
  transit: "Транзит",
};

function formatMoney(value: number | null, currency: string): string {
  if (value == null) return "\u2014";
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  return `${formatted} ${symbol}`;
}

function formatPercent(value: number | null): string {
  if (value == null) return "\u2014";
  return `${value.toFixed(1)}%`;
}

function display(value: string | number | null): string {
  if (value == null) return "\u2014";
  return String(value);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <span className="block text-xs text-muted-foreground">{label}</span>
      <span className="block text-sm font-semibold text-foreground">{children}</span>
    </div>
  );
}

export function DealSummaryPanel({
  dealType,
  incoterms,
  currency,
  markup,
  itemCount,
  clientPrepayment,
  supplierAdvance,
  totalAmount,
  financingAmount,
  importVat,
}: DealSummaryPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Параметры сделки</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="Тип сделки">
            {dealType ? (DEAL_TYPE_LABELS[dealType] ?? dealType) : "\u2014"}
          </Field>
          <Field label="Инкотермс">{display(incoterms)}</Field>
          <Field label="Валюта">{currency}</Field>
          <Field label="Наценка">{`${markup.toFixed(1)}%`}</Field>
          <Field label="Позиций">{itemCount}</Field>
          <Field label="Предоплата клиента">{formatPercent(clientPrepayment)}</Field>
          <Field label="Аванс поставщику">{formatPercent(supplierAdvance)}</Field>
          <Field label="Импортный НДС">{formatPercent(importVat)}</Field>
          <Field label="Сумма сделки">{formatMoney(totalAmount, currency)}</Field>
          <Field label="Финансирование">{formatMoney(financingAmount, currency)}</Field>
        </div>
      </CardContent>
    </Card>
  );
}
