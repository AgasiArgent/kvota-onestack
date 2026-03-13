import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { Sidebar } from "@/widgets/sidebar";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getSessionUser();

  if (!user) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar user={user} />
      <main className="flex-1 sidebar-margin p-6 max-w-[1200px]">
        {children}
      </main>
    </div>
  );
}
