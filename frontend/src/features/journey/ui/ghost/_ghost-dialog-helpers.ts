/**
 * Pure helpers shared by the ghost CRUD dialogs — payload construction and
 * error classification. Split out of the UI components so behaviour is
 * testable without a DOM (the frontend workspace ships no jsdom).
 */

import type {
  GhostStatus,
  JourneyGhostNode,
  JourneyNodeId,
} from "@/entities/journey";

// ---------------------------------------------------------------------------
// Payload
// ---------------------------------------------------------------------------

/** Inputs collected by the create dialog form. */
export interface GhostPayloadInput {
  readonly title: string;
  readonly slug: string;
  readonly cluster: string | null;
  readonly proposed_route: string | null;
  readonly status: GhostStatus;
  readonly planned_in: string | null;
  readonly created_by: string;
}

/**
 * Build the row payload accepted by `createGhost` in `entities/journey/queries.ts`.
 *
 * `node_id` is derived from the validated slug; other optional fields default
 * to `null` so the Supabase insert matches the table's nullable columns.
 */
export function buildGhostPayload(
  input: GhostPayloadInput
): Omit<JourneyGhostNode, "id" | "created_at"> {
  return {
    node_id: (`ghost:${input.slug}` as JourneyNodeId),
    proposed_route: input.proposed_route,
    title: input.title,
    planned_in: input.planned_in,
    assignee: null,
    parent_node_id: null,
    cluster: input.cluster,
    status: input.status,
    created_by: input.created_by,
  };
}

// ---------------------------------------------------------------------------
// Error classification
// ---------------------------------------------------------------------------

export type GhostWriteErrorKind =
  | "SLUG_COLLISION"
  | "PERMISSION_DENIED"
  | "UNKNOWN";

export interface GhostWriteErrorInfo {
  readonly kind: GhostWriteErrorKind;
  readonly userMessage: string;
}

interface MaybePgError {
  readonly code?: string;
  readonly message?: string;
}

/**
 * Classify a Supabase / PostgREST error returned from a ghost CUD operation.
 *
 * The classification uses the Postgres error code when available and falls
 * back to message-string matching for PostgREST-wrapped errors.
 */
export function classifyGhostWriteError(
  err: unknown
): GhostWriteErrorInfo {
  if (err === null || err === undefined) {
    return {
      kind: "UNKNOWN",
      userMessage: "Не удалось выполнить операцию. Попробуйте ещё раз.",
    };
  }

  const e = err as MaybePgError;
  const code = e.code ?? "";
  const message = (e.message ?? "").toLowerCase();

  if (code === "23505" || message.includes("duplicate key")) {
    return {
      kind: "SLUG_COLLISION",
      userMessage: "Слаг занят, измените заголовок или введите другой слаг.",
    };
  }

  if (
    code === "42501" ||
    message.includes("row-level security") ||
    message.includes("permission denied")
  ) {
    return {
      kind: "PERMISSION_DENIED",
      userMessage: "Недостаточно прав для выполнения операции.",
    };
  }

  return {
    kind: "UNKNOWN",
    userMessage:
      e.message && e.message.length > 0
        ? e.message
        : "Не удалось выполнить операцию. Попробуйте ещё раз.",
  };
}
