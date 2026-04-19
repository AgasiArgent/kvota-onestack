import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";
import { renderToBuffer } from "@react-pdf/renderer";
import { createClient } from "@/shared/lib/supabase/server";
import { KPDocument } from "@/features/quotes/ui/pdf/kp-document";
import type { KPComposedItem } from "@/features/quotes/ui/pdf/kp-document";

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

  // Fetch quote detail with FK resolution
  const { data: quote, error: quoteError } = await supabase
    .from("quotes")
    .select("*")
    .eq("id", id)
    .is("deleted_at", null)
    .single();

  if (quoteError || !quote) {
    return NextResponse.json({ error: "Quote not found" }, { status: 404 });
  }

  // Phase 5d Pattern B (Group 5 Appendix, mirroring Task 11 b5b0173):
  // items for the KP are the composed invoice_items (filtered by each
  // quote_item's composition_selected_invoice_id), not raw quote_items.
  // Migration 284 drops base_price_vat and product_code from quote_items;
  // both live on invoice_items now.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const untyped = supabase as unknown as { from: (t: string) => any };

  // Resolve FKs + composition in parallel
  const [customerRes, contactRes, creatorRes, composedRes] = await Promise.all([
    quote.customer_id
      ? supabase
          .from("customers")
          .select("id, name, inn")
          .eq("id", quote.customer_id)
          .single()
      : null,
    quote.contact_person_id
      ? supabase
          .from("customer_contacts")
          .select("id, name, phone, email")
          .eq("id", quote.contact_person_id)
          .single()
      : null,
    quote.created_by
      ? supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .eq("user_id", quote.created_by)
          .single()
      : null,
    untyped
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
      .eq("id", id)
      .single(),
  ]);

  const quoteDetail = {
    ...quote,
    customer: customerRes?.data ?? null,
    contact_person: contactRes?.data ?? null,
    seller_company: null,
    created_by_profile: creatorRes?.data
      ? {
          id: creatorRes.data.user_id,
          full_name: creatorRes.data.full_name ?? "",
        }
      : null,
  };

  // Flatten composition → items for the PDF renderer. For each quote_item
  // we keep the invoice_item(s) covered by the currently-selected
  // invoice; split cases produce multiple rows.
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

  const items: KPComposedItem[] = orderedQuoteItems.flatMap((qi) => {
    const selected = qi.composition_selected_invoice_id;
    return (qi.coverage ?? [])
      .map((c, covIdx) => ({ ii: c.invoice_items, covIdx }))
      .filter(
        (entry): entry is { ii: InvoiceItemComposedRow; covIdx: number } =>
          entry.ii != null && entry.ii.invoice_id === selected
      )
      .map(({ ii, covIdx }) => ({
        id: `${qi.id}:${covIdx}`,
        brand: ii.brand ?? qi.brand,
        product_code: ii.supplier_sku,
        product_name: ii.product_name ?? "",
        unit: null as string | null,
        quantity: ii.quantity,
        base_price_vat: ii.base_price_vat,
      }));
  });

  // Determine VAT rate from calc variables (DDP + not export → 20%, else → 0%)
  const { data: calcVars } = await supabase
    .from("quote_calculation_variables")
    .select("variables")
    .eq("quote_id", id)
    .limit(1)
    .single();

  let vatRate = 22; // default for uncalculated quotes
  if (calcVars?.variables) {
    const vars = calcVars.variables as Record<string, unknown>;
    const incoterms = vars.offer_incoterms as string | undefined;
    const saleType = vars.offer_sale_type as string | undefined;
    const isExport = saleType === "экспорт" || saleType === "export";
    vatRate = incoterms === "DDP" && !isExport ? 22 : 0;
  }

  const buffer = await renderToBuffer(
    <KPDocument quote={quoteDetail} items={items} logoBase64={getLogoBase64() ?? ""} vatRate={vatRate} />
  );

  // Build filename: KP_{customer}_{date}.pdf
  const customerName = (quote.customer_id ? quoteDetail.customer?.name : null)
    ?? "Client";
  const asciiName = customerName.replace(/[^a-zA-Z0-9]/g, "_");
  const utfName = customerName.replace(/[^\w\u0400-\u04FF]/g, "_");
  const dateStr = new Date().toISOString().split("T")[0];
  const filename = `KP_${asciiName}_${dateStr}.pdf`;
  const filenameUtf = `KP_${utfName}_${dateStr}.pdf`;

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${filename}"; filename*=UTF-8''${encodeURIComponent(filenameUtf)}`,
    },
  });
}
