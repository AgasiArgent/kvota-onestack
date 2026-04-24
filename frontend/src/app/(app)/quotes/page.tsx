import { redirect } from "next/navigation";
import { getSessionUser, fetchUserSalesGroupId } from "@/entities/user/server";
import {
  fetchQuotesList,
  fetchFilterOptions,
  getActionStatusesForUser,
} from "@/entities/quote";
import type { QuotesFilterParams } from "@/entities/quote";
import { isSalesOnly } from "@/shared/lib/roles";
import { QuotesTableClient } from "@/features/quotes";

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * Parse multi-value URL params (comma-separated) into string arrays.
 * Handles single value, comma-separated value, or already-array case.
 */
function parseMultiValue(
  raw: string | string[] | undefined
): string[] | undefined {
  if (raw === undefined) return undefined;
  if (Array.isArray(raw)) {
    return raw.flatMap((v) => v.split(",")).filter((v) => v.length > 0);
  }
  const parts = raw.split(",").filter((v) => v.length > 0);
  return parts.length > 0 ? parts : undefined;
}

function parseNumericParam(raw: string | string[] | undefined): number | undefined {
  if (raw === undefined || Array.isArray(raw)) return undefined;
  const n = Number(raw);
  return Number.isFinite(n) ? n : undefined;
}

function parseStringParam(raw: string | string[] | undefined): string | undefined {
  if (raw === undefined) return undefined;
  if (Array.isArray(raw)) return raw[0];
  return raw;
}

export default async function QuotesPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const params = await searchParams;

  const participantsLogicRaw = parseStringParam(params.participants__logic);
  const participantsLogic: "or" | "and" | undefined =
    participantsLogicRaw === "and" ? "and" : undefined;

  const filters: QuotesFilterParams = {
    status: parseMultiValue(params.status),
    customer: parseMultiValue(params.customer),
    manager: parseMultiValue(params.manager),
    brand: parseMultiValue(params.brand),
    procurement_manager: parseMultiValue(params.procurement_manager),
    participants: parseMultiValue(params.participants),
    participants_logic: participantsLogic,
    amount_min: parseNumericParam(params.amount__min),
    amount_max: parseNumericParam(params.amount__max),
    sort: parseStringParam(params.sort),
    search: parseStringParam(params.search),
    page: params.page ? parseInt(parseStringParam(params.page) ?? "1", 10) : 1,
  };

  // Sales users need their group ID to expand head_of_sales access to group members.
  const salesGroupId = isSalesOnly(user.roles)
    ? await fetchUserSalesGroupId(user.id, user.orgId)
    : null;

  const accessUser = {
    id: user.id,
    roles: user.roles,
    orgId: user.orgId,
    salesGroupId,
  };

  const [quotesResult, filterOptions] = await Promise.all([
    fetchQuotesList(filters, accessUser),
    fetchFilterOptions(user.orgId, accessUser),
  ]);

  const actionStatuses = getActionStatusesForUser(user.roles);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Коммерческие предложения</h1>
      <QuotesTableClient
        rows={quotesResult.data}
        total={quotesResult.total}
        page={quotesResult.page}
        pageSize={quotesResult.pageSize}
        filterOptions={filterOptions}
        userRoles={user.roles}
        userId={user.id}
        orgId={user.orgId}
        actionStatuses={actionStatuses}
      />
    </div>
  );
}
