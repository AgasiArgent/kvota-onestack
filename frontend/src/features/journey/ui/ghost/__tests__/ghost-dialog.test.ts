/**
 * Ghost CRUD helpers — payload building + error classification.
 *
 * Full interactive dialog behaviour (open/close, optimistic query
 * invalidation) is verified via localhost browser testing; the frontend
 * workspace has no jsdom, so these tests exercise the pure helpers that
 * back the dialog components.
 */

import { describe, it, expect } from "vitest";
import {
  buildGhostPayload,
  classifyGhostWriteError,
} from "../_ghost-dialog-helpers";

describe("buildGhostPayload", () => {
  it("derives node_id from the slug and spreads the row fields", () => {
    const payload = buildGhostPayload({
      title: "My Feature",
      slug: "my-feature",
      cluster: "Quotes",
      proposed_route: "/quotes/new",
      status: "proposed",
      planned_in: "v1.1",
      created_by: "u-1",
    });
    expect(payload.node_id).toBe("ghost:my-feature");
    expect(payload.title).toBe("My Feature");
    expect(payload.cluster).toBe("Quotes");
    expect(payload.proposed_route).toBe("/quotes/new");
    expect(payload.status).toBe("proposed");
    expect(payload.planned_in).toBe("v1.1");
    expect(payload.created_by).toBe("u-1");
  });

  it("leaves optional fields null when not provided", () => {
    const payload = buildGhostPayload({
      title: "Foo",
      slug: "foo",
      cluster: null,
      proposed_route: null,
      status: "proposed",
      planned_in: null,
      created_by: "u-1",
    });
    expect(payload.cluster).toBeNull();
    expect(payload.proposed_route).toBeNull();
    expect(payload.planned_in).toBeNull();
    expect(payload.assignee).toBeNull();
    expect(payload.parent_node_id).toBeNull();
  });
});

describe("classifyGhostWriteError", () => {
  it("maps Postgres 23505 unique-violation to SLUG_COLLISION", () => {
    const err = { code: "23505", message: "duplicate key value" };
    const result = classifyGhostWriteError(err);
    expect(result.kind).toBe("SLUG_COLLISION");
    expect(result.userMessage).toMatch(/слаг|занят/i);
  });

  it("maps RLS violation (42501) to PERMISSION_DENIED", () => {
    const err = { code: "42501", message: "new row violates row-level security policy" };
    const result = classifyGhostWriteError(err);
    expect(result.kind).toBe("PERMISSION_DENIED");
    expect(result.userMessage).toMatch(/прав|доступ/i);
  });

  it("maps PostgREST-wrapped RLS message to PERMISSION_DENIED", () => {
    const err = { message: "new row violates row-level security policy for table \"journey_ghost_nodes\"" };
    const result = classifyGhostWriteError(err);
    expect(result.kind).toBe("PERMISSION_DENIED");
  });

  it("falls back to UNKNOWN with a generic message for unmapped errors", () => {
    const err = { code: "XX000", message: "internal error" };
    const result = classifyGhostWriteError(err);
    expect(result.kind).toBe("UNKNOWN");
    expect(result.userMessage.length).toBeGreaterThan(0);
  });

  it("returns UNKNOWN when the error is null/undefined", () => {
    expect(classifyGhostWriteError(null).kind).toBe("UNKNOWN");
    expect(classifyGhostWriteError(undefined).kind).toBe("UNKNOWN");
  });
});
