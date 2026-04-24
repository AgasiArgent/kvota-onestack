import { createClient } from "@/shared/lib/supabase/client";

// ---------------------------------------------------------------------------
// VAT rates
// ---------------------------------------------------------------------------

export interface VatRate {
  country_code: string;
  rate: number;
  notes: string | null;
  updated_at: string;
  updated_by: string | null;
}

export async function fetchVatRates(): Promise<VatRate[]> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("vat_rates_by_country")
    .select("country_code, rate, notes, updated_at, updated_by")
    .order("country_code", { ascending: true });

  if (error) throw error;
  return data ?? [];
}

export type VatResolverReason = "domestic" | "export_zero_rated" | "unknown";

export async function fetchSupplierVatRate(params: {
  supplierCountryCode: string;
  buyerCompanyId: string;
}): Promise<{ rate: number; reason: VatResolverReason } | null> {
  const { supplierCountryCode, buyerCompanyId } = params;
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const url =
    `/api/geo/vat-rate?supplier_country_code=${encodeURIComponent(supplierCountryCode)}` +
    `&buyer_company_id=${encodeURIComponent(buyerCompanyId)}`;

  let res: Response;
  try {
    res = await fetch(url, {
      headers: {
        ...(session?.access_token
          ? { Authorization: `Bearer ${session.access_token}` }
          : {}),
      },
    });
  } catch {
    // Network error (DNS, offline, abort) — caller stays on user-editable VAT.
    return null;
  }

  let json: unknown;
  try {
    json = await res.json();
  } catch {
    return null;
  }

  if (!res.ok) return null;

  if (
    !json ||
    typeof json !== "object" ||
    !(json as { success?: unknown }).success
  ) {
    return null;
  }

  const data = (json as { data?: unknown }).data;
  if (!data || typeof data !== "object") return null;

  const rateRaw = (data as { rate?: unknown }).rate;
  const reasonRaw = (data as { reason?: unknown }).reason;

  if (typeof rateRaw !== "number" || !Number.isFinite(rateRaw)) return null;
  if (
    reasonRaw !== "domestic" &&
    reasonRaw !== "export_zero_rated" &&
    reasonRaw !== "unknown"
  ) {
    return null;
  }

  return { rate: rateRaw, reason: reasonRaw };
}

// ---------------------------------------------------------------------------
// Letter drafts
// ---------------------------------------------------------------------------

export interface LetterDraft {
  id: string;
  invoice_id: string;
  created_by: string;
  language: string;
  method: string;
  recipient_email: string | null;
  subject: string | null;
  body_text: string | null;
  created_at: string;
  updated_at: string;
  sent_at: string | null;
}

export async function fetchActiveLetterDraft(
  invoiceId: string
): Promise<LetterDraft | null> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/invoices/${invoiceId}/letter-draft`, {
    headers: {
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
  });

  const json = await res.json();
  if (!res.ok || !json.success) return null;
  return json.data as LetterDraft;
}

export async function fetchSendHistory(
  invoiceId: string
): Promise<LetterDraft[]> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/invoices/${invoiceId}/letter-drafts/history`, {
    headers: {
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
  });

  const json = await res.json();
  if (!res.ok || !json.success) return [];
  return (json.data ?? []) as LetterDraft[];
}
