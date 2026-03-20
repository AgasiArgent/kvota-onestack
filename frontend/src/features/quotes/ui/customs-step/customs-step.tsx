"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { completeCustoms } from "@/entities/quote/mutations";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { CustomsActionBar } from "./customs-action-bar";
import { CustomsItemsEditor } from "./customs-items-editor";
import { CustomsExpenses } from "./customs-expenses";
import { CustomsNotes } from "./customs-notes";

function ext<T>(row: unknown): T {
  return row as T;
}

interface CustomsStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  userRoles: string[];
}

export function CustomsStep({
  quote,
  items,
  invoices,
}: CustomsStepProps) {
  const router = useRouter();
  const [completing, setCompleting] = useState(false);

  const invoiceCountryMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const inv of invoices) {
      if (inv.pickup_country) {
        map.set(inv.id, inv.pickup_country);
      }
    }
    return map;
  }, [invoices]);

  const customsNotes = ext<{ customs_notes?: string | null }>(quote).customs_notes ?? "";

  async function handleCompleteCustoms() {
    setCompleting(true);
    try {
      await completeCustoms(quote.id);
      toast.success("Таможня завершена");
      router.refresh();
    } catch {
      toast.error("Не удалось завершить таможню");
    } finally {
      setCompleting(false);
    }
  }

  return (
    <div className="flex-1 min-w-0">
      <CustomsActionBar
        items={items}
        onCompleteCustoms={handleCompleteCustoms}
        completing={completing}
      />

      <div className="p-6 space-y-4">
        <CustomsItemsEditor
          items={items}
          invoiceCountryMap={invoiceCountryMap}
        />

        <CustomsExpenses quoteId={quote.id} />

        <CustomsNotes quoteId={quote.id} initialNotes={customsNotes} />
      </div>
    </div>
  );
}
