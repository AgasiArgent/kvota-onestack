import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  AvailabilityStatus,
  ProductListItem,
  SourcingEntry,
} from "./types";

const PAGE_SIZE = 50;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any };

/**
 * positions_registry_view is not in generated DB types (created in migration 228).
 * Use untyped client for queries to that view.
 */
function getUntypedClient(): UntypedClient {
  return createAdminClient() as unknown as UntypedClient;
}

export interface PositionFilters {
  availability?: "available" | "unavailable";
  brand?: string;
  mozId?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
}

export interface PositionsListResult {
  products: ProductListItem[];
  details: Record<string, SourcingEntry[]>;
  total: number;
  filterOptions: {
    brands: string[];
    managers: { id: string; name: string }[];
  };
}

interface ViewRow {
  brand: string;
  product_code: string;
  product_name: string;
  latest_price: number | null;
  latest_currency: string | null;
  last_moz_name: string | null;
  last_moz_id: string | null;
  last_updated: string;
  entry_count: number;
  availability_status: string;
  organization_id: string;
}

export async function fetchPositionsList(
  orgId: string,
  filters: PositionFilters
): Promise<PositionsListResult> {
  const untyped = getUntypedClient();
  const supabase = createAdminClient();
  const { availability, brand, mozId, dateFrom, dateTo, page = 1 } = filters;
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  // Build master query on the view
  let masterQuery = untyped
    .from("positions_registry_view")
    .select("*", { count: "exact" })
    .eq("organization_id", orgId)
    .order("last_updated", { ascending: false })
    .range(from, to);

  if (availability === "available") {
    masterQuery = masterQuery.eq("availability_status", "available");
  } else if (availability === "unavailable") {
    masterQuery = masterQuery.eq("availability_status", "unavailable");
  }
  if (brand) {
    masterQuery = masterQuery.eq("brand", brand);
  }
  if (mozId) {
    masterQuery = masterQuery.eq("last_moz_id", mozId);
  }
  if (dateFrom) {
    masterQuery = masterQuery.gte("last_updated", dateFrom);
  }
  if (dateTo) {
    masterQuery = masterQuery.lte("last_updated", dateTo + "T23:59:59");
  }

  // Build filter options queries (distinct brands and managers)
  const brandsQuery = untyped
    .from("positions_registry_view")
    .select("brand")
    .eq("organization_id", orgId)
    .order("brand");

  const managersQuery = untyped
    .from("positions_registry_view")
    .select("last_moz_id, last_moz_name")
    .eq("organization_id", orgId)
    .not("last_moz_id", "is", null);

  // Execute master + filter options in parallel
  const [masterResult, brandsResult, managersResult] = await Promise.all([
    masterQuery,
    brandsQuery,
    managersQuery,
  ]);

  if (masterResult.error) throw masterResult.error;

  const rows = (masterResult.data ?? []) as ViewRow[];
  const total = masterResult.count ?? 0;

  // Map master rows to ProductListItem
  const products: ProductListItem[] = rows.map((row) => ({
    brand: row.brand,
    productCode: row.product_code,
    productName: row.product_name ?? "",
    latestPrice: row.latest_price,
    latestCurrency: row.latest_currency,
    lastMozName: row.last_moz_name,
    lastMozId: row.last_moz_id,
    lastUpdated: row.last_updated,
    entryCount: row.entry_count,
    availabilityStatus: (row.availability_status as AvailabilityStatus) ?? "unavailable",
  }));

  // Fetch detail rows for products on current page
  const details: Record<string, SourcingEntry[]> = {};

  if (products.length > 0) {
    // Build product keys for filtering details
    const productBrands = [...new Set(products.map((p) => p.brand))];
    // Query quote_items for detail entries joined with quotes and user_profiles
    // We use RPC-style query since we need a multi-table join
    let detailQuery = supabase
      .from("quote_items")
      .select(
        `id, quote_id, brand, product_code, updated_at, is_unavailable,
         purchase_price_original, purchase_currency, assigned_procurement_user,
         proforma_number,
         quotes!inner(idn, organization_id)`
      )
      .in("brand", productBrands)
      .or("procurement_status.eq.completed,is_unavailable.eq.true")
      .order("updated_at", { ascending: false });

    // Filter by org through the quotes join
    detailQuery = detailQuery.eq("quotes.organization_id", orgId);

    // PostgREST doesn't support tuple IN (brand+sku combos),
    // so we filter to current-page products client-side below.

    const detailResult = await detailQuery;
    const detailRows = (detailResult.data ?? []) as unknown as Array<{
      id: string;
      quote_id: string;
      brand: string;
      product_code: string | null;
      updated_at: string;
      is_unavailable: boolean | null;
      purchase_price_original: number | null;
      purchase_currency: string | null;
      assigned_procurement_user: string | null;
      proforma_number: string | null;
      quotes: { idn: string; organization_id: string } | null;
    }>;

    // Fetch user_profiles for moz names
    const mozIds = [
      ...new Set(
        detailRows
          .map((r) => r.assigned_procurement_user)
          .filter((id): id is string => id != null)
      ),
    ];
    const mozMap = new Map<string, string>();
    if (mozIds.length > 0) {
      const { data: mozData } = await supabase
        .from("user_profiles")
        .select("user_id, full_name")
        .in("user_id", mozIds);
      for (const m of mozData ?? []) {
        mozMap.set(m.user_id, m.full_name ?? "");
      }
    }

    // Build product key set for current page
    const pageProductKeys = new Set(
      products.map((p) => `${p.brand}::${p.productCode}`)
    );

    // Group detail rows by product key, filtering to current page products
    for (const row of detailRows) {
      const key = `${row.brand}::${row.product_code ?? ""}`;
      if (!pageProductKeys.has(key)) continue;

      const entry: SourcingEntry = {
        id: row.id,
        quoteId: row.quote_id,
        quoteIdn: (row.quotes || {}).idn ?? "",
        updatedAt: row.updated_at,
        isUnavailable: row.is_unavailable ?? false,
        price: row.purchase_price_original,
        currency: row.purchase_currency,
        mozName: mozMap.get(row.assigned_procurement_user ?? "") ?? null,
        proformaNumber: row.proforma_number,
      };

      if (!details[key]) {
        details[key] = [];
      }
      details[key].push(entry);
    }
  }

  // Deduplicate filter options
  const brandsList = brandsResult.data ?? [];
  const brands = [...new Set(brandsList.map((b: { brand: string }) => b.brand))].filter(Boolean) as string[];

  const managersList = managersResult.data ?? [];
  const managersMap = new Map<string, string>();
  for (const m of managersList as Array<{ last_moz_id: string; last_moz_name: string }>) {
    if (m.last_moz_id && !managersMap.has(m.last_moz_id)) {
      managersMap.set(m.last_moz_id, m.last_moz_name ?? "");
    }
  }
  const managers = [...managersMap.entries()]
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name));

  return { products, details, total, filterOptions: { brands, managers } };
}
