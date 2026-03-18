import { TelegramStatus } from "@/features/telegram";

interface Props {
  initialData: {
    id: string;
    telegram_id: number;
    telegram_username: string | null;
    is_verified: boolean | null;
    verified_at: string | null;
  } | null;
  userId: string;
  botUsername: string;
}

export function TelegramSection({ initialData, userId, botUsername }: Props) {
  return (
    <div id="notifications">
      <h2 className="text-lg font-semibold mb-3">Уведомления</h2>
      <TelegramStatus
        initialData={initialData}
        userId={userId}
        botUsername={botUsername}
      />
    </div>
  );
}
