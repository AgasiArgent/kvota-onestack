"use client";

import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import type { QuoteStep } from "@/entities/quote/types";
import { SalesStep } from "./sales-step/sales-step";
import { ProcurementStep } from "./procurement-step/procurement-step";
import { LogisticsStep } from "./logistics-step/logistics-step";

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
  invoices,
  activeStep,
  userRoles,
}: QuoteStepContentProps) {
  switch (activeStep) {
    case "sales":
      return <SalesStep quote={quote} items={items} userRoles={userRoles} />;
    case "procurement":
      return (
        <ProcurementStep
          quote={quote}
          items={items}
          invoices={invoices}
          userRoles={userRoles}
        />
      );
    case "logistics":
      return (
        <LogisticsStep
          quote={quote}
          items={items}
          invoices={invoices}
          userRoles={userRoles}
        />
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
