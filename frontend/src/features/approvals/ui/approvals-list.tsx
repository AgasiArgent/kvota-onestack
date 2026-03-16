import Link from "next/link";
import { CheckCircle2, Clock, Eye, FileText } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface QuoteCustomer {
  name: string | null;
  inn: string | null;
}

interface PendingQuote {
  id: string;
  idn_quote: string;
  total_amount: number;
  currency: string;
  approval_reason: string | null;
  approval_justification: string | null;
  updated_at: string | null;
  customers: QuoteCustomer | null;
}

interface ApprovalsListProps {
  quotes: PendingQuote[];
}

const CURRENCY_MAP: Record<string, string> = {
  RUB: "RUB",
  USD: "USD",
  EUR: "EUR",
  CNY: "CNY",
};

function formatMoney(amount: number, currency: string): string {
  const currencyCode = CURRENCY_MAP[currency] ?? "RUB";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: currencyCode,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "\u2026";
}

export function ApprovalsList({ quotes }: ApprovalsListProps) {
  const totalPending = quotes.length;
  const totalAmount = quotes.reduce((sum, q) => sum + (q.total_amount ?? 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Clock className="h-7 w-7 text-[var(--warning)]" />
          Согласования
        </h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Коммерческие предложения, ожидающие вашего решения
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="text-center py-2">
            <div className="text-3xl font-bold text-[var(--warning)]">
              {totalPending}
            </div>
            <div className="text-sm text-[var(--text-muted)]">
              Ожидают решения
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-2">
            <div className="text-xl font-bold text-[var(--success)]">
              {formatMoney(totalAmount, "RUB")}
            </div>
            <div className="text-sm text-[var(--text-muted)]">
              Общая сумма
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Section title */}
      <h2 className="text-lg font-semibold">
        КП на согласовании ({totalPending})
      </h2>

      {/* Quote cards or empty state */}
      {quotes.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-3">
          {quotes.map((quote) => (
            <QuoteCard key={quote.id} quote={quote} />
          ))}
        </div>
      )}
    </div>
  );
}

function QuoteCard({ quote }: { quote: PendingQuote }) {
  const customer = (quote.customers ?? null) as QuoteCustomer | null;
  const customerName = customer?.name ?? "\u2014";
  const amount = quote.total_amount ?? 0;
  const currency = quote.currency ?? "RUB";

  return (
    <Card className="border-l-4 border-l-[var(--warning)] transition-shadow hover:shadow-md">
      <CardContent className="space-y-3">
        {/* Header row */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <Link
              href={`/quotes/${quote.id}`}
              className="text-base font-semibold text-[var(--accent)] hover:underline flex items-center gap-1"
            >
              <FileText className="h-4 w-4" />
              {quote.idn_quote}
            </Link>
            <span className="text-sm text-[var(--text-muted)]">
              {customerName}
            </span>
          </div>
          <Badge className="bg-[var(--success-bg)] text-[var(--success)] border-0 text-sm font-semibold shrink-0">
            {formatMoney(amount, currency)}
          </Badge>
        </div>

        {/* Context: approval reason + justification */}
        {(quote.approval_reason || quote.approval_justification) && (
          <div className="space-y-2">
            {quote.approval_reason && (
              <div className="rounded-md bg-[var(--warning-bg)] px-3 py-2 text-sm">
                <span className="font-medium">Причина:</span>{" "}
                <span className="text-[var(--text-muted)]">
                  {truncate(quote.approval_reason, 100)}
                </span>
              </div>
            )}
            {quote.approval_justification && (
              <div className="rounded-md bg-blue-50 dark:bg-blue-950/30 px-3 py-2 text-sm">
                <span className="font-medium">Обоснование:</span>{" "}
                <span className="text-[var(--text-muted)]">
                  {truncate(quote.approval_justification, 100)}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Actions row */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-xs text-[var(--text-muted)]">
            Обновлено: {formatDate(quote.updated_at)}
          </span>
          <div className="flex gap-2">
            <Link
              href={`/quotes/${quote.id}?tab=overview`}
              className={cn(
                buttonVariants({ size: "sm" }),
                "bg-[var(--success)] text-white hover:bg-[var(--success)]/90"
              )}
            >
              <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
              Одобрить
            </Link>
            <Link
              href={`/quotes/${quote.id}`}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
            >
              <Eye className="h-3.5 w-3.5 mr-1" />
              Подробнее
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center py-10 text-center">
        <CheckCircle2 className="h-12 w-12 text-[var(--success)] mb-3" />
        <h3 className="text-lg font-semibold mb-1">Все согласовано!</h3>
        <p className="text-sm text-[var(--text-muted)]">
          Нет КП, ожидающих вашего решения.
        </p>
      </CardContent>
    </Card>
  );
}
