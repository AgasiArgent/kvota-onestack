/**
 * Date formatting helpers for chat / messages UI.
 *
 * All chat surfaces show **absolute** timestamps so optimistic-inserted
 * messages don't visibly snap from "только что" → "29 апр. 14:55" when the
 * server round-trip completes (МОП/РОП тест 2026-05-03 — M5/M6/QP8/QP9).
 *
 * Times are rendered in `Europe/Moscow` so messages around midnight don't
 * land on the wrong day for users in non-MSK timezones.
 */

const MOSCOW_TZ = "Europe/Moscow";

function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

/**
 * Telegram-style chat-list timestamp.
 *
 * - today           → `HH:mm` (e.g., "14:55")
 * - yesterday       → `вчера`
 * - same calendar yr→ `D MMM` (e.g., "29 апр")
 * - older           → `DD.MM.YYYY`
 *
 * Returns an empty string if the input is missing/invalid so callers can
 * pass `chat.lastMessageAt` for empty chats without an explicit guard.
 */
export function formatChatListTimestamp(
  value: string | null | undefined,
  now: Date = new Date(),
): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  const startOfToday = startOfDay(now);
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);

  if (date >= startOfToday) {
    return date.toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: MOSCOW_TZ,
    });
  }

  if (date >= startOfYesterday) {
    return "вчера";
  }

  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "short",
      timeZone: MOSCOW_TZ,
    });
  }

  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: MOSCOW_TZ,
  });
}
