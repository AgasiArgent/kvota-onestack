"use client";

import Link from "next/link";
import { User, Package, TrendingUp, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import { ContactDropdownSelect } from "./contact-dropdown-select";
import { AddressDropdownSelect } from "./address-dropdown-select";
import {
  SalesChecklistBlock,
  hasSalesChecklistContent,
} from "./sales-checklist-block";
import type { ParticipantRow } from "./participants-block";
import { ROLE_LABELS_RU } from "@/entities/user/types";
import { canEditQuoteCustomerFields, canViewQuoteFinancials } from "@/shared/lib/roles";
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
  userRoles: string[];
}

export function ContextPanel({ quote, data, userRoles }: ContextPanelProps) {
  const showFinancials = canViewQuoteFinancials(userRoles);
  const canEditCustomerFields = canEditQuoteCustomerFields(userRoles);
  const showSalesChecklist = hasSalesChecklistContent(data.salesChecklist);
  return (
    <div className="mx-6 mt-3 mb-1 rounded-lg border border-border bg-muted/30 p-4">
      <QuoteInfoBlock
        quote={quote}
        salesManager={data.salesManager}
        participants={data.participants}
        procurementAssignees={data.procurementAssignees}
        logisticsAssignees={data.logisticsAssignees}
        customsAssignees={data.customsAssignees}
        showFinancials={showFinancials}
        canEditCustomerFields={canEditCustomerFields}
      />
      {/* Testing 2 row 29 (FB-260514-220805-be23): МОП's «Контрольный список»
          (проценка / тендер / прямой / через торгующих + equipment description)
          is captured at hand-off but was invisible on procurement+ steps. The
          fetch in queries.ts already loads it; this block surfaces it for
          every role that can read the quote past Заявка. Hidden entirely when
          the checklist carries no content (legacy quotes / quotes that
          skipped the dialog). */}
      {showSalesChecklist && (
        <div className="mt-4 pt-4 border-t border-border">
          <SalesChecklistBlock checklist={data.salesChecklist} />
        </div>
      )}
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
  procurementAssignees,
  logisticsAssignees,
  customsAssignees,
  showFinancials,
  canEditCustomerFields,
}: {
  quote: QuoteDetailRow;
  salesManager: QuoteContextData["salesManager"];
  participants: ParticipantRow[];
  procurementAssignees: QuoteContextData["procurementAssignees"];
  logisticsAssignees: QuoteContextData["logisticsAssignees"];
  customsAssignees: QuoteContextData["customsAssignees"];
  showFinancials: boolean;
  canEditCustomerFields: boolean;
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

  // When financials are hidden (procurement / logistics / customs roles), the
  // grid collapses from 4 to 3 columns so the remaining sections fill the
  // panel evenly instead of leaving a blank slot. МОЗ-60.
  const gridClass = showFinancials
    ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
    : "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6";

  return (
    <div className={gridClass}>
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
        <InfoRow label="Контакт" dataField="contact_person_id">
          {quote.customer ? (
            canEditCustomerFields ? (
              <ContactDropdownSelect
                quoteId={quote.id}
                customerId={quote.customer.id}
                initialContact={
                  quote.contact_person
                    ? {
                        id: quote.contact_person.id,
                        name: quote.contact_person.name,
                        last_name: quote.contact_person.last_name,
                        patronymic: quote.contact_person.patronymic,
                      }
                    : null
                }
              />
            ) : (
              <span
                className="block truncate text-sm font-medium"
                data-testid="context-panel-contact-readonly"
              >
                {quote.contact_person
                  ? [
                      quote.contact_person.name,
                      quote.contact_person.last_name,
                      quote.contact_person.patronymic,
                    ]
                      .filter(Boolean)
                      .join(" ") || "—"
                  : "—"}
              </span>
            )
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
            canEditCustomerFields ? (
              <AddressDropdownSelect
                quoteId={quote.id}
                customerId={quote.customer.id}
                initialAddress={quote.delivery_address ?? null}
              />
            ) : (
              <span
                className="block text-sm font-medium line-clamp-2 break-words"
                data-testid="context-panel-address-readonly"
              >
                {quote.delivery_address ?? "—"}
              </span>
            )
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
              ? new Date(quote.valid_until).toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" })
              : "\u2014"}
          </span>
        </InfoRow>
      </div>

      {/* Financials — hidden for procurement / logistics / customs (МОЗ-60) */}
      {showFinancials && (
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
      )}

      {/* Participants — active responsibles (МОП / МОЗ / МОЛ / МОТ) up top
          with attach dates, then a separated «История переходов» log so the
          tester can tell them apart at a glance. Testing 2 row 2
          (FB-260513-100338-a778). */}
      <div className="space-y-2 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <Users size={14} className="text-muted-foreground" />
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Участники
          </h4>
        </div>
        {/* МОП — assignment moment = quote creation. Mirrors МОЛ/МОТ shape so
            the four responsibles render with a uniform «ФИО + дата» line.
            Testing 2 row 2 — tester reported МОП had no date. */}
        {salesManager && (
          <DomainAssigneeRow
            label="МОП"
            data-testid="context-panel-sales-manager"
            assignee={{
              full_name: salesManager.full_name,
              assigned_at: quote.created_at ?? null,
            }}
          />
        )}
        {/* МОЗ — sourced from quote_items.assigned_procurement_user. Testing 2
            row 2 — tester reported МОЗ missing from the active responsibles
            block. `assigned_at` is derived from the brand-slice routing
            moment in status_history (reason='auto: all items routed') —
            see fetchQuoteContextData step 4b. Testing 2 row 79 fix. */}
        {procurementAssignees.map((a) => (
          <DomainAssigneeRow
            key={`moz-${a.user_id}`}
            label="МОЗ"
            data-testid="context-panel-procurement-assignee"
            assignee={a}
          />
        ))}
        {/* МОЛ / МОТ — sourced from invoices.assigned_logistics_user /
            assigned_customs_user. РОЛ Тест 07 → 3.1 + 4.1: tester wants ФИО +
            момент прикрепления (logistics_assigned_at / customs_assigned_at)
            visible from any pipeline step, not buried in workspace tables. */}
        {logisticsAssignees.map((a) => (
          <DomainAssigneeRow
            key={`mol-${a.user_id}`}
            label="МОЛ"
            data-testid="context-panel-logistics-assignee"
            assignee={a}
          />
        ))}
        {customsAssignees.map((a) => (
          <DomainAssigneeRow
            key={`mot-${a.user_id}`}
            label="МОТ"
            data-testid="context-panel-customs-assignee"
            assignee={a}
          />
        ))}
        {participants.length > 0 ? (
          /* Collapsed by default — Testing 2 row 2: 8 testers reported the
             history occupied too much space. Native <details> keeps the
             interaction cost low (one click, no JS) and the count gives the
             user a glanceable signal of how much is behind the disclosure. */
          <details
            className="pt-2 mt-1 border-t border-border group/history"
            data-testid="context-panel-history"
          >
            <summary className="cursor-pointer list-none text-[10px] font-semibold text-muted-foreground uppercase tracking-wide hover:text-foreground transition-colors flex items-center gap-1">
              <span className="inline-block transition-transform group-open/history:rotate-90">▸</span>
              <span>История переходов</span>
              <span className="text-muted-foreground/60 normal-case font-normal">({participants.length})</span>
            </summary>
            <ul className="space-y-1.5 max-h-32 overflow-y-auto mt-2">
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
          </details>
        ) : (
          !salesManager &&
          procurementAssignees.length === 0 &&
          logisticsAssignees.length === 0 &&
          customsAssignees.length === 0 && (
            <p className="text-sm text-muted-foreground">Нет участников</p>
          )
        )}
      </div>
    </div>
  );
}

/**
 * Single МОЛ / МОТ row. Mirrors the МОП row format (label · ФИО) and adds the
 * attach timestamp underneath in muted small text — keeps the panel compact
 * but answers «когда привязали» without expanding history.
 */
function DomainAssigneeRow({
  label,
  assignee,
  ...rest
}: {
  label: string;
  assignee: { full_name: string; assigned_at: string | null };
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className="text-sm min-w-0" {...rest}>
      <div className="flex items-baseline gap-1.5">
        <span className="text-xs text-muted-foreground shrink-0">{label}</span>
        <span className="font-medium truncate">{assignee.full_name}</span>
      </div>
      {assignee.assigned_at && (
        <div className="text-[11px] text-muted-foreground tabular-nums pl-[2.25rem]">
          {formatParticipantDate(assignee.assigned_at)}
        </div>
      )}
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
    timeZone: "Europe/Moscow",
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
