// @vitest-environment jsdom
/**
 * REQ-7 regression: a member dragging an invoice from «Нераспределено» to
 * «В работе» must actually invoke the `selfPullInvoice` server action.
 *
 * Root cause of the bug: `handleDragEnd`'s self-pull branch relied on
 * `moveCard()`'s return value, but `moveCard` assigns its `moved` variable
 * INSIDE the `setBoard` state-updater callback — that callback runs on the
 * next render, not synchronously. So `moveCard` returned `undefined`, the
 * `if (moved)` guard was false, and `commitSelfPull` (→ `selfPullInvoice`)
 * was never called. The card moved optimistically but nothing hit the DB.
 *
 * This test fires dnd-kit's `onDragEnd` with a synthetic `DragEndEvent` and
 * asserts the mocked server action IS invoked with the card id + domain.
 * It fails against the buggy code and passes after the fix.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render } from "@testing-library/react";
import type { DragEndEvent } from "@dnd-kit/core";

import type {
  WorkspaceKanbanBoard,
  WorkspaceKanbanCard,
} from "../model/types";

// Capture the board's onDragEnd handler by mocking DndContext — full pointer
// drag needs a real DnD backend; firing the handler directly is deterministic.
let capturedOnDragEnd: ((event: DragEndEvent) => void) | undefined;
vi.mock("@dnd-kit/core", async () => {
  const actual =
    await vi.importActual<typeof import("@dnd-kit/core")>("@dnd-kit/core");
  return {
    ...actual,
    DndContext: (props: {
      children?: React.ReactNode;
      onDragEnd?: (event: DragEndEvent) => void;
    }) => {
      capturedOnDragEnd = props.onDragEnd;
      return React.createElement(React.Fragment, null, props.children);
    },
  };
});

// Mock the server action — it is what must (or must not) be invoked.
const selfPullInvoice = vi.fn().mockResolvedValue(undefined);
vi.mock("../server-actions", () => ({
  selfPullInvoice: (...args: unknown[]) => selfPullInvoice(...args),
}));

// next/navigation router is used for refresh() — stub it.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

/**
 * React may run a functional state updater eagerly inside the `dispatch`
 * call (the eager-state bailout optimisation). That implementation detail
 * would let `moveCard`'s `let moved` closure variable get populated
 * synchronously in jsdom and mask the production bug. To pin the documented
 * contract — "a state updater runs on the NEXT render, not synchronously" —
 * `useState` is wrapped so functional updaters are always deferred. The bug
 * (relying on `moveCard`'s return value) then reproduces deterministically.
 */
vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  function useDeferredState<S>(initial: S | (() => S)) {
    const [value, setValue] = actual.useState(initial);
    const set = actual.useCallback(
      (next: React.SetStateAction<S>) => {
        if (typeof next === "function") {
          queueMicrotask(() =>
            setValue((prev) => (next as (p: S) => S)(prev)),
          );
        } else {
          setValue(next);
        }
      },
      [setValue],
    );
    return [value, set] as [S, React.Dispatch<React.SetStateAction<S>>];
  }
  return { ...actual, default: actual, useState: useDeferredState };
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
  };
}

function makeBoard(): WorkspaceKanbanBoard {
  return {
    unassigned: [makeCard()],
    in_progress: [],
    completed: [],
  };
}

describe("KanbanBoard — member self-pull invokes selfPullInvoice (REQ-7)", () => {
  afterEach(() => {
    cleanup();
    capturedOnDragEnd = undefined;
    vi.clearAllMocks();
  });

  it("calls selfPullInvoice with the card id + domain on a self-pull drag", async () => {
    const card = makeCard();

    render(
      <KanbanBoard
        domain="customs"
        initialBoard={makeBoard()}
        isHead={false}
        teamUsers={[]}
      />,
    );

    expect(capturedOnDragEnd).toBeDefined();

    // Synthetic drag: card dropped from «Нераспределено» onto «В работе».
    await act(async () => {
      capturedOnDragEnd!({
        active: { id: CARD_ID, data: { current: { card } } },
        over: { id: "in_progress" },
      } as unknown as DragEndEvent);
      // Flush the deferred `setBoard` updater + the awaited commitSelfPull.
      await Promise.resolve();
    });

    expect(selfPullInvoice).toHaveBeenCalledTimes(1);
    expect(selfPullInvoice).toHaveBeenCalledWith(CARD_ID, "customs");
  });
});
