"use client";

import { useState } from "react";
import { Toaster } from "sonner";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";
import { SalesActionBar } from "./sales-action-bar";
import type { ClientResponseModal } from "./sales-action-bar";
import { SalesInfoGrid } from "./sales-info-grid";
import { SalesItemsTable } from "./sales-items-table";
import { SalesCollapsible } from "./sales-collapsible";
import { ClientResponseModals } from "./client-response-modals";

interface SalesStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  userRoles: string[];
}

export function SalesStep({ quote, items }: SalesStepProps) {
  const [activeModal, setActiveModal] = useState<ClientResponseModal>(null);

  return (
    <div className="flex-1 min-w-0">
      <SalesActionBar quote={quote} onOpenModal={setActiveModal} />
      <div className="p-6 space-y-6">
        <SalesInfoGrid quote={quote} />
        <SalesItemsTable
          items={items}
          currency={quote.currency ?? "USD"}
          quoteId={quote.id}
        />
        <SalesCollapsible quote={quote} />
      </div>
      <ClientResponseModals
        quoteId={quote.id}
        idnQuote={quote.idn_quote}
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
      />
      <Toaster position="top-right" richColors />
    </div>
  );
}
