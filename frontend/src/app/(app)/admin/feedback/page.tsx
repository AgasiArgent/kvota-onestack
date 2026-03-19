import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchFeedbackList } from "@/entities/admin";
import { FeedbackList } from "@/features/admin-feedback";

interface Props {
  searchParams: Promise<{
    status?: string;
    search?: string;
    page?: string;
  }>;
}

export default async function AdminFeedbackPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  if (!user.roles.includes("admin")) redirect("/quotes");

  const params = await searchParams;

  const status = params.status || undefined;
  const search = params.search || "";
  const page = params.page ? parseInt(params.page, 10) : 1;

  const result = await fetchFeedbackList(user.orgId, status, search, page);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Обращения пользователей</h1>
      <FeedbackList
        items={result.data}
        total={result.total}
        page={result.page}
        pageSize={result.pageSize}
        activeStatus={status ?? null}
        searchQuery={search}
      />
    </div>
  );
}
