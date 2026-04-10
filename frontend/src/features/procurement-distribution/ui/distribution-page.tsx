"use client";

import { CheckCircle2 } from "lucide-react";
import { Toaster } from "sonner";
import { WorkloadCards } from "./workload-cards";
import { QuoteBrandCard } from "./quote-brand-card";
import type {
  QuoteWithBrandGroups,
  ProcurementUserWorkload,
} from "../model/types";

interface Props {
  quotes: QuoteWithBrandGroups[];
  workload: ProcurementUserWorkload[];
  orgId: string;
}

export function DistributionPage({ quotes, workload, orgId }: Props) {
  const totalQuotes = quotes.length;
  const totalItems = quotes.reduce(
    (sum, q) => sum + q.brandGroups.reduce((s, bg) => s + bg.itemCount, 0),
    0
  );

  return (
    <>
      <div className="space-y-6 max-w-4xl">
        {/* Header */}
        <div>
          <h1 className="text-xl font-semibold text-text">
            Распределение заявок
          </h1>
          {totalQuotes > 0 && (
            <p className="text-sm text-text-muted mt-1">
              {totalQuotes} {totalQuotes === 1 ? "заявка" : totalQuotes < 5 ? "заявки" : "заявок"} ({totalItems} поз.)
            </p>
          )}
        </div>

        {/* Workload cards */}
        <WorkloadCards users={workload} />

        {/* Quote list or empty state */}
        {quotes.length === 0 ? (
          <div className="py-16 text-center">
            <CheckCircle2
              size={40}
              className="mx-auto text-success mb-3"
            />
            <p className="text-text-muted mb-1">Все заявки распределены</p>
            <p className="text-xs text-text-subtle">
              Новые нераспределённые позиции появятся здесь автоматически
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {quotes.map((q) => (
              <QuoteBrandCard
                key={q.quote.id}
                data={q}
                users={workload}
                orgId={orgId}
              />
            ))}
          </div>
        )}
      </div>
      <Toaster position="top-right" richColors />
    </>
  );
}
