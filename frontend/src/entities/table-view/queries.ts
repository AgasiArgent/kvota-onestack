"use client";

import { createClient } from "@/shared/lib/supabase/client";
import type { FilterValue } from "@/shared/ui/data-table/types";

import type { TableView } from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any };

/**
 * user_table_views is not yet in generated DB types (added in migration 261).
 * Use the untyped client until types are regenerated.
 */
function getUntypedClient(): UntypedClient {
  return createClient() as unknown as UntypedClient;
}

// Raw row shape as returned by Supabase (snake_case).
interface RawTableViewRow {
  id: string;
  user_id: string;
  table_key: string;
  name: string;
  filters: Record<string, FilterValue> | null;
  sort: string | null;
  visible_columns: string[] | null;
  is_shared: boolean;
  organization_id: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

function rowToTableView(row: RawTableViewRow): TableView {
  return {
    id: row.id,
    userId: row.user_id,
    tableKey: row.table_key,
    name: row.name,
    filters: row.filters ?? {},
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
 * List all personal views for the given user and registry table.
 * Ordered by is_default DESC (default view first), then by name.
 */
export async function listViews(
  tableKey: string,
  userId: string
): Promise<TableView[]> {
  const client = getUntypedClient();
  const { data, error } = await client
    .from("user_table_views")
    .select("*")
    .eq("user_id", userId)
    .eq("table_key", tableKey)
    .eq("is_shared", false)
    .order("is_default", { ascending: false })
    .order("name", { ascending: true });

  if (error) {
    console.error("Failed to list table views:", error);
    return [];
  }

  return (data as RawTableViewRow[] | null)?.map(rowToTableView) ?? [];
}

/**
 * List all views available to the user for a given registry: their personal
 * views plus every shared view within their organization. Ordered so
 * personal views appear first (by name), followed by shared views (by name).
 *
 * RLS enforces access: personal views are filtered to `user_id = self`;
 * shared views are readable to any org member (migration 261 policies).
 * The explicit `.or()` clause matches the policy union so a single round-trip
 * returns both sets.
 */
export async function fetchAllAvailable(
  orgId: string,
  tableKey: string,
  userId: string
): Promise<TableView[]> {
  const client = getUntypedClient();
  const { data, error } = await client
    .from("user_table_views")
    .select("*")
    .eq("table_key", tableKey)
    .or(
      `and(is_shared.eq.false,user_id.eq.${userId}),and(is_shared.eq.true,organization_id.eq.${orgId})`
    );

  if (error) {
    console.error("Failed to fetch available table views:", error);
    return [];
  }

  const rows = (data as RawTableViewRow[] | null) ?? [];
  const views = rows.map(rowToTableView);

  // Personal first (by name), then shared (by name).
  return views.sort((a, b) => {
    if (a.isShared !== b.isShared) {
      return a.isShared ? 1 : -1;
    }
    return a.name.localeCompare(b.name, "ru");
  });
}

/** Fetch a single view by id. Returns null if not found or access denied. */
export async function fetchView(id: string): Promise<TableView | null> {
  const client = getUntypedClient();
  const { data, error } = await client
    .from("user_table_views")
    .select("*")
    .eq("id", id)
    .maybeSingle();

  if (error || !data) return null;
  return rowToTableView(data as RawTableViewRow);
}
