"use client";

/**
 * Custom React Flow node for ghost (planned-but-unshipped) routes (`ghost:*`).
 *
 * Reqs:
 *   - 3.9 — ghosts render on the canvas alongside real routes
 *   - 7.3 — dashed border, 👻 prefix, ghost-status badge; proposed_route shown
 *     where the route would be
 */

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { JourneyNodeCardData } from "./build-graph";
import { ghostStatusBadgeClasses, ghostStatusLabel } from "./status-colors";

export function GhostNode({ data, selected }: NodeProps) {
  const d = data as unknown as JourneyNodeCardData;
  const status = d.ghost_status ?? "proposed";

  return (
    <div
      data-testid="journey-node"
      data-node-id={d.node_id}
      data-ghost="true"
      className={[
        "w-[280px] rounded-md border-2 border-dashed bg-background px-3 py-2",
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
            title={d.proposed_route ?? ""}
          >
            <span aria-hidden className="mr-1">
              👻
            </span>
            {d.proposed_route ?? "—"}
          </p>
        </div>

        <span
          data-testid="ghost-status-badge"
          className={[
            "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
            ghostStatusBadgeClasses(status),
          ].join(" ")}
        >
          {ghostStatusLabel(status)}
        </span>
      </div>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}
