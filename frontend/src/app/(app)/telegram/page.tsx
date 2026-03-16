import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { createAdminClient } from "@/shared/lib/supabase/server";
import { TelegramStatus } from "@/features/telegram";

export default async function TelegramPage() {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? "";

  const admin = createAdminClient();
  const { data: telegramUser } = await admin
    .from("telegram_users")
    .select(
      "id, telegram_id, telegram_username, is_verified, verified_at"
    )
    .eq("user_id", user.id)
    .maybeSingle();

  return (
    <TelegramStatus
      initialData={telegramUser}
      userId={user.id}
      botUsername={botUsername}
    />
  );
}
