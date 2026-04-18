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
// Procurement-unlock request (Phase 5c)
//
// Exported name preserved (requestEditApproval) for minimal cross-commit
// breakage — the React component rename happens in Task 11.
// ---------------------------------------------------------------------------

export async function requestEditApproval(invoiceId: string): Promise<void> {
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
