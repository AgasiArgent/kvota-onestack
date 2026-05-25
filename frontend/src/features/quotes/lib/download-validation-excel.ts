import { toast } from "sonner";

/**
 * Download the Validation Excel (.xlsm) file for a quote.
 *
 * Replaces the old `window.open('/export/validation/{id}', '_blank')` flow.
 * That flow opened a new tab regardless of the response status — if the
 * Python API returned a JSON error (401/403/404/500), the new tab rendered
 * raw JSON, which is poor UX.
 *
 * This helper:
 *   1. Fetches `/export/validation/{quoteId}` (the Next.js proxy route,
 *      which forwards to the Python `/api/quotes/{id}/export/validation`
 *      endpoint).
 *   2. On 200: streams bytes into a Blob, derives a filename from the
 *      `Content-Disposition` header (fallback `validation_{id}.xlsm`),
 *      triggers a hidden `<a download>` click, then revokes the object URL.
 *   3. On non-2xx: parses the JSON error envelope and shows a `toast.error`
 *      in the current tab — no new tab opens.
 *   4. On network failure: shows a generic fallback toast.
 *
 * Reused by both `CalculationActionBar` and `ControlActionBar`.
 */
export async function downloadValidationExcel(quoteId: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`/export/validation/${quoteId}`);
  } catch {
    toast.error("Не удалось скачать файл валидации");
    return;
  }

  if (!response.ok) {
    let message = response.statusText || `HTTP ${response.status}`;
    let code: string | null = null;
    try {
      const body = (await response.json()) as {
        error?: string | { code?: string; message?: string };
      };
      if (typeof body.error === "string") {
        message = body.error;
      } else if (body.error) {
        if (body.error.message) message = body.error.message;
        if (typeof body.error.code === "string") code = body.error.code;
      }
    } catch {
      // Body was not JSON — fall back to statusText / HTTP code message above.
    }

    // 409 NO_CALCULATION — the quote has stale `total_amount` but the
    // per-item `quote_calculation_results` rows are missing (CASCADE-cleared
    // after items changed). Show a directive toast that names the next
    // action instead of the generic "Не удалось скачать..." copy. See
    // /tmp/validation-xlsm-investigate-2026-05-25.md.
    if (response.status === 409 && code === "NO_CALCULATION") {
      toast.error(
        "Расчёт не выполнен — нажмите «Рассчитать» перед скачиванием",
      );
      return;
    }

    toast.error(`Не удалось скачать файл валидации: ${message}`);
    return;
  }

  const blob = await response.blob();
  const filename = parseFilename(response.headers.get("Content-Disposition"))
    ?? `validation_${quoteId}.xlsm`;

  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  // Defer revoke so the browser has time to start the download.
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);

  toast.success("Файл валидации скачан");
}

/**
 * Extract `filename` from a Content-Disposition header.
 *
 * Handles both quoted (`filename="foo.xlsm"`) and unquoted
 * (`filename=foo.xlsm`) forms. Returns null when the header is missing or
 * the filename cannot be parsed; the caller falls back to a default.
 */
function parseFilename(header: string | null): string | null {
  if (!header) return null;
  // RFC 6266 filename* (encoded) takes precedence when both are present.
  const encoded = header.match(/filename\*=(?:UTF-8'')?([^;]+)/i);
  if (encoded?.[1]) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      // Malformed encoding — fall through to plain `filename=`.
    }
  }
  const plain = header.match(/filename="?([^";]+)"?/i);
  return plain?.[1] ?? null;
}
