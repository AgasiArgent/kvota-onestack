// @vitest-environment jsdom
/**
 * «Комментарий для распределения» (distribution_comment) — optional free-text
 * note МОП can attach to the «Контрольный список» modal before handing the
 * quote to procurement. It surfaces later on the «Нераспределено» kanban card
 * and on the quote/deal context panel so МОЛ / МОТ pick up the hint without
 * re-opening the modal.
 *
 * Acceptance:
 *   - The textarea exists in the modal with the agreed label.
 *   - The field is optional — submit succeeds with it empty (only the
 *     equipment_description required gate matters).
 *   - On submit, the mutation is called with the textarea's trimmed value.
 *   - Empty / whitespace-only input is forwarded as `null` so the backend
 *     and JSONB shape stay clean.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type {
  QuoteDetailRow,
  QuoteItemRow,
} from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks (hoisted by vi.mock before component import)
// ---------------------------------------------------------------------------

const submitMock = vi.fn().mockResolvedValue(undefined);
const patchQuoteMock = vi.fn().mockResolvedValue(undefined);

vi.mock("@/entities/quote/mutations", () => ({
  submitToProcurementWithChecklist: (
    quoteId: string,
    payload: Record<string, unknown>,
  ) => submitMock(quoteId, payload),
  patchQuote: (...args: unknown[]) => patchQuoteMock(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { TransferDialog } from "../transfer-dialog";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeQuote(): QuoteDetailRow {
  // Minimum fields needed for validateForTransfer to pass (no missing required
  // fields → "Передать в закупки" button is enabled and the dialog opens).
  return {
    id: "q-1",
    customer_id: "c-1",
    contact_person_id: "ct-1",
    seller_company_id: "s-1",
    delivery_city: "Москва",
    delivery_country: "Россия",
    delivery_method: "auto",
    incoterms: "DAP",
    delivery_priority: "normal",
  } as unknown as QuoteDetailRow;
}

function makeItem(): QuoteItemRow {
  return {
    id: "qi-1",
    product_name: "Болт М8",
    quantity: 10,
    unit: "шт",
  } as unknown as QuoteItemRow;
}

afterEach(() => {
  cleanup();
  submitMock.mockClear();
  patchQuoteMock.mockClear();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TransferDialog — distribution_comment field", () => {
  async function openDialog() {
    const user = userEvent.setup();
    render(<TransferDialog quote={makeQuote()} items={[makeItem()]} />);
    await user.click(screen.getByRole("button", { name: /Передать в закупки/ }));
    return user;
  }

  it("renders the «Комментарий для распределения» textarea in the modal", async () => {
    await openDialog();

    // Use a flexible regex — the field's accessible name must contain the
    // canonical Russian label; tests should not break on minor wording tweaks.
    const field = screen.getByLabelText(/Комментарий для распределения/i);
    expect(field).toBeInTheDocument();
    expect(field.tagName).toBe("TEXTAREA");
  });

  it("submits with distribution_comment trimmed when the user fills it", async () => {
    const user = await openDialog();

    const desc = screen.getByLabelText(
      /Что это за оборудование и для чего оно необходимо/i,
    );
    await user.type(desc, "Сервер DL380");

    const comment = screen.getByLabelText(/Комментарий для распределения/i);
    await user.type(comment, "  Срочно к Алейне  ");

    // Click the dialog's "Передать в закупки" — there are two buttons with
    // that label (trigger + submit); the submit lives in the DialogFooter.
    const buttons = screen.getAllByRole("button", {
      name: /Передать в закупки/,
    });
    await user.click(buttons[buttons.length - 1]);

    expect(submitMock).toHaveBeenCalledTimes(1);
    expect(submitMock).toHaveBeenCalledWith(
      "q-1",
      expect.objectContaining({
        equipment_description: "Сервер DL380",
        distribution_comment: "Срочно к Алейне",
      }),
    );
  });

  it("submits with distribution_comment=null when the textarea is left blank (optional field)", async () => {
    const user = await openDialog();

    // Fill only the required description; leave the optional comment empty.
    const desc = screen.getByLabelText(
      /Что это за оборудование и для чего оно необходимо/i,
    );
    await user.type(desc, "Сервер DL380");

    const buttons = screen.getAllByRole("button", {
      name: /Передать в закупки/,
    });
    await user.click(buttons[buttons.length - 1]);

    expect(submitMock).toHaveBeenCalledTimes(1);
    expect(submitMock).toHaveBeenCalledWith(
      "q-1",
      expect.objectContaining({
        equipment_description: "Сервер DL380",
        distribution_comment: null,
      }),
    );
  });

  it("does NOT block submission when distribution_comment is empty (field is optional)", async () => {
    const user = await openDialog();

    const desc = screen.getByLabelText(
      /Что это за оборудование и для чего оно необходимо/i,
    );
    await user.type(desc, "Сервер DL380");

    const buttons = screen.getAllByRole("button", {
      name: /Передать в закупки/,
    });
    await user.click(buttons[buttons.length - 1]);

    // submitMock having fired = the optional field did not gate submit.
    expect(submitMock).toHaveBeenCalled();
  });
});
