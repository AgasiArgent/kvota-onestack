"use server";

import { createClient } from "@/shared/lib/supabase/server";
import { apiServerClient } from "@/shared/lib/api-server";
import { getSessionUser } from "@/entities/user/server";
import { revalidatePath } from "next/cache";

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
  const user = await getSessionUser();
  if (!user?.orgId) throw new Error("Not authenticated");

  const res = await apiServerClient<{
    deal_id: string;
    deal_number: string;
    logistics_stages: number;
    invoices_created: number;
    invoices_skipped_reason: string | null;
  }>("/deals", {
    method: "POST",
    body: JSON.stringify({
      spec_id: specId,
      user_id: user.id,
      org_id: user.orgId,
    }),
  });

  if (!res.success) {
    throw new Error(res.error?.message || "Failed to create deal");
  }

  revalidatePath("/quotes");

  return res.data;
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
