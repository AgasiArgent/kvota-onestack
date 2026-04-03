"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { createClient } from "@/shared/lib/supabase/client";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import {
  SalesChecklistBlock,
  type SalesChecklist,
} from "./sales-checklist-block";
import {
  ParticipantsBlock,
  type ParticipantRow,
} from "./participants-block";
import { ContactDropdownSelect } from "./contact-dropdown-select";
import { AddressDropdownSelect } from "./address-dropdown-select";
import { DeliveryPrioritySelect } from "./delivery-priority-select";

const DELIVERY_METHOD_LABELS: Record<string, string> = {
  air: "Авиа",
  auto: "Авто",
  sea: "Море",
  multimodal: "Мультимодально",
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

interface ContextPanelData {
  salesChecklist: SalesChecklist | null;
  contactPerson: {
    name: string;
    phone: string | null;
    email: string | null;
  } | null;
  salesManager: { id: string; full_name: string } | null;
  participants: ParticipantRow[];
}

interface ContextPanelProps {
  quoteId: string;
  quote: QuoteDetailRow;
  isOpen: boolean;
}

export function ContextPanel({ quoteId, quote, isOpen }: ContextPanelProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ContextPanelData | null>(null);
  const fetchedRef = useRef(false);
  const prevQuoteIdRef = useRef(quoteId);

  useEffect(() => {
    if (prevQuoteIdRef.current !== quoteId) {
      prevQuoteIdRef.current = quoteId;
      fetchedRef.current = false;
      setData(null);
    }
    if (!isOpen || fetchedRef.current) return;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const supabase = createClient();

        // 1. Fetch quote fields for checklist + FK IDs
        const { data: quoteRow, error: quoteError } = await supabase
          .from("quotes")
          .select("sales_checklist, created_by, contact_person_id")
          .eq("id", quoteId)
          .single();

        if (quoteError) throw quoteError;

        const checklist =
          (quoteRow?.sales_checklist as SalesChecklist | null) ?? null;
        const contactPersonId = quoteRow?.contact_person_id ?? null;
        const createdBy = quoteRow?.created_by ?? null;

        // 2. Parallel fetch: contact person, sales manager, transitions
        const [contactRes, managerRes, transitionsRes] = await Promise.all([
          contactPersonId
            ? supabase
                .from("customer_contacts")
                .select("id, name, phone, email")
                .eq("id", contactPersonId)
                .single()
            : Promise.resolve({ data: null, error: null }),
          createdBy
            ? supabase
                .from("user_profiles")
                .select("user_id, full_name")
                .eq("user_id", createdBy)
                .single()
            : Promise.resolve({ data: null, error: null }),
          supabase
            .from("workflow_transitions")
            .select(
              "id, from_status, to_status, actor_id, actor_role, created_at"
            )
            .eq("quote_id", quoteId)
            .order("created_at", { ascending: true }),
        ]);

        const contact = contactRes.data
          ? {
              name: contactRes.data.name,
              phone: contactRes.data.phone ?? null,
              email: contactRes.data.email ?? null,
            }
          : null;

        const manager = managerRes.data
          ? {
              id: managerRes.data.user_id,
              full_name: managerRes.data.full_name ?? "",
            }
          : null;

        const transitions = transitionsRes.data ?? [];

        // 3. Batch-fetch actor names from unique actor_ids
        const actorIds = [
          ...new Set(transitions.map((t) => t.actor_id).filter(Boolean)),
        ] as string[];

        let profileMap = new Map<string, string>();

        if (actorIds.length > 0) {
          const { data: profiles } = await supabase
            .from("user_profiles")
            .select("user_id, full_name")
            .in("user_id", actorIds);

          profileMap = new Map(
            (profiles ?? []).map((p) => [
              p.user_id,
              p.full_name ?? "Неизвестный",
            ])
          );
        }

        const participants: ParticipantRow[] = transitions.map((t) => ({
          id: t.id,
          actor_id: t.actor_id ?? "",
          actor_role: t.actor_role ?? "",
          actor_name: profileMap.get(t.actor_id ?? "") ?? "Неизвестный",
          from_status: t.from_status ?? "",
          to_status: t.to_status ?? "",
          created_at: t.created_at,
        }));

        setData({
          salesChecklist: checklist,
          contactPerson: contact,
          salesManager: manager,
          participants,
        });
        fetchedRef.current = true;
      } catch {
        setError("Не удалось загрузить контекст");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [isOpen, quoteId]);

  if (!isOpen) return null;

  return (
    <div className="border-t border-border bg-card px-6 py-4">
      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={14} className="animate-spin" />
          Загрузка...
        </div>
      )}

      {error && (
        <p className="text-sm text-muted-foreground">{error}</p>
      )}

      <QuoteInfoBlock quote={quote} />

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SalesChecklistBlock
            checklist={data.salesChecklist}
            contactPerson={data.contactPerson}
            salesManager={data.salesManager}
          />
          <ParticipantsBlock participants={data.participants} />
        </div>
      )}
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
        <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Клиент
        </h4>
        <InfoRow label="Клиент">
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
        <InfoRow label="Город доставки">
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
        <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Условия
        </h4>
        <InfoRow label="Валюта">
          <span className="text-sm font-medium">{currency}</span>
        </InfoRow>
        <InfoRow label="Способ доставки">
          <span className="text-sm font-medium">
            {DELIVERY_METHOD_LABELS[quote.delivery_method ?? ""] ?? quote.delivery_method ?? "\u2014"}
          </span>
        </InfoRow>
        <InfoRow label="Оплата">
          <span className="text-sm font-medium">
            {quote.payment_terms ?? "\u2014"}
          </span>
        </InfoRow>
        <InfoRow label="Инкотермс">
          {quote.incoterms ? (
            <Badge variant="outline" className="text-xs font-semibold px-2 py-0">
              {quote.incoterms}
            </Badge>
          ) : (
            <span className="text-sm text-muted-foreground">{"\u2014"}</span>
          )}
        </InfoRow>
        <InfoRow label="Тип доставки">
          <DeliveryPrioritySelect
            quoteId={quote.id}
            initialValue={quote.delivery_priority ?? null}
          />
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
