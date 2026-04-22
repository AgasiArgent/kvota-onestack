"use server";

import { revalidatePath } from "next/cache";
import { createAdminClient } from "@/shared/lib/supabase/server";
import { getSessionUser } from "@/entities/user";
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
