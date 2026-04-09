import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchOrgMembers, fetchAllRoles, fetchSalesGroups } from "@/entities/admin";
import { UsersPageClient } from "@/features/admin-users";

export default async function AdminUsersPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  if (!user.roles.includes("admin")) redirect("/quotes");

  const [members, allRoles, salesGroups] = await Promise.all([
    fetchOrgMembers(user.orgId),
    fetchAllRoles(user.orgId),
    fetchSalesGroups(),
  ]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Пользователи</h1>
      <UsersPageClient
        members={members}
        allRoles={allRoles}
        salesGroups={salesGroups}
        orgId={user.orgId}
      />
    </div>
  );
}
