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
import { CustomsStep } from "./customs-step/customs-step";
import { CalculationStep } from "./calculation-step/calculation-step";
import { ControlStep } from "./control-step/control-step";
import { SpecificationStep } from "./specification-step/specification-step";

interface QuoteStepContentProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  activeStep: QuoteStep;
  userRoles: string[];
  calcVariables?: Record<string, unknown> | null;
}

export function QuoteStepContent({
  quote,
  items,
  invoices,
  activeStep,
  userRoles,
  calcVariables,
}: QuoteStepContentProps) {
  switch (activeStep) {
    case "sales":
    case "negotiation":
      return <SalesStep quote={quote} items={items} userRoles={userRoles} />;
    case "calculation":
      return (
        <CalculationStep
          quote={quote}
          items={items}
          userRoles={userRoles}
          savedVariables={calcVariables ?? null}
        />
      );
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
        <CustomsStep
          quote={quote}
          items={items}
          invoices={invoices}
          userRoles={userRoles}
        />
      );
    case "control":
      return (
        <ControlStep
          quote={quote}
          items={items}
          invoices={invoices}
          userRoles={userRoles}
          calcVariables={calcVariables ?? null}
        />
      );
    case "specification":
      return (
        <SpecificationStep
          quote={quote}
          items={items}
          userRoles={userRoles}
        />
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
