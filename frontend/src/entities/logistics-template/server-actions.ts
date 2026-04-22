"use server";

import { revalidatePath } from "next/cache";
import { apiServerClient } from "@/shared/lib/api-server";
import { getSessionUser } from "@/entities/user";
import type { LocationType } from "@/entities/location";

/**
 * logistics-template server actions — thin wrappers over Python API.
 * See spec §6.1 for the API contract. `apply` materialises the template
 * into concrete segments for a given invoice (placeholder locations until
 * the logistician picks concrete ones in the constructor).
 */

interface TemplateSegmentDraft {
  sequence_order: number;
  from_location_type: LocationType;
  to_location_type: LocationType;
  default_label?: string;
  default_days?: number;
}

export async function createLogisticsTemplate(input: {
  name: string;
  description?: string;
  segments: TemplateSegmentDraft[];
  revalidate_path: string;
}): Promise<{ template_id: string }> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient<{ template_id: string }>(
    "/logistics/templates",
    {
      method: "POST",
      body: JSON.stringify({
        name: input.name,
        description: input.description,
        segments: input.segments,
      }),
    },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось создать шаблон");
  }
  revalidatePath(input.revalidate_path);
  return res.data!;
}

export async function deleteLogisticsTemplate(input: {
  template_id: string;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(
    `/logistics/templates/${input.template_id}`,
    { method: "DELETE" },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось удалить шаблон");
  }
  revalidatePath(input.revalidate_path);
}

/**
 * applyLogisticsTemplate — creates draft segments on an invoice from the
 * template's types. Replaces any existing *draft* segments (spec §5.5).
 * Concrete `from_location_id` / `to_location_id` are null-placeholders
 * until the logistician fills them via the details panel.
 */
export async function applyLogisticsTemplate(input: {
  template_id: string;
  invoice_id: string;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(
    `/logistics/templates/${input.template_id}/apply?invoice_id=${encodeURIComponent(input.invoice_id)}`,
    { method: "POST" },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось применить шаблон");
  }
  revalidatePath(input.revalidate_path);
}
