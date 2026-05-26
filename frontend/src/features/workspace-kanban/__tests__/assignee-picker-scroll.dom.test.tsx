// @vitest-environment jsdom
/**
 * Testing 2 rows 62 + 63 (follow-up) — when a head picks an assignee from the
 * «Назначить» / «Переназначить» popover on a logistics / customs kanban card,
 * the page must NOT jump to the top after the assignment completes.
 *
 * The initial popover-open scroll was fixed earlier (commit cd7863f2 — see
 * `assignee-picker-popover-focus.dom.test.tsx`). The tester reproduced a
 * different scroll-to-top on the SAME flow: after picking an assignee, the
 * server action resolves, the parent kanban-board calls `router.refresh()`,
 * the card moves column (Нераспределено → В работе) via the
 * `setBoard(initialBoard)` re-seed effect, and the brief layout reflow
 * causes the browser to reset scrollTop to 0.
 *
 * Root cause: same class as Testing 2 row 58 (PR #248 — applyLogisticsTemplate
 * scroll jump). Fix: snapshot `window.scrollY` before firing
 * `router.refresh()` and restore it on a two-rAF chain via the shared
 * `preserveScroll` helper (frontend/src/shared/lib/scroll.ts).
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render } from "@testing-library/react";

import type {
  WorkspaceKanbanBoard,
  WorkspaceKanbanCard,
} from "../model/types";

// next/navigation router — the board calls .refresh() in handleAssigned.
const routerRefreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: routerRefreshMock }),
}));

// Server action surface is not exercised in this test — the assignee flow is
// fired by invoking the board's onAssigned hook directly via a mocked
// KanbanCard. We only need to confirm that handleAssigned preserves scroll.
vi.mock("../server-actions", () => ({
  selfPullInvoice: vi.fn().mockResolvedValue(undefined),
}));

// Capture the onAssigned callback wired up to a KanbanCard so the test can
// fire it without exercising the full popover open / select flow.
let capturedOnAssigned: (() => void) | undefined;
vi.mock("../ui/kanban-card", () => ({
  KanbanCard: (props: {
    onAssigned?: () => void;
    card: WorkspaceKanbanCard;
  }) => {
    // Only capture the first card's handler; that is enough for the test.
    if (!capturedOnAssigned && props.onAssigned) {
      capturedOnAssigned = props.onAssigned;
    }
    return React.createElement(
      "div",
      { "data-testid": `card-${props.card.id}` },
      props.card.idn,
    );
  },
}));

// dnd-kit DragOverlay portals to body — replace with a passthrough.
vi.mock("@dnd-kit/core", async () => {
  const actual =
    await vi.importActual<typeof import("@dnd-kit/core")>("@dnd-kit/core");
  return {
    ...actual,
    DndContext: (props: { children?: React.ReactNode }) =>
      React.createElement(React.Fragment, null, props.children),
    DragOverlay: () => null,
  };
});

import { KanbanBoard } from "../ui/kanban-board";

const CARD_ID = "invoice-1";

function makeCard(): WorkspaceKanbanCard {
  return {
    id: CARD_ID,
    quoteId: "quote-1",
    invoiceNumber: "inv-1",
    idn: "Q-202604-0018 / inv-1",
    quoteIdn: "Q-202604-0018",
    customerName: "ООО Ромашка",
    pickupLocation: { country: "Китай", iso2: "CN", city: "Шанхай" },
    deliveryLocation: { country: "Россия", iso2: "RU", city: "Москва" },
    stageEnteredAt: "2026-05-10T08:00:00Z",
    assignedAt: null,
    deadlineAt: null,
    completedAt: null,
    assignedUserId: null,
    itemCount: 3,
    dealSumTotal: 100000,
    dealSumCurrency: "RUB",
    totalWeightKg: null,
    totalVolumeM3: null,
    packageCount: null,
    cargoPlaces: [],
    distributionComment: null,
  };
}

function makeBoard(): WorkspaceKanbanBoard {
  return {
    unassigned: [makeCard()],
    in_progress: [],
    completed: [],
  };
}

// rAF polyfill so the post-mutation scroll restore fires deterministically.
let rafQueue: Array<() => void> = [];
function flushRaf(): void {
  const q = rafQueue;
  rafQueue = [];
  q.forEach((fn) => fn());
}

beforeEach(() => {
  rafQueue = [];
  capturedOnAssigned = undefined;
  routerRefreshMock.mockReset();
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
    rafQueue.push(() => cb(performance.now()));
    return 0 as unknown as number;
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe.each(["logistics", "customs"] as const)(
  "KanbanBoard (%s) — handleAssigned preserves scroll (Testing 2 rows 62/63 follow-up)",
  (domain) => {
    it("restores window.scrollY after onAssigned fires router.refresh()", async () => {
      const scrollToMock = vi.fn();
      window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;
      // The user scrolled down to a card that lives below the fold — 720px is
      // typical for the 2nd-3rd row of cards on a 1080p workspace board.
      Object.defineProperty(window, "scrollY", {
        configurable: true,
        value: 720,
      });

      render(
        <KanbanBoard
          domain={domain}
          initialBoard={makeBoard()}
          isHead={true}
          teamUsers={[]}
        />,
      );

      expect(capturedOnAssigned).toBeDefined();

      await act(async () => {
        capturedOnAssigned!();
        // Let microtasks settle so preserveScroll's awaited inner action runs.
        await Promise.resolve();
      });

      // router.refresh() must still be called — scroll preservation is purely
      // additive, never replacing the refresh.
      expect(routerRefreshMock).toHaveBeenCalledTimes(1);

      // Drain both rAF ticks (the first lets React commit, the second lets
      // the browser lay out after the refresh).
      flushRaf();
      flushRaf();

      // The contract: scrollTo restores the previous Y so the head does NOT
      // land at the top of the page after picking an assignee.
      expect(scrollToMock).toHaveBeenCalledTimes(1);
      const arg = scrollToMock.mock.calls[0][0] as ScrollToOptions;
      expect(arg.top).toBe(720);
      expect(arg.behavior).toBe("instant");
    });

    it("does not call scrollTo when the user was already at the top", async () => {
      const scrollToMock = vi.fn();
      window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;
      Object.defineProperty(window, "scrollY", {
        configurable: true,
        value: 0,
      });

      render(
        <KanbanBoard
          domain={domain}
          initialBoard={makeBoard()}
          isHead={true}
          teamUsers={[]}
        />,
      );

      expect(capturedOnAssigned).toBeDefined();

      await act(async () => {
        capturedOnAssigned!();
        await Promise.resolve();
      });

      flushRaf();
      flushRaf();

      // Already at the top — no restore needed.
      expect(scrollToMock).not.toHaveBeenCalled();
      // Refresh still fires.
      expect(routerRefreshMock).toHaveBeenCalledTimes(1);
    });
  },
);
