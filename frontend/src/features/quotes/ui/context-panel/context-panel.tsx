"use client";

import Link from "next/link";
import { User, Package, TrendingUp, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import { ContactDropdownSelect } from "./contact-dropdown-select";
import { AddressDropdownSelect } from "./address-dropdown-select";
import type { ParticipantRow } from "./participants-block";
import { ROLE_LABELS_RU } from "@/entities/user/types";
import type { QuoteContextData } from "./queries";

const DELIVERY_METHOD_LABELS: Record<string, string> = {
  air: "Авиа",
  auto: "Авто",
  sea: "Море",
  multimodal: "Любой",
};

const PRIORITY_LABELS: Record<string, string> = {
  fast: "Быстрее",
  normal: "Обычно",
  cheap: "Дешевле",
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
      <QuoteInfoBlock
        quote={quote}
        salesManager={data.salesManager}
        participants={data.participants}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quote info summary block (Client / Terms / Financials)
// ---------------------------------------------------------------------------

function QuoteInfoBlock({
  quote,
  salesManager,
  participants,
}: {
  quote: QuoteDetailRow;
  salesManager: QuoteContextData["salesManager"];
  participants: ParticipantRow[];
}) {
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
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* Client */}
      <div className="space-y-2 min-w-0">
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
          <span className="block truncate text-sm font-medium">
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
      <div className="space-y-2 min-w-0">
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
          <span className="text-sm font-medium truncate">
            {DELIVERY_METHOD_LABELS[quote.delivery_method ?? ""] ?? quote.delivery_method ?? "\u2014"}
            {quote.incoterms && <>{" \u00B7 "}{quote.incoterms}</>}
          </span>
        </InfoRow>
        <InfoRow label="Приоритет">
          <span className="text-sm font-medium">
            {PRIORITY_LABELS[quote.delivery_priority ?? ""] ?? "\u2014"}
          </span>
        </InfoRow>
        <InfoRow label="Оплата">
          <span className="block truncate text-sm font-medium">
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

      {/* Participants */}
      <div className="space-y-2 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <Users size={14} className="text-muted-foreground" />
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Участники
          </h4>
        </div>
        {salesManager && (
          <div className="flex items-baseline gap-1.5 text-sm">
            <span className="text-xs text-muted-foreground shrink-0">МОП</span>
            <span className="font-medium truncate">{salesManager.full_name}</span>
          </div>
        )}
        {participants.length > 0 ? (
          <ul className="space-y-1.5 max-h-32 overflow-y-auto">
            {participants.map((p) => (
              <li key={p.id} className="text-sm text-muted-foreground truncate">
                <span className="tabular-nums">
                  {formatParticipantDate(p.created_at)}
                </span>
                {" "}
                <span className="text-foreground">{p.actor_name}</span>
                {" "}
                <Badge variant="outline" className="text-[10px] h-4 px-1 align-middle">
                  {ROLE_LABELS_RU[p.actor_role] ?? p.actor_role}
                </Badge>
              </li>
            ))}
          </ul>
        ) : (
          !salesManager && (
            <p className="text-sm text-muted-foreground">Нет участников</p>
          )
        )}
      </div>
    </div>
  );
}

function formatParticipantDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  const d = new Date(dateStr);
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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
      className="flex justify-between items-baseline gap-2 rounded px-1 -mx-1 transition-colors duration-300 min-w-0"
      {...(dataField ? { "data-field": dataField } : {})}
    >
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      {/*
        NOTE: do NOT apply blanket truncate (e.g. `[&>*]:truncate`) here.
        truncate sets `overflow:hidden` on the child, which clips
        absolutely-positioned popovers (contact / address dropdowns) to a
        ~30px sliver — see FB-260413-094409-0e1f. Each child is responsible
        for its own truncation; long text values use `truncate` directly.
      */}
      <span className="min-w-0">{children}</span>
    </div>
  );
}
