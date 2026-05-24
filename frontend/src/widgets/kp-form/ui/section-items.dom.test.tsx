import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useState } from "react";

import type { KpProposal } from "@/entities/kp-proposal";
import { DEFAULT_PROPOSAL } from "@/entities/kp-proposal";

import { SectionItems } from "./section-items";

/**
 * Harness: wraps SectionItems in a tiny state container so the controlled
 * inputs work end-to-end. setData spy is exposed to assert it was called.
 */
function Harness({
  initial,
  onChange,
}: {
  initial: KpProposal;
  onChange?: (next: KpProposal) => void;
}) {
  const [data, setData] = useState<KpProposal>(initial);
  return (
    <SectionItems
      data={data}
      setData={(updater) => {
        setData((prev) => {
          const next =
            typeof updater === "function"
              ? (updater as (p: KpProposal) => KpProposal)(prev)
              : updater;
          onChange?.(next);
          return next;
        });
      }}
    />
  );
}

describe("SectionItems (dom)", () => {
  it("renders one row per item from the proposal", () => {
    const proposal: KpProposal = {
      ...DEFAULT_PROPOSAL,
      items: [{ name: "Test Item", model: "Model X", qty: "2", price: "100" }],
    };
    render(<Harness initial={proposal} />);

    expect(screen.getByDisplayValue("Test Item")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Model X")).toBeInTheDocument();
  });

  it("appends an empty row when '+ Добавить позицию' is clicked", () => {
    const proposal: KpProposal = {
      ...DEFAULT_PROPOSAL,
      items: [{ name: "Only", model: "", qty: "1", price: "50" }],
    };
    const onChange = vi.fn();
    render(<Harness initial={proposal} onChange={onChange} />);

    const addButton = screen.getByRole("button", { name: /Добавить позицию/i });
    fireEvent.click(addButton);

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.items).toHaveLength(2);
    expect(lastCall.items[1]).toEqual({
      name: "",
      model: "",
      qty: "",
      price: "",
    });
  });

  it("removes a row when its remove button is clicked", () => {
    const proposal: KpProposal = {
      ...DEFAULT_PROPOSAL,
      items: [
        { name: "First", model: "", qty: "1", price: "100" },
        { name: "Second", model: "", qty: "1", price: "200" },
      ],
    };
    const onChange = vi.fn();
    render(<Harness initial={proposal} onChange={onChange} />);

    const removeButtons = screen.getAllByRole("button", {
      name: /Удалить строку/i,
    });
    fireEvent.click(removeButtons[0]);

    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.items).toHaveLength(1);
    expect(lastCall.items[0].name).toBe("Second");
  });

  it("updates qty input via setData", () => {
    const proposal: KpProposal = {
      ...DEFAULT_PROPOSAL,
      items: [{ name: "Item", model: "", qty: "1", price: "100" }],
    };
    const onChange = vi.fn();
    render(<Harness initial={proposal} onChange={onChange} />);

    const qtyInput = screen.getByLabelText("Количество");
    fireEvent.change(qtyInput, { target: { value: "5" } });

    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.items[0].qty).toBe("5");
  });

  it("updates price input via setData", () => {
    const proposal: KpProposal = {
      ...DEFAULT_PROPOSAL,
      items: [{ name: "Item", model: "", qty: "1", price: "100" }],
    };
    const onChange = vi.fn();
    render(<Harness initial={proposal} onChange={onChange} />);

    const priceInput = screen.getByLabelText("Цена за единицу");
    fireEvent.change(priceInput, { target: { value: "250" } });

    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall.items[0].price).toBe("250");
  });
});
