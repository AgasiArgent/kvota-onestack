import { createClient } from "@/shared/lib/supabase/client";
import type { ProcurementUser, SalesGroup } from "../model/types";

// ---------- Helpers ----------

function getClient() {
  return createClient();
}

async function getCurrentUserId(): Promise<string> {
  const supabase = getClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();
  if (error || !user) throw new Error("Not authenticated");
  return user.id;
}

// ---------- Brand Assignment Mutations ----------

export async function createBrandAssignment(
  orgId: string,
  brand: string,
  userId: string
): Promise<void> {
  const supabase = getClient();
  const currentUserId = await getCurrentUserId();

  const { error } = await supabase.from("brand_assignments").insert({
    organization_id: orgId,
    brand,
    user_id: userId,
    created_by: currentUserId,
  });

  if (error) throw error;
}

export async function updateBrandAssignment(
  assignmentId: string,
  userId: string,
  orgId: string
): Promise<void> {
  const supabase = getClient();

  const { error } = await supabase
    .from("brand_assignments")
    .update({ user_id: userId })
    .eq("id", assignmentId)
    .eq("organization_id", orgId);

  if (error) throw error;
}

export async function deleteBrandAssignment(
  assignmentId: string,
  orgId: string
): Promise<void> {
  const supabase = getClient();

  const { error } = await supabase
    .from("brand_assignments")
    .delete()
    .eq("id", assignmentId)
    .eq("organization_id", orgId);

  if (error) throw error;
}

// ---------- Group Assignment Mutations ----------

export async function createGroupAssignment(
  orgId: string,
  salesGroupId: string,
  userId: string
): Promise<void> {
  const supabase = getClient();
  const currentUserId = await getCurrentUserId();

  const { error } = await supabase
    .from("route_procurement_group_assignments")
    .insert({
      organization_id: orgId,
      sales_group_id: salesGroupId,
      user_id: userId,
      created_by: currentUserId,
    });

  if (error) throw error;
}

export async function updateGroupAssignment(
  assignmentId: string,
  userId: string,
  orgId: string
): Promise<void> {
  const supabase = getClient();

  const { error } = await supabase
    .from("route_procurement_group_assignments")
    .update({ user_id: userId })
    .eq("id", assignmentId)
    .eq("organization_id", orgId);

  if (error) throw error;
}

export async function deleteGroupAssignment(
  assignmentId: string,
  orgId: string
): Promise<void> {
  const supabase = getClient();

  const { error } = await supabase
    .from("route_procurement_group_assignments")
    .delete()
    .eq("id", assignmentId)
    .eq("organization_id", orgId);

  if (error) throw error;
}

// ---------- Tender Chain Mutations ----------

// tender_routing_chain may not be in generated types — use untyped helper
function getUntypedClient() {
  const supabase = getClient();
  return supabase as unknown as {
    from: (table: string) => ReturnType<typeof supabase.from>;
  };
}

export async function createTenderStep(
  orgId: string,
  stepOrder: number,
  userId: string,
  roleLabel: string
): Promise<void> {
  const currentUserId = await getCurrentUserId();
  const client = getUntypedClient();

  const { error } = await client.from("tender_routing_chain").insert({
    organization_id: orgId,
    step_order: stepOrder,
    user_id: userId,
    role_label: roleLabel,
    created_by: currentUserId,
  });

  if (error) throw error;
}

export async function deleteTenderStep(
  stepId: string,
  orgId: string,
): Promise<void> {
  const client = getUntypedClient();

  // Defense in depth: tender_routing_chain has RLS policies that filter by
  // organization_id (migration 225), but adding an explicit filter here
  // means the delete cannot affect another org even if RLS is ever
  // misconfigured. orgId is required from the caller.
  const { error } = await client
    .from("tender_routing_chain")
    .delete()
    .eq("id", stepId)
    .eq("organization_id", orgId);

  if (error) throw error;
}

export async function reorderTenderSteps(
  stepA: { id: string; step_order: number },
  stepB: { id: string; step_order: number },
  orgId: string,
): Promise<void> {
  const supabase = getClient();

  // CRITICAL: swap_tender_steps RPC (migration 226) is SECURITY DEFINER and
  // GRANTed to `authenticated` — meaning it bypasses RLS and any logged-in
  // user can call it with any UUIDs. The RPC's internal `v_org_a == v_org_b`
  // check ensures both steps share an org, but does NOT verify the caller
  // is in that org. Without this app-level pre-check, a user from org A
  // could reorder org B's chain by guessing step UUIDs. Pre-check both
  // steps belong to the caller's org before invoking the RPC.
  const { data: owned, error: ownershipError } = await supabase
    .from("tender_routing_chain")
    .select("id")
    .in("id", [stepA.id, stepB.id])
    .eq("organization_id", orgId);
  if (ownershipError) {
    console.error("[reorderTenderSteps] ownership check failed:", ownershipError);
    throw new Error("Failed to reorder steps");
  }
  if (!owned || owned.length !== 2) {
    throw new Error("Forbidden");
  }

  // swap_tender_steps RPC is not yet in generated types — cast to bypass
  const { error } = await (supabase.rpc as Function)("swap_tender_steps", {
    p_step_a: stepA.id,
    p_step_b: stepB.id,
  });
  if (error) {
    console.error("[reorderTenderSteps] swap failed:", error);
    throw new Error("Failed to reorder steps");
  }
}

// ---------- Unassigned Item Mutations ----------

export async function assignUnassignedItem(
  itemId: string,
  userId: string,
  createBrandRule: boolean,
  orgId: string,
  brand: string | null
): Promise<void> {
  const supabase = getClient();

  // Defense in depth: quote_items has RLS enabled (migration 042) but no
  // direct organization_id column — org-scope is enforced via the
  // quote_items → quotes FK join. Pre-check ownership through the join
  // before mutating, mirroring PR #129's reassignInvoice pattern.
  const { data: ownership, error: ownershipError } = await supabase
    .from("quote_items")
    .select("id, quotes!inner(organization_id)")
    .eq("id", itemId)
    .eq("quotes.organization_id", orgId)
    .maybeSingle();
  if (ownershipError) {
    console.error("[assignUnassignedItem] ownership check failed:", ownershipError);
    throw new Error("Failed to assign item");
  }
  if (!ownership) {
    throw new Error("Forbidden");
  }

  const { error } = await supabase
    .from("quote_items")
    .update({ assigned_procurement_user: userId })
    .eq("id", itemId);

  if (error) throw error;

  if (createBrandRule && brand) {
    const currentUserId = await getCurrentUserId();
    const { error: brandError } = await supabase
      .from("brand_assignments")
      .insert({
        organization_id: orgId,
        brand,
        user_id: userId,
        created_by: currentUserId,
      });

    // Ignore duplicate constraint errors
    if (brandError && !brandError.message.includes("unique_brand_per_org")) {
      throw brandError;
    }
  }
}

// ---------- Reference Data (Client-Side) ----------

export async function fetchProcurementUsers(
  orgId: string
): Promise<ProcurementUser[]> {
  const supabase = getClient();

  const { data: roleRows } = await supabase
    .from("user_roles")
    .select("user_id, roles!inner(slug)")
    .eq("organization_id", orgId);

  const procurementUserIds = new Set<string>();
  for (const row of roleRows ?? []) {
    const role = row.roles as unknown as { slug: string } | null;
    const slug = role?.slug;
    if (slug === "procurement" || slug === "head_of_procurement") {
      procurementUserIds.add(row.user_id);
    }
  }

  if (procurementUserIds.size === 0) return [];

  const userIdArr = [...procurementUserIds];

  const { data: profiles } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .eq("organization_id", orgId)
    .in("user_id", userIdArr);

  const profileMap = new Map<string, string | null>();
  for (const p of profiles ?? []) {
    profileMap.set(p.user_id, p.full_name);
  }

  return userIdArr.map((uid) => ({
    id: uid,
    full_name: profileMap.get(uid) ?? null,
    email: "",
  }));
}

export async function fetchSalesGroups(orgId: string): Promise<SalesGroup[]> {
  const supabase = getClient();
  void orgId; // sales_groups is a shared table

  const { data, error } = await supabase
    .from("sales_groups")
    .select("id, name")
    .order("name");

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
  }));
}
