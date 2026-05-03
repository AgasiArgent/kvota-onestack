"use client";

import { CheckCircle2 } from "lucide-react";
import { AppToaster } from "@/shared/ui/app-toaster";
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

/** Russian plural for "заявка" (quote). 1 → заявка, 2-4 → заявки, 5+ → заявок. */
function pluralizeQuotes(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "заявка";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "заявки";
  return "заявок";
}

/** Russian plural for "карточка" (card). 1 → карточка, 2-4 → карточки, 5+ → карточек. */
function pluralizeCards(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "карточка";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "карточки";
  return "карточек";
}

export function DistributionPage({ quotes, workload, orgId }: Props) {
  const totalQuotes = quotes.length;
  const totalBrandSlices = quotes.reduce(
    (sum, q) => sum + q.brandGroups.length,
    0
  );
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
              {totalQuotes} {pluralizeQuotes(totalQuotes)} · {totalBrandSlices}{" "}
              {pluralizeCards(totalBrandSlices)} ({totalItems} поз.)
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
      <AppToaster />
    </>
  );
}
