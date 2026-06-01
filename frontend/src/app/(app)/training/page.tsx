import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchTrainingVideos, fetchCategories } from "@/entities/training-video";
import { fetchAllRoles } from "@/entities/admin";
import { TrainingPage } from "@/features/training";

interface Props {
  searchParams: Promise<{ category?: string }>;
}

export default async function TrainingRoute({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const params = await searchParams;
  const category = params.category ?? "";

  const isAdmin = user.roles.includes("admin");

  // Admins manage materials, so they see everything (pass no role filter).
  // Everyone else is filtered to materials visible to their department + role
  // (Testing 2 row 54). The filter runs on the data path in queries.ts.
  const viewerRoles = isAdmin ? undefined : user.roles;

  const [videos, categories, roleOptions] = await Promise.all([
    fetchTrainingVideos(user.orgId, category || undefined, viewerRoles),
    fetchCategories(user.orgId, viewerRoles),
    // Role options for the visibility editor — only needed for admins.
    isAdmin ? fetchAllRoles(user.orgId) : Promise.resolve([]),
  ]);

  return (
    <div>
      <TrainingPage
        videos={videos}
        categories={categories}
        activeCategory={category}
        isAdmin={isAdmin}
        orgId={user.orgId}
        userId={user.id}
        roleOptions={roleOptions}
      />
    </div>
  );
}
