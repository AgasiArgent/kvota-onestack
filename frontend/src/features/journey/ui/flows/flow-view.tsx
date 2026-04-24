"use client";

/**
 * Three-pane flow runner — orchestrates fetching a single flow by slug,
 * owns the stepIndex state (via `useFlowState`), and wires the three panes.
 *
 * Req 18.4 — three-pane layout: step list | focus node | navigation.
 * Req 18.6 — keyboard nav + explicit buttons.
 * Req 18.11 — Esc returns to canvas with the last node preselected.
 *
 * Data source: `useFlows()` from `entities/journey` — filters client-side
 * by slug. Keeps the caching model simple (one query key shared with the
 * sidebar in Task 28). A dedicated `useFlow(slug)` would double-fetch for
 * marginal benefit; low-count flows make the filter cheap.
 */

import { useRouter } from "next/navigation";
import { useCallback, useMemo } from "react";
import { useFlows } from "@/entities/journey";
import { useFlowState } from "@/features/journey/lib/use-flow-state";
import { FlowStepList } from "./flow-step-list";
import { FlowFocusNode } from "./flow-focus-node";
import { FlowNavigation } from "./flow-navigation";

interface Props {
  readonly slug: string;
  /**
   * Set of manifest node_ids — passed from the page so `<FlowFocusNode />`
   * can flag missing nodes without waiting for the API. Optional; when
   * omitted the focus-node falls back to the query error state.
   */
  readonly manifestNodeIds?: ReadonlySet<string>;
}

export function FlowView({ slug, manifestNodeIds }: Props) {
  const router = useRouter();
  const { data: flows, isLoading, isError } = useFlows();
  const flow = useMemo(
    () => flows?.find((f) => f.slug === slug),
    [flows, slug]
  );

  const stepCount = flow?.steps.length ?? 0;
  const onExit = useCallback(
    (lastNodeId: string | null) => {
      const query = lastNodeId
        ? `?node=${encodeURIComponent(lastNodeId)}`
        : "";
      router.replace(`/journey${query}`);
    },
    [router]
  );

  const resolveNodeId = useCallback(
    (index: number) => flow?.steps[index]?.node_id ?? null,
    [flow]
  );
  const { stepIndex, next, prev, jumpTo, exit } = useFlowState({
    stepCount,
    onExit,
    resolveNodeId,
  });

  if (isLoading) {
    return (
      <div
        data-testid="journey-flow-view-loading"
        className="flex h-full items-center justify-center text-sm text-text-subtle"
      >
        Загрузка пути…
      </div>
    );
  }
  if (isError || !flows) {
    return (
      <div
        data-testid="journey-flow-view-error"
        className="flex h-full items-center justify-center text-sm text-text-subtle"
      >
        Не удалось загрузить пути.
      </div>
    );
  }
  if (!flow) {
    return (
      <div
        data-testid="journey-flow-view-notfound"
        className="flex h-full flex-col items-center justify-center gap-3 text-sm text-text-subtle"
      >
        <p>Путь «{slug}» не найден.</p>
        <button
          type="button"
          onClick={() => router.replace("/journey")}
          className="rounded-md border border-border-light bg-background px-3 py-2 text-sm font-medium text-text-default hover:border-border-strong"
        >
          ← К карте
        </button>
      </div>
    );
  }

  const step = flow.steps[stepIndex];
  if (!step) {
    // Defensive: flow with zero steps — render an empty-state exit card.
    return (
      <div
        data-testid="journey-flow-view-empty"
        className="flex h-full flex-col items-center justify-center gap-3 p-6 text-sm text-text-subtle"
      >
        <p>В пути «{flow.title}» нет шагов.</p>
        <button
          type="button"
          onClick={() => router.replace("/journey")}
          className="rounded-md border border-border-light bg-background px-3 py-2 text-sm font-medium text-text-default hover:border-border-strong"
        >
          ← К карте
        </button>
      </div>
    );
  }

  return (
    <div
      data-testid="journey-flow-view"
      className="grid h-[calc(100vh-64px)] grid-cols-[320px_1fr_340px]"
    >
      <FlowStepList
        steps={flow.steps}
        activeIndex={stepIndex}
        onJumpTo={jumpTo}
      />
      <main className="flex flex-col overflow-y-auto bg-background">
        <FlowFocusNode step={step} manifestNodeIds={manifestNodeIds} />
      </main>
      <FlowNavigation
        flow={flow}
        stepIndex={stepIndex}
        onPrev={prev}
        onNext={next}
        onExit={exit}
      />
    </div>
  );
}
