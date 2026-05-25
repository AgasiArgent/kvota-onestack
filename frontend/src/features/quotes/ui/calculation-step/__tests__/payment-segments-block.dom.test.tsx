/**
 * <PaymentSegmentsBlock> dom tests (Testing 2 row 46, spec
 * `.kiro/specs/payment-segments-row-46/` REQ-3 / REQ-5).
 *
 * Covers the verdict-bearing behaviours called out in tasks.md Task 5:
 *   - Default render with initial state (anchor 1 = 100, others = 0).
 *   - Live auto-balance on anchor-1 change (anchor 5 % = 100 - anchor 1).
 *   - Warning + save disabled when sum > 100.
 *   - Preset «30/70» application.
 *   - Preset «Сброс» reset to 100% anchor 1.
 *
 * Auto-balance is asserted via the read-only «После получения» % input.
 * The block uses string-typed parent state to mirror the calc form's
 * `formValues` map — the same shape the calc API POST body carries.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useState } from "react";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

const { updateSpecificationPaymentMock } = vi.hoisted(() => ({
  updateSpecificationPaymentMock: vi.fn(),
}));
vi.mock("@/entities/specification", () => ({
  updateSpecificationPayment: updateSpecificationPaymentMock,
}));

import { PaymentSegmentsBlock } from "../payment-segments-block";

interface HarnessProps {
  initial?: Partial<Record<string, string>>;
  specId?: string | null;
}

/**
 * Wrapper mirroring the parent calc form: holds string values in local
 * state and feeds them down + collects onFieldChange. Lets each test
 * observe live re-renders driven by the same map shape the calc API uses.
 */
function Harness({ initial = {}, specId }: HarnessProps) {
  const [values, setValues] = useState<Record<string, string>>({
    advance_from_client: "100",
    time_to_advance: "0",
    advance_on_loading: "0",
    time_to_advance_loading: "0",
    advance_on_going_to_country_destination: "0",
    time_to_advance_going_to_country_destination: "0",
    advance_on_customs_clearance: "0",
    time_to_advance_on_customs_clearance: "0",
    time_to_advance_on_receiving: "0",
    ...initial,
  });
  return (
    <PaymentSegmentsBlock
      values={values as Parameters<typeof PaymentSegmentsBlock>[0]["values"]}
      onFieldChange={(k, v) => setValues((prev) => ({ ...prev, [k]: v }))}
      specId={specId ?? null}
    />
  );
}

function getPctInput(label: string): HTMLInputElement {
  return screen.getByLabelText(`${label} — процент`) as HTMLInputElement;
}

function getDaysInput(label: string): HTMLInputElement {
  return screen.getByLabelText(`${label} — дни`) as HTMLInputElement;
}

afterEach(() => {
  cleanup();
  updateSpecificationPaymentMock.mockReset();
});

beforeEach(() => {
  updateSpecificationPaymentMock.mockResolvedValue({ success: true });
});

describe("PaymentSegmentsBlock (dom)", () => {
  it("renders default state: anchor 1 = 100, others = 0, sum badge green", () => {
    render(<Harness />);

    expect(getPctInput("Аванс клиента").value).toBe("100");
    expect(getPctInput("При погрузке").value).toBe("0");
    expect(getPctInput("При прибытии в страну").value).toBe("0");
    expect(getPctInput("При таможне").value).toBe("0");
    // Anchor 5 % is read-only and derived = 100 - 100 = 0.
    expect(getPctInput("После получения").value).toBe("0");
    expect(getPctInput("После получения").readOnly).toBe(true);

    const indicator = screen.getByTestId("payment-sum-indicator");
    expect(indicator).toHaveAttribute("data-status", "valid");
    expect(indicator.textContent).toContain("Σ = 100%");
  });

  it("auto-balances anchor 5 % when anchor 1 % changes", () => {
    render(<Harness />);

    const anchor1 = getPctInput("Аванс клиента");
    fireEvent.change(anchor1, { target: { value: "30" } });

    // Anchor 5 derived: 100 - 30 = 70.
    expect(getPctInput("После получения").value).toBe("70");
    // Sum is still 100% — block is valid.
    expect(screen.getByTestId("payment-sum-indicator")).toHaveAttribute(
      "data-status",
      "valid"
    );
  });

  it("flags 'over 100%' state when anchors 1-4 sum exceeds 100, and disables save", () => {
    render(<Harness specId="spec-uuid-1" />);

    // Drive anchor 1 to 80, anchor 2 to 30 → sum 110 > 100.
    fireEvent.change(getPctInput("Аванс клиента"), { target: { value: "80" } });
    fireEvent.change(getPctInput("При погрузке"), { target: { value: "30" } });

    const indicator = screen.getByTestId("payment-sum-indicator");
    expect(indicator).toHaveAttribute("data-status", "over");
    expect(indicator.textContent).toContain("превышение");

    const saveBtn = screen.getByRole("button", { name: /Сохранить/ });
    expect(saveBtn).toBeDisabled();
  });

  it("applies the 30/70 preset", () => {
    render(<Harness />);

    fireEvent.click(screen.getByTestId("payment-preset-30/70"));

    expect(getPctInput("Аванс клиента").value).toBe("30");
    expect(getDaysInput("Аванс клиента").value).toBe("7");
    expect(getPctInput("При погрузке").value).toBe("0");
    expect(getPctInput("При прибытии в страну").value).toBe("0");
    expect(getPctInput("При таможне").value).toBe("0");
    // Anchor 5 % auto-balanced to 70.
    expect(getPctInput("После получения").value).toBe("70");
    expect(getDaysInput("После получения").value).toBe("30");
  });

  it("applies the Сброс preset", () => {
    render(<Harness initial={{ advance_from_client: "50", time_to_advance: "10" }} />);

    // Sanity: starts at 50/50.
    expect(getPctInput("Аванс клиента").value).toBe("50");
    expect(getPctInput("После получения").value).toBe("50");

    fireEvent.click(screen.getByTestId("payment-preset-Сброс"));

    expect(getPctInput("Аванс клиента").value).toBe("100");
    expect(getDaysInput("Аванс клиента").value).toBe("0");
    expect(getPctInput("После получения").value).toBe("0");
    expect(getDaysInput("После получения").value).toBe("0");
  });

  it("hides the save button when specId is null (block lives pre-spec)", () => {
    render(<Harness />);

    expect(
      screen.queryByRole("button", { name: /Сохранить/ })
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/применятся при пересчёте/i)
    ).toBeInTheDocument();
  });

  it("calls updateSpecificationPayment with parsed segments when save is clicked", async () => {
    render(<Harness specId="spec-uuid-1" />);

    fireEvent.click(screen.getByTestId("payment-preset-50/50"));
    const saveBtn = screen.getByRole("button", { name: /Сохранить/ });
    fireEvent.click(saveBtn);

    // useTransition flushes async on a queued microtask — waitFor handles
    // the deterministic polling against the mock's call count.
    await waitFor(() =>
      expect(updateSpecificationPaymentMock).toHaveBeenCalledTimes(1)
    );
    expect(updateSpecificationPaymentMock).toHaveBeenCalledWith(
      "spec-uuid-1",
      expect.objectContaining({
        advance_percent_from_client: 50,
        payment_deferral_days: 7,
        payment_on_loading_pct: 0,
        payment_on_country_arrival_pct: 0,
        payment_on_customs_clearance_pct: 0,
        payment_on_receiving_days: 30,
      })
    );
  });
});
