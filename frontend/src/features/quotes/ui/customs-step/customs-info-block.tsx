"use client";

import { useState, useEffect } from "react";
import { Loader2, User, History } from "lucide-react";
import { createClient } from "@/shared/lib/supabase/client";

const STATUS_LABELS_RU: Record<string, string> = {
  draft: "Черновик",
  pending_procurement: "На закупке",
  procurement_complete: "Закупка завершена",
  pending_logistics: "На логистике",
  logistics_complete: "Логистика завершена",
  pending_customs: "На таможне",
  customs_complete: "Таможня завершена",
  calculated: "Рассчитано",
  pending_approval: "На согласовании",
  pending_quote_control: "Контроль КП",
  pending_spec_control: "Контроль спецификации",
  pending_sales_review: "Ревью продаж",
  approved: "Одобрено",
  sent_to_client: "Отправлено клиенту",
  accepted: "Принято",
  spec_signed: "Сделка",
  rejected: "Отклонено",
  cancelled: "Отменено",
};

const ROLE_LABELS_RU: Record<string, string> = {
  admin: "Администратор",
  sales: "Продажи",
  procurement: "Закупки",
  logistics: "Логистика",
  customs: "Таможня",
  quote_controller: "Контроль КП",
  spec_controller: "Контроль спецификаций",
  finance: "Финансы",
  top_manager: "Руководитель",
  head_of_sales: "Руководитель продаж",
  head_of_procurement: "Руководитель закупок",
  head_of_logistics: "Руководитель логистики",
  head_of_customs: "Руководитель таможни",
};

interface PersonInfo {
  fullName: string;
  phone: string;
  /** Origin of the data, surfaced as a tooltip when the primary source was empty. */
  sourceNote?: string;
}

interface TransitionRow {
  id: string;
  from_status: string;
  to_status: string;
  actor_role: string;
  actor_id: string;
  created_at: string | null;
}

interface CustomsInfoBlockProps {
  quoteId: string;
  orgId: string;
}

function formatTransitionDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Moscow",
  });
}

export function CustomsInfoBlock({ quoteId, orgId }: CustomsInfoBlockProps) {
  const [loading, setLoading] = useState(true);
  const [sales, setSales] = useState<PersonInfo | null>(null);
  const [procurementList, setProcurementList] = useState<PersonInfo[]>([]);
  const [customs, setCustoms] = useState<PersonInfo | null>(null);
  const [transitions, setTransitions] = useState<TransitionRow[]>([]);

  useEffect(() => {
    async function load() {
      const supabase = createClient();

      // Fetch quote to get responsible user IDs.
      // Procurement assignment lives per-item on quote_items.assigned_procurement_user
      // (single source of truth — see .kiro/specs/procurement-users-single-source/).
      const { data: quote } = await supabase
        .from("quotes")
        .select(
          "created_by, assigned_customs_user, quote_items(assigned_procurement_user)"
        )
        .eq("id", quoteId)
        .is("deleted_at", null)
        .single();

      if (!quote) {
        setLoading(false);
        return;
      }

      // Extract user IDs
      const salesUserId = quote.created_by ?? null;
      const quoteItems = (quote.quote_items ?? []) as unknown as Array<{
        assigned_procurement_user: string | null;
      }>;
      // Primary procurement source: distinct quote_items.assigned_procurement_user.
      // Preserve insertion order so the first item's МОЗ shows first.
      const procurementUserIdsPrimary: string[] = Array.from(
        new Set(
          quoteItems
            .map((i) => i.assigned_procurement_user)
            .filter((id): id is string => !!id)
        )
      );
      const customsUserId = (quote.assigned_customs_user as string) ?? null;

      // Always load workflow_transitions; we need them for the history card AND
      // for the procurement fallback below.
      const transitionsResult = await supabase
        .from("workflow_transitions")
        .select("id, from_status, to_status, actor_role, actor_id, created_at")
        .eq("quote_id", quoteId)
        .order("created_at", { ascending: false });

      const transitionRows = (transitionsResult.data ?? []) as TransitionRow[];

      // Fallback: when no per-item МОЗ is recorded, derive it from the most
      // recent workflow_transitions row that left `pending_procurement`. The
      // actor on that transition is the user who marked procurement as done.
      let procurementFallbackTransition: TransitionRow | null = null;
      let procurementUserIds: string[] = procurementUserIdsPrimary;
      if (procurementUserIds.length === 0) {
        procurementFallbackTransition =
          transitionRows.find(
            (t) => t.from_status === "pending_procurement" && !!t.actor_id
          ) ?? null;
        if (procurementFallbackTransition) {
          procurementUserIds = [procurementFallbackTransition.actor_id];
        }
      }

      // Collect unique user IDs to batch-fetch profiles
      const userIds = Array.from(
        new Set(
          [salesUserId, ...procurementUserIds, customsUserId].filter(
            (id): id is string => id !== null
          )
        )
      );

      const profilesResult =
        userIds.length > 0
          ? await supabase
              .from("user_profiles")
              .select("user_id, full_name, phone")
              .eq("organization_id", orgId)
              .in("user_id", userIds)
          : { data: [] as { user_id: string; full_name: string | null; phone: string | null }[] };

      const profiles = profilesResult.data ?? [];
      const profileMap = new Map(
        profiles.map((p) => [
          p.user_id,
          {
            fullName: (p.full_name as string) ?? "—",
            phone: (p.phone as string) ?? "—",
          },
        ])
      );

      setSales(
        salesUserId ? profileMap.get(salesUserId) ?? null : null
      );

      const fallbackNote = procurementFallbackTransition
        ? `Назначен на этапе закупок · ${formatTransitionDate(
            procurementFallbackTransition.created_at
          )}`
        : undefined;
      const procurementResolved: PersonInfo[] = procurementUserIds
        .map((id) => {
          const profile = profileMap.get(id);
          if (!profile) return null;
          return fallbackNote ? { ...profile, sourceNote: fallbackNote } : profile;
        })
        .filter((p): p is PersonInfo => p !== null);
      setProcurementList(procurementResolved);

      setCustoms(
        customsUserId ? profileMap.get(customsUserId) ?? null : null
      );
      setTransitions(transitionRows);
      setLoading(false);
    }

    load();
  }, [quoteId, orgId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
        <Loader2 size={14} className="animate-spin" />
        Загрузка информации...
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Card: Responsible Persons */}
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-center gap-2 mb-3">
          <User size={14} className="text-muted-foreground" />
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Ответственные
          </h4>
        </div>

        <div className="space-y-2">
          <PersonRow role="МОП" person={sales} />
          <ProcurementRows people={procurementList} />
          <PersonRow role="Таможня" person={customs} />
        </div>
      </div>

      {/* Card: Workflow History */}
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-center gap-2 mb-3">
          <History size={14} className="text-muted-foreground" />
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            История
          </h4>
        </div>

        {transitions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Нет переходов</p>
        ) : (
          <ul className="space-y-1.5 max-h-48 overflow-y-auto">
            {transitions.map((t) => (
              <li key={t.id} className="text-sm text-foreground">
                <span className="text-muted-foreground">
                  {formatDate(t.created_at)}
                </span>
                {" — "}
                <span className="font-medium">
                  {ROLE_LABELS_RU[t.actor_role] ?? t.actor_role}
                </span>
                {": "}
                {STATUS_LABELS_RU[t.from_status] ?? t.from_status}
                {" → "}
                {STATUS_LABELS_RU[t.to_status] ?? t.to_status}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function PersonRow({
  role,
  person,
}: {
  role: string;
  person: PersonInfo | null;
}) {
  return (
    <div className="grid grid-cols-[80px_1fr_auto] items-center gap-2 text-sm">
      <span className="text-muted-foreground font-medium">{role}</span>
      <span className="truncate" title={person?.sourceNote}>
        {person ? person.fullName : "Не назначен"}
      </span>
      <span className="text-muted-foreground text-xs tabular-nums">
        {person?.phone && person.phone !== "—" ? person.phone : ""}
      </span>
    </div>
  );
}

function ProcurementRows({ people }: { people: PersonInfo[] }) {
  if (people.length === 0) {
    return <PersonRow role="МОЗ" person={null} />;
  }
  return (
    <>
      {people.map((person, idx) => (
        <PersonRow
          // Index is safe — list is rebuilt as a whole on each load() and
          // ordering is stable within a single render pass.
          key={`${person.fullName}-${idx}`}
          role={idx === 0 ? "МОЗ" : ""}
          person={person}
        />
      ))}
    </>
  );
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Moscow",
    });
}
