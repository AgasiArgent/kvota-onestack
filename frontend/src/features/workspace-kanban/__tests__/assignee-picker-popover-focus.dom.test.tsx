// @vitest-environment jsdom
/**
 * Testing 2 rows 62 & 63 — «Workspace · Логистика / Таможня»: clicking the
 * «Назначить» / «Переназначить» button on a kanban card scrolled the whole
 * page to the top instead of opening the assignee picker in place. Reported
 * by 3 testers (РОЛ, МОЛ, МВЭД).
 *
 * Root cause: the search input inside the head assignee popover used the
 * native `autoFocus` attribute. React focuses an `autoFocus` element with a
 * plain `.focus()` call (no `preventScroll`). The popover content is portaled
 * to <body>, so it briefly sits at (0,0) before Floating UI positions it.
 * Focusing the off-screen input made the browser scroll the viewport to the
 * top to bring it into view, yanking the kanban board with it.
 *
 * Fix (mirrors the earlier searchable-combobox fix for row 39): route initial
 * focus through Base UI's `initialFocus` callback, which calls
 * `.focus({ preventScroll: true })` and returns `false` so Base UI doesn't
 * double-focus the first tabbable child with its scroll-causing default.
 *
 * This test pins the contract: when the assignee popover opens, the search
 * input IS focused, AND every `focus()` call on it carries
 * `{ preventScroll: true }`. jsdom doesn't lay out / scroll, so we assert on
 * the focus-call options rather than on a scrollTop delta. The companion
 * assertion (no native `autofocus` attribute) closes the regression door even
 * for code paths that bypass the focus spy.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

// `reassignInvoice` is a server action — replace with a no-op stub so the
// jsdom render never touches the network or Next server pipeline. The test
// only exercises the open / focus path; assignment behavior is covered
// elsewhere.
vi.mock("@/features/workspace-logistics", () => ({
  reassignInvoice: vi.fn().mockResolvedValue(undefined),
}));

// UserAvatarChip pulls in next/image + supabase URL builders that the jsdom
// render can't satisfy. Stub it to a plain span — we don't assert on its
// contents here.
vi.mock("@/entities/user/ui/user-avatar-chip", () => ({
  UserAvatarChip: ({ user }: { user: { id: string; name: string } }) => (
    <span data-testid={`user-${user.id}`}>{user.name}</span>
  ),
}));

import { AssigneePickerPopover } from "../ui/assignee-picker-popover";
import type { WorkspaceKanbanCard } from "../model/types";

function makeCard(): WorkspaceKanbanCard {
  return {
    id: "invoice-1",
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

const TEAM = [
  { id: "u-1", name: "Алейна Алешина", email: "aleyna@kvota.ru" },
  { id: "u-2", name: "Борис Боровиков", email: "boris@kvota.ru" },
];

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AssigneePickerPopover — opens in place without scrolling the page (Testing 2 rows 62/63)", () => {
  it("focuses the search input with { preventScroll: true } when opened", async () => {
    const focusSpy = vi.spyOn(HTMLInputElement.prototype, "focus");

    function Harness() {
      return (
        <AssigneePickerPopover
          card={makeCard()}
          domain="logistics"
          teamUsers={TEAM}
          open={true}
          onOpenChange={() => {}}
          onAssigned={() => {}}
          onCancelled={() => {}}
        />
      );
    }

    render(<Harness />);

    // Search input mounts inside the portaled popover content. Wait until
    // Base UI's open effect + microtask focus dispatch has run.
    const input = (await waitFor(() =>
      screen.getByPlaceholderText("Поиск..."),
    )) as HTMLInputElement;
    expect(input).toBeInTheDocument();

    // The input must have been focused on open...
    await waitFor(() => {
      expect(focusSpy).toHaveBeenCalled();
    });

    // ...and every focus() call must opt out of scroll-into-view. A bare
    // `.focus()` (no options object, or `preventScroll !== true`) is exactly
    // what `autoFocus` / Base UI's default does and what causes the page to
    // jump to the top.
    for (const call of focusSpy.mock.calls) {
      expect(call[0]).toMatchObject({ preventScroll: true });
    }
  });

  it("does not set the native autoFocus attribute on the search input", async () => {
    function Harness() {
      return (
        <AssigneePickerPopover
          card={makeCard()}
          domain="customs"
          teamUsers={TEAM}
          open={true}
          onOpenChange={() => {}}
          onAssigned={() => {}}
          onCancelled={() => {}}
        />
      );
    }

    render(<Harness />);

    const input = (await screen.findByPlaceholderText(
      "Поиск...",
    )) as HTMLInputElement;
    // `autoFocus` is the scroll-causing path — it must be gone.
    expect(input.hasAttribute("autofocus")).toBe(false);
  });

  it("uses the controlled `open` prop to open in place (no trigger click required)", async () => {
    // Opening via the trigger pointerdown / click would be picked up by
    // dnd-kit in production; this test verifies the popover *can* be opened
    // purely via the controlled `open` prop, which is what the board does
    // for the head-drag flow (and what the trigger click ultimately routes
    // through). The picker must render without any drag-or-scroll hop.
    function Harness() {
      return (
        <AssigneePickerPopover
          card={makeCard()}
          domain="logistics"
          teamUsers={TEAM}
          open={true}
          onOpenChange={() => {}}
          onAssigned={() => {}}
          onCancelled={() => {}}
        />
      );
    }

    render(<Harness />);

    // Header copy is rendered only when the popover is mounted.
    expect(await screen.findByText(/Назначить логиста/i)).toBeInTheDocument();
    // Team roster renders.
    expect(screen.getByTestId("user-u-1")).toBeInTheDocument();
    expect(screen.getByTestId("user-u-2")).toBeInTheDocument();
  });

  it("clicking the trigger calls onOpenChange — confirming it is a button, not a form submit", () => {
    // Defense in depth: the trigger must be type="button" so a click never
    // submits an enclosing form / reloads the page (one of the candidate
    // scroll-to-top causes during triage).
    const onOpenChange = vi.fn();

    render(
      <AssigneePickerPopover
        card={makeCard()}
        domain="logistics"
        teamUsers={TEAM}
        open={false}
        onOpenChange={onOpenChange}
        onAssigned={() => {}}
        onCancelled={() => {}}
      />,
    );

    const trigger = screen.getByRole("button", { name: /Назначить/i });
    expect(trigger).toHaveAttribute("type", "button");

    fireEvent.click(trigger);
    expect(onOpenChange).toHaveBeenCalledWith(true);
  });
});
