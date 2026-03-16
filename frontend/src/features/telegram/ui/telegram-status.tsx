"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Send,
  CheckCircle2,
  LinkIcon,
  Unlink,
  Bell,
  ClipboardCheck,
  ArrowRightLeft,
  Loader2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { createClient } from "@/shared/lib/supabase/client";

interface TelegramUser {
  id: string;
  telegram_id: number;
  telegram_username: string | null;
  is_verified: boolean | null;
  verified_at: string | null;
}

interface Props {
  initialData: TelegramUser | null;
  userId: string;
  botUsername: string;
}

const NOTIFICATION_TYPES = [
  { icon: ClipboardCheck, label: "Новые задачи и назначения" },
  { icon: Bell, label: "Согласования и одобрения" },
  { icon: ArrowRightLeft, label: "Смена статусов КП и сделок" },
];

const POLL_INTERVAL_MS = 3000;
const POLL_MAX_DURATION_MS = 30000;

export function TelegramStatus({ initialData, userId, botUsername }: Props) {
  const router = useRouter();
  const [telegramUser, setTelegramUser] = useState<TelegramUser | null>(
    initialData
  );
  const [polling, setPolling] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollStartRef = useRef<number>(0);

  const isConnected = telegramUser?.is_verified === true;

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setPolling(false);
  }, []);

  const checkStatus = useCallback(async () => {
    const supabase = createClient();
    const { data } = await supabase
      .from("telegram_users")
      .select(
        "id, telegram_id, telegram_username, is_verified, verified_at"
      )
      .eq("user_id", userId)
      .maybeSingle();

    if (data?.is_verified) {
      setTelegramUser(data);
      stopPolling();
      return;
    }

    if (Date.now() - pollStartRef.current >= POLL_MAX_DURATION_MS) {
      stopPolling();
    }
  }, [userId, stopPolling]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, []);

  function handleConnect() {
    const deepLink = `https://t.me/${botUsername}?start=${userId}`;
    window.open(deepLink, "_blank");

    setPolling(true);
    pollStartRef.current = Date.now();
    pollTimerRef.current = setInterval(checkStatus, POLL_INTERVAL_MS);
  }

  async function handleDisconnect() {
    setDisconnecting(true);
    try {
      const supabase = createClient();
      await supabase
        .from("telegram_users")
        .delete()
        .eq("user_id", userId);

      setTelegramUser(null);
      router.refresh();
    } catch (err) {
      console.error("Failed to disconnect Telegram:", err);
    } finally {
      setDisconnecting(false);
    }
  }

  if (isConnected) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Уведомления в Telegram</h1>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-[var(--success)]" />
              Telegram подключен
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                {telegramUser.telegram_username && (
                  <p className="text-sm">
                    <span className="text-[var(--text-muted)]">Аккаунт: </span>
                    <span className="font-medium">
                      @{telegramUser.telegram_username}
                    </span>
                  </p>
                )}
                {telegramUser.verified_at && (
                  <p className="text-sm text-[var(--text-muted)]">
                    Подключен{" "}
                    {new Date(telegramUser.verified_at).toLocaleDateString(
                      "ru-RU",
                      {
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                      }
                    )}
                  </p>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="text-[var(--error)]"
              >
                {disconnecting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Unlink className="h-4 w-4 mr-2" />
                )}
                {disconnecting ? "Отключение..." : "Отключить"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <NotificationTypesCard />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Уведомления в Telegram</h1>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Send className="h-5 w-5 text-[var(--text-muted)]" />
            Подключите Telegram
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-[var(--text-muted)]">
            Получайте мгновенные уведомления о задачах, согласованиях и
            изменениях статусов прямо в Telegram.
          </p>

          <Button
            onClick={handleConnect}
            disabled={polling}
            className="bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]"
          >
            {polling ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Ожидание подключения...
              </>
            ) : (
              <>
                <LinkIcon className="h-4 w-4 mr-2" />
                Подключить Telegram
              </>
            )}
          </Button>

          {polling && (
            <p className="text-xs text-[var(--text-muted)]">
              Откройте бота в Telegram и нажмите Start. Статус обновится
              автоматически.
            </p>
          )}
        </CardContent>
      </Card>

      <NotificationTypesCard />
    </div>
  );
}

function NotificationTypesCard() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Какие уведомления вы получите</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {NOTIFICATION_TYPES.map((item) => (
            <li key={item.label} className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent-subtle)]">
                <item.icon className="h-4 w-4 text-[var(--accent)]" />
              </div>
              <span className="text-sm">{item.label}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
