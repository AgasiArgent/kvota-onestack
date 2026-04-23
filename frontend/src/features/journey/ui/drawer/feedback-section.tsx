"use client";

/**
 * Feedback section — top-3 items + "view all" link (Req 5.1, 5.3, 11).
 *
 * The backend ensures `detail.feedback` is already the top-3 (server-side
 * limit per Task 11). The "view all" link opens the existing admin feedback
 * page filtered by this node — we do NOT duplicate feedback-list logic
 * (Req 5.3).
 */

import type { JourneyNodeDetail, JourneyNodeId } from "@/entities/journey";

/** Pure URL builder — exported for unit tests. */
export function feedbackHrefForNode(nodeId: JourneyNodeId): string {
  const params = new URLSearchParams({ node_id: nodeId });
  return `/admin/feedback?${params.toString()}`;
}

export interface FeedbackSectionProps {
  readonly detail: JourneyNodeDetail;
}

export function FeedbackSection({ detail }: FeedbackSectionProps) {
  const href = feedbackHrefForNode(detail.node_id);
  return (
    <section
      data-testid="feedback-section"
      className="p-4"
      aria-label="Отзывы пользователей"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Отзывы пользователей
      </h3>
      {detail.feedback.length === 0 ? (
        <p className="text-xs text-text-subtle">Отзывов пока нет</p>
      ) : (
        <ul className="space-y-2">
          {detail.feedback.map((fb) => (
            <li
              key={fb.id}
              className="rounded-md border border-border-light bg-background p-2 text-xs"
            >
              <div className="flex items-center justify-between text-text-subtle">
                <span className="font-mono">{fb.short_id ?? fb.id.slice(0, 8)}</span>
                {fb.status && <span>{fb.status}</span>}
              </div>
              {fb.description && (
                <p className="mt-1 text-text line-clamp-2">{fb.description}</p>
              )}
            </li>
          ))}
        </ul>
      )}
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 inline-block text-xs font-medium text-accent hover:underline"
      >
        Все отзывы →
      </a>
    </section>
  );
}
