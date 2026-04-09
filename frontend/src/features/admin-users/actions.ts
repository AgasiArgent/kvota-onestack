"use server";

import { apiServerClient } from "@/shared/lib/api-server";
import type { ApiResponse } from "@/shared/types/api";
import type { CreateUserPayload } from "@/entities/admin/types";
import { revalidatePath } from "next/cache";

export async function createUserAction(
  payload: CreateUserPayload
): Promise<ApiResponse<{ user_id: string }>> {
  const res = await apiServerClient<{ user_id: string }>("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (res.success) {
    revalidatePath("/admin/users");
  }
  return res;
}

export async function updateUserStatusAction(
  userId: string,
  status: "active" | "suspended"
): Promise<ApiResponse<{ user_id: string }>> {
  const res = await apiServerClient<{ user_id: string }>(
    `/admin/users/${userId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }
  );
  if (res.success) {
    revalidatePath("/admin/users");
  }
  return res;
}

export async function updateUserRolesAction(
  userId: string,
  roleSlugs: string[]
): Promise<ApiResponse<{ user_id: string; roles: string[] }>> {
  const res = await apiServerClient<{ user_id: string; roles: string[] }>(
    `/admin/users/${userId}/roles`,
    {
      method: "PATCH",
      body: JSON.stringify({ role_slugs: roleSlugs }),
    }
  );
  if (res.success) {
    revalidatePath("/admin/users");
  }
  return res;
}
