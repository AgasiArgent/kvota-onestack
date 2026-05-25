import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { getSessionUser, isNewbieOnly } from "@/entities/user";
import { Sidebar } from "@/widgets/sidebar";
import { FeedbackButton } from "@/features/feedback";
import { fetchUnassignedItemCount } from "@/features/procurement-distribution/api/server-queries";

const AWAITING_ROLE_PATH = "/awaiting-role";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();

  if (!user) {
    redirect("/login");
  }

  // Testing 2 row 38p2 — newbie-only users have no functional access.
  // Redirect every (app)/* request to the awaiting-role placeholder so
  // they cannot reach quotes, dashboards, admin pages, etc. by URL.
  // Allow the awaiting-role page itself to render to avoid a redirect
  // loop. The pathname comes from a middleware-injected header
  // (shared/lib/supabase/middleware.ts) since Server Components cannot
  // read the current URL directly.
  if (isNewbieOnly(user.roles)) {
    const headerList = await headers();
    const pathname = headerList.get("x-pathname") ?? "";
    if (!pathname.startsWith(AWAITING_ROLE_PATH)) {
      redirect(AWAITING_ROLE_PATH);
    }
  }

  const canSeeDistribution =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement");
  const unassignedDistributionCount =
    canSeeDistribution && user.orgId
      ? await fetchUnassignedItemCount(user.orgId)
      : 0;

  return (
    <div className="flex min-h-screen">
      <Sidebar user={user} unassignedDistributionCount={unassignedDistributionCount} />
      <main className="flex-1 min-w-0 sidebar-margin p-6">
        {children}
      </main>
      <FeedbackButton />
    </div>
  );
}
