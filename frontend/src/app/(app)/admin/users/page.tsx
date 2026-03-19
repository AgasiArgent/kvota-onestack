import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchOrgMembers, fetchAllRoles } from "@/entities/admin";
import { UsersPageClient } from "@/features/admin-users";

export default async function AdminUsersPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  if (!user.roles.includes("admin")) redirect("/quotes");

  const [members, allRoles] = await Promise.all([
    fetchOrgMembers(user.orgId),
    fetchAllRoles(user.orgId),
  ]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Пользователи</h1>
      <UsersPageClient
        members={members}
        allRoles={allRoles}
        orgId={user.orgId}
        currentUserId={user.id}
      />
    </div>
  );
}
