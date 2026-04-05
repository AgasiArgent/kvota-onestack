"use client";

import { useState } from "react";
import { Toaster } from "sonner";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";
import { SalesActionBar } from "./sales-action-bar";
import type { ClientResponseModal } from "./sales-action-bar";
import { SalesItemsTable } from "./sales-items-table";
import { SalesItemsEditor } from "./sales-items-editor";
import { ClientResponseModals } from "./client-response-modals";

interface SalesStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  userRoles: string[];
}

export function SalesStep({ quote, items }: SalesStepProps) {
  const [activeModal, setActiveModal] = useState<ClientResponseModal>(null);
  const isDraft = (quote.workflow_status ?? "draft") === "draft";

  return (
    <div className="flex-1 min-w-0">
      <SalesActionBar quote={quote} items={items} onOpenModal={setActiveModal} />
      <div className="p-6 space-y-6">
        {isDraft ? (
          <SalesItemsEditor
            quoteId={quote.id}
            items={items}
            currency={quote.currency ?? "USD"}
          />
        ) : (
          <SalesItemsTable
            items={items}
            currency={quote.currency ?? "USD"}
            quoteId={quote.id}
          />
        )}
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
