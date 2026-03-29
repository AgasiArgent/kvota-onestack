"use server";

import { createClient } from "@/shared/lib/supabase/server";

export async function createSpecification(data: {
  quote_id: string;
  organization_id: string;
  contract_id?: string;
  quote_version_id?: string;
  specification_number: string;
  sign_date?: string;
  readiness_period?: string;
  delivery_day_type?: string;
}) {
  const supabase = await createClient();

  const { data: spec, error } = await supabase
    .from("specifications")
    .insert({
      quote_id: data.quote_id,
      organization_id: data.organization_id,
      contract_id: data.contract_id || null,
      quote_version_id: data.quote_version_id || null,
      specification_number: data.specification_number,
      sign_date: data.sign_date || null,
      readiness_period: data.readiness_period || null,
      status: "draft",
    })
    .select("id, specification_number")
    .single();

  if (error) throw error;
  return spec;
}

export async function updateSpecification(
  specId: string,
  updates: Record<string, unknown>
) {
  const supabase = await createClient();

  const { error } = await supabase
    .from("specifications")
    .update({ ...updates, updated_at: new Date().toISOString() })
    .eq("id", specId);

  if (error) throw error;
}

export async function uploadSignedScan(specId: string, file: File) {
  const supabase = await createClient();

  const ext = file.name.split(".").pop() ?? "pdf";
  const path = `specifications/${specId}/signed-scan.${ext}`;

  const { error: uploadError } = await supabase.storage
    .from("kvota-documents")
    .upload(path, file, { upsert: true });

  if (uploadError) throw uploadError;

  const { data: urlData } = supabase.storage
    .from("kvota-documents")
    .getPublicUrl(path);

  await updateSpecification(specId, { signed_scan_url: urlData.publicUrl });

  return urlData.publicUrl;
}

export async function confirmSignatureAndCreateDeal(specId: string) {
  const supabase = await createClient();

  // Fetch spec with quote data
  const { data: spec, error: specError } = await supabase
    .from("specifications")
    .select("id, quote_id, organization_id, specification_number, sign_date, signed_scan_url")
    .eq("id", specId)
    .single();

  if (specError || !spec) throw specError ?? new Error("Specification not found");
  if (!spec.signed_scan_url) throw new Error("Signed scan not uploaded");

  // Fetch quote for deal data
  const { data: quote, error: quoteError } = await supabase
    .from("quotes")
    .select("id, total_amount, currency")
    .eq("id", spec.quote_id)
    .single();

  if (quoteError || !quote) throw quoteError ?? new Error("Quote not found");

  // Generate deal number
  const now = new Date();
  const year = now.getFullYear();
  const { count } = await supabase
    .from("deals")
    .select("id", { count: "exact", head: true })
    .gte("created_at", `${year}-01-01`);

  const seq = (count ?? 0) + 1;
  const dealNumber = `DEAL-${year}-${String(seq).padStart(4, "0")}`;

  // Update spec status to signed
  await updateSpecification(specId, { status: "signed" });

  // Create deal
  const { data: deal, error: dealError } = await supabase
    .from("deals")
    .insert({
      specification_id: specId,
      quote_id: spec.quote_id,
      organization_id: spec.organization_id,
      deal_number: dealNumber,
      signed_at: spec.sign_date ?? new Date().toISOString().slice(0, 10),
      total_amount: quote.total_amount,
      currency: quote.currency,
      status: "active",
    })
    .select("id, deal_number")
    .single();

  if (dealError) throw dealError;

  // Update quote workflow status
  await supabase
    .from("quotes")
    .update({ workflow_status: "spec_signed" })
    .eq("id", spec.quote_id);

  return deal;
}

export async function createCustomerContract(data: {
  organization_id: string;
  customer_id: string;
  contract_number: string;
  contract_date: string;
}) {
  const supabase = await createClient();

  const { data: contract, error } = await supabase
    .from("customer_contracts")
    .insert({
      organization_id: data.organization_id,
      customer_id: data.customer_id,
      contract_number: data.contract_number,
      contract_date: data.contract_date,
      status: "active",
    })
    .select("id, contract_number, contract_date, next_specification_number")
    .single();

  if (error) throw error;
  return contract;
}
