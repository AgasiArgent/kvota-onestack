import { redirect } from "next/navigation";
import { getSessionUser, fetchUserSalesGroupId } from "@/entities/user";
import { fetchAllChats, fetchOrgMembers } from "@/features/messages";
import { MessagesInbox } from "@/features/messages";
import { isSalesOnly } from "@/shared/lib/roles";

export default async function MessagesPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

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

  const [chats, orgMembers] = await Promise.all([
    fetchAllChats(accessUser, "all"),
    fetchOrgMembers(user.orgId),
  ]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Сообщения</h1>
      <MessagesInbox
        chats={chats}
        userId={user.id}
        orgId={user.orgId}
        orgMembers={orgMembers}
      />
    </div>
  );
}
