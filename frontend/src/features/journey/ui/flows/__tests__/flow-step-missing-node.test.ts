/**
 * Unit tests for the missing-node detection helper used by
 * `<FlowFocusNode />`. Req 18.10 — a step referencing a node_id not in the
 * manifest renders a "Узел недоступен" badge but remains skippable.
 */

import { describe, it, expect } from "vitest";
import type { JourneyFlowStep } from "@/entities/journey";
import { isStepMissingNode } from "../flow-focus-node";

const manifest = new Set<string>(["app:/quotes", "app:/quotes/[id]", "app:/"]);

const presentStep: JourneyFlowStep = {
  node_id: "app:/quotes",
  action: "Открыть список КП",
  note: "",
};

const ghostStep: JourneyFlowStep = {
  node_id: "ghost:future-dashboard",
  action: "Изучить будущий дашборд",
  note: "Этот узел пока не реализован.",
};

const staleStep: JourneyFlowStep = {
  node_id: "app:/removed-route",
  action: "Старый узел",
  note: "",
};

describe("isStepMissingNode", () => {
  it("returns false when the step's node_id is in the manifest", () => {
    expect(isStepMissingNode(presentStep, manifest)).toBe(false);
  });

  it("returns true for ghost nodes not in manifest", () => {
    expect(isStepMissingNode(ghostStep, manifest)).toBe(true);
  });

  it("returns true for stale references", () => {
    expect(isStepMissingNode(staleStep, manifest)).toBe(true);
  });

  it("identifies the single ghost in a 3-step flow fixture", () => {
    const flow: readonly JourneyFlowStep[] = [presentStep, ghostStep, staleStep];
    const missing = flow.filter((s) => isStepMissingNode(s, manifest));
    expect(missing).toHaveLength(2);
    expect(missing.map((s) => s.node_id)).toContain("ghost:future-dashboard");
    expect(missing.map((s) => s.node_id)).toContain("app:/removed-route");
  });
});
