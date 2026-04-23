/**
 * StatusSection (Task 19) — inline-edit behaviour tests.
 *
 * Scope (Req 5.5, 6.1, 6.2, 6.3):
 *   - Pure helpers: `buildOptimisticPatch`, `handleStatusMutationError`,
 *     `canEditField`.
 *   - SSR render assertions: editable controls appear for writers, read-only
 *     badges appear for view-only roles, notes textarea renders for notes
 *     writers.
 *
 * The frontend workspace has no jsdom — we follow the same SSR + pure-helper
 * pattern documented in `node-drawer.test.tsx`. Full click/keyboard
 * interaction is covered via localhost browser verification.
 */

import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import {
  buildOptimisticPatch,
  handleStatusMutationError,
  canEditField,
  type StatusMutationErrorKind,
} from "../_status-mutation-helpers";
import { StatusSection } from "../status-section";
import type { JourneyNodeDetail, JourneyNodeId } from "@/entities/journey";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BASE_NODE: JourneyNodeDetail = {
  node_id: "app:/quotes" as JourneyNodeId,
  route: "/quotes",
  title: "Реестр КП",
  cluster: "Quotes",
  roles: ["sales"],
  stories_count: 0,
  impl_status: "done",
  qa_status: "verified",
  version: 4,
  notes: "Заметка",
  updated_at: "2026-04-22T10:00:00Z",
  ghost_status: null,
  proposed_route: null,
  pins: [],
  verifications_by_pin: {},
  feedback: [],
};

function ssr(detail: JourneyNodeDetail, roles: readonly import("@/entities/journey").RoleSlug[]): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return renderToString(
    <QueryClientProvider client={client}>
      <StatusSection detail={detail} userRoles={roles} />
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// 1. buildOptimisticPatch
// ---------------------------------------------------------------------------

describe("buildOptimisticPatch (Req 5.5)", () => {
  it("includes version from current state", () => {
    const patch = buildOptimisticPatch({
      currentVersion: 4,
      changes: { impl_status: "partial" },
    });
    expect(patch.version).toBe(4);
  });

  it("includes only touched fields (omits undefined keys)", () => {
    const patch = buildOptimisticPatch({
      currentVersion: 1,
      changes: { impl_status: "done" },
    });
    expect(patch).toEqual({ version: 1, impl_status: "done" });
    expect("qa_status" in patch).toBe(false);
    expect("notes" in patch).toBe(false);
  });

  it("supports notes + impl_status together", () => {
    const patch = buildOptimisticPatch({
      currentVersion: 2,
      changes: { impl_status: "partial", notes: "WIP" },
    });
    expect(patch).toEqual({ version: 2, impl_status: "partial", notes: "WIP" });
  });

  it("preserves explicit null (used to clear a field)", () => {
    const patch = buildOptimisticPatch({
      currentVersion: 3,
      changes: { notes: null },
    });
    expect(patch).toEqual({ version: 3, notes: null });
  });
});

// ---------------------------------------------------------------------------
// 2. handleStatusMutationError
// ---------------------------------------------------------------------------

describe("handleStatusMutationError (Req 6.2, 6.3)", () => {
  it("409 STALE_VERSION → 'refresh-and-retry' with server state", () => {
    const serverState: JourneyNodeDetail = { ...BASE_NODE, version: 5, impl_status: "partial" };
    const err = Object.assign(new Error("conflict"), {
      code: "STALE_VERSION",
      status: 409,
      data: { current: serverState },
    });
    const kind: StatusMutationErrorKind = handleStatusMutationError(err);
    expect(kind.kind).toBe("refresh-and-retry");
    if (kind.kind === "refresh-and-retry") {
      expect(kind.serverState).toBe(serverState);
    }
  });

  it("403 FORBIDDEN_FIELD → 'no-permission' with fieldName", () => {
    const err = Object.assign(new Error("forbidden"), {
      code: "FORBIDDEN_FIELD",
      status: 403,
      data: { field: "impl_status" },
    });
    const kind = handleStatusMutationError(err);
    expect(kind.kind).toBe("no-permission");
    if (kind.kind === "no-permission") {
      expect(kind.field).toBe("impl_status");
    }
  });

  it("403 FORBIDDEN_FIELD without field data falls back to generic field name", () => {
    const err = Object.assign(new Error("forbidden"), {
      code: "FORBIDDEN_FIELD",
      status: 403,
    });
    const kind = handleStatusMutationError(err);
    expect(kind.kind).toBe("no-permission");
  });

  it("500 / unknown → 'generic' rollback signal", () => {
    const err = new Error("boom");
    const kind = handleStatusMutationError(err);
    expect(kind.kind).toBe("generic");
  });

  it("network error → 'generic'", () => {
    const err = Object.assign(new Error("fetch failed"), { status: undefined });
    const kind = handleStatusMutationError(err);
    expect(kind.kind).toBe("generic");
  });

  it("STALE_VERSION without current state in data → 'generic'", () => {
    const err = Object.assign(new Error("conflict"), {
      code: "STALE_VERSION",
      status: 409,
      data: {},
    });
    const kind = handleStatusMutationError(err);
    // No server state to hydrate → treat like generic so rollback kicks in
    expect(kind.kind).toBe("generic");
  });
});

// ---------------------------------------------------------------------------
// 3. canEditField — thin adapter over entities/journey access helpers
// ---------------------------------------------------------------------------

describe("canEditField (Req 6.4, 6.5)", () => {
  it("admin can edit impl / qa / notes", () => {
    expect(canEditField("impl_status", ["admin"])).toBe(true);
    expect(canEditField("qa_status", ["admin"])).toBe(true);
    expect(canEditField("notes", ["admin"])).toBe(true);
  });

  it("sales can edit impl + notes but NOT qa", () => {
    expect(canEditField("impl_status", ["sales"])).toBe(true);
    expect(canEditField("qa_status", ["sales"])).toBe(false);
    expect(canEditField("notes", ["sales"])).toBe(true);
  });

  it("quote_controller can edit qa + notes but NOT impl", () => {
    expect(canEditField("impl_status", ["quote_controller"])).toBe(false);
    expect(canEditField("qa_status", ["quote_controller"])).toBe(true);
    expect(canEditField("notes", ["quote_controller"])).toBe(true);
  });

  it("top_manager has no write rights", () => {
    expect(canEditField("impl_status", ["top_manager"])).toBe(false);
    expect(canEditField("qa_status", ["top_manager"])).toBe(false);
    expect(canEditField("notes", ["top_manager"])).toBe(false);
  });

  it("empty role list → no edits", () => {
    expect(canEditField("impl_status", [])).toBe(false);
    expect(canEditField("qa_status", [])).toBe(false);
    expect(canEditField("notes", [])).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 4. SSR render — StatusSection surfaces edit controls only for writers
// ---------------------------------------------------------------------------

describe("StatusSection SSR (Req 5.5, 6.4–6.5)", () => {
  it("renders read-only badges when user has no write rights", () => {
    const html = ssr(BASE_NODE, ["top_manager"]);
    // No form controls for view-only user
    expect(html).not.toContain("<select");
    expect(html).not.toContain("<textarea");
    // Russian labels still present
    expect(html).toContain("Реализация");
    expect(html).toContain("QA");
  });

  it("renders impl select for impl-writer (sales)", () => {
    const html = ssr(BASE_NODE, ["sales"]);
    // Editable impl control is a shadcn Select — find the test hook
    expect(html).toContain('data-testid="impl-status-control"');
    // qa is view-only for sales
    expect(html).not.toContain('data-testid="qa-status-control"');
  });

  it("renders qa select for qa-writer (quote_controller)", () => {
    const html = ssr(BASE_NODE, ["quote_controller"]);
    expect(html).toContain('data-testid="qa-status-control"');
    expect(html).not.toContain('data-testid="impl-status-control"');
  });

  it("renders both selects + notes editor for admin", () => {
    const html = ssr(BASE_NODE, ["admin"]);
    expect(html).toContain('data-testid="impl-status-control"');
    expect(html).toContain('data-testid="qa-status-control"');
    expect(html).toContain('data-testid="notes-editor"');
  });

  it("ghost nodes still render controls (status editing is identical)", () => {
    const ghost: JourneyNodeDetail = {
      ...BASE_NODE,
      node_id: "ghost:plans/customs" as JourneyNodeId,
      ghost_status: "proposed",
      proposed_route: "/customs",
    };
    const html = ssr(ghost, ["admin"]);
    expect(html).toContain('data-testid="impl-status-control"');
    expect(html).toContain('data-testid="qa-status-control"');
  });
});

// Silence potential React Testing noise during render-to-string
void vi;
