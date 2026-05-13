"use server";

import { revalidatePath } from "next/cache";
import { createAdminClient } from "@/shared/lib/supabase/server";
import { getSessionUser } from "@/entities/user";
import { canCreateLocation } from "@/shared/lib/roles";
import type { LocationType } from "./ui/location-chip";

/**
 * location Server Actions — admin-only edits on kvota.locations.
 *
 * Kept to a narrow surface: currently just location_type. More fields
 * (code, city rename, deactivation) can follow when the admin UI grows.
 */

const ALLOWED_TYPES: readonly LocationType[] = [
  "supplier",
  "hub",
  "customs",
  "own_warehouse",
  "client",
];

function assertCanEditLocations(roles: string[]): void {
  const ok =
    roles.includes("admin") ||
    roles.includes("head_of_logistics") ||
    roles.includes("head_of_customs");
  if (!ok) throw new Error("Нет прав на редактирование локаций");
}

function assertCanCreateLocations(roles: string[]): void {
  if (!canCreateLocation(roles)) {
    throw new Error("Нет прав на создание локаций");
  }
}

export async function updateLocationType(input: {
  id: string;
  type: LocationType;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user?.orgId) throw new Error("Unauthorized");
  assertCanEditLocations(user.roles);

  if (!ALLOWED_TYPES.includes(input.type)) {
    throw new Error(`Недопустимый тип: ${input.type}`);
  }

  const admin = createAdminClient();

  // Scope check: row must belong to caller's org (defense in depth alongside RLS).
  const { data: existing } = await admin
    .from("locations")
    .select("id, organization_id")
    .eq("id", input.id)
    .eq("organization_id", user.orgId)
    .limit(1)
    .maybeSingle();

  if (!existing) {
    throw new Error("Локация не найдена");
  }

  const { error } = await admin
    .from("locations")
    .update({ location_type: input.type })
    .eq("id", input.id);

  if (error) {
    throw new Error(error.message || "Не удалось обновить тип локации");
  }

  revalidatePath("/locations");
}

export interface CreateLocationInput {
  country: string;
  city?: string;
  code?: string;
  location_type: LocationType;
}

/**
 * createLocation — adds a row to kvota.locations for the caller's org.
 *
 * Country is required (Russian display name, e.g. "Китай"). City and code
 * are optional. Type defaults to "hub" on the DB side if omitted, but we
 * always send an explicit value from the UI to avoid relying on the default.
 *
 * Used by /locations page «Создать локацию» dialog (Testing 2 row 13).
 */
export async function createLocation(
  input: CreateLocationInput,
): Promise<{ id: string }> {
  const user = await getSessionUser();
  if (!user?.orgId) throw new Error("Unauthorized");
  assertCanCreateLocations(user.roles);

  const country = input.country.trim();
  if (!country) {
    throw new Error("Укажите страну");
  }

  if (!ALLOWED_TYPES.includes(input.location_type)) {
    throw new Error(`Недопустимый тип: ${input.location_type}`);
  }

  const city = input.city?.trim() || null;
  const code = input.code?.trim() || null;

  const admin = createAdminClient();
  const { data, error } = await admin
    .from("locations")
    .insert({
      organization_id: user.orgId,
      country,
      city,
      code,
      location_type: input.location_type,
      is_active: true,
    })
    .select("id")
    .single();

  if (error) {
    throw new Error(error.message || "Не удалось создать локацию");
  }

  revalidatePath("/locations");
  return { id: data.id };
}
