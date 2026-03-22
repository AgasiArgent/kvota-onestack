import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchAllChats, fetchOrgMembers } from "@/features/messages";
import { MessagesInbox } from "@/features/messages";

export default async function MessagesPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const [chats, orgMembers] = await Promise.all([
    fetchAllChats(user.id, user.orgId),
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
