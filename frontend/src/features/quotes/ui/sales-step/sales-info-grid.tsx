import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import type { QuoteDetailRow } from "@/entities/quote/queries";

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "\u20AC",
  USD: "$",
  CNY: "\u00A5",
  RUB: "\u20BD",
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

interface SalesInfoGridProps {
  quote: QuoteDetailRow;
}

export function SalesInfoGrid({ quote }: SalesInfoGridProps) {
  const currency = quote.currency ?? "USD";
  const profit = quote.profit_quote_currency ?? null;
  const revenue = quote.revenue_no_vat_quote_currency ?? null;
  const cogs = quote.cogs_quote_currency ?? null;

  // Compute margin and markup from available columns
  const marginPercent =
    profit != null && revenue != null && revenue !== 0
      ? (profit / revenue) * 100
      : null;
  const markupPercent =
    profit != null && cogs != null && cogs !== 0
      ? (profit / cogs) * 100
      : null;

  return (
    <Card>
      <CardContent className="py-4 px-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Column 1: Customer */}
          <div className="space-y-3">
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Клиент
            </h4>
            <InfoRow label="Клиент">
              {quote.customer ? (
                <Link
                  href={`/customers/${quote.customer.id}`}
                  className="text-sm font-medium text-accent hover:underline"
                >
                  {quote.customer.name}
                </Link>
              ) : (
                <span className="text-sm text-muted-foreground">{"\u2014"}</span>
              )}
            </InfoRow>
            <InfoRow label="Контакт">
              <span className="text-sm font-medium">
                {quote.contact_person?.name ?? "\u2014"}
              </span>
            </InfoRow>
            <InfoRow label="Город доставки">
              <span className="text-sm font-medium">
                {quote.delivery_city ?? "\u2014"}
              </span>
            </InfoRow>
          </div>

          {/* Column 2: Terms */}
          <div className="space-y-3">
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Условия
            </h4>
            <InfoRow label="Валюта">
              <span className="text-sm font-medium">{currency}</span>
            </InfoRow>
            <InfoRow label="Способ доставки">
              <span className="text-sm font-medium">
                {quote.delivery_method ?? "\u2014"}
              </span>
            </InfoRow>
            <InfoRow label="Оплата">
              <span className="text-sm font-medium">
                {quote.payment_terms ?? "\u2014"}
              </span>
            </InfoRow>
          </div>

          {/* Column 3: Financials */}
          <div className="space-y-3">
            <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Финансы
            </h4>
            <InfoRow label="Прибыль">
              <span className="text-sm font-medium">
                {formatMoney(profit, currency)}
              </span>
            </InfoRow>
            <InfoRow label="Маржа">
              <span className="text-sm font-medium">
                {formatPercent(marginPercent)}
              </span>
            </InfoRow>
            <InfoRow label="Наценка">
              <span className="text-sm font-medium">
                {formatPercent(markupPercent)}
              </span>
            </InfoRow>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function InfoRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      {children}
    </div>
  );
}
