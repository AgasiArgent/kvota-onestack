/**
 * Pure helpers for the Task 23 QA verify-buttons UI.
 *
 * Isolated so behaviour is testable without a DOM (the frontend workspace
 * ships no jsdom). The button row component orchestrates toasts + mutations
 * on top of these.
 *
 * Reqs: 9.1 (INSERT shape), 9.2 (append-only RLS), 9.3 (latest per pin
 * drives node status), 8.7/Req 8 note 7 (training pins: no verify buttons).
 */

import {
  canRecordVerification,
  type JourneyNodeId,
  type JourneyPin,
  type JourneyVerification,
  type QaStatus,
  type RoleSlug,
  type VerifyResult,
} from "@/entities/journey";

// ---------------------------------------------------------------------------
// Payload construction
// ---------------------------------------------------------------------------

/**
 * Shape accepted by `createVerification` in `entities/journey/queries.ts` —
 * omits DB-default columns (`id`, `tested_at`).
 */
export interface VerificationInsert {
  readonly pin_id: string;
  readonly node_id: JourneyNodeId;
  readonly result: VerifyResult;
  readonly note: string | null;
  readonly attachment_urls: readonly string[] | null;
  readonly tested_by: string;
}

export interface BuildVerificationPayloadInput {
  readonly pinId: string;
  readonly nodeId: JourneyNodeId;
  readonly result: VerifyResult;
  /** Optional — trimmed; empty/whitespace becomes `null`. */
  readonly note?: string | null;
  readonly testedBy: string;
  /**
   * Task 24: Supabase Storage object keys for up to 3 screenshots. When
   * omitted or empty, the payload stores `null` (no attachments). The UI
   * uploads files first via `uploadAttachments` and only on success does
   * it pass the returned paths here — partial attachment is not permitted
   * (Req 9.6).
   */
  readonly attachmentUrls?: readonly string[] | null;
}

export function buildVerificationPayload(
  input: BuildVerificationPayloadInput,
): VerificationInsert {
  const { pinId, nodeId, result, note, testedBy, attachmentUrls } = input;
  const trimmed =
    typeof note === "string" && note.trim().length > 0 ? note.trim() : null;
  const attachments =
    Array.isArray(attachmentUrls) && attachmentUrls.length > 0
      ? attachmentUrls
      : null;
  return {
    pin_id: pinId,
    node_id: nodeId,
    result,
    note: trimmed,
    attachment_urls: attachments,
    tested_by: testedBy,
  };
}

// ---------------------------------------------------------------------------
// Error classification
// ---------------------------------------------------------------------------

export type VerifyErrorKind =
  | "PERMISSION_DENIED"
  | "APPEND_ONLY_VIOLATION"
  | "GENERIC_ERROR";

export interface VerifyErrorInfo {
  readonly kind: VerifyErrorKind;
  readonly userMessage: string;
}

interface MaybePgError {
  readonly code?: string;
  readonly message?: string;
}

export function classifyVerifyError(err: unknown): VerifyErrorInfo {
  if (err === null || err === undefined) {
    return {
      kind: "GENERIC_ERROR",
      userMessage: "Не удалось записать верификацию. Попробуйте ещё раз.",
    };
  }
  const e = err as MaybePgError;
  const code = e.code ?? "";
  const message = (e.message ?? "").toLowerCase();

  // Defensive: UPDATE / DELETE denials shouldn't reach the wire from the UI
  // (we never emit those), but if something (a rogue caller, a stale row
  // with a Supabase upsert shape) does, we surface the append-only nature.
  if (
    message.includes("update") && message.includes("permission denied") ||
    message.includes("delete") && message.includes("permission denied")
  ) {
    return {
      kind: "APPEND_ONLY_VIOLATION",
      userMessage:
        "Верификации нельзя править или удалять — запишите новую.",
    };
  }

  if (
    code === "42501" ||
    message.includes("row-level security") ||
    message.includes("permission denied")
  ) {
    return {
      kind: "PERMISSION_DENIED",
      userMessage: "Недостаточно прав для записи верификации.",
    };
  }

  return {
    kind: "GENERIC_ERROR",
    userMessage:
      e.message && e.message.length > 0
        ? e.message
        : "Не удалось записать верификацию. Попробуйте ещё раз.",
  };
}

// ---------------------------------------------------------------------------
// Visibility gate
// ---------------------------------------------------------------------------

/**
 * True iff the verify-button row should render for this pin + user.
 *
 * - Training-mode pins never get verify buttons (Req 8 note 7).
 * - QA pins require the user to hold a role in `VERIFICATION_WRITERS`.
 */
export function shouldShowVerifyButtons(
  pin: JourneyPin,
  userRoles: readonly RoleSlug[],
): boolean {
  if (pin.mode !== "qa") return false;
  return canRecordVerification(userRoles);
}

// ---------------------------------------------------------------------------
// Node-level derivation (Req 9.3)
// ---------------------------------------------------------------------------

/**
 * Derive a node's `qa_status` from the latest verification per pin.
 *
 *   - Any pin whose latest is `broken` → `'broken'`.
 *   - Else, every pin latest is `verified` and at least one exists → `'verified'`.
 *   - Else (no pins, or any `skip`) → `'untested'`.
 *
 * The backend-returned `qa_status` remains authoritative; this helper exists
 * for future client-side optimistic UI (Tasks 32/33) and for a dev-mode
 * consistency check.
 */
export function deriveNodeQaStatus(
  verificationsByPin: Readonly<Record<string, JourneyVerification>>,
): QaStatus {
  const values = Object.values(verificationsByPin);
  if (values.length === 0) return "untested";
  let allVerified = true;
  for (const v of values) {
    if (v.result === "broken") return "broken";
    if (v.result !== "verified") allVerified = false;
  }
  return allVerified ? "verified" : "untested";
}
