"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/shared/lib/supabase/client";

export interface DocumentRow {
  id: string;
  entity_id: string;
  storage_path: string;
  original_filename: string;
  mime_type: string | null;
}

export interface CalcSummaryRow {
  calc_s16_total_purchase_price: number | null;
  calc_ab16_cogs_total: number | null;
  calc_v16_total_logistics: number | null;
  calc_al16_total_with_vat: number | null;
  calc_ae16_sale_price_total: number | null;
  calc_af16_profit_margin: number | null;
  calc_y16_customs_duty: number | null;
  calc_ak16_final_price_total: number | null;
  calculated_at: string | null;
}

export interface ControlData {
  calcSummary: CalcSummaryRow | null;
  invoiceDocuments: Map<string, DocumentRow>;
  isLoading: boolean;
}

export function useControlData(
  quoteId: string,
  invoiceIds: string[]
): ControlData {
  const [calcSummary, setCalcSummary] = useState<CalcSummaryRow | null>(null);
  const [invoiceDocuments, setInvoiceDocuments] = useState<
    Map<string, DocumentRow>
  >(new Map());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!quoteId) {
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    const supabase = createClient();

    async function fetchData() {
      setIsLoading(true);

      const calcPromise = supabase
        .from("quote_calculation_summaries")
        .select(
          "calc_s16_total_purchase_price, calc_ab16_cogs_total, calc_v16_total_logistics, calc_al16_total_with_vat, calc_ae16_sale_price_total, calc_af16_profit_margin, calc_y16_customs_duty, calc_ak16_final_price_total, calculated_at"
        )
        .eq("quote_id", quoteId)
        .maybeSingle();

      const docsPromise =
        invoiceIds.length > 0
          ? supabase
              .from("documents")
              .select(
                "id, entity_id, storage_path, original_filename, mime_type"
              )
              .eq("entity_type", "supplier_invoice")
              .in("entity_id", invoiceIds)
          : Promise.resolve({
              data: [] as Array<{
                id: string;
                entity_id: string;
                storage_path: string;
                original_filename: string;
                mime_type: string | null;
              }>,
              error: null,
            });

      const [calcResult, docsResult] = await Promise.all([
        calcPromise,
        docsPromise,
      ]);

      if (cancelled) return;

      if (calcResult.error) {
        console.error(
          "Failed to fetch calculation summary:",
          calcResult.error
        );
      }
      if (docsResult.error) {
        console.error(
          "Failed to fetch invoice documents:",
          docsResult.error
        );
      }

      setCalcSummary(calcResult.data ?? null);

      const docsMap = new Map<string, DocumentRow>();
      for (const doc of docsResult.data ?? []) {
        docsMap.set(doc.entity_id, doc);
      }
      setInvoiceDocuments(docsMap);

      setIsLoading(false);
    }

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [quoteId, invoiceIds.join(",")]);

  return { calcSummary, invoiceDocuments, isLoading };
}
