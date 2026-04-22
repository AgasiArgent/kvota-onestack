/**
 * Type-level tests for `entities/journey/types.ts`.
 *
 * Uses Vitest's built-in `expectTypeOf` helper. Each `it` block performs
 * compile-time assertions; the runtime body is intentionally empty because
 * the checks are resolved by `tsc` during build. Runtime runs still pass
 * because `expectTypeOf(...).toEqualTypeOf<...>()` is a zero-op at runtime.
 */

import { describe, it, expectTypeOf } from "vitest";
import type {
  JourneyNodeId,
  JourneyPin,
  JourneyFlow,
  JourneyFlowStep,
  RoleSlug,
} from "../types";

describe("JourneyNodeId", () => {
  it("accepts strings prefixed with app: or ghost:", () => {
    const appId: JourneyNodeId = "app:/quotes/[id]";
    const ghostId: JourneyNodeId = "ghost:new-feature";
    expectTypeOf(appId).toMatchTypeOf<JourneyNodeId>();
    expectTypeOf(ghostId).toMatchTypeOf<JourneyNodeId>();
  });

  it("rejects bare strings without the app:/ghost: prefix", () => {
    // @ts-expect-error — must not accept arbitrary strings.
    const bad: JourneyNodeId = "/quotes/[id]";
    // @ts-expect-error — must not accept empty string.
    const empty: JourneyNodeId = "";
    // Reference the unused locals so the test file passes noUnusedLocals
    // if anyone tightens the compiler options in the future.
    void bad;
    void empty;
  });
});

describe("JourneyPin.last_rel_*", () => {
  it("last_rel_x accepts number | null", () => {
    expectTypeOf<JourneyPin["last_rel_x"]>().toEqualTypeOf<number | null>();
    expectTypeOf<JourneyPin["last_rel_y"]>().toEqualTypeOf<number | null>();
    expectTypeOf<JourneyPin["last_rel_width"]>().toEqualTypeOf<number | null>();
    expectTypeOf<JourneyPin["last_rel_height"]>().toEqualTypeOf<number | null>();
  });

  it("last_rel_x rejects string", () => {
    // @ts-expect-error — last_rel_x must not accept a string literal.
    const _bad: JourneyPin["last_rel_x"] = "0.25";
    void _bad;
  });
});

describe("JourneyFlow.steps", () => {
  it("is readonly — assignment to index mutates a readonly array", () => {
    expectTypeOf<JourneyFlow["steps"]>().toEqualTypeOf<readonly JourneyFlowStep[]>();
  });

  it("rejects mutation via index write", () => {
    const steps: JourneyFlow["steps"] = [];
    // @ts-expect-error — readonly arrays disallow index assignment.
    steps[0] = { node_id: "app:/x", action: "", note: "" };
  });
});

describe("RoleSlug", () => {
  it("contains the 13 active slugs", () => {
    const admin: RoleSlug = "admin";
    const topManager: RoleSlug = "top_manager";
    const headOfSales: RoleSlug = "head_of_sales";
    const headOfProcurement: RoleSlug = "head_of_procurement";
    const headOfLogistics: RoleSlug = "head_of_logistics";
    const sales: RoleSlug = "sales";
    const quoteController: RoleSlug = "quote_controller";
    const specController: RoleSlug = "spec_controller";
    const finance: RoleSlug = "finance";
    const procurement: RoleSlug = "procurement";
    const procurementSenior: RoleSlug = "procurement_senior";
    const logistics: RoleSlug = "logistics";
    const customs: RoleSlug = "customs";
    // Reference to keep noUnusedLocals happy; actual validation happens at the
    // type-annotation site above.
    void [
      admin,
      topManager,
      headOfSales,
      headOfProcurement,
      headOfLogistics,
      sales,
      quoteController,
      specController,
      finance,
      procurement,
      procurementSenior,
      logistics,
      customs,
    ];
  });

  it("excludes legacy slug 'sales_manager' (removed in migration 168)", () => {
    // @ts-expect-error — sales_manager was removed from the active role set.
    const legacy: RoleSlug = "sales_manager";
    void legacy;
  });

  it("excludes legacy slug 'currency_controller' (removed in migration 168)", () => {
    // @ts-expect-error — currency_controller was removed from the active role set.
    const legacy: RoleSlug = "currency_controller";
    void legacy;
  });
});
