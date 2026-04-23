"use client";

/**
 * Status section — read-only in Task 18. Task 19 replaces the badges with
 * editable controls (the inline-edit + optimistic PATCH flow in Req 5.5,
 * 6.1). We keep the shape stable so Task 19 can drop in controls without
 * touching adjacent sections.
 */

import type { ImplStatus, JourneyNodeDetail, QaStatus } from "@/entities/journey";

export interface StatusSectionProps {
  readonly detail: JourneyNodeDetail;
}

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

export function StatusSection({ detail }: StatusSectionProps) {
  return (
    <section
      data-testid="status-section"
      className="p-4"
      aria-label="Статус"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Статус
      </h3>
      <dl className="space-y-2 text-xs">
        <div className="flex items-center gap-2">
          <dt className="w-24 text-text-subtle">Реализация</dt>
          <dd>
            <ImplBadge status={detail.impl_status} />
          </dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="w-24 text-text-subtle">QA</dt>
          <dd>
            <QaBadge status={detail.qa_status} />
          </dd>
        </div>
        {detail.notes && (
          <div className="flex items-start gap-2">
            <dt className="w-24 text-text-subtle">Заметки</dt>
            <dd className="text-text">{detail.notes}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}
