"use client";

import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import type { QuoteStep } from "@/entities/quote/types";
import type { EntityNoteCardData } from "@/entities/entity-note/ui/entity-note-card";
import type { TableView } from "@/entities/table-view";
import { SalesStep } from "./sales-step/sales-step";
import { ProcurementStep } from "./procurement-step/procurement-step";
import { LogisticsStep } from "./logistics-step/logistics-step";
import { CustomsStep } from "./customs-step/customs-step";
import { CalculationStep } from "./calculation-step/calculation-step";
import { ControlStep } from "./control-step/control-step";
import { SpecificationStep } from "./specification-step/specification-step";
import { DocumentsStep } from "./documents-step/documents-step";
import { PlanFactStep } from "@/features/plan-fact";

interface QuoteStepContentProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  activeStep: QuoteStep;
  userRoles: string[];
  userId: string;
  calcVariables?: Record<string, unknown> | null;
  dealId?: string | null;
  isReadOnly?: boolean;
  quoteNotes?: EntityNoteCardData[];
  invoiceNotesById?: Record<string, EntityNoteCardData[]>;
  /** Table-view presets for the customs step (personal + shared). */
  customsTableViews?: readonly TableView[];
  /** Whether the user may create/edit org-shared customs views. */
  canCreateCustomsSharedView?: boolean;
}

function ReadOnlyOverlay({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex-1">
      <div className="pointer-events-none select-none opacity-60">
        {children}
      </div>
      <div className="absolute top-3 right-3 bg-muted/90 text-muted-foreground text-xs px-2 py-1 rounded pointer-events-none">
        Только просмотр
      </div>
    </div>
  );
}

export function QuoteStepContent({
  quote,
  items,
  invoices,
  activeStep,
  userRoles,
  userId,
  calcVariables,
  dealId,
  isReadOnly = false,
  quoteNotes = [],
  invoiceNotesById = {},
  customsTableViews = [],
  canCreateCustomsSharedView = false,
}: QuoteStepContentProps) {
  function wrapReadOnly(content: React.ReactNode) {
    if (!isReadOnly) return content;
    return <ReadOnlyOverlay>{content}</ReadOnlyOverlay>;
  }

  switch (activeStep) {
    case "sales":
    case "negotiation":
      return wrapReadOnly(<SalesStep quote={quote} items={items} userRoles={userRoles} />);
    case "calculation":
      return wrapReadOnly(
        <CalculationStep
          quote={quote}
          items={items}
          userRoles={userRoles}
          savedVariables={calcVariables ?? null}
        />
      );
    case "procurement":
      return wrapReadOnly(
        <ProcurementStep
          quote={quote}
          items={items}
          invoices={invoices}
          userRoles={userRoles}
        />
      );
    case "logistics":
      return wrapReadOnly(
        <LogisticsStep
          quote={quote}
          invoices={invoices}
          userId={userId}
          userRoles={userRoles}
          quoteNotes={quoteNotes}
          invoiceNotesById={invoiceNotesById}
        />
      );
    case "customs":
      return wrapReadOnly(
        <CustomsStep
          quote={quote}
          items={items}
          invoices={invoices}
          userRoles={userRoles}
          userId={userId}
          quoteNotes={quoteNotes}
          tableViews={customsTableViews}
          canCreateSharedView={canCreateCustomsSharedView}
        />
      );
    case "control":
      return wrapReadOnly(
        <ControlStep
          quote={quote}
          items={items}
          invoices={invoices}
          userRoles={userRoles}
          calcVariables={calcVariables ?? null}
        />
      );
    case "specification":
      return wrapReadOnly(
        <SpecificationStep
          quote={quote}
          items={items}
          userRoles={userRoles}
        />
      );
    case "documents":
      return wrapReadOnly(<DocumentsStep quote={quote} userId={userId} />);
    case "plan-fact":
      return wrapReadOnly(
        <PlanFactStep
          quoteId={quote.id}
          dealId={dealId ?? null}
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
