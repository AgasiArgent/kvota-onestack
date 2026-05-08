// @vitest-environment jsdom
/**
 * L-D 1.1 — Default tab logic on /workspace/logistics and /workspace/customs.
 *
 * The page server-renders activeTab = (URL ?tab=...) ?? defaultTab where
 * defaultTab is "all" for heads (head_of_logistics / head_of_customs / admin /
 * top_manager) and "my" for everyone else. The client wrapper mirrors that
 * default in setTab so URLs stay clean — clicking the default tab strips
 * `?tab=...`, while clicking any other tab writes it.
 *
 * Asserted contracts:
 *   1. A regular logistics user (default = "my") who clicks «Все заявки»
 *      gets `?tab=all`.
 *   2. A head_of_logistics user (default = "all") who clicks «Мои заявки»
 *      gets `?tab=my` — the regression we are fixing (used to strip).
 *   3. A head clicking the default tab («Все заявки») strips the query
 *      string entirely.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    refresh: () => {},
    replace: () => {},
    back: () => {},
    forward: () => {},
    prefetch: () => {},
  }),
  usePathname: () => "/workspace/logistics",
}));

import { WorkspaceLogisticsClient } from "../workspace-logistics-client";

afterEach(() => {
  cleanup();
  pushMock.mockReset();
});

const slots = {
  my: <div>my-slot</div>,
  completed: <div>completed-slot</div>,
  unassigned: <div>unassigned-slot</div>,
  all: <div>all-slot</div>,
};

describe("WorkspaceLogisticsClient — default tab navigation", () => {
  it("regular user (default=my) clicking «Все заявки» writes ?tab=all", () => {
    // Regular logistics user can't see «Все заявки» tab (head-only), so this
    // contract guards the rare admin who happens to be only "logistics" + a
    // head role swap; for completeness we feed an admin role here so the tab
    // is visible.
    render(
      <WorkspaceLogisticsClient
        userRoles={["logistics", "admin"]}
        activeTab="my"
        defaultTab="my"
        counts={{ my: 1, completed: 0, unassigned: 0, all: 5 }}
      >
        {slots}
      </WorkspaceLogisticsClient>,
    );

    const allTab = screen.getByRole("tab", { name: /Все заявки/i });
    allTab.click();

    expect(pushMock).toHaveBeenCalledTimes(1);
    expect(pushMock.mock.calls[0][0]).toBe("/workspace/logistics?tab=all");
  });

  it("head_of_logistics (default=all) clicking «Мои заявки» writes ?tab=my", () => {
    render(
      <WorkspaceLogisticsClient
        userRoles={["head_of_logistics"]}
        activeTab="all"
        defaultTab="all"
        counts={{ my: 1, completed: 0, unassigned: 0, all: 5 }}
      >
        {slots}
      </WorkspaceLogisticsClient>,
    );

    const myTab = screen.getByRole("tab", { name: /Мои заявки/i });
    myTab.click();

    expect(pushMock).toHaveBeenCalledTimes(1);
    expect(pushMock.mock.calls[0][0]).toBe("/workspace/logistics?tab=my");
  });

  it("head_of_logistics clicking «Все заявки» (their default) strips the query string", () => {
    render(
      <WorkspaceLogisticsClient
        userRoles={["head_of_logistics"]}
        activeTab="my"
        defaultTab="all"
        counts={{ my: 1, completed: 0, unassigned: 0, all: 5 }}
      >
        {slots}
      </WorkspaceLogisticsClient>,
    );

    const allTab = screen.getByRole("tab", { name: /Все заявки/i });
    allTab.click();

    expect(pushMock).toHaveBeenCalledTimes(1);
    expect(pushMock.mock.calls[0][0]).toBe("/workspace/logistics");
  });
});
