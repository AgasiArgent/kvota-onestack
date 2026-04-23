"use client";

import { createClient } from "@/shared/lib/supabase/client";

import type { CreateViewInput, TableView, UpdateViewInput } from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any; auth: any };

function getUntypedClient(): UntypedClient {
  return createClient() as unknown as UntypedClient;
}

/** Roles allowed to create/edit/delete organization-shared views. */
const SHARED_VIEW_ADMIN_ROLES = new Set(["head_of_customs", "admin"]);

/**
 * Resolve the acting user's role slugs in the given organization. Used to
 * gate shared-view mutations client-side. RLS in the DB is the ultimate
 * check — this gate is for responsive UX and clear error messages.
 */
async function fetchUserRoles(
  userId: string,
  orgId: string
): Promise<Set<string>> {
  const client = getUntypedClient();
  const { data, error } = await client
    .from("user_roles")
    .select("roles(slug)")
    .eq("user_id", userId)
    .eq("organization_id", orgId);

  if (error) {
    throw new Error(error.message || "Не удалось получить роли");
  }

  const roles = new Set<string>();
  for (const row of (data ?? []) as Array<{
    roles: { slug: string | null } | null;
  }>) {
    const slug = row.roles?.slug;
    if (slug) roles.add(slug);
  }
  return roles;
}

function hasSharedViewAdminRole(roles: Set<string>): boolean {
  for (const r of roles) {
    if (SHARED_VIEW_ADMIN_ROLES.has(r)) return true;
  }
  return false;
}

/** Payload shape for INSERT — snake_case to match DB columns. */
function createInputToRow(
  userId: string,
  input: CreateViewInput,
  orgId: string | null
) {
  const isShared = input.isShared ?? false;
  return {
    user_id: userId,
    table_key: input.tableKey,
    name: input.name,
    filters: input.filters,
    sort: input.sort,
    visible_columns: [...input.visibleColumns],
    is_default: input.isDefault ?? false,
    is_shared: isShared,
    organization_id: isShared ? orgId : null,
  };
}

/** Partial payload for UPDATE — only provided fields are included. */
function updateInputToRow(input: UpdateViewInput): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  if (input.name !== undefined) payload.name = input.name;
  if (input.filters !== undefined) payload.filters = input.filters;
  if (input.sort !== undefined) payload.sort = input.sort;
  if (input.visibleColumns !== undefined)
    payload.visible_columns = [...input.visibleColumns];
  if (input.isDefault !== undefined) payload.is_default = input.isDefault;
  return payload;
}

/** Map a raw INSERT/UPDATE return row to the typed domain object. */
function dataToTableView(row: {
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
}): TableView {
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
 * Create a new personal or shared view.
 *
 * Backward-compatible signature: `userId` is the acting user id, used as
 * `user_id` on the new row. When `input.isShared` is true, `orgId` is
 * required and the acting user must hold `head_of_customs` or `admin` in
 * that organization; otherwise an error is thrown before the DB call.
 *
 * Throws with a descriptive message on unique-name conflict.
 */
export async function createView(
  userId: string,
  input: CreateViewInput,
  orgId: string | null = null
): Promise<TableView> {
  const client = getUntypedClient();
  const isShared = input.isShared ?? false;

  if (isShared) {
    if (!orgId) {
      throw new Error("Общему представлению требуется организация");
    }
    const roles = await fetchUserRoles(userId, orgId);
    if (!hasSharedViewAdminRole(roles)) {
      throw new Error(
        "Только head_of_customs/admin может создавать общие представления"
      );
    }
  }

  const { data, error } = await client
    .from("user_table_views")
    .insert(createInputToRow(userId, input, orgId))
    .select()
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new Error("Вид с таким названием уже существует");
    }
    throw new Error(error.message || "Не удалось создать вид");
  }

  return dataToTableView(data);
}

/**
 * Update an existing view. Returns the updated row.
 *
 * Backward-compatible signature: callers that don't need shared-view gating
 * can pass just `(id, input)` — the role check only runs when `guard` is
 * provided and identifies the row as shared. RLS on the server is the
 * ultimate enforcement; this gate just surfaces a clear error upfront.
 *
 * Throws with a descriptive message on unique-name conflict.
 */
export async function updateView(
  id: string,
  input: UpdateViewInput,
  guard?: { existing: TableView; actingUserId: string; orgId: string }
): Promise<TableView> {
  const client = getUntypedClient();

  if (guard) {
    const { existing, actingUserId, orgId } = guard;
    if (existing.isShared) {
      const roles = await fetchUserRoles(actingUserId, orgId);
      if (!hasSharedViewAdminRole(roles) && existing.userId !== actingUserId) {
        throw new Error(
          "Редактировать общее представление может только владелец или admin/head_of_customs"
        );
      }
    }
  }

  const { data, error } = await client
    .from("user_table_views")
    .update(updateInputToRow(input))
    .eq("id", id)
    .select()
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new Error("Вид с таким названием уже существует");
    }
    throw new Error(error.message || "Не удалось обновить вид");
  }

  return dataToTableView(data);
}

/**
 * Delete a view by id. Throws on error (RLS denial, missing row, etc.).
 *
 * Backward-compatible signature — the optional `guard` argument adds a
 * client-side role check for shared views, matching the one in updateView.
 */
export async function deleteView(
  id: string,
  guard?: { existing: TableView; actingUserId: string; orgId: string }
): Promise<void> {
  const client = getUntypedClient();

  if (guard) {
    const { existing, actingUserId, orgId } = guard;
    if (existing.isShared) {
      const roles = await fetchUserRoles(actingUserId, orgId);
      if (!hasSharedViewAdminRole(roles) && existing.userId !== actingUserId) {
        throw new Error(
          "Удалять общее представление может только владелец или admin/head_of_customs"
        );
      }
    }
  }

  const { error } = await client.from("user_table_views").delete().eq("id", id);
  if (error) {
    throw new Error(error.message || "Не удалось удалить вид");
  }
}

/**
 * Set a view as the default for its (user, table_key) scope.
 *
 * The DB trigger `enforce_single_default_view` will automatically unset
 * any previously-default view for the same scope, so a single UPDATE is
 * sufficient here.
 */
export async function setDefaultView(id: string): Promise<void> {
  const client = getUntypedClient();
  const { error } = await client
    .from("user_table_views")
    .update({ is_default: true })
    .eq("id", id);
  if (error) {
    throw new Error(error.message || "Не удалось назначить вид по умолчанию");
  }
}
