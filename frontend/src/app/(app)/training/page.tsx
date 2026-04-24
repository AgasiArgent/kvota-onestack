import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user/server";
import { fetchTrainingVideos, fetchCategories } from "@/entities/training-video";
import { TrainingPage } from "@/features/training";

interface Props {
  searchParams: Promise<{ category?: string }>;
}

export default async function TrainingRoute({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const params = await searchParams;
  const category = params.category ?? "";

  const [videos, categories] = await Promise.all([
    fetchTrainingVideos(user.orgId, category || undefined),
    fetchCategories(user.orgId),
  ]);

  const isAdmin = user.roles.includes("admin");

  return (
    <div>
      <TrainingPage
        videos={videos}
        categories={categories}
        activeCategory={category}
        isAdmin={isAdmin}
        orgId={user.orgId}
        userId={user.id}
      />
    </div>
  );
}
