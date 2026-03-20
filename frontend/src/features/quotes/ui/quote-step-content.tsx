"use client";

import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import type { QuoteStep } from "@/entities/quote/types";
import { SalesStep } from "./sales-step/sales-step";

interface QuoteStepContentProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  activeStep: QuoteStep;
  userRoles: string[];
}

export function QuoteStepContent({
  quote,
  items,
  activeStep,
  userRoles,
}: QuoteStepContentProps) {
  switch (activeStep) {
    case "sales":
      return <SalesStep quote={quote} items={items} userRoles={userRoles} />;
    case "procurement":
      return (
        <div className="flex-1 p-6 text-sm text-muted-foreground">
          Закупки &mdash; Phase 2
        </div>
      );
    case "logistics":
      return (
        <div className="flex-1 p-6 text-sm text-muted-foreground">
          Логистика &mdash; Phase 3
        </div>
      );
    case "customs":
      return (
        <div className="flex-1 p-6 text-sm text-muted-foreground">
          Таможня &mdash; Phase 5
        </div>
      );
    case "control":
      return (
        <div className="flex-1 p-6 text-sm text-muted-foreground">
          Контроль &mdash; Phase 6
        </div>
      );
    case "cost-analysis":
      return (
        <div className="flex-1 p-6 text-sm text-muted-foreground">
          Кост-анализ &mdash; Phase 6
        </div>
      );
    default:
      return (
        <div className="flex-1 p-6 text-sm text-muted-foreground">
          Unknown step
        </div>
      );
  }
}
