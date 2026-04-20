import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";
import { renderToBuffer } from "@react-pdf/renderer";
import { createClient } from "@/shared/lib/supabase/server";
import { SpecDocument } from "@/features/quotes/ui/pdf/spec-document";

// Lazy-load logo (avoid build-time fs.readFileSync which fails in Docker)
let logoBase64Cache: string | null = null;
function getLogoBase64(): string | null {
  if (logoBase64Cache) return logoBase64Cache;
  try {
    const logoPath = path.join(process.cwd(), "public", "logo-master-bearing.png");
    logoBase64Cache = `data:image/png;base64,${fs.readFileSync(logoPath).toString("base64")}`;
    return logoBase64Cache;
  } catch {
    return null;
  }
}

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const supabase = await createClient();

  // Fetch specification
  const { data: spec, error: specError } = await supabase
    .from("specifications")
    .select("id, quote_id, contract_id, specification_number, sign_date, readiness_period, status")
    .eq("id", id)
    .is("deleted_at", null)
    .single();

  if (specError || !spec) {
    return NextResponse.json({ error: "Specification not found" }, { status: 404 });
  }

  // Phase 5d Pattern B (design.md §2.3.4): items for the specification
  // are the composed invoice_items (filtered by each quote_item's
  // composition_selected_invoice_id), not raw quote_items. Migration
  // 284 drops base_price_vat and product_code from quote_items; both
  // live on invoice_items now.
  const [quoteRes, contractRes, composedRes] = await Promise.all([
    supabase
      .from("quotes")
      .select("id, idn_quote, customer_id, currency")
      .eq("id", spec.quote_id)
      .is("deleted_at", null)
      .single(),
    spec.contract_id
      ? supabase
          .from("customer_contracts")
          .select("id, contract_number, contract_date")
          .eq("id", spec.contract_id)
          .single()
      : null,
    supabase
      .from("quotes")
      .select(
        "id, " +
          "quote_items!inner(" +
          "id, position, composition_selected_invoice_id, brand, " +
          "coverage:invoice_item_coverage!quote_item_id(" +
          "invoice_items!inner(" +
          "invoice_id, product_name, supplier_sku, brand, quantity, " +
          "base_price_vat" +
          ")" +
          ")" +
          ")"
      )
      .eq("id", spec.quote_id)
      .single(),
  ]);

  const quote = quoteRes.data;
  if (!quote) {
    return NextResponse.json({ error: "Quote not found" }, { status: 404 });
  }

  // Fetch customer if available
  const customerRes = quote.customer_id
    ? await supabase
        .from("customers")
        .select("id, name, inn")
        .eq("id", quote.customer_id)
        .single()
    : null;

  const customer = customerRes?.data ?? null;
  const contract = contractRes?.data ?? null;

  // Flatten composition → items for the PDF renderer. For each quote_item
  // we keep the invoice_item(s) covered by the currently-selected
  // invoice; split cases produce multiple rows, merge cases may share an
  // invoice_item across several quote_items (still rendered once per
  // coverage row, matching the customer's KP view).
  type InvoiceItemComposedRow = {
    invoice_id: string;
    product_name: string | null;
    supplier_sku: string | null;
    brand: string | null;
    quantity: number | null;
    base_price_vat: number | null;
  };
  type CoverageComposedRow = { invoice_items: InvoiceItemComposedRow | null };
  type QuoteItemComposedRow = {
    id: string;
    position: number | null;
    composition_selected_invoice_id: string | null;
    brand: string | null;
    coverage: CoverageComposedRow[] | null;
  };
  type QuoteComposedRow = {
    id: string;
    quote_items: QuoteItemComposedRow[] | null;
  };

  const composedData = composedRes.data as QuoteComposedRow | null;
  const orderedQuoteItems = (composedData?.quote_items ?? []).slice().sort(
    (a, b) => (a.position ?? 0) - (b.position ?? 0)
  );

  const items = orderedQuoteItems.flatMap((qi) => {
    const selected = qi.composition_selected_invoice_id;
    return (qi.coverage ?? [])
      .map((c) => c.invoice_items)
      .filter(
        (ii): ii is InvoiceItemComposedRow =>
          ii != null && ii.invoice_id === selected
      )
      .map((ii) => ({
        brand: ii.brand ?? qi.brand,
        product_code: ii.supplier_sku,
        product_name: ii.product_name ?? "",
        unit: null as string | null,
        quantity: ii.quantity,
        base_price_vat: ii.base_price_vat,
      }));
  });

  const specNumber = spec.specification_number ?? "SP-???";

  const buffer = await renderToBuffer(
    <SpecDocument
      specNumber={specNumber}
      signDate={spec.sign_date}
      readinessPeriod={spec.readiness_period}
      contractNumber={contract?.contract_number ?? null}
      contractDate={contract?.contract_date ?? null}
      customerName={customer?.name ?? "Клиент"}
      customerInn={customer?.inn ?? null}
      quoteCurrency={quote.currency ?? "RUB"}
      quoteIdn={quote.idn_quote}
      items={items}
      logoBase64={getLogoBase64() ?? ""}
    />
  );

  const filename = `SP_${specNumber.replace(/[^a-zA-Z0-9-]/g, "_")}.pdf`;
  const filenameUtf = `SP_${specNumber.replace(/[^\w\u0400-\u04FF-]/g, "_")}.pdf`;

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${filename}"; filename*=UTF-8''${encodeURIComponent(filenameUtf)}`,
    },
  });
}
