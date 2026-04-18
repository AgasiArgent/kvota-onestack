"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { createClient } from "@/shared/lib/supabase/client";
import { completeProcurement } from "@/entities/quote/mutations";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { ProcurementActionBar } from "./procurement-action-bar";
import { QuotePositionsList } from "./quote-positions-list";
import { InvoiceCard } from "./invoice-card";
import { InvoiceCreateModal } from "./invoice-create-modal";

interface Supplier {
  id: string;
  name: string;
  country: string | null;
}

interface BuyerCompany {
  id: string;
  name: string;
  company_code: string;
}

interface ProcurementStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  userRoles?: string[];
}

export function ProcurementStep({
  quote,
  items,
  invoices,
  userRoles = [],
}: ProcurementStepProps) {
  const router = useRouter();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [preselectedItemIds, setPreselectedItemIds] = useState<string[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [buyerCompanies, setBuyerCompanies] = useState<BuyerCompany[]>([]);
  const [completing, setCompleting] = useState(false);

  // Load suppliers and buyer companies for the invoice creation modal
  useEffect(() => {
    const supabase = createClient();

    supabase
      .from("suppliers")
      .select("id, name, country")
      .eq("organization_id", quote.organization_id)
      .order("name")
      .then(({ data }) => setSuppliers(data ?? []));

    supabase
      .from("buyer_companies")
      .select("id, name, company_code")
      .eq("organization_id", quote.organization_id)
      .order("name")
      .then(({ data }) => setBuyerCompanies(data ?? []));
  }, [quote.organization_id]);

  const invoiceItemsMap = useMemo(() => {
    const map = new Map<string, QuoteItemRow[]>();
    for (const item of items) {
      if (item.invoice_id != null) {
        const existing = map.get(item.invoice_id) ?? [];
        existing.push(item);
        map.set(item.invoice_id, existing);
      }
    }
    return map;
  }, [items]);

  function handleCreateInvoice() {
    setPreselectedItemIds([]);
    setCreateModalOpen(true);
  }

  function handleCreateInvoiceWithItems(itemIds: string[]) {
    setPreselectedItemIds(itemIds);
    setCreateModalOpen(true);
  }

  async function handleCompleteProcurement() {
    // Guard: every item must either have a purchase price or be marked Н/Д
    const noPriceCount = items.filter(
      (i) => i.purchase_price_original == null && i.is_unavailable !== true
    ).length;
    if (noPriceCount > 0) {
      toast.error(
        `Нельзя завершить: ${noPriceCount} поз. без цены. Заполните цену или отметьте Н/Д.`
      );
      return;
    }

    // Guard: every item must be assigned to an invoice
    const unassignedCount = items.filter(
      (i) => !i.invoice_id && i.is_unavailable !== true
    ).length;
    if (unassignedCount > 0) {
      toast.error(
        `Нельзя завершить: ${unassignedCount} поз. не распределены по КП поставщиков.`
      );
      return;
    }

    setCompleting(true);
    try {
      await completeProcurement(quote.id);
      toast.success("Закупка завершена");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Не удалось завершить закупку");
    } finally {
      setCompleting(false);
    }
  }

  const preselectedItems = items.filter((i) =>
    preselectedItemIds.includes(i.id)
  );

  return (
    <div className="flex-1 min-w-0">
      <ProcurementActionBar
        items={items}
        onCreateInvoice={handleCreateInvoice}
        onCompleteProcurement={handleCompleteProcurement}
        completing={completing}
        procurementCompleted={quote.procurement_completed_at != null}
      />

      <div className="p-6 space-y-4">
        <QuotePositionsList
          key={invoices.length}
          items={items}
          invoices={invoices}
          onCreateInvoiceWithItems={handleCreateInvoiceWithItems}
        />

        {invoices.map((invoice) => (
          <InvoiceCard
            key={invoice.id}
            invoice={invoice}
            items={invoiceItemsMap.get(invoice.id) ?? []}
            defaultExpanded={invoices.length === 1}
            procurementCompleted={quote.procurement_completed_at != null}
            userRoles={userRoles}
          />
        ))}

        {invoices.length === 0 && items.every((i) => i.invoice_id != null) && (
          <div className="text-center py-12 text-muted-foreground">
            Нет КП поставщиков
          </div>
        )}
      </div>

      <InvoiceCreateModal
        open={createModalOpen}
        onClose={() => { setCreateModalOpen(false); setPreselectedItemIds([]); }}
        quoteId={quote.id}
        idnQuote={quote.idn_quote}
        selectedItems={preselectedItems}
        suppliers={suppliers}
        buyerCompanies={buyerCompanies}
      />
    </div>
  );
}
