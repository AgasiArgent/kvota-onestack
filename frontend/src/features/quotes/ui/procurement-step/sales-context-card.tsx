"use client";

import { useState, useEffect } from "react";
import { Loader2, ArrowRightLeft, ClipboardList } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ROLE_LABELS_RU } from "@/entities/user";
import { createClient } from "@/shared/lib/supabase/client";

interface SalesChecklist {
  is_estimate?: boolean;
  is_tender?: boolean;
  direct_request?: boolean;
  trading_org_request?: boolean;
  equipment_description?: string;
  completed_at?: string;
  completed_by?: string;
}

interface HandoverData {
  date: string | null;
  actorName: string;
  actorRole: string;
}

interface SalesContextCardProps {
  quoteId: string;
  salesChecklist: SalesChecklist | null;
  salesManagerName: string | null;
}

export function SalesContextCard({
  quoteId,
  salesChecklist,
  salesManagerName,
}: SalesContextCardProps) {
  const [loading, setLoading] = useState(true);
  const [handover, setHandover] = useState<HandoverData | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const supabase = createClient();

        const { data: transitions, error: transitionsError } = await supabase
          .from("workflow_transitions")
          .select(
            "id, from_status, to_status, actor_id, actor_role, created_at"
          )
          .eq("quote_id", quoteId)
          .order("created_at", { ascending: true });

        if (transitionsError) throw transitionsError;

        const handoverTransition = [...(transitions ?? [])]
          .reverse()
          .find((t) => t.to_status === "pending_procurement");

        if (!handoverTransition) {
          setLoading(false);
          return;
        }

        // Fetch actor name
        const { data: profile } = await supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .eq("user_id", handoverTransition.actor_id)
          .single();

        setHandover({
          date: handoverTransition.created_at,
          actorName: profile?.full_name ?? "—",
          actorRole: handoverTransition.actor_role,
        });
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [quoteId]);

  // No data at all — old quote transferred before checklist existed
  if (!loading && !handover && !salesChecklist) {
    return null;
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
        <Loader2 size={14} className="animate-spin" />
        Загрузка контекста...
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-sm text-muted-foreground">
        Не удалось загрузить данные о передаче
      </p>
    );
  }

  const requestBadges = buildRequestBadges(salesChecklist);

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Handover info */}
        {handover && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <ArrowRightLeft size={14} className="text-muted-foreground" />
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Передача в закупки
              </h4>
            </div>
            <div className="space-y-1.5 text-sm">
              <InfoRow label="Дата" value={formatDate(handover.date)} />
              <InfoRow
                label="Передал"
                value={`${handover.actorName} (${ROLE_LABELS_RU[handover.actorRole] ?? handover.actorRole})`}
              />
              {salesManagerName && (
                <InfoRow label="МОП" value={salesManagerName} />
              )}
            </div>
          </div>
        )}

        {/* Request context */}
        {salesChecklist && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <ClipboardList size={14} className="text-muted-foreground" />
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Контекст запроса
              </h4>
            </div>

            {requestBadges.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {requestBadges.map((badge) => (
                  <Badge key={badge} variant="secondary">
                    {badge}
                  </Badge>
                ))}
              </div>
            )}

            {salesChecklist.equipment_description && (
              <p className="text-sm text-muted-foreground mt-2">
                {salesChecklist.equipment_description}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[80px_1fr] items-center gap-2">
      <span className="text-muted-foreground font-medium">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function buildRequestBadges(checklist: SalesChecklist | null): string[] {
  if (!checklist) return [];
  const badges: string[] = [];
  if (checklist.is_estimate) badges.push("Проценка");
  if (checklist.is_tender) badges.push("Тендер");
  if (checklist.direct_request) badges.push("Прямой запрос");
  if (checklist.trading_org_request) badges.push("Через торгующих");
  return badges;
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
  });
}
