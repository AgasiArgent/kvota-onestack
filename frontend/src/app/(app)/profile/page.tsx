import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchCurrentUserProfile } from "@/entities/profile";
import { ProfileForm } from "@/features/profile";

export default async function ProfilePage() {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const profile = await fetchCurrentUserProfile();
  if (!profile) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-4">Профиль</h1>
        <p className="text-text-muted">Профиль не найден.</p>
      </div>
    );
  }

  return <ProfileForm profile={profile} email={user.email} />;
}
