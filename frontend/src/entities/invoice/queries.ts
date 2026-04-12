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

export async function fetchVatRate(
  countryCode: string
): Promise<{ country_code: string; rate: number } | null> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/geo/vat-rate?country_code=${encodeURIComponent(countryCode)}`, {
    headers: {
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
  });

  const json = await res.json();
  if (!res.ok || !json.success) return null;
  return json.data as { country_code: string; rate: number };
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
