/**
 * Pure-helper tests for Task 22 pin-overlay positioning.
 *
 * The overlay component itself is verified via localhost browser testing;
 * these tests exercise the side-effect-free logic that backs it:
 *
 *   - computePinAbsolutePosition — rel-coords (0-1) → container px
 *   - partitionPinsByBbox        — split pins with/without position cache
 *   - classifyPinBadgeState      — broken | pending | ok
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import type { JourneyPin } from "@/entities/journey";
import {
  computePinAbsolutePosition,
  partitionPinsByBbox,
  classifyPinBadgeState,
} from "../_overlay-math";

const pin = (overrides: Partial<JourneyPin> = {}): JourneyPin => ({
  id: "pin-1",
  node_id: "app:/quotes",
  selector: '[data-testid="x"]',
  expected_behavior: "поведение",
  mode: "qa",
  training_step_order: null,
  linked_story_ref: null,
  last_rel_x: 0.1,
  last_rel_y: 0.2,
  last_rel_width: 0.05,
  last_rel_height: 0.05,
  last_position_update: "2026-04-24T00:00:00Z",
  selector_broken: false,
  created_by: "user-1",
  created_at: "2026-04-24T00:00:00Z",
  ...overrides,
});

describe("computePinAbsolutePosition", () => {
  it("maps relative coords to container pixels", () => {
    expect(
      computePinAbsolutePosition(
        { rel_x: 0.5, rel_y: 0.25, rel_width: 0.1, rel_height: 0.08 },
        { width: 800, height: 600 },
      ),
    ).toEqual({ x: 400, y: 150, width: 80, height: 48 });
  });

  it("clamps values slightly above 1.0 to 1.0 with a warning", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const result = computePinAbsolutePosition(
      { rel_x: 1.05, rel_y: 0.5, rel_width: 0.1, rel_height: 0.1 },
      { width: 1000, height: 500 },
    );
    expect(result.x).toBe(1000);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("clamps negative values to 0 with a warning", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const result = computePinAbsolutePosition(
      { rel_x: -0.1, rel_y: -0.2, rel_width: 0.1, rel_height: 0.1 },
      { width: 1000, height: 500 },
    );
    expect(result.x).toBe(0);
    expect(result.y).toBe(0);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("returns zeroed rect for a 0×0 container", () => {
    expect(
      computePinAbsolutePosition(
        { rel_x: 0.5, rel_y: 0.5, rel_width: 0.1, rel_height: 0.1 },
        { width: 0, height: 0 },
      ),
    ).toEqual({ x: 0, y: 0, width: 0, height: 0 });
  });
});

describe("partitionPinsByBbox", () => {
  it("splits pins into withBbox and pending buckets", () => {
    const p1 = pin({ id: "a" });
    const p2 = pin({ id: "b", last_rel_x: null });
    const p3 = pin({ id: "c", last_rel_y: null });
    const p4 = pin({ id: "d", last_rel_width: null });

    const { withBbox, pending } = partitionPinsByBbox([p1, p2, p3, p4]);
    expect(withBbox.map((p) => p.id)).toEqual(["a"]);
    expect(pending.map((p) => p.id).sort()).toEqual(["b", "c", "d"]);
  });

  it("returns empty arrays for empty input", () => {
    expect(partitionPinsByBbox([])).toEqual({ withBbox: [], pending: [] });
  });
});

describe("classifyPinBadgeState", () => {
  it("returns 'broken' when selector_broken is true", () => {
    expect(classifyPinBadgeState(pin({ selector_broken: true }))).toBe(
      "broken",
    );
  });

  it("returns 'pending' when rel_x is null and selector is not broken", () => {
    expect(
      classifyPinBadgeState(
        pin({ selector_broken: false, last_rel_x: null }),
      ),
    ).toBe("pending");
  });

  it("returns 'ok' when selector resolved and not broken", () => {
    expect(classifyPinBadgeState(pin())).toBe("ok");
  });

  it("prioritises 'broken' over 'pending' (broken + no bbox → broken)", () => {
    expect(
      classifyPinBadgeState(
        pin({ selector_broken: true, last_rel_x: null }),
      ),
    ).toBe("broken");
  });
});

describe("deterministic overlay snapshot", () => {
  it("renders 4 pins into stable {id, style} rects for a 1000×600 container", () => {
    const pins = [
      pin({ id: "a", last_rel_x: 0.0, last_rel_y: 0.0, last_rel_width: 0.1, last_rel_height: 0.1 }),
      pin({ id: "b", last_rel_x: 0.5, last_rel_y: 0.5, last_rel_width: 0.1, last_rel_height: 0.1 }),
      pin({ id: "c", last_rel_x: 0.9, last_rel_y: 0.9, last_rel_width: 0.05, last_rel_height: 0.05 }),
      pin({ id: "d", last_rel_x: 0.25, last_rel_y: 0.75, last_rel_width: 0.2, last_rel_height: 0.05 }),
    ];

    const output = pins.map((p) => {
      const rect = computePinAbsolutePosition(
        {
          rel_x: p.last_rel_x as number,
          rel_y: p.last_rel_y as number,
          rel_width: p.last_rel_width as number,
          rel_height: p.last_rel_height as number,
        },
        { width: 1000, height: 600 },
      );
      return {
        id: p.id,
        style: {
          left: rect.x,
          top: rect.y,
          width: rect.width,
          height: rect.height,
        },
      };
    });

    expect(output).toMatchInlineSnapshot(`
      [
        {
          "id": "a",
          "style": {
            "height": 60,
            "left": 0,
            "top": 0,
            "width": 100,
          },
        },
        {
          "id": "b",
          "style": {
            "height": 60,
            "left": 500,
            "top": 300,
            "width": 100,
          },
        },
        {
          "id": "c",
          "style": {
            "height": 30,
            "left": 900,
            "top": 540,
            "width": 50,
          },
        },
        {
          "id": "d",
          "style": {
            "height": 30,
            "left": 250,
            "top": 450,
            "width": 200,
          },
        },
      ]
    `);
  });
});

// Keep vi mocks tidy across describe blocks
beforeEach(() => {
  vi.restoreAllMocks();
});
afterEach(() => {
  vi.restoreAllMocks();
});
