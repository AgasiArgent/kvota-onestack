"use client";

/**
 * Centre pane of the flow runner — the focused node for the current step.
 * If the step's `node_id` resolves to a node in the API manifest, we render
 * a larger version of the node card (title, route, cluster, status chips).
 * If it doesn't (ghost nodes or stale references), we render a
 * "Узел недоступен" badge per Req 18.10 and still show the action/note so
 * the user can skip forward.
 *
 * The pure `isStepMissingNode` helper lives here so tests can verify the
 * missing-node detection without mounting TanStack Query.
 */

import { useNodeDetail, type JourneyFlowStep } from "@/entities/journey";

// ---------------------------------------------------------------------------
// Pure helper — exported for unit tests.
// ---------------------------------------------------------------------------

/**
 * True if the step references a node_id absent from the current manifest.
 * Caller supplies the set of manifest node_ids (typically from
 * `journey-manifest.json`); the helper is a set-membership check expressed
 * as a named function for readability in tests.
 */
export function isStepMissingNode(
  step: JourneyFlowStep,
  manifestNodeIds: ReadonlySet<string>
): boolean {
  return !manifestNodeIds.has(step.node_id);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  readonly step: JourneyFlowStep;
  /**
   * Set of known manifest node_ids — passed from FlowView so the component
   * can show "Узел недоступен" without waiting for a 404 from the API.
   * Optional: if undefined, we trust the API result and fall back to
   * detecting missing via the query error state.
   */
  readonly manifestNodeIds?: ReadonlySet<string>;
}

export function FlowFocusNode({ step, manifestNodeIds }: Props) {
  const missing = manifestNodeIds
    ? isStepMissingNode(step, manifestNodeIds)
    : false;

  // Always call the hook (Rules of Hooks) but short-circuit rendering
  // before the query result is read when the node is known missing. React
  // Query will still issue a request for the real id; the missing branch
  // just doesn't consume it.
  const detail = useNodeDetail(step.node_id);

  return (
    <section
      data-testid="journey-flow-focus-node"
      className="flex flex-col items-stretch gap-4 overflow-y-auto p-6"
    >
      <header className="flex flex-col gap-1">
        <div className="text-[11px] font-medium uppercase tracking-wide text-text-subtle">
          Действие
        </div>
        <h2 className="text-lg font-semibold text-text-default">
          {step.action}
        </h2>
        {step.note ? (
          <p className="text-sm text-text-subtle">{step.note}</p>
        ) : null}
      </header>

      {missing ? (
        <div
          data-testid="journey-flow-focus-missing"
          role="status"
          className="flex flex-col gap-2 rounded-md border border-warning bg-warning/10 p-4"
        >
          <span className="inline-flex w-fit items-center gap-2 rounded-sm bg-warning/20 px-2 py-0.5 text-xs font-medium text-warning">
            Узел недоступен
          </span>
          <p className="text-sm text-text-subtle">
            Этот шаг ссылается на узел{" "}
            <code className="rounded bg-surface-muted px-1 py-0.5 text-xs">
              {step.node_id}
            </code>
            , которого нет в текущем манифесте. Можно перейти к следующему шагу.
          </p>
        </div>
      ) : detail.isLoading ? (
        <div
          data-testid="journey-flow-focus-loading"
          className="rounded-md border border-border-light bg-background p-6 text-sm text-text-subtle"
        >
          Загрузка узла…
        </div>
      ) : detail.isError || !detail.data ? (
        <div
          data-testid="journey-flow-focus-missing"
          role="status"
          className="flex flex-col gap-2 rounded-md border border-warning bg-warning/10 p-4"
        >
          <span className="inline-flex w-fit items-center gap-2 rounded-sm bg-warning/20 px-2 py-0.5 text-xs font-medium text-warning">
            Узел недоступен
          </span>
          <p className="text-sm text-text-subtle">
            Не удалось загрузить узел{" "}
            <code className="rounded bg-surface-muted px-1 py-0.5 text-xs">
              {step.node_id}
            </code>
            . Можно перейти к следующему шагу.
          </p>
        </div>
      ) : (
        <article
          data-testid="journey-flow-focus-card"
          className="flex flex-col gap-3 rounded-lg border border-border-strong bg-background p-6 shadow-sm"
        >
          <div className="flex flex-col gap-0.5">
            <div className="text-[11px] font-medium uppercase tracking-wide text-text-subtle">
              {detail.data.cluster}
            </div>
            <h3 className="text-xl font-semibold text-text-default">
              {detail.data.title}
            </h3>
            <code className="text-xs text-text-subtle">
              {detail.data.route}
            </code>
          </div>
          <div className="flex flex-wrap gap-2">
            {detail.data.impl_status ? (
              <span className="inline-flex rounded-sm bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-text-default">
                impl: {detail.data.impl_status}
              </span>
            ) : null}
            {detail.data.qa_status ? (
              <span className="inline-flex rounded-sm bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-text-default">
                qa: {detail.data.qa_status}
              </span>
            ) : null}
            {detail.data.roles.map((role) => (
              <span
                key={role}
                className="inline-flex rounded-sm bg-accent/10 px-2 py-0.5 text-[11px] font-medium text-accent"
              >
                {role}
              </span>
            ))}
          </div>
          {detail.data.notes ? (
            <p className="text-sm text-text-default">{detail.data.notes}</p>
          ) : null}
        </article>
      )}
    </section>
  );
}
