// @vitest-environment jsdom
/**
 * Testing 2 row 61 — context-panel «Комментарий для распределения» edit
 * affordance.
 *
 * The block was already wired (Testing 2 row 29 — sales-checklist-block.tsx)
 * but only as a read-only render. After transfer to procurement the modal
 * becomes unreachable, so МОП / РОП need a way to amend the hint from the
 * always-visible context panel. This test pins:
 *   - Edit button visible for sales-tier viewers (admin / sales /
 *     head_of_sales) when the block is shown.
 *   - Edit button hidden for read-only roles (procurement / logistics / etc.).
 *   - The block stays visible for sales-tier even when the comment is empty,
 *     so the affordance is reachable post-transfer for legacy quotes.
 *   - Clicking «Изменить» / «Добавить» opens an inline textarea + save/cancel
 *     buttons.
 *   - Saving calls `updateDistributionComment` with the trimmed value.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { QuoteDetailRow } from "@/entities/quote/queries";
import type { QuoteContextData } from "../queries";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// The contact / address dropdowns pull supabase + next routing into render —
// stub them out so we can focus on the checklist block. Same pattern as the
// adjacent context-panel.dom.test.tsx.
vi.mock("../contact-dropdown-select", () => ({
  ContactDropdownSelect: () => (
    <button type="button" data-testid="context-panel-contact-editable">
      contact-editable
    </button>
  ),
}));
vi.mock("../address-dropdown-select", () => ({
  AddressDropdownSelect: () => (
    <button type="button" data-testid="context-panel-address-editable">
      address-editable
    </button>
  ),
}));

const updateMock = vi.fn();
vi.mock("@/entities/quote/server-actions", () => ({
  updateDistributionComment: (quoteId: string, comment: string | null) =>
    updateMock(quoteId, comment),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { ContextPanel } from "../context-panel";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeQuote(overrides: Partial<QuoteDetailRow> = {}): QuoteDetailRow {
  return {
    id: "q-1",
    customer_id: "c-1",
    contact_person_id: "ct-1",
    delivery_address: "Москва",
    delivery_city: "Москва",
    delivery_method: "auto",
    delivery_priority: "normal",
    payment_terms: "Postpaid",
    valid_until: null,
    currency: "USD",
    incoterms: "DAP",
    customer: { id: "c-1", name: "ACME", inn: null },
    contact_person: null,
    seller_company: null,
    created_by_profile: null,
    ...overrides,
  } as unknown as QuoteDetailRow;
}

function makeData(distributionComment: string | null): QuoteContextData {
  return {
    salesChecklist: {
      is_estimate: false,
      is_tender: false,
      direct_request: false,
      trading_org_request: false,
      equipment_description: "Сервер DL380",
      distribution_comment: distributionComment,
      completed_at: null,
      completed_by: null,
    },
    contactPerson: null,
    salesManager: null,
    participants: [],
    procurementAssignees: [],
    logisticsAssignees: [],
    customsAssignees: [],
    pickupLocations: [],
  };
}

afterEach(() => {
  cleanup();
  updateMock.mockReset();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ContextPanel — distribution_comment edit affordance (row 61)", () => {
  it("shows an «Изменить» button for sales when a comment exists", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={makeData("Старый комментарий")}
        userRoles={["sales"]}
      />,
    );

    const btn = screen.getByTestId("context-panel-distribution-comment-edit");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent("Изменить");
  });

  it("shows an «Добавить» button for sales when the comment is empty", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={makeData(null)}
        userRoles={["sales"]}
      />,
    );

    const btn = screen.getByTestId("context-panel-distribution-comment-edit");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent("Добавить");
  });

  it("shows the edit button for head_of_sales", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={makeData("Старый комментарий")}
        userRoles={["head_of_sales"]}
      />,
    );

    expect(
      screen.getByTestId("context-panel-distribution-comment-edit"),
    ).toBeInTheDocument();
  });

  it("shows the edit button for admin", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={makeData("Старый комментарий")}
        userRoles={["admin"]}
      />,
    );

    expect(
      screen.getByTestId("context-panel-distribution-comment-edit"),
    ).toBeInTheDocument();
  });

  it("does NOT show the edit button for procurement (read-only render)", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={makeData("Старый комментарий")}
        userRoles={["procurement"]}
      />,
    );

    expect(
      screen.queryByTestId("context-panel-distribution-comment-edit"),
    ).not.toBeInTheDocument();
    // But the value is still displayed as a static block.
    const row = screen.getByTestId("context-panel-distribution-comment");
    expect(row).toHaveTextContent("Старый комментарий");
  });

  it("does NOT show the edit button for logistics / customs", () => {
    for (const role of ["logistics", "customs", "head_of_logistics", "head_of_customs"]) {
      const { unmount } = render(
        <ContextPanel
          quote={makeQuote()}
          data={makeData("Старый комментарий")}
          userRoles={[role]}
        />,
      );
      expect(
        screen.queryByTestId("context-panel-distribution-comment-edit"),
      ).not.toBeInTheDocument();
      unmount();
    }
  });

  it("clicking «Изменить» opens an inline textarea", async () => {
    const user = userEvent.setup();
    render(
      <ContextPanel
        quote={makeQuote()}
        data={makeData("Старый комментарий")}
        userRoles={["sales"]}
      />,
    );

    await user.click(
      screen.getByTestId("context-panel-distribution-comment-edit"),
    );

    const textarea = screen.getByTestId(
      "context-panel-distribution-comment-textarea",
    );
    expect(textarea.tagName).toBe("TEXTAREA");
    expect((textarea as HTMLTextAreaElement).value).toBe("Старый комментарий");
    expect(
      screen.getByTestId("context-panel-distribution-comment-save"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-distribution-comment-cancel"),
    ).toBeInTheDocument();
  });

  it("clicking «Сохранить» calls updateDistributionComment with trimmed value", async () => {
    updateMock.mockResolvedValueOnce({ success: true, value: "Срочно к Алейне" });
    const user = userEvent.setup();

    render(
      <ContextPanel
        quote={makeQuote()}
        data={makeData(null)}
        userRoles={["sales"]}
      />,
    );

    await user.click(
      screen.getByTestId("context-panel-distribution-comment-edit"),
    );
    const ta = screen.getByTestId(
      "context-panel-distribution-comment-textarea",
    );
    await user.type(ta, "  Срочно к Алейне  ");
    await user.click(
      screen.getByTestId("context-panel-distribution-comment-save"),
    );

    await waitFor(() => {
      expect(updateMock).toHaveBeenCalled();
    });
    expect(updateMock).toHaveBeenCalledWith("q-1", "Срочно к Алейне");
  });

  it("clicking «Отмена» discards changes without calling the action", async () => {
    const user = userEvent.setup();

    render(
      <ContextPanel
        quote={makeQuote()}
        data={makeData("Старый")}
        userRoles={["sales"]}
      />,
    );

    await user.click(
      screen.getByTestId("context-panel-distribution-comment-edit"),
    );
    const ta = screen.getByTestId(
      "context-panel-distribution-comment-textarea",
    );
    await user.clear(ta);
    await user.type(ta, "Новый текст");
    await user.click(
      screen.getByTestId("context-panel-distribution-comment-cancel"),
    );

    expect(updateMock).not.toHaveBeenCalled();
    // Editor closed; original value visible again.
    expect(
      screen.queryByTestId("context-panel-distribution-comment-textarea"),
    ).not.toBeInTheDocument();
    const row = screen.getByTestId("context-panel-distribution-comment");
    expect(row).toHaveTextContent("Старый");
  });

  it("keeps the sales-checklist block visible for sales even with empty payload (so «Добавить» is reachable)", () => {
    // Completely empty checklist — pre-row-61 this would hide the block.
    const dataEmpty: QuoteContextData = {
      salesChecklist: {
        is_estimate: false,
        is_tender: false,
        direct_request: false,
        trading_org_request: false,
        equipment_description: "",
        distribution_comment: null,
        completed_at: null,
        completed_by: null,
      },
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [],
      logisticsAssignees: [],
      customsAssignees: [],
      pickupLocations: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataEmpty}
        userRoles={["sales"]}
      />,
    );

    expect(
      screen.getByTestId("context-panel-sales-checklist"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-distribution-comment-edit"),
    ).toHaveTextContent("Добавить");
  });

  it("still hides the block entirely for read-only roles with no content (no edit affordance to surface)", () => {
    const dataEmpty: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [],
      logisticsAssignees: [],
      customsAssignees: [],
      pickupLocations: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataEmpty}
        userRoles={["procurement"]}
      />,
    );

    expect(
      screen.queryByTestId("context-panel-sales-checklist"),
    ).not.toBeInTheDocument();
  });
});
