// @vitest-environment jsdom
/**
 * МОЗ-58 / Track A 2026-05-07 — only sales-tier roles (admin / sales /
 * head_of_sales) may edit Контакт and Адрес доставки on a quote. All other
 * roles see plain read-only spans (no popover button, no dropdown).
 *
 * The mutation guard in `entities/quote/mutations.ts::patchQuote` is
 * defense-in-depth; the BEFORE UPDATE trigger on kvota.quotes (migration
 * 308) is the canonical enforcement layer. This test pins the UI gate.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import type { QuoteDetailRow } from "@/entities/quote/queries";
import type { QuoteContextData } from "../queries";

// ---------------------------------------------------------------------------
// Mocks (must come before component import — vitest hoists vi.mock)
// ---------------------------------------------------------------------------

// Heavy children whose internals would pull supabase / next routing into the
// jsdom render path. Replace with simple sentinels so we can assert on
// presence/absence of the editable affordance.
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

import { ContextPanel } from "../context-panel";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeQuote(overrides: Partial<QuoteDetailRow> = {}): QuoteDetailRow {
  return {
    id: "q-1",
    customer_id: "c-1",
    contact_person_id: "ct-1",
    delivery_address: "Москва, ул. Тверская, 1",
    delivery_city: "Москва",
    delivery_method: "auto",
    delivery_priority: "normal",
    payment_terms: "Postpaid",
    valid_until: null,
    currency: "USD",
    incoterms: "DAP",
    profit_quote_currency: 1234,
    revenue_no_vat_quote_currency: 10000,
    cogs_quote_currency: 8000,
    customer: { id: "c-1", name: "ACME", inn: null },
    contact_person: {
      id: "ct-1",
      name: "Иван Иванов",
      phone: "+7 999",
      email: "i@a.ru",
    },
    seller_company: null,
    created_by_profile: null,
    ...overrides,
  } as unknown as QuoteDetailRow;
}

const data: QuoteContextData = {
  salesChecklist: null,
  contactPerson: null,
  salesManager: null,
  participants: [],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ContextPanel — customer-field editability gating (МОЗ-58)", () => {
  it("renders editable Контакт + Адрес dropdowns for sales", () => {
    render(<ContextPanel quote={makeQuote()} data={data} userRoles={["sales"]} />);

    expect(
      screen.getByTestId("context-panel-contact-editable"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-address-editable"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("context-panel-contact-readonly"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("context-panel-address-readonly"),
    ).not.toBeInTheDocument();
  });

  it("renders editable affordance for head_of_sales", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={data}
        userRoles={["head_of_sales"]}
      />,
    );

    expect(
      screen.getByTestId("context-panel-contact-editable"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-address-editable"),
    ).toBeInTheDocument();
  });

  it("renders editable affordance for admin", () => {
    render(<ContextPanel quote={makeQuote()} data={data} userRoles={["admin"]} />);

    expect(
      screen.getByTestId("context-panel-contact-editable"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-address-editable"),
    ).toBeInTheDocument();
  });

  it("renders read-only spans for procurement (no editable button)", () => {
    render(
      <ContextPanel quote={makeQuote()} data={data} userRoles={["procurement"]} />,
    );

    expect(
      screen.queryByTestId("context-panel-contact-editable"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("context-panel-address-editable"),
    ).not.toBeInTheDocument();

    const contactReadonly = screen.getByTestId(
      "context-panel-contact-readonly",
    );
    expect(contactReadonly).toBeInTheDocument();
    expect(contactReadonly).toHaveTextContent("Иван Иванов");

    const addressReadonly = screen.getByTestId(
      "context-panel-address-readonly",
    );
    expect(addressReadonly).toBeInTheDocument();
    expect(addressReadonly).toHaveTextContent("Москва, ул. Тверская, 1");
  });

  it("renders read-only spans for procurement_senior", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={data}
        userRoles={["procurement_senior"]}
      />,
    );

    expect(
      screen.queryByTestId("context-panel-contact-editable"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("context-panel-address-editable"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-contact-readonly"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-address-readonly"),
    ).toBeInTheDocument();
  });

  it("renders read-only spans for logistics", () => {
    render(
      <ContextPanel quote={makeQuote()} data={data} userRoles={["logistics"]} />,
    );

    expect(
      screen.queryByTestId("context-panel-contact-editable"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("context-panel-address-editable"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-contact-readonly"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-address-readonly"),
    ).toBeInTheDocument();
  });

  it("renders an em-dash placeholder when contact / address are null and user is read-only", () => {
    render(
      <ContextPanel
        quote={makeQuote({ contact_person: null, delivery_address: null })}
        data={data}
        userRoles={["procurement"]}
      />,
    );

    const contactReadonly = screen.getByTestId(
      "context-panel-contact-readonly",
    );
    expect(contactReadonly).toHaveTextContent("—");
    const addressReadonly = screen.getByTestId(
      "context-panel-address-readonly",
    );
    expect(addressReadonly).toHaveTextContent("—");
  });
});
