"use client";

import { Badge } from "@/components/ui/badge";
import { ROLE_LABELS_RU } from "@/entities/user/types";

const STATUS_LABELS_RU: Record<string, string> = {
  draft: "Черновик",
  pending_procurement: "Закупки",
  pending_logistics: "Логистика",
  pending_customs: "Таможня",
  pending_logistics_and_customs: "Лог+Таможня",
  pending_quote_control: "Контроль КП",
  pending_sales_review: "У менеджера продаж",
  pending_approval: "На одобрении",
  pending_spec_control: "Контроль спек.",
  approved: "Одобрено",
  cancelled: "Отменено",
  procurement_complete: "Закупка завершена",
  logistics_complete: "Логистика завершена",
  customs_complete: "Таможня завершена",
  calculated: "Рассчитано",
  sent_to_client: "Отправлено клиенту",
  accepted: "Принято",
  spec_signed: "Сделка",
  rejected: "Отклонено",
};

export interface ParticipantRow {
  id: string;
  actor_id: string;
  actor_role: string;
  actor_name: string;
  from_status: string;
  to_status: string;
  created_at: string | null;
}

interface ParticipantsBlockProps {
  participants: ParticipantRow[];
}

export function ParticipantsBlock({ participants }: ParticipantsBlockProps) {
  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        Участники
      </h4>

      {participants.length === 0 ? (
        <p className="text-sm text-muted-foreground">Нет переходов</p>
      ) : (
        <ul className="space-y-2 max-h-56 overflow-y-auto">
          {participants.map((p) => (
            <li key={p.id} className="flex items-start gap-2 text-sm">
              <span className="text-muted-foreground tabular-nums whitespace-nowrap shrink-0">
                {formatDate(p.created_at)}
              </span>
              <span className="font-medium shrink-0">{p.actor_name}</span>
              <Badge
                variant="outline"
                className="shrink-0 text-[10px] h-4 px-1.5"
              >
                {ROLE_LABELS_RU[p.actor_role] ?? p.actor_role}
              </Badge>
              <span className="text-muted-foreground">
                {STATUS_LABELS_RU[p.from_status] ?? p.from_status}
                {" \u2192 "}
                {STATUS_LABELS_RU[p.to_status] ?? p.to_status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  const d = new Date(dateStr);
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Moscow",
    });
}
