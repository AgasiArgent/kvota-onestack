import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { getAppContext } from "@/shared/lib/app-context";
import { Sidebar } from "@/widgets/sidebar";
import { FeedbackButton } from "@/features/feedback";

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

  return (
    <div className="flex min-h-screen">
      <Sidebar user={user} appContext={appContext} />
      <main className="flex-1 sidebar-margin p-6 max-w-[1200px]">
        {children}
      </main>
      <FeedbackButton />
    </div>
  );
}
