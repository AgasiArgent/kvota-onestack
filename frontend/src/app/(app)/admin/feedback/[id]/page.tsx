import { redirect, notFound } from "next/navigation";
import { getSessionUser } from "@/entities/user/server";
import { fetchFeedbackDetail } from "@/entities/admin";
import { FeedbackDetailView } from "@/features/admin-feedback";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function AdminFeedbackDetailPage({ params }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  if (!user.roles.includes("admin")) redirect("/quotes");

  const { id } = await params;
  const feedback = await fetchFeedbackDetail(id, user.orgId);

  if (!feedback) notFound();

  return (
    <div>
      <FeedbackDetailView feedback={feedback} />
    </div>
  );
}
