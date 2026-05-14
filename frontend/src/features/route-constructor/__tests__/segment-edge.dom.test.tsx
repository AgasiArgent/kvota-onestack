// @vitest-environment jsdom
/**
 * Testing 2 row 30 (FB-260514-140640-699a): segment cost must render in
 * the segment's own currency, not always RUB. Earlier code hardcoded a
 * RUB Intl.NumberFormat, so a USD segment with cost=100 displayed as
 * "100 ₽" — confusing the tester whose quote was not denominated in RUB.
 */
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render } from "@testing-library/react";

import { SegmentEdge } from "../ui/segment-edge";
import type { LogisticsSegment } from "@/entities/logistics-segment";

function makeSegment(overrides: Partial<LogisticsSegment> = {}): LogisticsSegment {
  return {
    id: "seg-1",
    invoiceId: "inv-1",
    sequenceOrder: 1,
    mainCostRub: 0,
    currencyCode: "RUB",
    expenses: [],
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
});

describe("SegmentEdge currency rendering (Testing 2 row 30)", () => {
  it("renders RUB cost when segment currency is RUB", () => {
    const { container } = render(
      <SegmentEdge segment={makeSegment({ mainCostRub: 100, currencyCode: "RUB" })} />,
    );
    const text = (container.textContent ?? "").replace(/ /g, " ");
    expect(text).toMatch(/₽/);
  });

  it("renders USD cost when segment currency is USD (no hardcoded RUB)", () => {
    const { container } = render(
      <SegmentEdge segment={makeSegment({ mainCostRub: 100, currencyCode: "USD" })} />,
    );
    const text = (container.textContent ?? "").replace(/ /g, " ");
    expect(text).toMatch(/\$/);
    expect(text).not.toMatch(/₽/);
  });

  it("renders EUR cost when segment currency is EUR", () => {
    const { container } = render(
      <SegmentEdge segment={makeSegment({ mainCostRub: 250, currencyCode: "EUR" })} />,
    );
    const text = (container.textContent ?? "").replace(/ /g, " ");
    expect(text).toMatch(/€/);
    expect(text).not.toMatch(/₽/);
  });

  it("renders CNY cost when segment currency is CNY", () => {
    const { container } = render(
      <SegmentEdge segment={makeSegment({ mainCostRub: 700, currencyCode: "CNY" })} />,
    );
    const text = (container.textContent ?? "").replace(/ /g, " ");
    // ru-RU locale renders CNY as "CN¥" or "CNY"; just assert no RUB sign.
    expect(text).not.toMatch(/₽/);
  });

  it("renders em-dash when cost is zero (no currency at all)", () => {
    const { container } = render(
      <SegmentEdge segment={makeSegment({ mainCostRub: 0, currencyCode: "USD" })} />,
    );
    expect(container.textContent).toContain("—");
  });
});
