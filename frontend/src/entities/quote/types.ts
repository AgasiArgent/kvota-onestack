export interface QuoteListItem {
  id: string;
  idn_quote: string;
  created_at: string;
  workflow_status: string;
  total_amount_quote: number | null;
  total_profit_usd: number | null;
  currency: string | null;
  customer: { id: string; name: string } | null;
  manager: { id: string; full_name: string } | null;
  version_count: number;
  current_version: number;
}

export interface QuotesFilterParams {
  status?: string; // status group key or individual status
  customer?: string; // customer UUID
  manager?: string; // manager user UUID
  page?: number; // 1-based page number
  pageSize?: number; // default 20
}

export interface QuotesListResult {
  data: QuoteListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface StatusGroup {
  key: string;
  label: string;
  statuses: string[];
  color: string;
}

export const STATUS_GROUPS: StatusGroup[] = [
  {
    key: "draft",
    label: "Черновик",
    statuses: ["draft"],
    color: "bg-slate-100 text-slate-700",
  },
  {
    key: "in_progress",
    label: "В работе",
    statuses: ["pending_procurement", "logistics", "pending_customs"],
    color: "bg-blue-100 text-blue-700",
  },
  {
    key: "approval",
    label: "Согласование",
    statuses: [
      "pending_quote_control",
      "pending_spec_control",
      "pending_sales_review",
      "pending_approval",
    ],
    color: "bg-amber-100 text-amber-700",
  },
  {
    key: "deal",
    label: "Сделка",
    statuses: ["approved", "sent_to_client", "deal"],
    color: "bg-green-100 text-green-700",
  },
  {
    key: "closed",
    label: "Закрыт",
    statuses: ["rejected", "cancelled"],
    color: "bg-red-100 text-red-700",
  },
];

const STATUS_GROUP_MAP = new Map<string, StatusGroup>();
for (const group of STATUS_GROUPS) {
  for (const status of group.statuses) {
    STATUS_GROUP_MAP.set(status, group);
  }
}

export function getStatusesForGroup(groupKey: string): string[] {
  const group = STATUS_GROUPS.find((g) => g.key === groupKey);
  return group?.statuses ?? [];
}

export function getGroupForStatus(status: string): StatusGroup | undefined {
  return STATUS_GROUP_MAP.get(status);
}
