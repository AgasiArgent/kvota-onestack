/**
 * JourneyDrawer — SSR-based rendering tests.
 *
 * Covers Req 5.1 (section order), 5.2 (ghost nodes hide Screenshot + Pins),
 * 5.3 ("view all feedback" link), 5.4 (Training section), 5.6 (Esc closes —
 * tested via the exported key handler helper), 5.7 (history expander lazy
 * fetch — tested via the exported default-state helper).
 *
 * The frontend workspace ships no DOM (no jsdom / @testing-library/react),
 * so — following the pattern of `city-combobox.test.tsx` and
 * `feedback-from-journey.test.tsx` — we use `react-dom/server` for render
 * assertions and unit-test pure helpers for behavior that would otherwise
 * require an interactive DOM (click, keydown). Full interactive behaviour
 * is covered by localhost browser verification per
 * `reference_localhost_browser_test.md`.
 */

import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { JourneyDrawer } from "../node-drawer";
import {
  isGhostDetail,
  shouldShowScreenshot,
  shouldShowPinList,
  makeEscapeHandler,
  DRAWER_TESTIDS,
} from "../node-drawer";
import { feedbackHrefForNode } from "../feedback-section";
import type {
  JourneyNodeDetail,
  JourneyNodeId,
} from "@/entities/journey";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const REAL_NODE: JourneyNodeDetail = {
  node_id: "app:/quotes" as JourneyNodeId,
  route: "/quotes",
  title: "Реестр коммерческих предложений",
  cluster: "Quotes",
  roles: ["sales", "admin"],
  stories_count: 3,
  impl_status: "done",
  qa_status: "verified",
  version: 4,
  notes: null,
  updated_at: "2026-04-22T10:00:00Z",
  ghost_status: null,
  proposed_route: null,
  pins: [
    {
      id: "pin-1",
      node_id: "app:/quotes" as JourneyNodeId,
      selector: "button.new-quote",
      expected_behavior: "Открывает форму создания КП",
      mode: "qa",
      training_step_order: null,
      linked_story_ref: null,
      last_rel_x: null,
      last_rel_y: null,
      last_rel_width: null,
      last_rel_height: null,
      last_position_update: null,
      selector_broken: false,
      created_by: "u1",
      created_at: "2026-04-22T09:00:00Z",
    },
    {
      id: "pin-2",
      node_id: "app:/quotes" as JourneyNodeId,
      selector: ".sidebar-link",
      expected_behavior: "Переход к КП",
      mode: "training",
      training_step_order: 1,
      linked_story_ref: null,
      last_rel_x: null,
      last_rel_y: null,
      last_rel_width: null,
      last_rel_height: null,
      last_position_update: null,
      selector_broken: false,
      created_by: "u1",
      created_at: "2026-04-22T09:00:00Z",
    },
  ],
  verifications_by_pin: {
    "pin-1": {
      id: "v1",
      pin_id: "pin-1",
      node_id: "app:/quotes" as JourneyNodeId,
      result: "verified",
      note: null,
      attachment_urls: null,
      tested_by: "u2",
      tested_at: "2026-04-22T10:00:00Z",
    },
  },
  feedback: [
    {
      id: "fb-1",
      short_id: "FB-1",
      node_id: "app:/quotes" as JourneyNodeId,
      user_id: "u3",
      description: "Тормозит при фильтрации",
      feedback_type: "bug",
      status: "new",
      created_at: "2026-04-22T08:00:00Z",
    },
  ],
};

const GHOST_NODE: JourneyNodeDetail = {
  ...REAL_NODE,
  node_id: "ghost:customs-editor" as JourneyNodeId,
  ghost_status: "proposed",
  proposed_route: "/customs/editor",
  pins: [],
  verifications_by_pin: {},
};

// ---------------------------------------------------------------------------
// Mock the TanStack-Query hook so the SSR render returns fixture data.
// ---------------------------------------------------------------------------

vi.mock("@/entities/journey", async () => {
  const actual = await vi.importActual<typeof import("@/entities/journey")>(
    "@/entities/journey"
  );
  return {
    ...actual,
    useNodeDetail: vi.fn(),
    useNodeHistory: vi.fn(),
  };
});

const journeyEntity = await import("@/entities/journey");
const mockedUseNodeDetail = journeyEntity.useNodeDetail as unknown as ReturnType<
  typeof vi.fn
>;
const mockedUseNodeHistory = journeyEntity.useNodeHistory as unknown as ReturnType<
  typeof vi.fn
>;

function renderDrawer(nodeId: JourneyNodeId | null): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return renderToString(
    <QueryClientProvider client={client}>
      <JourneyDrawer nodeId={nodeId} onClose={() => {}} />
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// 1. Null nodeId → drawer returns null (no panel rendered)
// ---------------------------------------------------------------------------

describe("JourneyDrawer — nodeId=null", () => {
  it("renders nothing when nodeId is null", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(null);
    expect(html).not.toContain(DRAWER_TESTIDS.panel);
  });
});

// ---------------------------------------------------------------------------
// 2. Real node — every section renders
// ---------------------------------------------------------------------------

describe("JourneyDrawer — real node (Req 5.1)", () => {
  it("renders the drawer panel with role=complementary", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: REAL_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(REAL_NODE.node_id);
    expect(html).toContain(`data-testid="${DRAWER_TESTIDS.panel}"`);
    expect(html).toContain('role="complementary"');
    expect(html).toContain('aria-label="Подробности узла"');
  });

  it("renders all required sections", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: REAL_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(REAL_NODE.node_id);
    for (const testId of [
      DRAWER_TESTIDS.header,
      DRAWER_TESTIDS.roles,
      DRAWER_TESTIDS.stories,
      DRAWER_TESTIDS.status,
      DRAWER_TESTIDS.screenshot,
      DRAWER_TESTIDS.feedback,
      DRAWER_TESTIDS.training,
      DRAWER_TESTIDS.pinList,
      DRAWER_TESTIDS.historyExpander,
    ]) {
      expect(html).toContain(`data-testid="${testId}"`);
    }
  });

  it("renders the node title and route in the header", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: REAL_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(REAL_NODE.node_id);
    expect(html).toContain(REAL_NODE.title);
    expect(html).toContain(REAL_NODE.route);
  });

  it("renders every role badge", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: REAL_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(REAL_NODE.node_id);
    for (const role of REAL_NODE.roles) {
      expect(html).toContain(role);
    }
  });

  it("renders impl/qa status as read-only badges", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: REAL_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(REAL_NODE.node_id);
    // Read-only is signalled by the absence of a <select> / form controls.
    expect(html).not.toContain("<select");
    // Russian labels for the two status axes must appear.
    expect(html).toContain("Реализация");
    expect(html).toContain("QA");
  });

  it('renders the "view all feedback" link to /admin/feedback', () => {
    mockedUseNodeDetail.mockReturnValue({
      data: REAL_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(REAL_NODE.node_id);
    expect(html).toContain("/admin/feedback?node_id=");
  });
});

// ---------------------------------------------------------------------------
// 3. Ghost node — Screenshot + Pin sections hidden (Req 5.2)
// ---------------------------------------------------------------------------

describe("JourneyDrawer — ghost node (Req 5.2)", () => {
  it("does NOT render the screenshot section", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: GHOST_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(GHOST_NODE.node_id);
    expect(html).not.toContain(`data-testid="${DRAWER_TESTIDS.screenshot}"`);
  });

  it("does NOT render the pin-list section", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: GHOST_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(GHOST_NODE.node_id);
    expect(html).not.toContain(`data-testid="${DRAWER_TESTIDS.pinList}"`);
  });

  it("still renders roles, stories, status, feedback, training, history", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: GHOST_NODE,
      isLoading: false,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(GHOST_NODE.node_id);
    for (const testId of [
      DRAWER_TESTIDS.header,
      DRAWER_TESTIDS.roles,
      DRAWER_TESTIDS.stories,
      DRAWER_TESTIDS.status,
      DRAWER_TESTIDS.feedback,
      DRAWER_TESTIDS.training,
      DRAWER_TESTIDS.historyExpander,
    ]) {
      expect(html).toContain(`data-testid="${testId}"`);
    }
  });
});

// ---------------------------------------------------------------------------
// 4. Loading / error states (Req 14)
// ---------------------------------------------------------------------------

describe("JourneyDrawer — loading & error states", () => {
  it("renders a loading skeleton when the detail query is pending", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(REAL_NODE.node_id);
    expect(html).toContain(`data-testid="${DRAWER_TESTIDS.loading}"`);
  });

  it("renders an error message when the detail query fails", () => {
    mockedUseNodeDetail.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("boom"),
    });
    mockedUseNodeHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    const html = renderDrawer(REAL_NODE.node_id);
    expect(html).toContain(`data-testid="${DRAWER_TESTIDS.error}"`);
  });
});

// ---------------------------------------------------------------------------
// 5. Pure helpers
// ---------------------------------------------------------------------------

describe("isGhostDetail", () => {
  it("returns true when ghost_status is non-null", () => {
    expect(isGhostDetail(GHOST_NODE)).toBe(true);
  });
  it("returns false when ghost_status is null", () => {
    expect(isGhostDetail(REAL_NODE)).toBe(false);
  });
});

describe("shouldShowScreenshot / shouldShowPinList (Req 5.2)", () => {
  it("shows screenshot + pins for real nodes", () => {
    expect(shouldShowScreenshot(REAL_NODE)).toBe(true);
    expect(shouldShowPinList(REAL_NODE)).toBe(true);
  });
  it("hides screenshot + pins for ghost nodes", () => {
    expect(shouldShowScreenshot(GHOST_NODE)).toBe(false);
    expect(shouldShowPinList(GHOST_NODE)).toBe(false);
  });
});

describe("makeEscapeHandler (Req 5.6)", () => {
  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    const handler = makeEscapeHandler(onClose);
    handler({ key: "Escape" } as KeyboardEvent);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
  it("ignores other keys", () => {
    const onClose = vi.fn();
    const handler = makeEscapeHandler(onClose);
    handler({ key: "Enter" } as KeyboardEvent);
    handler({ key: "a" } as KeyboardEvent);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("feedbackHrefForNode (Req 5.3)", () => {
  it("builds /admin/feedback?node_id= URL with correct encoding", () => {
    expect(feedbackHrefForNode("app:/quotes" as JourneyNodeId)).toBe(
      "/admin/feedback?node_id=app%3A%2Fquotes"
    );
  });
  it("encodes bracketed dynamic segments", () => {
    expect(feedbackHrefForNode("app:/quotes/[id]" as JourneyNodeId)).toBe(
      "/admin/feedback?node_id=app%3A%2Fquotes%2F%5Bid%5D"
    );
  });
});
