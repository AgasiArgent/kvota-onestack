import { redirect } from "next/navigation";
import { getSessionUser, fetchUserSalesGroupId } from "@/entities/user";
import { fetchAllChats, fetchOrgMembers } from "@/features/messages";
import { MessagesInbox } from "@/features/messages";
import { isSalesOnly } from "@/shared/lib/roles";

interface Props {
  searchParams: Promise<{ filter?: string }>;
}

export default async function MessagesPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const { filter: filterParam } = await searchParams;
  const filter: "all" | "my" = filterParam === "my" ? "my" : "all";

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

  // Fetch BOTH lists at once so the inbox can switch tabs client-side without
  // a roundtrip. They are role-scoped server-side; "Мои КП" further narrows
  // to quotes the user is personally responsible for (МОП/МОЗ/МОЛ/МОТ).
  const [allChats, myChats, orgMembers] = await Promise.all([
    fetchAllChats(accessUser, "all"),
    fetchAllChats(accessUser, "my"),
    fetchOrgMembers(user.orgId),
  ]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Сообщения</h1>
      <MessagesInbox
        chats={allChats}
        myChats={myChats}
        initialFilter={filter}
        userId={user.id}
        orgId={user.orgId}
        orgMembers={orgMembers}
      />
    </div>
  );
}
