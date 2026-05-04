// @vitest-environment jsdom
/**
 * Phase 1a / Phase 3 hotfix plan — jsdom regression suite for `<TableViewsDropdown>`.
 *
 * History:
 * - Phase 1a (2026-05-04) introduced this file as the proof-of-concept for
 *   the new jsdom + @testing-library/react + @testing-library/user-event
 *   substrate. The original Base UI #31 reproduction case was authored as
 *   `it.skip(...)` because the markup error escaped the test boundary as a
 *   raw React/Base UI throw — see commit log of `dropdown-jsdom.dom.test.tsx`.
 * - Phase 3 (2026-05-04) wrapped each `<DropdownMenuLabel>` in a
 *   `<DropdownMenuGroup>` (Base UI `<Menu.Group>`), eliminating the
 *   `MenuGroupRootContext is missing` throw. The previously-skipped test
 *   was flipped to plain `it(...)` and now passes — it stays in the suite
 *   as the regression guard.
 * - Phase 3 also folded `CUSTOMS_SYSTEM_VIEWS` into the `views` prop with a
 *   `is_system: true` flag rather than introducing a separate `systemViews?`
 *   prop. The new tests below verify that flag-based grouping renders the
 *   «Системные» heading and routes click events through `onViewChange`.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { TableView } from "@/entities/table-view";

import {
  TableViewsDropdown,
  type DropdownTableView,
} from "../ui/table-views-dropdown";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
//
// `<TableViewsSettingsDialog>` opens a Base UI dialog with form internals that
// are out of scope for this proof-of-concept. Mock the export so the
// dropdown renders the dialog mount-point as a no-op — render flow stays
// focused on the dropdown itself.
vi.mock("../ui/table-views-settings-dialog", () => ({
  TableViewsSettingsDialog: () => null,
}));

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const personalView: TableView = {
  id: "view-personal-1",
  userId: "user-1",
  tableKey: "customs",
  name: "Мой вид",
  filters: {},
  sort: null,
  visibleColumns: ["sku", "name"],
  isShared: false,
  organizationId: null,
  isDefault: false,
  createdAt: "2026-05-01T00:00:00.000Z",
  updatedAt: "2026-05-01T00:00:00.000Z",
};

const sharedView: TableView = {
  ...personalView,
  id: "view-shared-1",
  name: "Общий вид",
  isShared: true,
  organizationId: "org-1",
};

// Phase 3 fixtures — synthetic «Системные» views adapted to the
// `DropdownTableView` shape (the dropdown's view model). These mirror the
// production constant `CUSTOMS_SYSTEM_VIEWS` from
// `frontend/src/features/quotes/ui/customs-step/customs-views.ts` after
// the customs-step adapter normalises `SystemView` → `DropdownTableView`.
const systemViewAll: DropdownTableView = {
  id: "system:all",
  userId: "system",
  tableKey: "customs",
  name: "Все колонки",
  filters: {},
  sort: null,
  visibleColumns: ["sku", "name"],
  isShared: false,
  organizationId: null,
  isDefault: false,
  createdAt: "1970-01-01T00:00:00.000Z",
  updatedAt: "1970-01-01T00:00:00.000Z",
  is_system: true,
};

const systemViewTariffs: DropdownTableView = {
  ...systemViewAll,
  id: "system:tariffs-nds",
  name: "Тарифы и НДС",
};

const systemViewDocuments: DropdownTableView = {
  ...systemViewAll,
  id: "system:documents",
  name: "Документы и сертификаты",
};

const systemViewIdentification: DropdownTableView = {
  ...systemViewAll,
  id: "system:identification",
  name: "Только идентификация",
};

function renderDropdown(overrides: Partial<React.ComponentProps<typeof TableViewsDropdown>> = {}) {
  const onViewChange = vi.fn();
  const onViewsRefresh = vi.fn();
  const props: React.ComponentProps<typeof TableViewsDropdown> = {
    views: [personalView, sharedView],
    activeViewId: null,
    onViewChange,
    onViewsRefresh,
    tableKey: "customs",
    availableColumns: [
      { key: "sku", label: "Артикул" },
      { key: "name", label: "Наименование" },
    ],
    userId: "user-1",
    orgId: "org-1",
    canCreateShared: false,
    ...overrides,
  };

  const utils = render(<TableViewsDropdown {...props} />);
  return { ...utils, onViewChange, onViewsRefresh };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TableViewsDropdown — DOM behaviour (jsdom substrate)", () => {
  it("mounts without throwing and renders the trigger button", () => {
    renderDropdown();

    // Trigger renders «Все колонки» when no view is active.
    expect(screen.getByRole("button", { name: /Все колонки/ })).toBeInTheDocument();
  });

  it("renders the active view's name in the trigger", () => {
    renderDropdown({ activeViewId: personalView.id });

    expect(
      screen.getByRole("button", { name: new RegExp(personalView.name) })
    ).toBeInTheDocument();
  });

  /**
   * Regression guard for the Base UI #31 «MenuGroupRootContext is missing»
   * crash. Pre-Phase 3, `<TableViewsDropdown>` rendered
   * `<DropdownMenuLabel>` (Base UI `<Menu.GroupLabel>`) at the top level of
   * the popup, which threw on first paint of the menu because Menu group
   * parts must live inside a `<Menu.Group>`.
   *
   * Phase 3 wrapped each labelled section in `<DropdownMenuGroup>`; this
   * test ensures the wrapper stays in place. If a future refactor unwraps
   * a label, this test fails on `await user.click(trigger)` with the
   * original Base UI throw.
   */
  it("opens the menu on trigger click without crashing (Base UI #31 regression)", async () => {
    const user = userEvent.setup();
    const { onViewChange } = renderDropdown();

    const trigger = screen.getByRole("button", { name: /Все колонки/ });
    await user.click(trigger);

    // After click, the personal-view item should be reachable in the DOM —
    // Base UI mounts the popup via portal into document.body. If the click
    // crashes (Base UI #31 / portal mount mismatch), this query throws.
    const personalItem = await screen.findByText(personalView.name);
    expect(personalItem).toBeInTheDocument();

    // Click the personal view to confirm the click handler fires.
    await user.click(personalItem);
    expect(onViewChange).toHaveBeenCalledWith(personalView.id);
  });

  /**
   * Phase 3 acceptance — REQ-11 AC#4: the dropdown groups system views
   * under «Системные» heading above any user views. Mounting with the 4
   * production `CUSTOMS_SYSTEM_VIEWS` plus a personal/shared row should
   * render all 4 names + the «Системные» / «Личные» / «Общие» labels in
   * the popup.
   */
  it("renders 4 system views grouped under «Системные»", async () => {
    const user = userEvent.setup();
    renderDropdown({
      views: [
        systemViewAll,
        systemViewTariffs,
        systemViewDocuments,
        systemViewIdentification,
        personalView,
        sharedView,
      ],
    });

    await user.click(screen.getByRole("button", { name: /Все колонки/ }));

    // Wait on the «Системные» heading — it only appears inside the popup
    // (never in the trigger), so this is a reliable signal that the menu
    // finished mounting.
    expect(await screen.findByText("Системные")).toBeInTheDocument();

    // All 3 group headings render — proves grouping survived the click.
    expect(screen.getByText("Личные")).toBeInTheDocument();
    expect(screen.getByText("Общие")).toBeInTheDocument();

    // System view names — the systemViewAll name "Все колонки" duplicates
    // the static «Все колонки» menu item label, so we assert via
    // getAllByText (≥ 2). The other 3 system view names are unique.
    expect(screen.getAllByText(systemViewAll.name).length).toBeGreaterThanOrEqual(
      2
    );
    expect(screen.getByText(systemViewTariffs.name)).toBeInTheDocument();
    expect(screen.getByText(systemViewDocuments.name)).toBeInTheDocument();
    expect(screen.getByText(systemViewIdentification.name)).toBeInTheDocument();
  });

  /**
   * Phase 3 acceptance — clicking a system view in the dropdown forwards
   * the synthetic `system:*` id to the parent's `onViewChange` callback.
   * The parent is responsible for URL persistence (see customs-step.tsx
   * `handleViewChange`); the dropdown only emits the id.
   */
  it("clicking a system view fires onViewChange with the synthetic system:* id", async () => {
    const user = userEvent.setup();
    const { onViewChange } = renderDropdown({
      views: [
        systemViewAll,
        systemViewTariffs,
        personalView,
      ],
    });

    await user.click(screen.getByRole("button", { name: /Все колонки/ }));
    const tariffsItem = await screen.findByText(systemViewTariffs.name);
    await user.click(tariffsItem);

    expect(onViewChange).toHaveBeenCalledWith("system:tariffs-nds");
  });
});
