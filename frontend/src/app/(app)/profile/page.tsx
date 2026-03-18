import { redirect } from "next/navigation";
import { getSessionUser, fetchUserDepartment } from "@/entities/user";
import { fetchCurrentUserProfile } from "@/entities/profile/queries";
import { createAdminClient } from "@/shared/lib/supabase/server";
import { ProfileForm } from "@/features/profile";
import { DepartmentSection } from "@/features/profile/ui/department-section";
import { TelegramSection } from "@/features/profile/ui/telegram-section";

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

  const department = user.orgId
    ? await fetchUserDepartment(user.id, user.orgId)
    : null;

  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? "";
  const admin = createAdminClient();
  const { data: telegramUser } = await admin
    .from("telegram_users")
    .select("id, telegram_id, telegram_username, is_verified, verified_at")
    .eq("user_id", user.id)
    .maybeSingle();

  return (
    <div className="space-y-6">
      <ProfileForm profile={profile} email={user.email} />
      {department && <DepartmentSection department={department} />}
      <TelegramSection
        initialData={telegramUser}
        userId={user.id}
        botUsername={botUsername}
      />
    </div>
  );
}
