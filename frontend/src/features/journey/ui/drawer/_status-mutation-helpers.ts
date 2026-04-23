/**
 * Pure helpers supporting `StatusSection` (Task 19).
 *
 * Isolated from the component so they can be unit-tested with plain Vitest
 * (the frontend workspace has no jsdom). All three helpers are side-effect
 * free — toasts are fired by the component based on the classification the
 * helper returns.
 *
 * Reqs: 5.5 (inline edit builds PATCH body), 6.2 (409 STALE_VERSION handling),
 * 6.3 (403 FORBIDDEN_FIELD handling), 6.4–6.5 (field-level ACL).
 */

import {
  canEditImpl,
  canEditNotes,
  canEditQa,
} from "@/entities/journey";
import type {
  ImplStatus,
  JourneyNodeDetail,
  QaStatus,
  RoleSlug,
} from "@/entities/journey";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type StatusField = "impl_status" | "qa_status" | "notes";

/**
 * The shape mirrors `JourneyStatePatch` in `entities/journey/mutations.ts` —
 * we rebuild it here rather than importing so the serialization contract
 * (omit-undefined, preserve-null) has its own test surface.
 */
export interface StatusPatchBody {
  readonly version: number;
  readonly impl_status?: ImplStatus | null;
  readonly qa_status?: QaStatus | null;
  readonly notes?: string | null;
}

export interface BuildPatchInput {
  readonly currentVersion: number;
  readonly changes: {
    readonly impl_status?: ImplStatus | null;
    readonly qa_status?: QaStatus | null;
    readonly notes?: string | null;
  };
}

/**
 * Discriminated union describing what the UI should do after a mutation
 * fails. Emitted by `handleStatusMutationError` so the component can choose
 * the right toast copy + cache strategy without duplicating the classification
 * in the component body.
 */
export type StatusMutationErrorKind =
  | {
      readonly kind: "refresh-and-retry";
      /** Server-returned authoritative row — already seeded into cache by the mutation hook. */
      readonly serverState: JourneyNodeDetail;
    }
  | {
      readonly kind: "no-permission";
      readonly field: StatusField | null;
    }
  | {
      readonly kind: "generic";
    };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build a PATCH body from the user's field-level changes. Only includes keys
 * the user actually touched so the backend ACL check stays field-scoped
 * (Req 6.4–6.5). Explicit `null` is preserved — it is the signal to clear a
 * field.
 */
export function buildOptimisticPatch(input: BuildPatchInput): StatusPatchBody {
  const body: Record<string, unknown> = { version: input.currentVersion };
  if (input.changes.impl_status !== undefined) {
    body.impl_status = input.changes.impl_status;
  }
  if (input.changes.qa_status !== undefined) {
    body.qa_status = input.changes.qa_status;
  }
  if (input.changes.notes !== undefined) {
    body.notes = input.changes.notes;
  }
  return body as unknown as StatusPatchBody;
}

type RawError = Error & {
  code?: string;
  status?: number;
  data?: unknown;
};

/**
 * Classify a thrown error from `useUpdateNodeState` into one of three
 * UI-actionable kinds. The mutation hook has already applied the right
 * cache strategy (seed with server state on 409, rollback on everything
 * else) — this helper only decides what toast to show.
 */
export function handleStatusMutationError(err: unknown): StatusMutationErrorKind {
  const e = err as RawError;
  const code = e?.code;

  if (code === "STALE_VERSION") {
    const data = e?.data as { current?: JourneyNodeDetail } | undefined;
    if (data && typeof data === "object" && data.current) {
      return { kind: "refresh-and-retry", serverState: data.current };
    }
    // Malformed 409 payload — treat like generic so rollback is honoured.
    return { kind: "generic" };
  }

  if (code === "FORBIDDEN_FIELD") {
    const data = e?.data as { field?: string } | undefined;
    const field = data?.field;
    if (field === "impl_status" || field === "qa_status" || field === "notes") {
      return { kind: "no-permission", field };
    }
    return { kind: "no-permission", field: null };
  }

  return { kind: "generic" };
}

/**
 * Thin adapter over `entities/journey/access.ts`. Keeps field-name knowledge
 * in one place so the component body stays declarative.
 */
export function canEditField(
  field: StatusField,
  heldRoles: readonly RoleSlug[]
): boolean {
  switch (field) {
    case "impl_status":
      return canEditImpl(heldRoles);
    case "qa_status":
      return canEditQa(heldRoles);
    case "notes":
      return canEditNotes(heldRoles);
  }
}

/**
 * Human-readable Russian field name for toast messages (Req 6.3).
 */
export function statusFieldLabelRu(field: StatusField | null): string {
  switch (field) {
    case "impl_status":
      return "Реализация";
    case "qa_status":
      return "QA";
    case "notes":
      return "Заметки";
    default:
      return "поле";
  }
}
