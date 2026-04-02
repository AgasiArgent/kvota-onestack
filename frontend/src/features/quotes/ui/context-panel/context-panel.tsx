"use client";

import { useState, useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import { createClient } from "@/shared/lib/supabase/client";
import {
  SalesChecklistBlock,
  type SalesChecklist,
} from "./sales-checklist-block";
import {
  ParticipantsBlock,
  type ParticipantRow,
} from "./participants-block";

interface ContextPanelData {
  salesChecklist: SalesChecklist | null;
  contactPerson: {
    name: string;
    phone: string | null;
    email: string | null;
  } | null;
  salesManager: { id: string; full_name: string } | null;
  participants: ParticipantRow[];
}

interface ContextPanelProps {
  quoteId: string;
  isOpen: boolean;
}

export function ContextPanel({ quoteId, isOpen }: ContextPanelProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ContextPanelData | null>(null);
  const fetchedRef = useRef(false);
  const prevQuoteIdRef = useRef(quoteId);

  useEffect(() => {
    if (prevQuoteIdRef.current !== quoteId) {
      prevQuoteIdRef.current = quoteId;
      fetchedRef.current = false;
      setData(null);
    }
    if (!isOpen || fetchedRef.current) return;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const supabase = createClient();

        // 1. Fetch quote fields for checklist + FK IDs
        const { data: quoteRow, error: quoteError } = await supabase
          .from("quotes")
          .select("sales_checklist, created_by, contact_person_id")
          .eq("id", quoteId)
          .single();

        if (quoteError) throw quoteError;

        const checklist =
          (quoteRow?.sales_checklist as SalesChecklist | null) ?? null;
        const contactPersonId = quoteRow?.contact_person_id ?? null;
        const createdBy = quoteRow?.created_by ?? null;

        // 2. Parallel fetch: contact person, sales manager, transitions
        const [contactRes, managerRes, transitionsRes] = await Promise.all([
          contactPersonId
            ? supabase
                .from("customer_contacts")
                .select("id, name, phone, email")
                .eq("id", contactPersonId)
                .single()
            : Promise.resolve({ data: null, error: null }),
          createdBy
            ? supabase
                .from("user_profiles")
                .select("user_id, full_name")
                .eq("user_id", createdBy)
                .single()
            : Promise.resolve({ data: null, error: null }),
          supabase
            .from("workflow_transitions")
            .select(
              "id, from_status, to_status, actor_id, actor_role, created_at"
            )
            .eq("quote_id", quoteId)
            .order("created_at", { ascending: true }),
        ]);

        const contact = contactRes.data
          ? {
              name: contactRes.data.name,
              phone: contactRes.data.phone ?? null,
              email: contactRes.data.email ?? null,
            }
          : null;

        const manager = managerRes.data
          ? {
              id: managerRes.data.user_id,
              full_name: managerRes.data.full_name ?? "",
            }
          : null;

        const transitions = transitionsRes.data ?? [];

        // 3. Batch-fetch actor names from unique actor_ids
        const actorIds = [
          ...new Set(transitions.map((t) => t.actor_id).filter(Boolean)),
        ] as string[];

        let profileMap = new Map<string, string>();

        if (actorIds.length > 0) {
          const { data: profiles } = await supabase
            .from("user_profiles")
            .select("user_id, full_name")
            .in("user_id", actorIds);

          profileMap = new Map(
            (profiles ?? []).map((p) => [
              p.user_id,
              p.full_name ?? "Неизвестный",
            ])
          );
        }

        const participants: ParticipantRow[] = transitions.map((t) => ({
          id: t.id,
          actor_id: t.actor_id ?? "",
          actor_role: t.actor_role ?? "",
          actor_name: profileMap.get(t.actor_id ?? "") ?? "Неизвестный",
          from_status: t.from_status ?? "",
          to_status: t.to_status ?? "",
          created_at: t.created_at,
        }));

        setData({
          salesChecklist: checklist,
          contactPerson: contact,
          salesManager: manager,
          participants,
        });
        fetchedRef.current = true;
      } catch {
        setError("Не удалось загрузить контекст");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [isOpen, quoteId]);

  if (!isOpen) return null;

  return (
    <div className="border-t border-border bg-card px-6 py-4">
      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={14} className="animate-spin" />
          Загрузка...
        </div>
      )}

      {error && (
        <p className="text-sm text-muted-foreground">{error}</p>
      )}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SalesChecklistBlock
            checklist={data.salesChecklist}
            contactPerson={data.contactPerson}
            salesManager={data.salesManager}
          />
          <ParticipantsBlock participants={data.participants} />
        </div>
      )}
    </div>
  );
}
