import "server-only";

import { createAdminClient } from "@/shared/lib/supabase/server";

import type { TableView } from "./types";

// user_table_views is not yet in generated DB types (migration 261). Use an
// untyped admin client for reads — admin bypasses RLS, so the `orgId` and
// `userId` filters must be applied explicitly here.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedAdminClient = { from: (table: string) => any };

interface RawRow {
  id: string;
  user_id: string;
  table_key: string;
  name: string;
  filters: Record<string, unknown> | null;
  sort: string | null;
  visible_columns: string[] | null;
  is_shared: boolean;
  organization_id: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

function rowToTableView(row: RawRow): TableView {
  return {
    id: row.id,
    userId: row.user_id,
    tableKey: row.table_key,
    name: row.name,
    filters: (row.filters ?? {}) as TableView["filters"],
    sort: row.sort,
    visibleColumns: row.visible_columns ?? [],
    isShared: row.is_shared,
    organizationId: row.organization_id,
    isDefault: row.is_default,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

/**
 * Server-side variant of {@link fetchAllAvailable}. Returns the user's
 * personal views plus every shared view within the given organization for
 * the specified registry. Sorted personal-first (by name), then shared (by
 * name) for a stable UI order.
 *
 * Uses the admin client to bypass RLS — the explicit filters below enforce
 * the same visibility rules as the RLS policies defined in migration 261.
 */
export async function fetchAllAvailableOnServer(
  orgId: string,
  tableKey: string,
  userId: string
): Promise<TableView[]> {
  const admin = createAdminClient() as unknown as UntypedAdminClient;
  const { data, error } = await admin
    .from("user_table_views")
    .select("*")
    .eq("table_key", tableKey)
    .or(
      `and(is_shared.eq.false,user_id.eq.${userId}),and(is_shared.eq.true,organization_id.eq.${orgId})`
    );

  if (error) {
    console.error("Failed to fetch table views on server:", error);
    return [];
  }

  const rows = (data as RawRow[] | null) ?? [];
  const views = rows.map(rowToTableView);
  return views.sort((a, b) => {
    if (a.isShared !== b.isShared) {
      return a.isShared ? 1 : -1;
    }
    return a.name.localeCompare(b.name, "ru");
  });
}
