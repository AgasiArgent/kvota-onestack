import "server-only";
import { apiServerClient } from "@/shared/lib/api-server";
import type { EntityNoteCardData } from "./ui/entity-note-card";
import type { EntityNoteEntityType } from "./server-actions";

/**
 * entity-note server reads — called from Server Components to seed
 * EntityNotesPanel with initialNotes.
 *
 * API: GET /api/notes?entity_type=<t>&entity_id=<id>
 * RLS (m291) handles visibility; this helper just shapes the response.
 * Returns [] on any failure — notes panels must stay usable even if the
 * Python API is degraded.
 */

interface RawNoteRow {
  id: string;
  body: string;
  pinned: boolean | null;
  /** DB column on ``kvota.entity_notes``. Source of truth for author identity. */
  author_id: string;
  /** Joined from ``auth.users`` by the Python API (see api/notes.py). */
  author_name: string | null;
  author_email: string | null;
  author_avatar_url: string | null;
  author_role: string | null;
  visible_to: string[] | null;
  created_at: string;
}

function mapRow(r: RawNoteRow): EntityNoteCardData {
  // ``author.id`` MUST be a non-empty string — the avatar chip's hash
  // function blows up on undefined and tears down the whole customer
  // profile. Fall back to the row id so rendering stays safe even if a
  // historical note has a stale author_id.
  const safeAuthorId = r.author_id ?? r.id;
  return {
    id: r.id,
    body: r.body,
    pinned: !!r.pinned,
    authorRole: r.author_role ?? "",
    author: {
      id: safeAuthorId,
      name: r.author_name ?? "",
      email: r.author_email ?? undefined,
      avatarUrl: r.author_avatar_url,
    },
    visibleTo: r.visible_to ?? ["*"],
    createdAt: r.created_at,
  };
}

export async function fetchEntityNotes(
  entityType: EntityNoteEntityType,
  entityId: string,
): Promise<EntityNoteCardData[]> {
  try {
    const res = await apiServerClient<RawNoteRow[]>(
      `/notes?entity_type=${encodeURIComponent(entityType)}&entity_id=${encodeURIComponent(entityId)}`,
      { method: "GET" },
    );
    if (!res.success || !res.data) return [];
    return res.data.map(mapRow);
  } catch {
    return [];
  }
}
