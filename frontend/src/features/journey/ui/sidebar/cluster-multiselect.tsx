"use client";

/**
 * Cluster multi-select. Clusters are derived from the currently-loaded node
 * list (not from a global enum) so new clusters become visible automatically.
 *
 * `excluded` = IDs the user has toggled OFF. All clusters are ON by default.
 */

import { useMemo } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { JourneyNodeAggregated } from "@/entities/journey";

interface Props {
  readonly nodes: readonly JourneyNodeAggregated[];
  readonly excluded: readonly string[];
  readonly onToggle: (cluster: string) => void;
}

export function ClusterMultiselect({ nodes, excluded, onToggle }: Props) {
  const clusters = useMemo(() => {
    const seen = new Set<string>();
    for (const n of nodes) seen.add(n.cluster);
    return Array.from(seen).sort((a, b) => a.localeCompare(b));
  }, [nodes]);

  const excludedSet = useMemo(() => new Set<string>(excluded), [excluded]);

  if (clusters.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2" data-testid="journey-cluster-list">
      <span className="text-xs text-text-subtle">Кластеры</span>
      {clusters.map((cluster) => {
        const id = `journey-cluster-${cluster}`;
        const checked = !excludedSet.has(cluster);
        return (
          <div key={cluster} className="flex items-center gap-2">
            <Checkbox
              id={id}
              checked={checked}
              onCheckedChange={() => onToggle(cluster)}
              data-testid={`journey-cluster-${cluster}`}
            />
            <Label htmlFor={id} className="text-sm text-text cursor-pointer">
              {cluster}
            </Label>
          </div>
        );
      })}
    </div>
  );
}
