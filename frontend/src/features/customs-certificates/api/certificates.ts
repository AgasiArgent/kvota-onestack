"use client";

/**
 * Typed wrappers for the certificates CRUD endpoints (Phase B Task 5).
 *
 * Every wrapper returns `ApiResponse<T>` per the project envelope —
 * callers MUST check `success` before reading `data` (see `@/shared/types/api`).
 *
 * Endpoint reference (`api/customs.py` + `api/routers/customs.py`):
 *   POST   /api/customs/certificates                          → create
 *   GET    /api/customs/certificates?quote_id={uuid}          → list
 *   PATCH  /api/customs/certificates/{cert_id}                → update fields
 *   POST   /api/customs/certificates/{cert_id}/items          → attach item
 *   DELETE /api/customs/certificates/{cert_id}/items/{id}     → detach item
 *   DELETE /api/customs/certificates/{cert_id}                → cascade delete
 *
 * Auth: handled by `apiClient` — the active Supabase JWT is forwarded as
 * `Authorization: Bearer <token>` (see `@/shared/lib/api`).
 */
import { apiClient } from "@/shared/lib/api";

import type {
  ApiResponse,
  Certificate,
  CreateCertificateInput,
  DeleteCertificateData,
  ListCertificatesData,
  UpdateCertificateInput,
} from "../model/types";

/**
 * Create a certificate row + N item attachments atomically.
 *
 * Server-side error codes (per `create_certificate_handler`):
 *   - 400 VALIDATION_ERROR — bad body / cost_rub negative / missing fields
 *   - 401 UNAUTHORIZED / 403 FORBIDDEN — auth / role gate
 *   - 404 NOT_FOUND — quote or attached item missing
 *   - 422 NOT_IN_QUOTE — `item_ids[]` from a different quote
 *   - 500 INTERNAL — DB write failure (rollback applied server-side)
 *
 * Returns the freshly inserted `Certificate` with its computed
 * `attached_items[]` payload.
 */
export function createCertificate(
  input: CreateCertificateInput,
): Promise<ApiResponse<Certificate>> {
  return apiClient<Certificate>("/customs/certificates", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/**
 * Update the editable FIELDS of an existing certificate (fields-only —
 * positions are managed separately via attach/detach). Only the keys present
 * in `input` are written; absent keys are left untouched server-side.
 *
 * Server-side error codes (per `update_certificate_handler`):
 *   - 400 VALIDATION_ERROR — bad body / cost negative / bad currency
 *   - 401 UNAUTHORIZED / 403 FORBIDDEN — auth / role gate
 *   - 404 NOT_FOUND — cert missing or in a different org
 *   - 500 INTERNAL — DB write failure
 *
 * Returns the updated `Certificate` with recomputed `attached_items[]`
 * (shares are re-derived when the cost changes).
 */
export function updateCertificate(
  certId: string,
  input: UpdateCertificateInput,
): Promise<ApiResponse<Certificate>> {
  const path = `/customs/certificates/${encodeURIComponent(certId)}`;
  return apiClient<Certificate>(path, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

/**
 * List all certificates (and "Свой расход" rows) attached to a quote.
 *
 * Sorted `created_at DESC` server-side; per-cert `attached_items[]` is
 * pre-computed via `services.cost_split.split_cost_batch` so the UI can
 * render shares without recomputation.
 *
 * Server-side error codes:
 *   - 400 VALIDATION_ERROR — missing quote_id
 *   - 401 / 403 — auth / role gate
 *   - 404 NOT_FOUND — quote missing or in a different org
 */
export function listCertificates(
  quoteId: string,
): Promise<ApiResponse<ListCertificatesData>> {
  const qs = `?quote_id=${encodeURIComponent(quoteId)}`;
  return apiClient<ListCertificatesData>(`/customs/certificates${qs}`, {
    method: "GET",
  });
}

/**
 * Attach a single quote-item to an existing certificate; server returns
 * the cert with recomputed `attached_items[]` shares.
 *
 * Server-side error codes:
 *   - 400 VALIDATION_ERROR — missing item_id
 *   - 401 / 403 — auth / role gate
 *   - 404 NOT_FOUND — cert or item missing
 *   - 409 CONFLICT — item already attached (UNIQUE constraint)
 *   - 422 NOT_IN_QUOTE — item belongs to a different quote
 */
export function attachCertificateItem(
  certId: string,
  itemId: string,
): Promise<ApiResponse<Certificate>> {
  const path = `/customs/certificates/${encodeURIComponent(certId)}/items`;
  return apiClient<Certificate>(path, {
    method: "POST",
    body: JSON.stringify({ item_id: itemId }),
  });
}

/**
 * Detach a single quote-item from a certificate; server returns the cert
 * with recomputed `attached_items[]` (may be empty if this was the last
 * attachment).
 *
 * Server-side error codes:
 *   - 401 / 403 — auth / role gate
 *   - 404 NOT_FOUND — cert or attachment missing
 */
export function detachCertificateItem(
  certId: string,
  itemId: string,
): Promise<ApiResponse<Certificate>> {
  const path =
    `/customs/certificates/${encodeURIComponent(certId)}` +
    `/items/${encodeURIComponent(itemId)}`;
  return apiClient<Certificate>(path, { method: "DELETE" });
}

/**
 * Delete a certificate; the FK `ON DELETE CASCADE` on
 * `quote_certificate_items` removes its attachments in the same statement.
 *
 * Server-side error codes:
 *   - 401 / 403 — auth / role gate
 *   - 404 NOT_FOUND — cert missing or in a different org
 */
export function deleteCertificate(
  certId: string,
): Promise<ApiResponse<DeleteCertificateData>> {
  const path = `/customs/certificates/${encodeURIComponent(certId)}`;
  return apiClient<DeleteCertificateData>(path, { method: "DELETE" });
}
