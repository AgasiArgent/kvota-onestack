// @vitest-environment jsdom
/**
 * Validation-Excel button gating under the new hasCalculation contract
 * (2026-05-25, "validation file excel скачивается пустой" bug).
 *
 * Pre-fix: hasCalculation was derived from `quote.total_quote_currency != null`.
 * That column lingers after `quote_items` are replaced — the CASCADE clears
 * `quote_calculation_results` but the quote-level aggregate is left untouched.
 * Effect: the Validation Excel button stayed enabled for quotes whose engine
 * never ran on the current items, the download produced an all-zero .xlsm,
 * and testers reported it as "пустой".
 *
 * New contract: `hasCalculation` is true ONLY when at least one
 * `quote_calculation_results` row exists for the quote's items. The parent
 * `CalculationStep` performs the count query and passes a boolean down. This
 * file tests the action-bar's contract under that boolean — i.e., when the
 * caller has correctly computed hasCalculation=false for a quote that has a
 * lingering total but no per-item calc rows, the export section is hidden.
 *
 * Diagnostic: /tmp/validation-xlsm-investigate-2026-05-25.md.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

const { downloadValidationExcelMock } = vi.hoisted(() => ({
  downloadValidationExcelMock: vi.fn(),
}));
vi.mock("@/features/quotes/lib/download-validation-excel", () => ({
  downloadValidationExcel: downloadValidationExcelMock,
}));

import { CalculationActionBar } from "../calculation-action-bar";

afterEach(() => {
  cleanup();
  downloadValidationExcelMock.mockReset();
});

describe("CalculationActionBar — Validation Excel gating", () => {
  it("hides export buttons when hasCalculation=false (the new no-stale-total gate)", () => {
    // This is the regression scenario: in production, the parent would
    // previously have computed `hasCalculation = total_quote_currency != null`
    // and rendered the buttons even when no calc rows existed. The new
    // parent computes `hasCalculation = (calc-row count > 0)` so the right
    // value is passed in. Asserting the action-bar's downstream behavior:
    // when the gate is false, the export section is not rendered.
    render(
      <CalculationActionBar
        quoteId="q-stale-total"
        formValues={{}}
        hasCalculation={false}
        workflowStatus="pending_quote_control"
        isApproved={false}
      />,
    );

    // The "Validation Excel" and "КП PDF" buttons are wrapped in
    // `{hasCalculation && (...)}` — they should not be in the DOM.
    expect(
      screen.queryByRole("button", { name: /Validation Excel/ }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: /КП PDF/ }),
    ).toBeNull();
  });

  it("renders export buttons when hasCalculation=true (the parent confirmed calc rows exist)", () => {
    render(
      <CalculationActionBar
        quoteId="q-calculated"
        formValues={{}}
        hasCalculation={true}
        workflowStatus="pending_quote_control"
        isApproved={false}
      />,
    );

    // Both export buttons are visible. (The PDF button is disabled until
    // approval; that contract is unrelated to this bug.)
    expect(
      screen.getByRole("button", { name: /Validation Excel/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /КП PDF/ }),
    ).toBeInTheDocument();
  });

  it("Calculate button label flips from «Рассчитать» to «Пересчитать» based on hasCalculation, not total_amount", () => {
    // Companion check: the "first run vs subsequent run" wording is also
    // driven by hasCalculation, so it correctly says «Рассчитать» when the
    // calc never ran on the current items even if total_amount lingers.
    const { rerender } = render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={false}
        workflowStatus="pending_sales_review"
        isApproved={false}
      />,
    );

    expect(
      screen.getByRole("button", { name: /^Рассчитать$/ }),
    ).toBeInTheDocument();

    rerender(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={true}
        workflowStatus="pending_sales_review"
        isApproved={false}
      />,
    );

    expect(
      screen.getByRole("button", { name: /Пересчитать/ }),
    ).toBeInTheDocument();
  });
});
