import { apiServerClient } from "@/shared/lib/api-server";
import { PROCUREMENT_SUBSTATUSES } from "@/shared/lib/workflow-substates";
import type { KanbanColumns, KanbanResponse } from "../model/types";

/**
 * Fetches the procurement kanban board state from the Python API.
 *
 * The endpoint groups pending_procurement quotes by their procurement_substatus
 * into four columns. If the request fails, returns an empty board so the page
 * still renders (the user sees "no quotes" rather than a broken screen).
 */
export async function fetchKanbanData(): Promise<KanbanResponse> {
  const res = await apiServerClient<KanbanResponse>(
    "/quotes/kanban?status=pending_procurement"
  );

  if (!res.success || !res.data) {
    return { status: "pending_procurement", columns: emptyColumns() };
  }

  // Normalize: ensure every substatus key exists even if the API omits empties.
  const normalized: KanbanColumns = emptyColumns();
  for (const sub of PROCUREMENT_SUBSTATUSES) {
    normalized[sub] = res.data.columns?.[sub] ?? [];
  }
  return { status: res.data.status, columns: normalized };
}

function emptyColumns(): KanbanColumns {
  return Object.fromEntries(
    PROCUREMENT_SUBSTATUSES.map((sub) => [sub, [] as KanbanColumns[typeof sub]])
  ) as KanbanColumns;
}
