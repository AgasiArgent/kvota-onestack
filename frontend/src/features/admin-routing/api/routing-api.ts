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

/**
 * Sanitize Supabase/PostgrestError objects before they escape this module.
 * Raw error.message can include constraint names, column names, table names,
 * and other DB internals. Log the detailed error for ops/dev visibility,
 * throw a short labelled string for the UI/toast layer.
 */
function failOperation(action: string, error: unknown): never {
  console.error(`[routing-api] ${action} failed:`, error);
  throw new Error(`${action} failed`);
}

/**
 * Verify a user is a member of the given organization. Used to gate
 * mutations that take a `userId` parameter, preventing confused-deputy
 * attacks where an admin in org A could assign org B's users into org A's
 * routing.
 */
async function assertUserInOrg(userId: string, orgId: string): Promise<void> {
  const supabase = getClient();
  const { data, error } = await supabase
    .from("user_roles")
    .select("user_id")
    .eq("user_id", userId)
    .eq("organization_id", orgId)
    .limit(1);
  if (error) failOperation("user membership check", error);
  if (!data || data.length === 0) {
    throw new Error("User is not a member of this organization");
  }
}

// Postgres SQLSTATE for unique_violation. PostgrestError.code surfaces this
// for any unique constraint conflict — used instead of message-string
// matching, which breaks silently if a constraint is renamed.
const PG_UNIQUE_VIOLATION = "23505";

// ---------- Brand Assignment Mutations ----------

export async function createBrandAssignment(
  orgId: string,
  brand: string,
  userId: string
): Promise<void> {
  const supabase = getClient();
  const currentUserId = await getCurrentUserId();
  await assertUserInOrg(userId, orgId);

  const { error } = await supabase.from("brand_assignments").insert({
    organization_id: orgId,
    brand,
    user_id: userId,
    created_by: currentUserId,
  });

  if (error) failOperation("create brand assignment", error);
}

export async function updateBrandAssignment(
  assignmentId: string,
  userId: string,
  orgId: string
): Promise<void> {
  const supabase = getClient();
  await assertUserInOrg(userId, orgId);

  const { error } = await supabase
    .from("brand_assignments")
    .update({ user_id: userId })
    .eq("id", assignmentId)
    .eq("organization_id", orgId);

  if (error) failOperation("update brand assignment", error);
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

  if (error) failOperation("delete brand assignment", error);
}

// ---------- Group Assignment Mutations ----------

export async function createGroupAssignment(
  orgId: string,
  salesGroupId: string,
  userId: string
): Promise<void> {
  const supabase = getClient();
  const currentUserId = await getCurrentUserId();
  await assertUserInOrg(userId, orgId);

  const { error } = await supabase
    .from("route_procurement_group_assignments")
    .insert({
      organization_id: orgId,
      sales_group_id: salesGroupId,
      user_id: userId,
      created_by: currentUserId,
    });

  if (error) failOperation("create group assignment", error);
}

export async function updateGroupAssignment(
  assignmentId: string,
  userId: string,
  orgId: string
): Promise<void> {
  const supabase = getClient();
  await assertUserInOrg(userId, orgId);

  const { error } = await supabase
    .from("route_procurement_group_assignments")
    .update({ user_id: userId })
    .eq("id", assignmentId)
    .eq("organization_id", orgId);

  if (error) failOperation("update group assignment", error);
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

  if (error) failOperation("delete group assignment", error);
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
  // Verify the assigned user belongs to this org. Without this check, an
  // admin in org A could insert org B's user as a tender step — confused-
  // deputy: the user then appears in org A's routing without consent.
  await assertUserInOrg(userId, orgId);
  const client = getUntypedClient();

  const { error } = await client.from("tender_routing_chain").insert({
    organization_id: orgId,
    step_order: stepOrder,
    user_id: userId,
    role_label: roleLabel,
    created_by: currentUserId,
  });

  if (error) failOperation("create tender step", error);
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

  if (error) failOperation("delete tender step", error);
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
  if (ownershipError) failOperation("reorder tender steps ownership check", ownershipError);
  if (!owned || owned.length !== 2) {
    throw new Error("Forbidden");
  }

  // swap_tender_steps RPC is not yet in generated types — cast to bypass
  const { error } = await (supabase.rpc as Function)("swap_tender_steps", {
    p_step_a: stepA.id,
    p_step_b: stepB.id,
  });
  if (error) failOperation("reorder tender steps", error);
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
  if (ownershipError) failOperation("assign item ownership check", ownershipError);
  if (!ownership) throw new Error("Forbidden");

  await assertUserInOrg(userId, orgId);

  const { error } = await supabase
    .from("quote_items")
    .update({ assigned_procurement_user: userId })
    .eq("id", itemId);

  if (error) failOperation("assign item", error);

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

    // 23505 = unique_violation. brand_assignments has UNIQUE(organization_id,
    // brand) — re-asserting an existing brand→user mapping is intentional in
    // the "create brand rule" UX and should not error. Other unique conflicts
    // shouldn't fire on a fresh INSERT, so 23505 here is safe to swallow.
    // Replaces the prior `error.message.includes("unique_brand_per_org")`
    // string match, which silently broke if the constraint were ever renamed.
    const code = (brandError as { code?: string } | null)?.code;
    if (brandError && code !== PG_UNIQUE_VIOLATION) {
      failOperation("create brand rule", brandError);
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

  if (error) failOperation("fetch sales groups", error);

  return (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
  }));
}
