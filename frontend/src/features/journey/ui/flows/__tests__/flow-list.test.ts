/**
 * Unit tests for the pure grouping + sorting helpers used by `<FlowList />`.
 *
 * Covers Req 18.3 — "listing all non-archived flows grouped by persona role".
 * The component itself is a thin render layer over these helpers; the DOM
 * shape is exercised via integration/Playwright, not here.
 */

import { describe, it, expect } from "vitest";
import type { JourneyFlow } from "@/entities/journey";
import {
  groupFlowsByRole,
  sortFlowsByDisplayOrder,
} from "../flow-list";

const fixture: readonly JourneyFlow[] = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    slug: "sales-full",
    title: "Sales: лид → одобрение КП",
    role: "sales",
    persona: "А. Петров",
    description: "",
    est_minutes: 12,
    steps: [],
    display_order: 1,
    is_archived: false,
  },
  {
    id: "00000000-0000-0000-0000-000000000002",
    slug: "procurement-flow",
    title: "Procurement: распределение",
    role: "procurement",
    persona: "С. Голиков",
    description: "",
    est_minutes: 8,
    steps: [],
    display_order: 2,
    is_archived: false,
  },
  {
    id: "00000000-0000-0000-0000-000000000003",
    slug: "qa-onboarding",
    title: "QA onboarding",
    role: "spec_controller",
    persona: "Junior QA",
    description: "",
    est_minutes: 15,
    steps: [],
    display_order: 1,
    is_archived: false,
  },
  {
    id: "00000000-0000-0000-0000-000000000004",
    slug: "finance-monthly",
    title: "Finance: месячное закрытие",
    role: "finance",
    persona: "Н. Соколова",
    description: "",
    est_minutes: 6,
    steps: [],
    display_order: 1,
    is_archived: false,
  },
];

describe("groupFlowsByRole", () => {
  it("groups flows by their role slug", () => {
    const grouped = groupFlowsByRole(fixture);
    expect(Object.keys(grouped).sort()).toEqual(
      ["finance", "procurement", "sales", "spec_controller"].sort()
    );
    expect(grouped.sales).toHaveLength(1);
    expect(grouped.sales?.[0]?.slug).toBe("sales-full");
    expect(grouped.procurement?.[0]?.slug).toBe("procurement-flow");
    expect(grouped.spec_controller?.[0]?.slug).toBe("qa-onboarding");
    expect(grouped.finance?.[0]?.slug).toBe("finance-monthly");
  });

  it("omits roles that have zero flows", () => {
    const grouped = groupFlowsByRole(fixture);
    // RoleSlug has 13 values — only 4 appear in the fixture.
    expect(grouped.admin).toBeUndefined();
    expect(grouped.logistics).toBeUndefined();
    expect(grouped.customs).toBeUndefined();
  });

  it("returns an empty object when given no flows", () => {
    expect(groupFlowsByRole([])).toEqual({});
  });
});

describe("sortFlowsByDisplayOrder", () => {
  it("sorts flows by display_order ascending", () => {
    const shuffled: readonly JourneyFlow[] = [
      { ...fixture[0]!, display_order: 3 },
      { ...fixture[1]!, display_order: 1 },
      { ...fixture[2]!, display_order: 2 },
    ];
    const sorted = sortFlowsByDisplayOrder(shuffled);
    expect(sorted.map((f) => f.display_order)).toEqual([1, 2, 3]);
  });

  it("preserves input order for ties (stable sort)", () => {
    const tied: readonly JourneyFlow[] = [
      { ...fixture[0]!, display_order: 5, slug: "a" },
      { ...fixture[1]!, display_order: 5, slug: "b" },
      { ...fixture[2]!, display_order: 5, slug: "c" },
    ];
    const sorted = sortFlowsByDisplayOrder(tied);
    expect(sorted.map((f) => f.slug)).toEqual(["a", "b", "c"]);
  });

  it("does not mutate the input array", () => {
    const input: readonly JourneyFlow[] = [
      { ...fixture[0]!, display_order: 3 },
      { ...fixture[1]!, display_order: 1 },
    ];
    const snapshot = input.map((f) => f.display_order);
    sortFlowsByDisplayOrder(input);
    expect(input.map((f) => f.display_order)).toEqual(snapshot);
  });
});

describe("fixture shape", () => {
  it("yields the expected grouping + ordering when combined", () => {
    const grouped = groupFlowsByRole(fixture);
    const salesSorted = sortFlowsByDisplayOrder(grouped.sales ?? []);
    expect(salesSorted.map((f) => f.slug)).toEqual(["sales-full"]);
    expect(Object.keys(grouped)).toHaveLength(4);
  });
});
