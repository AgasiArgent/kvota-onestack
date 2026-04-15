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

  // Fetch quote, customer, contract, items in parallel
  const [quoteRes, contractRes, itemsRes] = await Promise.all([
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
      .from("quote_items")
      .select("brand, product_code, product_name, unit, quantity, base_price_vat")
      .eq("quote_id", spec.quote_id)
      .order("position", { ascending: true }),
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
  const items = itemsRes.data ?? [];

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
