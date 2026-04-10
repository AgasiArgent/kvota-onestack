"use client";

import { createClient } from "@/shared/lib/supabase/client";

import type { CreateViewInput, TableView, UpdateViewInput } from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any };

function getUntypedClient(): UntypedClient {
  return createClient() as unknown as UntypedClient;
}

/** Payload shape for INSERT — snake_case to match DB columns. */
function createInputToRow(userId: string, input: CreateViewInput) {
  return {
    user_id: userId,
    table_key: input.tableKey,
    name: input.name,
    filters: input.filters,
    sort: input.sort,
    visible_columns: [...input.visibleColumns],
    is_default: input.isDefault ?? false,
    is_shared: false,
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

/**
 * Create a new personal view.
 * Throws with a descriptive message on unique-name conflict.
 */
export async function createView(
  userId: string,
  input: CreateViewInput
): Promise<TableView> {
  const client = getUntypedClient();
  const { data, error } = await client
    .from("user_table_views")
    .insert(createInputToRow(userId, input))
    .select()
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new Error("Вид с таким названием уже существует");
    }
    throw new Error(error.message || "Не удалось создать вид");
  }

  return {
    id: data.id,
    userId: data.user_id,
    tableKey: data.table_key,
    name: data.name,
    filters: data.filters ?? {},
    sort: data.sort,
    visibleColumns: data.visible_columns ?? [],
    isShared: data.is_shared,
    organizationId: data.organization_id,
    isDefault: data.is_default,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  };
}

/**
 * Update an existing view. Returns the updated row.
 * Throws with a descriptive message on unique-name conflict.
 */
export async function updateView(
  id: string,
  input: UpdateViewInput
): Promise<TableView> {
  const client = getUntypedClient();
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

  return {
    id: data.id,
    userId: data.user_id,
    tableKey: data.table_key,
    name: data.name,
    filters: data.filters ?? {},
    sort: data.sort,
    visibleColumns: data.visible_columns ?? [],
    isShared: data.is_shared,
    organizationId: data.organization_id,
    isDefault: data.is_default,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  };
}

/** Delete a view by id. Throws on error (RLS denial, missing row, etc.). */
export async function deleteView(id: string): Promise<void> {
  const client = getUntypedClient();
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
