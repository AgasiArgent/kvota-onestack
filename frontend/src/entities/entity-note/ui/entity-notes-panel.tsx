"use client";

import { useTransition, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare } from "lucide-react";
import {
  EntityNoteCard,
  type EntityNoteCardData,
} from "./entity-note-card";
import { EntityNoteComposer } from "./entity-note-composer";
import {
  createEntityNote,
  updateEntityNote,
  deleteEntityNote,
  type EntityNoteEntityType,
} from "../server-actions";
import { cn } from "@/lib/utils";

/**
 * EntityNotesPanel — polymorphic comments panel.
 *
 * Server-first pattern (project convention):
 *   - Initial `initialNotes` fetched in the parent server component via
 *     apiServerClient and passed as props (no client-side React Query).
 *   - Mutations go through Server Actions which revalidatePath.
 *   - router.refresh() reruns the server component and delivers fresh data.
 *
 * entity_type="invoice" is special: invoices have no standalone route,
 * so the caller MUST pass `revalidatePath` (e.g. "/quotes/{parent_id}").
 * Propagated to Server Actions via the `revalidate_path` param.
 */

interface EntityNotesPanelProps {
  entityType: EntityNoteEntityType;
  entityId: string;
  /** Server-fetched notes, already RBAC-filtered by Python API. */
  initialNotes: EntityNoteCardData[];
  currentUser: {
    id: string;
    roles: string[];
  };
  title?: string;
  subtitle?: string;
  visibilityOptions?: Array<{ value: string; label: string }>;
  defaultVisibleTo?: string[];
  /**
   * Path to revalidate after mutations. REQUIRED when entityType="invoice".
   * For quote/customer, server action uses defaults but callers may pass
   * a more specific path.
   */
  revalidatePath?: string;
  /** Extra paths to revalidate beyond the primary one. */
  revalidateExtra?: string[];
  className?: string;
}

const DEFAULT_VISIBILITY: Array<{ value: string; label: string }> = [
  { value: "logistics", label: "Логистика" },
  { value: "customs", label: "Таможня" },
  { value: "sales", label: "Продажи (МОП)" },
  { value: "procurement", label: "Закупки (МОЗ)" },
  { value: "head_of_logistics", label: "Рук. логистики" },
  { value: "head_of_customs", label: "Рук. таможни" },
];

const DEFAULT_TITLE: Record<EntityNoteEntityType, string> = {
  quote: "Заметки по КП",
  customer: "Заметки о клиенте",
  invoice: "Комментарии к инвойсу",
};

function sortNotes(notes: EntityNoteCardData[]): EntityNoteCardData[] {
  return [...notes].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return +new Date(b.createdAt) - +new Date(a.createdAt);
  });
}

export function EntityNotesPanel({
  entityType,
  entityId,
  initialNotes,
  currentUser,
  title,
  subtitle,
  visibilityOptions = DEFAULT_VISIBILITY,
  defaultVisibleTo = ["*"],
  revalidatePath,
  revalidateExtra,
  className,
}: EntityNotesPanelProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const notes = sortNotes(initialNotes);
  const resolvedTitle = title ?? DEFAULT_TITLE[entityType];

  const handleCreate = async (body: string, visibleTo: string[]) => {
    setErrorMsg(null);
    try {
      await createEntityNote({
        entity_type: entityType,
        entity_id: entityId,
        body,
        visible_to: visibleTo,
        revalidate_path: revalidatePath,
        revalidate_extra: revalidateExtra,
      });
      startTransition(() => router.refresh());
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Не удалось создать заметку");
    }
  };

  const handleTogglePin = (id: string, currentPinned: boolean) => {
    setErrorMsg(null);
    startTransition(async () => {
      try {
        await updateEntityNote({
          note_id: id,
          entity_type: entityType,
          entity_id: entityId,
          patch: { pinned: !currentPinned },
          revalidate_path: revalidatePath,
          revalidate_extra: revalidateExtra,
        });
        router.refresh();
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Не удалось обновить");
      }
    });
  };

  const handleDelete = (id: string) => {
    setErrorMsg(null);
    startTransition(async () => {
      try {
        await deleteEntityNote({
          note_id: id,
          entity_type: entityType,
          entity_id: entityId,
          revalidate_path: revalidatePath,
          revalidate_extra: revalidateExtra,
        });
        router.refresh();
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "Не удалось удалить");
      }
    });
  };

  return (
    <section
      className={cn("rounded-lg border border-border-light bg-card", className)}
      aria-label={resolvedTitle}
      aria-busy={isPending}
    >
      <header className="px-4 py-3 border-b border-border-light">
        <div className="flex items-center gap-2">
          <MessageSquare size={14} strokeWidth={2} className="text-text-muted" aria-hidden />
          <h3 className="text-sm font-semibold text-text">{resolvedTitle}</h3>
          <span className="ml-auto text-xs text-text-subtle tabular-nums">
            {notes.length}
          </span>
        </div>
        {subtitle && <p className="mt-1 text-xs text-text-muted">{subtitle}</p>}
      </header>

      <div className="p-3 space-y-2">
        {notes.length === 0 ? (
          <div className="text-xs text-text-subtle py-4 text-center">
            Пока нет заметок
          </div>
        ) : (
          notes.map((n) => (
            <EntityNoteCard
              key={n.id}
              note={n}
              canModify={
                n.author.id === currentUser.id ||
                currentUser.roles.includes("admin") ||
                currentUser.roles.includes("top_manager")
              }
              onTogglePin={() => handleTogglePin(n.id, n.pinned)}
              onDelete={() => handleDelete(n.id)}
            />
          ))
        )}
      </div>

      {errorMsg && (
        <div
          role="alert"
          className="mx-3 mb-2 rounded-sm border border-error/30 bg-error-bg px-3 py-2 text-xs text-error"
        >
          {errorMsg}
        </div>
      )}

      <div className="p-3 pt-0">
        <EntityNoteComposer
          visibilityOptions={visibilityOptions}
          defaultVisibleTo={defaultVisibleTo}
          onSubmit={handleCreate}
          busy={isPending}
        />
      </div>
    </section>
  );
}
