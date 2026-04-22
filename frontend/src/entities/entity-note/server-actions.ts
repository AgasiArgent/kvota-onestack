"use server";

import { revalidatePath } from "next/cache";
import { apiServerClient } from "@/shared/lib/api-server";
import { getSessionUser } from "@/entities/user";

/**
 * entity-note Server Actions — thin wrappers over Python API.
 *
 * Conventions (project-wide, do not diverge):
 *   - apiServerClient is a FUNCTION, not an object with .post/.patch/etc.
 *     Call shape: apiServerClient<T>(path, { method, body }).
 *   - Paths have NO /api/ prefix — client adds it.
 *   - Response has {success, data?, error?}. Always check `success` —
 *     Python API returns {success:false, error} with HTTP 200 on business
 *     errors. Never rely on HTTP status alone.
 *   - DELETE sends no body (client has hasBody check internally).
 *
 * Revalidation mapping:
 *   entity_type="quote"    → /quotes/{entity_id}
 *   entity_type="customer" → /customers/{entity_id}
 *   entity_type="invoice"  → NO default; caller MUST pass revalidate_path
 *                            (e.g. /quotes/{parent_quote_id}) because
 *                            invoices don't have a standalone route.
 */

export type EntityNoteEntityType = "quote" | "customer" | "invoice";

function defaultRevalidatePath(
  entityType: EntityNoteEntityType,
  entityId: string,
): string | null {
  if (entityType === "quote") return `/quotes/${entityId}`;
  if (entityType === "customer") return `/customers/${entityId}`;
  return null; // invoice: caller-provided only
}

function doRevalidate(
  entityType: EntityNoteEntityType,
  entityId: string,
  explicit?: string,
  extra?: string[],
) {
  if (explicit) {
    revalidatePath(explicit);
  } else {
    const def = defaultRevalidatePath(entityType, entityId);
    if (def) revalidatePath(def);
  }
  extra?.forEach((p) => revalidatePath(p));
}

export async function createEntityNote(input: {
  entity_type: EntityNoteEntityType;
  entity_id: string;
  body: string;
  visible_to: string[];
  /**
   * Path to revalidate after mutation.
   * REQUIRED when entity_type="invoice" (invoices have no own route —
   * pass parent quote path, e.g. "/quotes/{quote_id}").
   * Optional for quote/customer (defaults applied).
   */
  revalidate_path?: string;
  /** Additional paths to revalidate (beyond the primary one). */
  revalidate_extra?: string[];
}): Promise<{ note_id: string }> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  if (input.entity_type === "invoice" && !input.revalidate_path) {
    throw new Error(
      "createEntityNote: revalidate_path is required when entity_type='invoice'",
    );
  }

  const res = await apiServerClient<{ note_id: string }>("/notes", {
    method: "POST",
    body: JSON.stringify({
      entity_type: input.entity_type,
      entity_id: input.entity_id,
      body: input.body,
      visible_to: input.visible_to,
    }),
  });

  if (!res.success) {
    throw new Error(res.error?.message ?? "Failed to create note");
  }

  doRevalidate(
    input.entity_type,
    input.entity_id,
    input.revalidate_path,
    input.revalidate_extra,
  );

  return res.data!;
}

export async function updateEntityNote(input: {
  note_id: string;
  entity_type: EntityNoteEntityType;
  entity_id: string;
  patch: Partial<{ body: string; pinned: boolean; visible_to: string[] }>;
  /** See createEntityNote.revalidate_path. */
  revalidate_path?: string;
  revalidate_extra?: string[];
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  if (input.entity_type === "invoice" && !input.revalidate_path) {
    throw new Error(
      "updateEntityNote: revalidate_path is required when entity_type='invoice'",
    );
  }

  const body: Record<string, unknown> = {};
  if (input.patch.body !== undefined) body.body = input.patch.body;
  if (input.patch.pinned !== undefined) body.pinned = input.patch.pinned;
  if (input.patch.visible_to !== undefined) body.visible_to = input.patch.visible_to;

  const res = await apiServerClient(`/notes/${input.note_id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

  if (!res.success) {
    throw new Error(res.error?.message ?? "Failed to update note");
  }

  doRevalidate(
    input.entity_type,
    input.entity_id,
    input.revalidate_path,
    input.revalidate_extra,
  );
}

export async function deleteEntityNote(input: {
  note_id: string;
  entity_type: EntityNoteEntityType;
  entity_id: string;
  /** See createEntityNote.revalidate_path. */
  revalidate_path?: string;
  revalidate_extra?: string[];
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  if (input.entity_type === "invoice" && !input.revalidate_path) {
    throw new Error(
      "deleteEntityNote: revalidate_path is required when entity_type='invoice'",
    );
  }

  const res = await apiServerClient(`/notes/${input.note_id}`, {
    method: "DELETE",
  });

  if (!res.success) {
    throw new Error(res.error?.message ?? "Failed to delete note");
  }

  doRevalidate(
    input.entity_type,
    input.entity_id,
    input.revalidate_path,
    input.revalidate_extra,
  );
}
