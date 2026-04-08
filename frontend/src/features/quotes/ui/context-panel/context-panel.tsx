"use client";

import Link from "next/link";
import { User, Package, TrendingUp } from "lucide-react";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import { SalesChecklistBlock } from "./sales-checklist-block";
import { ParticipantsBlock } from "./participants-block";
import { ContactDropdownSelect } from "./contact-dropdown-select";
import { AddressDropdownSelect } from "./address-dropdown-select";
import { DeliveryPrioritySelect } from "./delivery-priority-select";
import type { QuoteContextData } from "./queries";

const DELIVERY_METHOD_LABELS: Record<string, string> = {
  air: "Авиа",
  auto: "Авто",
  sea: "Море",
  multimodal: "Любой",
};

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

interface ContextPanelProps {
  quote: QuoteDetailRow;
  data: QuoteContextData;
}

export function ContextPanel({ quote, data }: ContextPanelProps) {
  return (
    <div className="mx-6 mt-3 mb-1 rounded-lg border border-border bg-muted/30 p-4">
      <QuoteInfoBlock quote={quote} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SalesChecklistBlock
          checklist={data.salesChecklist}
          contactPerson={data.contactPerson}
          salesManager={data.salesManager}
          additionalInfo={quote.additional_info ?? null}
        />
        <ParticipantsBlock participants={data.participants} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quote info summary block (Client / Terms / Financials)
// ---------------------------------------------------------------------------

function QuoteInfoBlock({ quote }: { quote: QuoteDetailRow }) {
  const currency = quote.currency ?? "USD";
  const profit = quote.profit_quote_currency ?? null;
  const revenue = quote.revenue_no_vat_quote_currency ?? null;
  const cogs = quote.cogs_quote_currency ?? null;

  const marginPercent =
    profit != null && revenue != null && revenue !== 0
      ? (profit / revenue) * 100
      : null;
  const markupPercent =
    profit != null && cogs != null && cogs !== 0
      ? (profit / cogs) * 100
      : null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pb-4 mb-4 border-b border-border">
      {/* Client */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 mb-2">
          <User size={14} className="text-muted-foreground" />
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Клиент
          </h4>
        </div>
        <InfoRow label="Клиент" dataField="customer_id">
          {quote.customer ? (
            <Link
              href={`/customers/${quote.customer.id}`}
              className="text-sm font-medium text-accent hover:underline truncate"
            >
              {quote.customer.name}
            </Link>
          ) : (
            <span className="text-sm text-muted-foreground">{"\u2014"}</span>
          )}
        </InfoRow>
        <InfoRow label="Контакт">
          {quote.customer ? (
            <ContactDropdownSelect
              quoteId={quote.id}
              customerId={quote.customer.id}
              initialContact={
                quote.contact_person
                  ? { id: quote.contact_person.id, name: quote.contact_person.name }
                  : null
              }
            />
          ) : (
            <span className="text-sm text-muted-foreground">{"\u2014"}</span>
          )}
        </InfoRow>
        <InfoRow label="Город доставки" dataField="delivery_city">
          <span className="text-sm font-medium">
            {quote.delivery_city ?? "\u2014"}
          </span>
        </InfoRow>
        <InfoRow label="Адрес доставки">
          {quote.customer ? (
            <AddressDropdownSelect
              quoteId={quote.id}
              customerId={quote.customer.id}
              initialAddress={quote.delivery_address ?? null}
            />
          ) : (
            <span className="text-sm text-muted-foreground">{"\u2014"}</span>
          )}
        </InfoRow>
      </div>

      {/* Terms */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 mb-2">
          <Package size={14} className="text-muted-foreground" />
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Условия
          </h4>
        </div>
        <InfoRow label="Валюта">
          <span className="text-sm font-medium">{currency}</span>
        </InfoRow>
        <InfoRow label="Доставка" dataField="delivery_method">
          <span className="text-sm font-medium flex items-center gap-1">
            {DELIVERY_METHOD_LABELS[quote.delivery_method ?? ""] ?? quote.delivery_method ?? "\u2014"}
            {quote.incoterms && (
              <>
                {" \u00B7 "}{quote.incoterms}
              </>
            )}
            {" \u00B7 "}
            <DeliveryPrioritySelect
              quoteId={quote.id}
              initialValue={quote.delivery_priority ?? null}
            />
          </span>
        </InfoRow>
        <InfoRow label="Оплата">
          <span className="text-sm font-medium">
            {quote.payment_terms ?? "\u2014"}
          </span>
        </InfoRow>
        <InfoRow label="Дедлайн КП">
          <span className="text-sm font-medium">
            {quote.valid_until
              ? new Date(quote.valid_until).toLocaleDateString("ru-RU")
              : "\u2014"}
          </span>
        </InfoRow>
      </div>

      {/* Financials */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp size={14} className="text-muted-foreground" />
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Финансы
          </h4>
        </div>
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
  );
}

function InfoRow({
  label,
  children,
  dataField,
}: {
  label: string;
  children: React.ReactNode;
  dataField?: string;
}) {
  return (
    <div
      className="flex justify-between items-baseline gap-2 rounded px-1 -mx-1 transition-colors duration-300"
      {...(dataField ? { "data-field": dataField } : {})}
    >
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      {children}
    </div>
  );
}
