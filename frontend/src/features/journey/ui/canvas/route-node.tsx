"use client";

/**
 * Custom React Flow node for real routes (`app:*`).
 *
 * Reqs:
 *   - 3.9 — rendered by the canvas for every non-ghost journey node
 *   - 4.2 — shows role chips (when the Roles layer is on — deferred to
 *     Task 18, currently always on)
 *   - 4.4 — impl_status coloured dot
 *   - 4.5 — qa_status coloured dot
 *   - 4.3 — stories-count badge
 *   - 4.6 — feedback-count badge
 *
 * Click behaviour: React Flow handles selection at the graph level; the
 * parent canvas translates `onNodeClick` into the drawer-opening callback.
 * We expose the selection visually via the `selected` prop React Flow
 * passes automatically.
 */

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { JourneyNodeCardData } from "./build-graph";
import {
  implStatusDotClass,
  qaStatusDotClass,
} from "./status-colors";

export function RouteNode({ data, selected }: NodeProps) {
  const d = data as unknown as JourneyNodeCardData;

  return (
    <div
      data-testid="journey-node"
      data-node-id={d.node_id}
      className={[
        "w-[280px] rounded-md border bg-background px-3 py-2 shadow-xs",
        selected ? "border-accent" : "border-border-light",
      ].join(" ")}
    >
      <Handle type="target" position={Position.Left} />

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-text" title={d.title}>
            {d.title}
          </p>
          <p
            className="mt-0.5 truncate font-mono text-xs text-text-subtle"
            title={d.route}
          >
            {d.route}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 pt-1">
          <span
            data-testid="impl-status-dot"
            aria-label={`impl: ${d.impl_status ?? "unset"}`}
            className={[
              "inline-block h-2 w-2 rounded-full",
              implStatusDotClass(d.impl_status),
            ].join(" ")}
          />
          <span
            data-testid="qa-status-dot"
            aria-label={`qa: ${d.qa_status ?? "untested"}`}
            className={[
              "inline-block h-2 w-2 rounded-full",
              qaStatusDotClass(d.qa_status),
            ].join(" ")}
          />
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-text-muted">
        <span data-testid="stories-count" className="inline-flex items-center gap-0.5">
          <span aria-hidden>📝</span>
          {d.stories_count}
        </span>
        <span data-testid="pins-count" className="inline-flex items-center gap-0.5">
          <span aria-hidden>📍</span>
          {d.pins_count}
        </span>
        <span data-testid="feedback-count" className="inline-flex items-center gap-0.5">
          <span aria-hidden>💬</span>
          {d.feedback_count}
        </span>
      </div>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}
