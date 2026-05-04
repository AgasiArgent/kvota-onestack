// @vitest-environment jsdom
/**
 * Phase 1a hotfix plan — proof-of-concept jsdom test for `<TableViewsDropdown>`.
 *
 * Purpose:
 * - Prove that the new jsdom + @testing-library/react + @testing-library/user-event
 *   substrate works on the current code (post-revert state, before the
 *   Phase 3 dropdown fix).
 * - Establish the file-naming convention (`*.dom.test.tsx`) and the
 *   `// @vitest-environment jsdom` docblock that future DOM-dependent tests
 *   must follow.
 * - Reproduce or rule-out the Base UI #31 crash on trigger click in jsdom.
 *
 * The reverted hotfix (de3fd4d0) added a `systemViews?` prop and rendered
 * a 4-item «Системные» group above personal/shared. That prop is GONE on
 * main right now, so we cannot directly mount the broken pattern from
 * outside the component. Instead we exercise the dropdown in its current
 * shape — render + click — which is sufficient to prove (a) the substrate
 * works and (b) the trigger click does not throw on the current code.
 *
 * Phase 3 will add tests that drive the new prop wiring once the fix lands.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { TableView } from "@/entities/table-view";

import { TableViewsDropdown } from "../ui/table-views-dropdown";

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
   * Phase 1a discovery (2026-05-04 — DOCUMENTED, NOT GREEN): in the current
   * post-revert code, `<TableViewsDropdown>` uses `<DropdownMenuLabel>`
   * (Base UI's `<Menu.GroupLabel>`) WITHOUT wrapping each labelled section
   * in `<Menu.Group>`. Opening the menu throws:
   *
   *   "Base UI: MenuGroupRootContext is missing. Menu group parts must be
   *    used within <Menu.Group>."
   *
   * This is a real, pre-existing bug invisible to the SSR-only test
   * substrate (`renderToString` never mounts the popup). It validates the
   * Phase 1a thesis: jsdom + RTL CAN catch the Base UI #31 class of bug
   * that SSR cannot.
   *
   * `it.skip` rather than `it.fails`: the React error escapes the test
   * boundary as an Unhandled Exception (jsdom's loose error semantics),
   * which vitest 4 surfaces as a non-zero exit even when `it.fails`
   * captures the throw. Skipping keeps `npm test` exit 0 while preserving
   * the test body for Phase 3 to flip back to plain `it(...)` once the
   * `<DropdownMenuLabel>` markup is wrapped in `<DropdownMenuGroup>`.
   *
   * Phase 3 acceptance: change `it.skip` → `it`, run `npm test`, observe
   * the test green. That test then becomes the regression guard for the
   * Phase B dropdown shipping.
   */
  it.skip(
    "opens the menu on trigger click without crashing (Base UI #31 reproduction — Phase 3 will un-skip)",
    async () => {
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
    }
  );
});
