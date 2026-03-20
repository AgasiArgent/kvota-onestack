import { NextResponse } from "next/server";
import path from "path";
import fs from "fs";
import { renderToBuffer } from "@react-pdf/renderer";
import { createClient } from "@/shared/lib/supabase/server";
import { KPDocument } from "@/features/quotes/ui/pdf/kp-document";

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
    .single();

  if (quoteError || !quote) {
    return NextResponse.json({ error: "Quote not found" }, { status: 404 });
  }

  // Resolve FKs in parallel
  const [customerRes, contactRes, creatorRes, itemsRes] = await Promise.all([
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
    supabase
      .from("quote_items")
      .select("*")
      .eq("quote_id", id)
      .order("position", { ascending: true }),
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

  const items = itemsRes.data ?? [];

  const buffer = await renderToBuffer(
    <KPDocument quote={quoteDetail} items={items} logoBase64={getLogoBase64() ?? ""} />
  );

  // Build filename: KP_{customer}_{date}.pdf
  const customerName = (quote.customer_id ? quoteDetail.customer?.name : null)
    ?? "Client";
  const safeName = customerName.replace(/[^a-zA-Zа-яА-ЯёЁ0-9]/g, "_");
  const dateStr = new Date().toISOString().split("T")[0];

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="KP_${safeName}_${dateStr}.pdf"`,
    },
  });
}
