// @vitest-environment jsdom
/**
 * Testing 2 row 58 — clicking «Шаблон маршрута» on /quotes/{id}/logistics
 * must NOT jump the page back to the top. The tester reported losing
 * their scroll position whenever they applied a route template.
 *
 * Root cause: applying a template triggers `router.refresh()` plus the
 * parent's `onMutation` (which increments a `refreshTick` in the
 * LogisticsStep). That re-runs the parent's data-load effect, which
 * toggles a loading spinner that briefly replaces the RouteConstructor
 * with a small Loader2 icon. The layout collapse shrinks the page
 * height, so the browser's scroll-restoration falls back to
 * `scrollTop=0`. By the time data reloads and the constructor
 * re-mounts, the user is at the top of the page.
 *
 * Fix: `RouteConstructor.handleApplyTemplate` snapshots `window.scrollY`
 * before the mutation and restores it after the post-mutation render
 * cycle (rAF chain) so the page stays anchored on the constructor.
 *
 * This is the user-facing contract — even if a downstream component
 * collapses the layout briefly, the constructor restores scroll on
 * behalf of the user.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RouteConstructor } from "../ui/route-constructor";
import type { LogisticsSegment } from "@/entities/logistics-segment";
import type { LocationOption } from "@/entities/location";
import type { LogisticsTemplate } from "@/entities/logistics-template";

// next/navigation — needed because RouteConstructor calls useRouter().refresh().
const routerRefreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: routerRefreshMock }),
}));

// sonner — used for success/error toasts after the action.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

// applyLogisticsTemplate — server action. The component awaits it before
// firing the scroll restoration.
type ApplyTemplateInput = {
  template_id: string;
  invoice_id: string;
  revalidate_path: string;
};
const applyLogisticsTemplateMock = vi.fn<
  (input: ApplyTemplateInput) => Promise<void>
>();
vi.mock("@/entities/logistics-template", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>;
  return {
    ...actual,
    // Thunk wrapper — vi.mock is hoisted above the const, so we can't
    // reference applyLogisticsTemplateMock directly here.
    applyLogisticsTemplate: (input: ApplyTemplateInput) =>
      applyLogisticsTemplateMock(input),
  };
});

// logistics-segment server actions — mocked so the test does not hit the API
// when other handlers fire.
vi.mock("@/entities/logistics-segment", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>;
  return {
    ...actual,
    createSegment: vi.fn(async () => ({ segment_id: "seg-new" })),
    updateSegment: vi.fn(async () => undefined),
    deleteSegment: vi.fn(async () => undefined),
    reorderSegment: vi.fn(async () => undefined),
    createSegmentExpense: vi.fn(async () => ({ expense_id: "exp-new" })),
    deleteSegmentExpense: vi.fn(async () => undefined),
  };
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const LOC_A: LocationOption = {
  id: "loc-a",
  country: "Россия",
  iso2: "RU",
  city: "Москва",
  type: "supplier",
};
const LOC_B: LocationOption = {
  id: "loc-b",
  country: "Китай",
  iso2: "CN",
  city: "Шанхай",
  type: "hub",
};

const TEMPLATE: LogisticsTemplate = {
  id: "tpl-1",
  name: "RU → CN",
  description: "Стандартный экспорт",
  createdAt: "2026-01-01T00:00:00Z",
  segments: [
    {
      id: "tps-1",
      sequenceOrder: 1,
      fromLocationType: "supplier",
      toLocationType: "hub",
    },
  ],
};

const SEGMENT: LogisticsSegment = {
  id: "seg-1",
  invoiceId: "inv-1",
  sequenceOrder: 1,
  fromLocation: LOC_A,
  toLocation: LOC_B,
  label: undefined,
  transitDays: undefined,
  mainCostRub: 0,
  currencyCode: "RUB",
  carrier: undefined,
  notes: undefined,
  expenses: [],
};

// rAF polyfill — jsdom 20+ ships one but it runs on a 16ms timer, which
// makes the test slow. Replace with a sync-on-microtask shim so the
// restore-scroll callback fires deterministically.
let rafQueue: Array<() => void> = [];
function flushRaf(): void {
  const q = rafQueue;
  rafQueue = [];
  q.forEach((fn) => fn());
}

beforeEach(() => {
  applyLogisticsTemplateMock.mockReset();
  applyLogisticsTemplateMock.mockResolvedValue(undefined);
  routerRefreshMock.mockReset();
  rafQueue = [];
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
    rafQueue.push(() => cb(performance.now()));
    return 0 as unknown as number;
  });
  // Reset scroll spies between tests.
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RouteConstructor — «Шаблон маршрута» scroll preservation (Testing 2 row 58)", () => {
  it("restores window.scrollY after applying a template", async () => {
    const user = userEvent.setup();
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;

    // Pretend the user is scrolled down by 480px (logistics card is below
    // the fold on a typical /quotes/{id} page).
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 480,
    });

    render(
      <RouteConstructor
        invoiceId="inv-1"
        orgId="org-1"
        initialSegments={[SEGMENT]}
        locations={[LOC_A, LOC_B]}
        templates={[TEMPLATE]}
        revalidatePath="/quotes/q-1"
      />,
    );

    // Open the popover via the «Шаблон маршрута» trigger.
    await user.click(screen.getByRole("button", { name: /Шаблон маршрута/i }));

    // Pick the template — this fires onApply → handleApplyTemplate.
    await user.click(screen.getByRole("button", { name: /RU → CN/i }));

    // Server action awaited + router.refresh + onMutation all happen
    // inside startTransition. Wait for the action to be invoked.
    await waitFor(() => {
      expect(applyLogisticsTemplateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          template_id: "tpl-1",
          invoice_id: "inv-1",
          revalidate_path: "/quotes/q-1",
        }),
      );
    });

    // Drain the rAF callback that restores scroll. We chain two flushes
    // to cover both the immediate rAF and any nested one used to wait
    // for the post-mutation paint.
    await waitFor(() => {
      expect(rafQueue.length).toBeGreaterThan(0);
    });
    flushRaf();
    flushRaf();

    // The contract: scrollTo restores the previous Y so the user
    // does NOT end up at scrollTop=0.
    expect(scrollToMock).toHaveBeenCalled();
    const lastCall = scrollToMock.mock.calls.at(-1);
    const arg = lastCall?.[0] as ScrollToOptions | number | undefined;
    if (typeof arg === "object" && arg !== null) {
      expect(arg.top).toBe(480);
    } else {
      // Legacy two-arg signature: scrollTo(x, y)
      expect(lastCall?.[1]).toBe(480);
    }
  });

  it("does not call scrollTo if the user was already at the top (scrollY === 0)", async () => {
    const user = userEvent.setup();
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;

    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 0,
    });

    render(
      <RouteConstructor
        invoiceId="inv-1"
        orgId="org-1"
        initialSegments={[SEGMENT]}
        locations={[LOC_A, LOC_B]}
        templates={[TEMPLATE]}
        revalidatePath="/quotes/q-1"
      />,
    );

    await user.click(screen.getByRole("button", { name: /Шаблон маршрута/i }));
    await user.click(screen.getByRole("button", { name: /RU → CN/i }));

    await waitFor(() => {
      expect(applyLogisticsTemplateMock).toHaveBeenCalled();
    });
    flushRaf();
    flushRaf();

    // No scroll restore needed when the user was already at the top.
    expect(scrollToMock).not.toHaveBeenCalled();
  });

  it("still calls router.refresh + the server action when a template is picked", async () => {
    const user = userEvent.setup();
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 200,
    });

    render(
      <RouteConstructor
        invoiceId="inv-1"
        orgId="org-1"
        initialSegments={[SEGMENT]}
        locations={[LOC_A, LOC_B]}
        templates={[TEMPLATE]}
        revalidatePath="/quotes/q-1"
      />,
    );

    await user.click(screen.getByRole("button", { name: /Шаблон маршрута/i }));
    await user.click(screen.getByRole("button", { name: /RU → CN/i }));

    await waitFor(() => {
      expect(applyLogisticsTemplateMock).toHaveBeenCalledTimes(1);
      expect(routerRefreshMock).toHaveBeenCalledTimes(1);
    });
  });
});
