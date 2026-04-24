/**
 * Centralized error-message extraction for use in toast/log calls.
 *
 * Handles the five error shapes that show up in OneStack's frontend:
 *
 *   1. Supabase PostgrestError — has `code` + `message`, plus optional
 *      `details` / `hint`. These carry the root cause for RLS rejections
 *      and DB-constraint violations (e.g. "permission denied for table X").
 *   2. Fetch-response envelope — `{success: false, error: {code, message}}`,
 *      per the project's api-first.md rule.
 *   3. Native `Error` — `err instanceof Error`, common for thrown strings
 *      wrapped via `new Error(...)`.
 *   4. Plain string — occasionally passed directly to `.catch(string)` flows.
 *   5. Anything else — null, undefined, objects without a usable message.
 *
 * Pure: no console/toast side effects.
 */
export function extractErrorMessage(err: unknown): string | null {
  // 4. String
  if (typeof err === "string") {
    const trimmed = err.trim();
    return trimmed.length > 0 ? trimmed : null;
  }

  // 3. Native Error (checked before duck-typed shapes to prefer the real
  // prototype message over any fields an Error subclass might add).
  if (err instanceof Error) {
    return normalizeWhitespace(err.message) || null;
  }

  if (!err || typeof err !== "object") {
    return null;
  }

  const obj = err as Record<string, unknown>;

  // 1. Supabase PostgrestError — has both `code` and `message`. Append
  // `details` or `hint` when available to surface the specifics (e.g.
  // "duplicate key value violates unique constraint (Key ...)").
  if (
    "code" in obj &&
    "message" in obj &&
    typeof obj.message === "string" &&
    obj.message.length > 0
  ) {
    const base = obj.message;
    const extra =
      typeof obj.details === "string" && obj.details.trim().length > 0
        ? obj.details
        : typeof obj.hint === "string" && obj.hint.trim().length > 0
          ? obj.hint
          : null;
    const combined = extra ? `${base} (${extra})` : base;
    return normalizeWhitespace(combined);
  }

  // 2. Fetch-response error shape: {success: false, error: {code, message}}.
  // The outer object is the parsed JSON body; `error.message` is the field
  // the api-first contract requires. We don't demand `success: false` here —
  // any nested `error.message` is enough to treat as a response error.
  if ("error" in obj && obj.error && typeof obj.error === "object") {
    const errorObj = obj.error as Record<string, unknown>;
    if (
      typeof errorObj.message === "string" &&
      errorObj.message.trim().length > 0
    ) {
      return normalizeWhitespace(errorObj.message);
    }
  }

  return null;
}

function normalizeWhitespace(s: string): string {
  return s.replace(/\s+/g, " ").trim();
}
