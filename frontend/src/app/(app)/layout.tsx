import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { getAppContext } from "@/shared/lib/app-context";
import { Sidebar } from "@/widgets/sidebar";
import { FeedbackButton } from "@/features/feedback";
import { fetchUnassignedItemCount } from "@/features/procurement-distribution/api/server-queries";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();

  if (!user) {
    redirect("/login");
  }

  const appContext = await getAppContext();

  const canSeeDistribution =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement");
  const unassignedDistributionCount =
    canSeeDistribution && user.orgId
      ? await fetchUnassignedItemCount(user.orgId)
      : 0;

  return (
    <div className="flex min-h-screen">
      <Sidebar user={user} appContext={appContext} unassignedDistributionCount={unassignedDistributionCount} />
      <main className="flex-1 sidebar-margin p-6">
        {children}
      </main>
      <FeedbackButton />
    </div>
  );
}
