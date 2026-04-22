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
  author_user_id: string;
  author_name: string | null;
  author_role: string | null;
  visible_to: string[] | null;
  created_at: string;
}

function mapRow(r: RawNoteRow): EntityNoteCardData {
  return {
    id: r.id,
    body: r.body,
    pinned: !!r.pinned,
    authorRole: r.author_role ?? "",
    author: {
      id: r.author_user_id,
      name: r.author_name ?? "",
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
