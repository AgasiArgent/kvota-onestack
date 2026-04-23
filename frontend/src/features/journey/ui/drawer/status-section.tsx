"use client";

/**
 * Status section — inline-editable in Task 19.
 *
 * Role-scoped (Req 6.4–6.5): controls only render for users holding the
 * relevant writer roles. View-only users (top_manager et al.) keep seeing
 * the read-only badges from Task 18.
 *
 * Wire-up (Req 5.5, 6.1–6.3):
 *   - Every change calls `useUpdateNodeState` — the hook already handles
 *     optimistic apply + snapshot + rollback on error.
 *   - On 409 STALE_VERSION the hook has already seeded the cache with the
 *     server's authoritative state; we show a toast nudging the user to
 *     retry (Req 6.2).
 *   - On 403 FORBIDDEN_FIELD the hook has rolled back to the snapshot; we
 *     show a toast naming the forbidden field (Req 6.3).
 *   - Everything else → generic toast (Req 6.6-ish).
 *
 * All orchestration is isolated here; the three sub-components
 * (`impl-status-control`, `qa-status-control`, `notes-editor`) are pure
 * presentational bits that know nothing about mutations.
 */

import { toast } from "sonner";

import { useUpdateNodeState } from "@/entities/journey";
import type {
  ImplStatus,
  JourneyNodeDetail,
  QaStatus,
  RoleSlug,
} from "@/entities/journey";

import { ImplStatusControl } from "./impl-status-control";
import { QaStatusControl } from "./qa-status-control";
import { NotesEditor } from "./notes-editor";
import {
  buildOptimisticPatch,
  canEditField,
  handleStatusMutationError,
  statusFieldLabelRu,
  type StatusField,
  type StatusPatchBody,
} from "./_status-mutation-helpers";

export interface StatusSectionProps {
  readonly detail: JourneyNodeDetail;
  /**
   * Current user's held role slugs. When empty (or the user holds only
   * view-only roles like `top_manager`), the section renders as read-only
   * badges — identical to Task 18's shape.
   */
  readonly userRoles?: readonly RoleSlug[];
}

// ---------------------------------------------------------------------------
// Read-only badges — reused when the user cannot edit a particular field.
// ---------------------------------------------------------------------------

const IMPL_LABELS: Record<ImplStatus, string> = {
  done: "Готово",
  partial: "Частично",
  missing: "Нет",
};

const QA_LABELS: Record<QaStatus, string> = {
  verified: "Проверено",
  broken: "Сломано",
  untested: "Не проверено",
};

const IMPL_CLASS: Record<ImplStatus, string> = {
  done: "bg-success-subtle text-success",
  partial: "bg-warning-subtle text-warning",
  missing: "bg-destructive/10 text-destructive",
};

const QA_CLASS: Record<QaStatus, string> = {
  verified: "bg-success-subtle text-success",
  broken: "bg-destructive/10 text-destructive",
  untested: "bg-background text-text-muted",
};

function ImplBadge({ status }: { status: ImplStatus | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center rounded-md bg-background px-2 py-0.5 text-xs text-text-subtle">
        —
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${IMPL_CLASS[status]}`}
    >
      {IMPL_LABELS[status]}
    </span>
  );
}

function QaBadge({ status }: { status: QaStatus | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center rounded-md bg-background px-2 py-0.5 text-xs text-text-subtle">
        —
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${QA_CLASS[status]}`}
    >
      {QA_LABELS[status]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StatusSection({ detail, userRoles = [] }: StatusSectionProps) {
  const mutation = useUpdateNodeState();

  const canImpl = canEditField("impl_status", userRoles);
  const canQa = canEditField("qa_status", userRoles);
  const canNotes = canEditField("notes", userRoles);

  async function commit(field: StatusField, changes: Partial<StatusPatchBody>) {
    const patch = buildOptimisticPatch({
      currentVersion: detail.version,
      changes,
    });
    try {
      await mutation.mutateAsync({ nodeId: detail.node_id, patch });
    } catch (err) {
      const kind = handleStatusMutationError(err);
      switch (kind.kind) {
        case "refresh-and-retry":
          toast.warning(
            "Узел обновлён другим пользователем. Состояние обновлено — проверьте и повторите.",
          );
          return;
        case "no-permission": {
          const label = statusFieldLabelRu(kind.field ?? field);
          toast.error(`Нет прав на изменение поля: ${label}`);
          return;
        }
        case "generic":
          toast.error("Не удалось сохранить. Попробуйте позже.");
          return;
      }
    }
  }

  return (
    <section
      data-testid="status-section"
      className="p-4"
      aria-label="Статус"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Статус
      </h3>
      <dl className="space-y-3 text-xs">
        {/* impl_status */}
        {canImpl ? (
          <ImplStatusControl
            value={detail.impl_status}
            disabled={mutation.isPending}
            onChange={(next) => void commit("impl_status", { impl_status: next })}
          />
        ) : (
          <div className="flex items-center gap-2">
            <dt className="w-24 text-text-subtle">Реализация</dt>
            <dd>
              <ImplBadge status={detail.impl_status} />
            </dd>
          </div>
        )}

        {/* qa_status */}
        {canQa ? (
          <QaStatusControl
            value={detail.qa_status}
            disabled={mutation.isPending}
            onChange={(next) => void commit("qa_status", { qa_status: next })}
          />
        ) : (
          <div className="flex items-center gap-2">
            <dt className="w-24 text-text-subtle">QA</dt>
            <dd>
              <QaBadge status={detail.qa_status} />
            </dd>
          </div>
        )}

        {/* notes */}
        {canNotes ? (
          <NotesEditor
            value={detail.notes}
            disabled={mutation.isPending}
            onSave={(next) => commit("notes", { notes: next })}
          />
        ) : (
          detail.notes && (
            <div className="flex items-start gap-2">
              <dt className="w-24 text-text-subtle">Заметки</dt>
              <dd className="text-text">{detail.notes}</dd>
            </div>
          )
        )}
      </dl>
    </section>
  );
}
