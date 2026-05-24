"use server";

/**
 * Server Action: POST the proposal JSON to the Python KP renderer and
 * stream the binary PDF back to the browser.
 *
 * Why a custom fetch instead of `apiServerClient`:
 * - `shared/lib/api-server.ts` assumes the response is JSON (it does
 *   `await response.text()` then `JSON.parse`), which would corrupt the
 *   PDF bytes and lose the binary payload.
 * - We forward the same Supabase JWT, hit the same `/api` prefix, and
 *   preserve the standard error envelope on failure — only the success
 *   path differs.
 *
 * The action returns a discriminated union so the calling component can
 * `if (result.ok)` and either trigger the download (success) or surface
 * a toast (failure) without any type-narrowing tricks.
 */

import { createClient } from "@/shared/lib/supabase/server";

import type { KpProposal } from "@/entities/kp-proposal";

const PYTHON_API_URL = process.env.PYTHON_API_URL || "http://localhost:5001";

export interface DownloadOk {
  ok: true;
  /** Base64-encoded PDF bytes — Server Actions can't return a Blob across
   *  the RSC boundary, so we round-trip through base64 and the client
   *  reconstructs a Blob before triggering the download. */
  pdfBase64: string;
}

export interface DownloadErr {
  ok: false;
  code: string;
  message: string;
  requestId?: string;
}

export type DownloadResult = DownloadOk | DownloadErr;

export async function downloadKpPdf(
  proposal: KpProposal,
): Promise<DownloadResult> {
  // REQ-18.1: an unauthenticated visitor must not be able to invoke this
  // — the server-side layout redirects them away from /kp-builder, but
  // verifying the session inside every Server Action is the standard
  // Next.js security posture (see typescript/nextjs.md).
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) {
    return {
      ok: false,
      code: "UNAUTHORIZED",
      message: "Не удалось получить токен сессии",
    };
  }

  let response: Response;
  try {
    response = await fetch(`${PYTHON_API_URL}/api/kp/render-pdf`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(proposal),
    });
  } catch (error) {
    // Server-side log — Server Actions don't bubble fetch errors to the
    // browser, so this is the only signal an operator gets if Python is
    // down or the URL is misconfigured.
    console.error("KP download network error", error);
    return {
      ok: false,
      code: "NETWORK_ERROR",
      message: "Не удалось связаться с сервером",
    };
  }

  const contentType = response.headers.get("content-type") ?? "";

  // Success path: backend returns application/pdf with the bytes.
  if (response.ok && contentType.includes("application/pdf")) {
    const buffer = await response.arrayBuffer();
    // Sanity check: a zero-byte body would still pass content-type but
    // produce a corrupt PDF on the client. Treat as a render failure.
    if (buffer.byteLength === 0) {
      return {
        ok: false,
        code: "RENDER_ERROR",
        message: "Empty PDF response from server",
      };
    }
    // Buffer is available in the Node runtime that hosts Server Actions.
    const pdfBase64 = Buffer.from(buffer).toString("base64");
    return { ok: true, pdfBase64 };
  }

  // Error path: backend returns the standard JSON envelope.
  if (contentType.includes("application/json")) {
    try {
      const body = (await response.json()) as {
        success?: boolean;
        error?: { code?: string; message?: string; request_id?: string };
      };
      const err = body.error ?? {};
      return {
        ok: false,
        code: err.code ?? "UNKNOWN_ERROR",
        message: err.message ?? `HTTP ${response.status}`,
        requestId: err.request_id,
      };
    } catch (error) {
      console.error("KP download JSON parse error", error);
      return {
        ok: false,
        code: "PARSE_ERROR",
        message: `HTTP ${response.status}`,
      };
    }
  }

  // Fallback: unexpected response shape.
  return {
    ok: false,
    code: "UNKNOWN_ERROR",
    message: `HTTP ${response.status}`,
  };
}
