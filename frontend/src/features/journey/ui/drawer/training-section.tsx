"use client";

/**
 * Training section (Task 27) — renders `mode="training"` pins as ordered
 * markdown cards. Admin / head_of_* can open the editor dialog to create,
 * edit, reorder, or delete steps.
 *
 * Reqs: 5.4 (ordered markdown blocks, ordered by `training_step_order`),
 * 8.2 (training pins require a non-null `training_step_order`), 12.10
 * (CUD restricted to admin + head_of_*).
 *
 * Collapsed by default via a native `<details>` element so SSR rendering
 * remains testable without a DOM. shadcn's Collapsible would require
 * Radix Portal, which doesn't SSR cleanly for the assertion pattern used
 * in the drawer tests (see `node-drawer.test.tsx` §header).
 *
 * `react-markdown` renders step bodies with its default safe config — raw
 * HTML is rejected, only standard markdown passes. No `rehype-raw` plugin
 * is registered, so injection from the DB is not a concern beyond what the
 * markdown grammar allows (hyperlinks, images, emphasis, code).
 */

import { useState } from "react";
import ReactMarkdown from "react-markdown";

import {
  canEditTraining,
  type JourneyNodeDetail,
  type RoleSlug,
} from "@/entities/journey";
import { Button } from "@/components/ui/button";

import { orderTrainingSteps } from "./_training-helpers";
import { TrainingEditor } from "./training-editor";

export interface TrainingSectionProps {
  readonly detail: JourneyNodeDetail;
  /**
   * Current user's held role slugs. Gates the "Редактировать" button
   * behind `canEditTraining`. Empty / omitted → read-only view, no
   * editor affordance.
   */
  readonly userRoles?: readonly RoleSlug[];
  /** User ID used as the `created_by` on new steps — omit → button hidden. */
  readonly userId?: string;
}

export function TrainingSection({
  detail,
  userRoles = [],
  userId,
}: TrainingSectionProps) {
  const steps = orderTrainingSteps(detail.pins);
  const [editorOpen, setEditorOpen] = useState(false);
  const canEdit = Boolean(userId) && canEditTraining(userRoles);

  return (
    <section
      data-testid="training-section"
      className="p-4"
      aria-label="Шаги обучения"
    >
      <details>
        <summary className="flex cursor-pointer items-center justify-between gap-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
          <span>Обучение · {steps.length} шагов</span>
          {canEdit && (
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.preventDefault();
                setEditorOpen(true);
              }}
              data-testid="training-editor-open"
            >
              Редактировать
            </Button>
          )}
        </summary>
        <div className="mt-2">
          {steps.length === 0 ? (
            <p className="text-xs text-text-subtle">
              Шаги обучения ещё не заданы.
            </p>
          ) : (
            <ol className="space-y-2">
              {steps.map((pin, idx) => (
                <li
                  key={pin.id}
                  data-testid={`training-step-${pin.id}`}
                  className="rounded-md border border-border-light bg-background p-2 text-xs"
                >
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-background-subtle font-mono text-[11px] text-text-subtle">
                      {pin.training_step_order ?? idx + 1}
                    </span>
                    <div className="flex-1 space-y-1">
                      <div className="prose prose-sm max-w-none text-text">
                        <ReactMarkdown>
                          {pin.expected_behavior}
                        </ReactMarkdown>
                      </div>
                      <p className="break-all font-mono text-[11px] text-text-subtle">
                        {pin.selector}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </details>
      {canEdit && userId && (
        <TrainingEditor
          open={editorOpen}
          onOpenChange={setEditorOpen}
          nodeId={detail.node_id}
          pins={detail.pins}
          userId={userId}
        />
      )}
    </section>
  );
}
