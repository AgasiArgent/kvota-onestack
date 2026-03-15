import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchProcurementQueue,
  fetchBrandGroups,
} from "@/entities/phmb-quote";
import type { ProcurementQueueStatus } from "@/entities/phmb-quote";
import { ProcurementQueue } from "@/features/phmb/ui/procurement-queue";

interface Props {
  searchParams: Promise<{
    status?: string;
    brand_group_id?: string;
  }>;
}

const ALLOWED_STATUSES: ProcurementQueueStatus[] = [
  "new",
  "requested",
  "priced",
];

export default async function ProcurementQueuePage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const isProcurementOrAdmin =
    user.roles.includes("admin") ||
    user.roles.includes("procurement") ||
    user.roles.includes("training_manager");

  if (!isProcurementOrAdmin) redirect("/dashboard");
  if (!user.orgId) redirect("/dashboard");

  const params = await searchParams;
  const statusParam = params.status ?? "";
  const status = ALLOWED_STATUSES.includes(statusParam as ProcurementQueueStatus)
    ? (statusParam as ProcurementQueueStatus)
    : undefined;
  const brandGroupId = params.brand_group_id ?? "";

  const [queueItems, brandGroups] = await Promise.all([
    fetchProcurementQueue({
      orgId: user.orgId,
      status,
      brandGroupId: brandGroupId || undefined,
    }),
    fetchBrandGroups(user.orgId),
  ]);

  return (
    <ProcurementQueue
      items={queueItems}
      brandGroups={brandGroups}
      initialStatus={status}
      initialBrandGroupId={brandGroupId}
    />
  );
}
