/**
 * Unit test for the pure label helper used by `<FlowStepList />`. DOM shape
 * is covered via integration/Playwright elsewhere.
 */

import { describe, it, expect } from "vitest";
import type { JourneyFlowStep } from "@/entities/journey";
import { formatStepLabel } from "../flow-step-list";

const step: JourneyFlowStep = {
  node_id: "app:/quotes",
  action: "Проверить customer",
  note: "Откройте первую КП в списке",
};

describe("formatStepLabel", () => {
  it("prefixes a 1-based index", () => {
    expect(formatStepLabel(step, 0)).toBe("1. Проверить customer");
    expect(formatStepLabel(step, 2)).toBe("3. Проверить customer");
  });
});
