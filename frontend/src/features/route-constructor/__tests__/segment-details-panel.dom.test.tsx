// @vitest-environment jsdom
/**
 * РОЛ Тест 07 #3.6 (cluster L-A, CRITICAL): typing in a segment field
 * must NOT wipe the in-flight characters.
 *
 * Root cause of the original bug: SegmentFields had a useEffect that
 * re-synced every local input from the prop on every change of any
 * field value:
 *   useEffect(() => { setLabel(segment.label ?? ""); ... },
 *     [segment.id, segment.label, segment.carrier, segment.notes,
 *      segment.transitDays, segment.mainCostRub]);
 *
 * The parent panel mounts SegmentFields with `key={segment.id}`, so
 * initial state from `useState(segment.label ?? "")` is enough — the
 * effect's job is only to re-sync when the user switches segments
 * (which already triggers a remount via the key). With the field-level
 * deps, ANY parent re-render that produced a fresh `segment` object
 * (same id, same field values) re-ran the effect mid-edit, blowing
 * away the user's keystrokes and creating the "remount loop" feel.
 *
 * The fix: depend ONLY on segment.id. Since `key={segment.id}` already
 * remounts the component on segment switch, the effect is now a
 * defensive no-op for the stable case and only fires on segment swap.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SegmentDetailsPanel } from "../ui/segment-details-panel";
import type { LogisticsSegment } from "@/entities/logistics-segment";
import type { LocationOption } from "@/entities/location";

// updateSegment is a server action — mock so the test does not hit the API.
vi.mock("@/entities/logistics-segment", async (orig) => {
  const actual = (await orig()) as Record<string, unknown>;
  return {
    ...actual,
    updateSegment: vi.fn(async () => undefined),
    createSegmentExpense: vi.fn(async () => ({ expense_id: "exp-new" })),
    deleteSegmentExpense: vi.fn(async () => undefined),
  };
});

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

function makeSegment(overrides: Partial<LogisticsSegment> = {}): LogisticsSegment {
  return {
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
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SegmentDetailsPanel (РОЛ Тест 07 #3.6)", () => {
  it("preserves typed input when the parent passes a fresh segment ref with the same id", async () => {
    const user = userEvent.setup();

    function Harness() {
      const [seg, setSeg] = React.useState<LogisticsSegment>(makeSegment());
      return (
        <>
          <button
            type="button"
            data-testid="bump-parent"
            onClick={() => {
              // Simulate a parent re-render that produces a fresh `segment`
              // object reference with the SAME id and SAME field values
              // (Next.js router.refresh / revalidatePath cycle).
              setSeg((prev) => ({ ...prev }));
            }}
          >
            bump
          </button>
          <SegmentDetailsPanel
            segment={seg}
            locations={[LOC_A, LOC_B]}
            revalidatePath="/quotes/x"
          />
        </>
      );
    }

    render(<Harness />);

    const labelInput = screen.getByPlaceholderText(
      /First mile, Main freight/i,
    ) as HTMLInputElement;

    await user.type(labelInput, "Первая миля");
    expect(labelInput.value).toBe("Первая миля");

    // Force a parent re-render with a fresh segment ref before blur.
    await user.click(screen.getByTestId("bump-parent"));

    // The input MUST still hold the user's typed text. Before the fix
    // it was reset to "" because the useEffect re-ran on every render
    // when the parent created a fresh segment object literal.
    expect(labelInput.value).toBe("Первая миля");
  });

  it("preserves typed input when the segment object's field values change underneath the user", async () => {
    const user = userEvent.setup();

    function Harness() {
      const [seg, setSeg] = React.useState<LogisticsSegment>(
        makeSegment({ carrier: "Initial carrier" }),
      );
      return (
        <>
          <button
            type="button"
            data-testid="server-update"
            onClick={() => {
              // Simulate a server-driven update arriving while the user
              // is still typing — for example, another field on the same
              // segment was patched. The label prop is unchanged but
              // `carrier` flips. Earlier deps array included carrier, so
              // the effect re-ran setLabel("") mid-edit.
              setSeg((prev) => ({ ...prev, carrier: "DHL" }));
            }}
          >
            server update
          </button>
          <SegmentDetailsPanel
            segment={seg}
            locations={[LOC_A, LOC_B]}
            revalidatePath="/quotes/x"
          />
        </>
      );
    }

    render(<Harness />);

    const labelInput = screen.getByPlaceholderText(
      /First mile, Main freight/i,
    ) as HTMLInputElement;

    await user.type(labelInput, "test");
    expect(labelInput.value).toBe("test");

    await user.click(screen.getByTestId("server-update"));

    // The user's keystrokes must survive the unrelated server update.
    expect(labelInput.value).toBe("test");
  });

  // -------------------------------------------------------------------------
  // Testing 2 row 30 #2 — clicking a cell without editing must NOT save.
  // -------------------------------------------------------------------------
  describe("no-op edit guard (Testing 2 row 30 #2)", () => {
    it("does not call updateSegment when a text field is blurred without a change", async () => {
      const { updateSegment } = (await import(
        "@/entities/logistics-segment"
      )) as unknown as { updateSegment: ReturnType<typeof vi.fn> };
      const user = userEvent.setup();
      const onMutation = vi.fn();

      render(
        <SegmentDetailsPanel
          segment={makeSegment({ carrier: "DHL", label: "Main", notes: "n" })}
          locations={[LOC_A, LOC_B]}
          revalidatePath="/quotes/x"
          onMutation={onMutation}
        />,
      );

      const carrierInput = screen.getByPlaceholderText(
        /Название перевозчика/i,
      ) as HTMLInputElement;

      // Click into the carrier cell, then click away — no edit made.
      await user.click(carrierInput);
      await user.tab();

      expect(updateSegment).not.toHaveBeenCalled();
      expect(onMutation).not.toHaveBeenCalled();
    });

    it("does not call updateSegment when a numeric field is blurred without a change", async () => {
      const { updateSegment } = (await import(
        "@/entities/logistics-segment"
      )) as unknown as { updateSegment: ReturnType<typeof vi.fn> };
      const user = userEvent.setup();

      render(
        <SegmentDetailsPanel
          segment={makeSegment({ transitDays: 7, mainCostRub: 500 })}
          locations={[LOC_A, LOC_B]}
          revalidatePath="/quotes/x"
        />,
      );

      const costInput = screen.getByLabelText("Сумма") as HTMLInputElement;
      await user.click(costInput);
      await user.tab();

      expect(updateSegment).not.toHaveBeenCalled();
    });

    it("still calls updateSegment when a text field IS edited", async () => {
      const { updateSegment } = (await import(
        "@/entities/logistics-segment"
      )) as unknown as { updateSegment: ReturnType<typeof vi.fn> };
      const user = userEvent.setup();

      render(
        <SegmentDetailsPanel
          segment={makeSegment({ carrier: "DHL" })}
          locations={[LOC_A, LOC_B]}
          revalidatePath="/quotes/x"
        />,
      );

      const carrierInput = screen.getByPlaceholderText(
        /Название перевозчика/i,
      ) as HTMLInputElement;

      await user.clear(carrierInput);
      await user.type(carrierInput, "FedEx");
      await user.tab();

      expect(updateSegment).toHaveBeenCalledTimes(1);
      expect(updateSegment).toHaveBeenCalledWith(
        expect.objectContaining({
          segment_id: "seg-1",
          patch: { carrier: "FedEx" },
        }),
      );
    });
  });

  // -------------------------------------------------------------------------
  // Testing 2 row 58 — a real field edit must persist silently (optimistic
  // local update + updateSegment) WITHOUT firing onMutation/router.refresh,
  // which would full-refresh the quote page and lose input focus.
  // -------------------------------------------------------------------------
  describe("field edit does not trigger a full page refresh (Testing 2 row 58)", () => {
    it("persists a carrier edit via updateSegment but does NOT call onMutation", async () => {
      const { updateSegment } = (await import(
        "@/entities/logistics-segment"
      )) as unknown as { updateSegment: ReturnType<typeof vi.fn> };
      const user = userEvent.setup();
      const onMutation = vi.fn();

      render(
        <SegmentDetailsPanel
          segment={makeSegment({ carrier: "DHL" })}
          locations={[LOC_A, LOC_B]}
          revalidatePath="/quotes/x"
          onMutation={onMutation}
        />,
      );

      const carrierInput = screen.getByPlaceholderText(
        /Название перевозчика/i,
      ) as HTMLInputElement;

      await user.clear(carrierInput);
      await user.type(carrierInput, "FedEx");
      await user.tab();

      // The edit is persisted...
      expect(updateSegment).toHaveBeenCalledTimes(1);
      // ...but onMutation (which the parent wires to router.refresh) must
      // NOT fire — field edits are optimistic-only.
      expect(onMutation).not.toHaveBeenCalled();
    });

    it("persists a numeric (cost) edit via updateSegment but does NOT call onMutation", async () => {
      const { updateSegment } = (await import(
        "@/entities/logistics-segment"
      )) as unknown as { updateSegment: ReturnType<typeof vi.fn> };
      const user = userEvent.setup();
      const onMutation = vi.fn();

      render(
        <SegmentDetailsPanel
          segment={makeSegment({ mainCostRub: 500 })}
          locations={[LOC_A, LOC_B]}
          revalidatePath="/quotes/x"
          onMutation={onMutation}
        />,
      );

      const costInput = screen.getByLabelText("Сумма") as HTMLInputElement;
      await user.clear(costInput);
      await user.type(costInput, "1200");
      await user.tab();

      expect(updateSegment).toHaveBeenCalledTimes(1);
      expect(onMutation).not.toHaveBeenCalled();
    });
  });

  it("re-syncs local state when the user switches to a different segment", () => {
    const { rerender } = render(
      <SegmentDetailsPanel
        segment={makeSegment({ id: "seg-1", label: "Первая миля" })}
        locations={[LOC_A, LOC_B]}
        revalidatePath="/quotes/x"
      />,
    );

    let labelInput = screen.getByPlaceholderText(
      /First mile, Main freight/i,
    ) as HTMLInputElement;
    expect(labelInput.value).toBe("Первая миля");

    // Switch to a different segment — `key={segment.id}` should remount
    // SegmentFields, picking up the new label as initial state.
    rerender(
      <SegmentDetailsPanel
        segment={makeSegment({ id: "seg-2", label: "Морской фрахт" })}
        locations={[LOC_A, LOC_B]}
        revalidatePath="/quotes/x"
      />,
    );

    labelInput = screen.getByPlaceholderText(
      /First mile, Main freight/i,
    ) as HTMLInputElement;
    expect(labelInput.value).toBe("Морской фрахт");
  });

  // -------------------------------------------------------------------------
  // Testing 2 row 81 — "Добавить" extras button must be visibly prominent.
  // Smoke test: button is present, accessible by name, and not disabled by
  // default (so МОЛ can find and click it without hunting).
  // -------------------------------------------------------------------------
  describe("extras add button visibility (Testing 2 row 81)", () => {
    it("renders the Добавить button with accessible name and enabled state", () => {
      render(
        <SegmentDetailsPanel
          segment={makeSegment()}
          locations={[LOC_A, LOC_B]}
          revalidatePath="/quotes/x"
        />,
      );

      const addButton = screen.getByRole("button", { name: /Добавить/i });
      expect(addButton).toBeDefined();
      expect(addButton.hasAttribute("disabled")).toBe(false);
    });
  });
});
