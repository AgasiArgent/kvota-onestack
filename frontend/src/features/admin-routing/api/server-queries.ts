import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  BrandAssignment,
  GroupAssignment,
  TenderChainStep,
  UnassignedItem,
} from "../model/types";

async function fetchUserProfileMap(
  orgId: string,
  userIds: string[]
): Promise<Map<string, string | null>> {
  if (userIds.length === 0) return new Map();
  const supabase = createAdminClient();

  const { data } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .eq("organization_id", orgId)
    .in("user_id", userIds);

  const map = new Map<string, string | null>();
  for (const row of data ?? []) {
    map.set(row.user_id, row.full_name);
  }
  return map;
}

export async function fetchBrandsData(
  orgId: string
): Promise<{ assignments: BrandAssignment[]; unassignedBrands: string[] }> {
  const supabase = createAdminClient();

  const { data: assignmentRows } = await supabase
    .from("brand_assignments")
    .select("id, brand, user_id, created_at")
    .eq("organization_id", orgId)
    .order("brand");

  const rows = assignmentRows ?? [];
  const userIds = [...new Set(rows.map((r) => r.user_id))];
  const profileMap = await fetchUserProfileMap(orgId, userIds);

  const assignments: BrandAssignment[] = rows.map((row) => ({
    id: row.id,
    brand: row.brand,
    user_id: row.user_id,
    user_full_name: profileMap.get(row.user_id) ?? null,
    user_email: null,
    created_at: row.created_at,
  }));

  // Fetch unassigned brands
  const assignedBrands = new Set(rows.map((r) => r.brand));

  const { data: quoteRows } = await supabase
    .from("quotes")
    .select("id")
    .eq("organization_id", orgId)
    .is("deleted_at", null);

  let unassignedBrands: string[] = [];

  if (quoteRows && quoteRows.length > 0) {
    const quoteIds = quoteRows.map((q) => q.id);
    const { data: itemRows } = await supabase
      .from("quote_items")
      .select("brand")
      .in("quote_id", quoteIds)
      .not("brand", "is", null);

    const allBrands = new Set<string>();
    for (const row of itemRows ?? []) {
      if (row.brand) allBrands.add(row.brand);
    }

    unassignedBrands = [...allBrands]
      .filter((b) => !assignedBrands.has(b))
      .sort();
  }

  return { assignments, unassignedBrands };
}

export async function fetchGroupsData(orgId: string): Promise<GroupAssignment[]> {
  const supabase = createAdminClient();

  const { data: rows } = await supabase
    .from("route_procurement_group_assignments")
    .select("id, sales_group_id, user_id, created_at")
    .eq("organization_id", orgId)
    .order("created_at", { ascending: false });

  const assignmentRows = rows ?? [];

  const groupIds = [...new Set(assignmentRows.map((r) => r.sales_group_id))];
  const groupMap = new Map<string, string>();
  if (groupIds.length > 0) {
    const { data: groups } = await supabase
      .from("sales_groups")
      .select("id, name")
      .in("id", groupIds);
    for (const g of groups ?? []) {
      groupMap.set(g.id, g.name);
    }
  }

  const userIds = [...new Set(assignmentRows.map((r) => r.user_id))];
  const profileMap = await fetchUserProfileMap(orgId, userIds);

  return assignmentRows.map((row) => ({
    id: row.id,
    sales_group_id: row.sales_group_id,
    sales_group_name: groupMap.get(row.sales_group_id) ?? null,
    user_id: row.user_id,
    user_full_name: profileMap.get(row.user_id) ?? null,
    user_email: null,
    created_at: row.created_at,
  }));
}

export async function fetchTenderData(orgId: string): Promise<TenderChainStep[]> {
  const supabase = createAdminClient();

  const untypedClient = supabase as unknown as {
    from: (table: string) => ReturnType<typeof supabase.from>;
  };

  const { data, error } = await untypedClient
    .from("tender_routing_chain")
    .select("id, step_order, user_id, role_label")
    .eq("organization_id", orgId)
    .order("step_order");

  if (error) {
    console.error("Failed to fetch tender chain:", error);
    return [];
  }

  type ChainRow = {
    id: string;
    step_order: number;
    user_id: string;
    role_label: string;
  };
  const rows = (data ?? []) as ChainRow[];

  const userIds = [...new Set(rows.map((r) => r.user_id))];
  const profileMap = await fetchUserProfileMap(orgId, userIds);

  return rows.map((row) => ({
    id: row.id,
    step_order: row.step_order,
    user_id: row.user_id,
    role_label: row.role_label,
    user_full_name: profileMap.get(row.user_id) ?? null,
    user_email: null,
  }));
}

export async function fetchUnassignedData(orgId: string): Promise<UnassignedItem[]> {
  const supabase = createAdminClient();

  const { data: quoteRows } = await supabase
    .from("quotes")
    .select("id, idn_quote, customer_id, created_by_user_id")
    .eq("organization_id", orgId)
    .is("deleted_at", null);

  if (!quoteRows || quoteRows.length === 0) return [];

  const quoteIds = quoteRows.map((q) => q.id);
  const quoteMap = new Map(quoteRows.map((q) => [q.id, q]));

  const { data: items } = await supabase
    .from("quote_items")
    .select("id, quote_id, brand, created_at")
    .in("quote_id", quoteIds)
    .is("assigned_procurement_user", null)
    .not("procurement_status", "is", null);

  if (!items || items.length === 0) return [];

  const customerIds = [
    ...new Set(
      quoteRows
        .map((q) => q.customer_id)
        .filter((id): id is string => id !== null)
    ),
  ];
  const customerMap = new Map<string, string>();
  if (customerIds.length > 0) {
    const { data: customers } = await supabase
      .from("customers")
      .select("id, name")
      .in("id", customerIds);
    for (const c of customers ?? []) {
      customerMap.set(c.id, c.name);
    }
  }

  const managerIds = [
    ...new Set(
      quoteRows
        .map((q) => q.created_by_user_id)
        .filter((id): id is string => id !== null)
    ),
  ];
  const managerProfileMap = await fetchUserProfileMap(orgId, managerIds);

  return items.map((item) => {
    const quote = quoteMap.get(item.quote_id);
    const customerId = quote?.customer_id;
    const managerId = quote?.created_by_user_id;

    return {
      id: item.id,
      quote_id: item.quote_id,
      quote_idn: quote?.idn_quote ?? "",
      brand: item.brand,
      customer_name: customerId
        ? (customerMap.get(customerId) ?? null)
        : null,
      sales_manager_name: managerId
        ? (managerProfileMap.get(managerId) ?? null)
        : null,
      created_at: item.created_at,
    };
  });
}
