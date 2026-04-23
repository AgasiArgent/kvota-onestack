/**
 * Runtime tests for the journey entity's access helpers.
 *
 * These assert that each `can*` guard mirrors the authoritative role lists
 * in `.kiro/specs/customer-journey-map/requirements.md`:
 *
 *  - §6.4 — impl_status writers
 *  - §6.5 — qa_status writers
 *  - §7.1 — ghost-node writers (admin only)
 *  - §8.1 — pin writers
 *  - §9.1–9.2 — verification writers
 *
 * We test both the boolean guard functions (single-role input) and the
 * exported `ReadonlySet<RoleSlug>` constants, so downstream callers can use
 * either shape without drift.
 */

import { describe, it, expect } from "vitest";
import type { RoleSlug } from "../types";
import {
  IMPL_STATUS_WRITERS,
  QA_STATUS_WRITERS,
  NOTES_WRITERS,
  GHOST_WRITERS,
  PIN_WRITERS,
  VERIFICATION_WRITERS,
  canEditImpl,
  canEditQa,
  canEditNotes,
  canCreateGhost,
  canCreatePin,
  canRecordVerification,
} from "../access";

const ALL_ROLES: readonly RoleSlug[] = [
  "admin",
  "top_manager",
  "head_of_sales",
  "head_of_procurement",
  "head_of_logistics",
  "sales",
  "quote_controller",
  "spec_controller",
  "finance",
  "procurement",
  "procurement_senior",
  "logistics",
  "customs",
];

describe("IMPL_STATUS_WRITERS (Req 6.4)", () => {
  it("contains admin + heads + line executors", () => {
    const expected: readonly RoleSlug[] = [
      "admin",
      "head_of_sales",
      "head_of_procurement",
      "head_of_logistics",
      "sales",
      "procurement",
      "procurement_senior",
      "logistics",
      "customs",
    ];
    expect([...IMPL_STATUS_WRITERS].sort()).toEqual([...expected].sort());
  });

  it("excludes top_manager (view-only per access-control.md)", () => {
    expect(IMPL_STATUS_WRITERS.has("top_manager")).toBe(false);
  });

  it("excludes QA controllers and finance", () => {
    expect(IMPL_STATUS_WRITERS.has("quote_controller")).toBe(false);
    expect(IMPL_STATUS_WRITERS.has("spec_controller")).toBe(false);
    expect(IMPL_STATUS_WRITERS.has("finance")).toBe(false);
  });
});

describe("canEditImpl()", () => {
  it("returns true for every IMPL_STATUS_WRITERS role", () => {
    for (const slug of IMPL_STATUS_WRITERS) {
      expect(canEditImpl([slug])).toBe(true);
    }
  });

  it("returns false for roles outside the set", () => {
    expect(canEditImpl(["top_manager"])).toBe(false);
    expect(canEditImpl(["finance"])).toBe(false);
    expect(canEditImpl(["quote_controller"])).toBe(false);
    expect(canEditImpl(["spec_controller"])).toBe(false);
  });

  it("returns true if any held role has permission", () => {
    expect(canEditImpl(["finance", "sales"])).toBe(true);
    expect(canEditImpl(["top_manager", "admin"])).toBe(true);
  });

  it("returns false on empty role list", () => {
    expect(canEditImpl([])).toBe(false);
  });
});

describe("QA_STATUS_WRITERS (Req 6.5)", () => {
  it("contains exactly admin, quote_controller, spec_controller", () => {
    expect([...QA_STATUS_WRITERS].sort()).toEqual(
      ["admin", "quote_controller", "spec_controller"].sort()
    );
  });

  it("excludes every non-QA-tier role", () => {
    for (const slug of ALL_ROLES) {
      if (slug === "admin" || slug === "quote_controller" || slug === "spec_controller") continue;
      expect(QA_STATUS_WRITERS.has(slug)).toBe(false);
    }
  });
});

describe("canEditQa()", () => {
  it("returns true for the three writer roles", () => {
    expect(canEditQa(["admin"])).toBe(true);
    expect(canEditQa(["quote_controller"])).toBe(true);
    expect(canEditQa(["spec_controller"])).toBe(true);
  });

  it("returns false for sales / procurement / logistics", () => {
    expect(canEditQa(["sales"])).toBe(false);
    expect(canEditQa(["procurement"])).toBe(false);
    expect(canEditQa(["logistics"])).toBe(false);
    expect(canEditQa(["customs"])).toBe(false);
  });
});

describe("NOTES_WRITERS = impl ∪ qa", () => {
  it("is the union of impl and qa writer sets", () => {
    const union = new Set<RoleSlug>([...IMPL_STATUS_WRITERS, ...QA_STATUS_WRITERS]);
    expect(NOTES_WRITERS.size).toBe(union.size);
    for (const slug of union) {
      expect(NOTES_WRITERS.has(slug)).toBe(true);
    }
  });

  it("canEditNotes is true for impl writers", () => {
    expect(canEditNotes(["sales"])).toBe(true);
    expect(canEditNotes(["logistics"])).toBe(true);
  });

  it("canEditNotes is true for qa writers", () => {
    expect(canEditNotes(["quote_controller"])).toBe(true);
    expect(canEditNotes(["spec_controller"])).toBe(true);
  });

  it("canEditNotes is false for top_manager and finance", () => {
    expect(canEditNotes(["top_manager"])).toBe(false);
    expect(canEditNotes(["finance"])).toBe(false);
  });
});

describe("GHOST_WRITERS (Req 7.1)", () => {
  it("contains admin only", () => {
    expect([...GHOST_WRITERS]).toEqual(["admin"]);
  });

  it("canCreateGhost is true only for admin", () => {
    expect(canCreateGhost(["admin"])).toBe(true);
    expect(canCreateGhost(["top_manager"])).toBe(false);
    expect(canCreateGhost(["head_of_sales"])).toBe(false);
    expect(canCreateGhost(["quote_controller"])).toBe(false);
  });
});

describe("PIN_WRITERS (Req 8.1)", () => {
  it("contains exactly admin, quote_controller, spec_controller", () => {
    expect([...PIN_WRITERS].sort()).toEqual(
      ["admin", "quote_controller", "spec_controller"].sort()
    );
  });

  it("canCreatePin is false for sales / procurement / top_manager", () => {
    expect(canCreatePin(["sales"])).toBe(false);
    expect(canCreatePin(["procurement"])).toBe(false);
    expect(canCreatePin(["top_manager"])).toBe(false);
  });
});

describe("VERIFICATION_WRITERS (Req 9.1–9.2)", () => {
  it("contains exactly admin, quote_controller, spec_controller", () => {
    expect([...VERIFICATION_WRITERS].sort()).toEqual(
      ["admin", "quote_controller", "spec_controller"].sort()
    );
  });

  it("canRecordVerification accepts the three writer roles", () => {
    expect(canRecordVerification(["admin"])).toBe(true);
    expect(canRecordVerification(["quote_controller"])).toBe(true);
    expect(canRecordVerification(["spec_controller"])).toBe(true);
  });

  it("canRecordVerification rejects every other role", () => {
    for (const slug of ALL_ROLES) {
      if (slug === "admin" || slug === "quote_controller" || slug === "spec_controller") continue;
      expect(canRecordVerification([slug])).toBe(false);
    }
  });
});
