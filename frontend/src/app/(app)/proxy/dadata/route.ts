import { NextResponse } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export const dynamic = "force-dynamic";

const DADATA_PARTY_URL =
  "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party";

/**
 * POST /proxy/dadata
 * Server-side proxy for DaData INN lookup.
 * Keeps DADATA_API_KEY secret from the browser.
 *
 * Body: { inn: "1234567890" }
 * Returns: { found: true, name, kpp, ogrn, address, director, is_active } or { found: false }
 */
export async function POST(req: Request) {
  // Verify the user is authenticated
  const cookieStore = await cookies();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const inn = String(body.inn ?? "").trim();

  if (!inn || !/^\d{10}$|^\d{12}$/.test(inn) || /^0+$/.test(inn)) {
    return NextResponse.json(
      { error: "Invalid INN format" },
      { status: 400 }
    );
  }

  const apiKey = process.env.DADATA_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "DaData API key not configured" },
      { status: 500 }
    );
  }

  try {
    const res = await fetch(DADATA_PARTY_URL, {
      method: "POST",
      headers: {
        Authorization: `Token ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: inn }),
      signal: AbortSignal.timeout(10_000),
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: "DaData API error" },
        { status: 502 }
      );
    }

    const data = await res.json();
    const suggestions = data.suggestions ?? [];

    if (suggestions.length === 0) {
      return NextResponse.json({ found: false });
    }

    const suggestion = suggestions[0];
    const d = suggestion.data ?? {};
    const nameData = d.name ?? {};
    const addressData = d.address ?? {};
    const management = d.management ?? {};
    const state = d.state ?? {};

    return NextResponse.json({
      found: true,
      name:
        nameData.short_with_opf || suggestion.value || "",
      kpp: d.type === "LEGAL" ? (d.kpp ?? null) : null,
      ogrn: d.ogrn ?? null,
      address:
        addressData.unrestricted_value || addressData.value || null,
      director: management.name ?? null,
      is_active: state.status === "ACTIVE",
    });
  } catch {
    return NextResponse.json(
      { error: "Failed to reach DaData" },
      { status: 502 }
    );
  }
}
