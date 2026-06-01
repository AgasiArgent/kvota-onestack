import { createClient } from "@/shared/lib/supabase/client";

// ---------------------------------------------------------------------------
// Helper: get auth headers for Python API calls
// ---------------------------------------------------------------------------

async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {};
}

// ---------------------------------------------------------------------------
// VAT rates (admin)
// ---------------------------------------------------------------------------

export async function updateVatRate(
  countryCode: string,
  rate: number,
  notes?: string
): Promise<void> {
  const headers = await getAuthHeaders();

  const res = await fetch("/api/admin/vat-rates", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify({ country_code: countryCode, rate, notes }),
  });

  const json = await res.json();
  if (!res.ok || !json.success) {
    throw new Error(json.error?.message ?? "Failed to update VAT rate");
  }
}

// ---------------------------------------------------------------------------
// Letter draft CRUD
// ---------------------------------------------------------------------------

export async function saveLetterDraft(
  invoiceId: string,
  data: {
    recipient_email: string;
    subject: string;
    body_text: string;
    language?: string;
  }
): Promise<void> {
  const headers = await getAuthHeaders();

  const res = await fetch(`/api/invoices/${invoiceId}/letter-draft`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(data),
  });

  const json = await res.json();
  if (!res.ok || !json.success) {
    throw new Error(json.error?.message ?? "Failed to save draft");
  }
}

export async function sendLetterDraft(invoiceId: string): Promise<void> {
  const headers = await getAuthHeaders();

  const res = await fetch(`/api/invoices/${invoiceId}/letter-draft/send`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  });

  const json = await res.json();
  if (!res.ok || !json.success) {
    throw new Error(json.error?.message ?? "Failed to send draft");
  }
}

export async function deleteLetterDraft(
  invoiceId: string,
  draftId: string
): Promise<void> {
  const headers = await getAuthHeaders();

  const res = await fetch(
    `/api/invoices/${invoiceId}/letter-draft/${draftId}`,
    {
      method: "DELETE",
      headers,
    }
  );

  const json = await res.json();
  if (!res.ok || !json.success) {
    throw new Error(json.error?.message ?? "Failed to delete draft");
  }
}

// ---------------------------------------------------------------------------
// XLS download
// ---------------------------------------------------------------------------

export async function downloadInvoiceXls(
  invoiceId: string,
  language: string = "ru"
): Promise<void> {
  const headers = await getAuthHeaders();

  const res = await fetch(`/api/invoices/${invoiceId}/download-xls`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify({ language }),
  });

  if (!res.ok) {
    const json = await res.json().catch(() => null);
    throw new Error(
      json?.error?.message ?? `Download failed (HTTP ${res.status})`
    );
  }

  // Trigger browser download from response blob
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  const filenameMatch = disposition?.match(/filename="?([^"]+)"?/);
  const filename = filenameMatch?.[1] ?? `invoice-${invoiceId}.xlsx`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// XLS import (Testing 2 row 70)
//
// Counterpart of `downloadInvoiceXls`: clients edit the downloaded XLS offline
// and re-upload it through «Загрузить XLS». The server matches rows back to
// `invoice_items` by `idn_sku` and updates the supplier-side fields.
//
// Returns the structured summary so the caller can toast both the count of
// updated rows and the list of articles that were not found in the КПП.
// Throws on any error — duplicate articles surface as a generic Error with
// the server's "Дубликаты артикулов: ..." message so the toast renders it
// verbatim.
// ---------------------------------------------------------------------------

export interface UploadInvoiceXlsResult {
  updated: number;
  skipped: string[];
  total_in_file: number;
}

export async function uploadInvoiceXls(
  invoiceId: string,
  file: File
): Promise<UploadInvoiceXlsResult> {
  const headers = await getAuthHeaders();

  const formData = new FormData();
  formData.append("file", file);

  // NOTE: do NOT set Content-Type manually here — the browser must add the
  // multipart boundary itself, otherwise Starlette's form parser can't read
  // the file. `getAuthHeaders()` only returns Authorization, which is safe.
  const res = await fetch(`/api/invoices/${invoiceId}/import-xls`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    let serverMessage: string | undefined;
    try {
      const json = (await res.json()) as { error?: { message?: string } };
      serverMessage = json?.error?.message;
    } catch {
      // Body unparseable — fall through to the HTTP-status fallback below.
    }
    throw new Error(serverMessage ?? `Upload failed (HTTP ${res.status})`);
  }

  const json = (await res.json()) as {
    success: boolean;
    data: UploadInvoiceXlsResult;
  };
  return json.data;
}

// ---------------------------------------------------------------------------
// Procurement-unlock request (Phase 5c)
//
// Name matches the backend route (/procurement-unlock-request). Phase 4a
// previously used /edit-approval — the old export name `requestEditApproval`
// has been renamed to `requestProcurementUnlock` to keep the contract obvious.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Mark invoice as sent to supplier
//
// Manual analogue of the letter-draft/send flow: stamps `sent_at = NOW()`
// directly on the invoice without going through the email composer. Used
// by the «Отправлено поставщику» button in InvoiceCard so procurement can
// progress the kanban (Phase B auto-advance to «Ожидание цен») without
// relying on the email pipeline.
// ---------------------------------------------------------------------------

export async function markInvoiceSent(invoiceId: string): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase
    .from("invoices")
    .update({ sent_at: new Date().toISOString() })
    .eq("id", invoiceId);
  if (error) throw error;
}

export async function requestProcurementUnlock(invoiceId: string): Promise<void> {
  const headers = await getAuthHeaders();

  const res = await fetch(`/api/invoices/${invoiceId}/procurement-unlock-request`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    // Send a valid empty JSON body — fasthtml's request middleware parses
    // application/json content-type before the handler runs and throws a
    // JSONDecodeError on empty body, bypassing the handler's optional-body
    // try/except. Sending {} keeps the contract honest.
    body: JSON.stringify({}),
  });

  const json = await res.json();
  if (!res.ok || !json.success) {
    throw new Error(json.error?.message ?? "Failed to request procurement-unlock approval");
  }
}

// ---------------------------------------------------------------------------
// Supplier-offer file («Файл КП поставщика»)
//
// Optional at create AND edit, but MANDATORY to finish procurement (the
// backend complete-procurement gate enforces that — see api/invoices.py,
// MISSING_SUPPLIER_FILE / 422). Storage write is a simple single-table
// effect, so per `.claude/rules/api-first.md` it stays Supabase-direct,
// mirroring the customer-document upload pattern
// (entities/customer/mutations.ts).
//
// The file lands in the shared `kvota-documents` bucket at
// `invoices/{invoiceId}/{uuid}.{ext}`, and the public URL is persisted on
// `invoices.invoice_file_url` (existing column — no migration). On the CREATE
// flow the invoice id only exists after `createInvoice`, so the modal stages
// the picked File and calls this AFTER creation; on EDIT the card calls it
// immediately on pick.
// ---------------------------------------------------------------------------

const SUPPLIER_FILE_BUCKET = "kvota-documents";

function supplierFileStoragePath(invoiceId: string, file: File): string {
  const ext = file.name.split(".").pop()?.toLowerCase() || "bin";
  return `invoices/${invoiceId}/${crypto.randomUUID()}.${ext}`;
}

/**
 * Uploads the supplier-offer file for an invoice and stores its public URL on
 * `invoices.invoice_file_url`. Returns the persisted URL. Cleans up the
 * orphaned storage object if the metadata update fails.
 */
export async function uploadSupplierOfferFile(
  invoiceId: string,
  file: File
): Promise<string> {
  const supabase = createClient();
  const storagePath = supplierFileStoragePath(invoiceId, file);

  const { error: uploadError } = await supabase.storage
    .from(SUPPLIER_FILE_BUCKET)
    .upload(storagePath, file, { upsert: false });
  if (uploadError) {
    if (
      uploadError.message?.includes("size") ||
      uploadError.message?.includes("limit")
    ) {
      const sizeMb = Math.round(file.size / 1024 / 1024);
      throw new Error(`Файл слишком большой (${sizeMb} МБ). Максимум: 50 МБ`);
    }
    throw new Error(`Ошибка загрузки: ${uploadError.message}`);
  }

  const {
    data: { publicUrl },
  } = supabase.storage.from(SUPPLIER_FILE_BUCKET).getPublicUrl(storagePath);

  const { error: updateError } = await supabase
    .from("invoices")
    .update({ invoice_file_url: publicUrl })
    .eq("id", invoiceId);
  if (updateError) {
    // Roll back the orphaned object so a failed PATCH does not leak files.
    await supabase.storage.from(SUPPLIER_FILE_BUCKET).remove([storagePath]);
    throw updateError;
  }

  return publicUrl;
}

/**
 * Clears the supplier-offer file from an invoice. Removes the storage object
 * (best-effort — a missing object must not block clearing the column) then
 * nulls `invoices.invoice_file_url`.
 */
export async function removeSupplierOfferFile(
  invoiceId: string,
  fileUrl: string
): Promise<void> {
  const supabase = createClient();

  // Derive the storage path from the public URL. getPublicUrl produces
  // `.../object/public/{bucket}/{path}`; we slice off everything up to and
  // including the bucket segment to recover `{path}`.
  const marker = `/${SUPPLIER_FILE_BUCKET}/`;
  const markerAt = fileUrl.indexOf(marker);
  if (markerAt !== -1) {
    const storagePath = decodeURIComponent(
      fileUrl.slice(markerAt + marker.length)
    );
    const { error: storageError } = await supabase.storage
      .from(SUPPLIER_FILE_BUCKET)
      .remove([storagePath]);
    if (storageError) {
      console.warn(
        "[removeSupplierOfferFile] storage remove failed:",
        storageError.message
      );
    }
  }

  const { error } = await supabase
    .from("invoices")
    .update({ invoice_file_url: null })
    .eq("id", invoiceId);
  if (error) throw error;
}
