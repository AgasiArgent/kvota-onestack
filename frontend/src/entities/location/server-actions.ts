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

/**
 * Tables that reference kvota.locations.id. The list mirrors the FK
 * constraints in the schema as of migration 318. If a future migration
 * adds another FK we'll need to widen this list — the safest signal is
 * a delete failing with «foreign key violation» on a path not enumerated
 * here.
 */
const LOCATION_REFERENCE_TABLES = [
  { table: "quote_items", column: "pickup_location_id", label: "позиции КП" },
  {
    table: "supplier_invoices",
    column: "pickup_location_id",
    label: "КП поставщиков",
  },
  {
    table: "logistics_route_segments",
    column: "from_location_id",
    label: "сегменты маршрутов (откуда)",
  },
  {
    table: "logistics_route_segments",
    column: "to_location_id",
    label: "сегменты маршрутов (куда)",
  },
  {
    table: "logistics_route_template_segments",
    column: "from_location_id",
    label: "шаблоны маршрутов (откуда)",
  },
  {
    table: "logistics_route_template_segments",
    column: "to_location_id",
    label: "шаблоны маршрутов (куда)",
  },
] as const;

export interface DeleteLocationResult {
  success: boolean;
  /**
   * Populated when delete is refused because the location is referenced
   * elsewhere. Lists each table:count pair so the UI can surface a
   * specific message instead of a generic «не удалось».
   */
  usage?: Array<{ label: string; count: number }>;
  error?: string;
}

/**
 * Deletes a location after verifying no КП / route segment / route template
 * still references it. Testing 2 row 77: «Удаление/изменение локаций только
 * если не используется в КП». The check is application-level (defense in
 * depth alongside DB FK rules) so the UI can give a helpful "used in N КП"
 * message instead of a raw FK violation toast.
 *
 * Role gate matches `updateLocationType` — admin / head_of_logistics /
 * head_of_customs.
 */
export async function deleteLocation(
  id: string,
): Promise<DeleteLocationResult> {
  const user = await getSessionUser();
  if (!user?.orgId) return { success: false, error: "Unauthorized" };

  try {
    assertCanEditLocations(user.roles);
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "Нет прав",
    };
  }

  const admin = createAdminClient();

  // Scope check: row must belong to caller's org (RLS belt-and-braces).
  const { data: existing } = await admin
    .from("locations")
    .select("id, organization_id")
    .eq("id", id)
    .eq("organization_id", user.orgId)
    .limit(1)
    .maybeSingle();

  if (!existing) {
    return { success: false, error: "Локация не найдена" };
  }

  // Probe every known FK table — parallel `count: "exact"` requests are
  // cheap and avoid one round-trip per table.
  const usage: Array<{ label: string; count: number }> = [];
  await Promise.all(
    LOCATION_REFERENCE_TABLES.map(async ({ table, column, label }) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { count } = await (admin as any)
        .from(table)
        .select("id", { count: "exact", head: true })
        .eq(column, id);
      if ((count ?? 0) > 0) {
        usage.push({ label, count: count as number });
      }
    }),
  );

  if (usage.length > 0) {
    return {
      success: false,
      error: "Локация используется и не может быть удалена",
      usage,
    };
  }

  const { error: deleteError } = await admin
    .from("locations")
    .delete()
    .eq("id", id);

  if (deleteError) {
    return {
      success: false,
      error: deleteError.message || "Не удалось удалить локацию",
    };
  }

  revalidatePath("/locations");
  return { success: true };
}
