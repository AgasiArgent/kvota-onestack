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
  logisticsAssignees: [],
  customsAssignees: [],
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

  // РОЛ Тест 07 — 3.9 + 4.2: Контакт inf-panel must be read-only on
  // logistics / customs steps regardless of which logistics-tier or
  // customs-tier role the viewer holds. The МОЗ-58 fix wired this through
  // canEditQuoteCustomerFields; these tests pin the four roles that the
  // тестировщик exercises so a future widening of the gate doesn't silently
  // re-introduce the dropdown for them.
  it.each([
    ["head_of_logistics"],
    ["customs"],
    ["head_of_customs"],
  ])("renders read-only Контакт for %s (no editable dropdown)", (role) => {
    render(
      <ContextPanel quote={makeQuote()} data={data} userRoles={[role]} />,
    );

    expect(
      screen.queryByTestId("context-panel-contact-editable"),
    ).not.toBeInTheDocument();
    const readonly = screen.getByTestId("context-panel-contact-readonly");
    expect(readonly).toHaveTextContent("Иван Иванов");
  });
});

// ---------------------------------------------------------------------------
// РОЛ Тест 07 — 3.1 + 4.1: МОЛ / МОТ in Участники inf-panel
// ---------------------------------------------------------------------------

describe("ContextPanel — МОЛ / МОТ assignees in Участники", () => {
  const baseData: QuoteContextData = {
    salesChecklist: null,
    contactPerson: null,
    salesManager: { id: "u-mop", full_name: "Иван Продажин", phone: null, email: null },
    participants: [],
    logisticsAssignees: [],
    customsAssignees: [],
  };

  it("renders МОЛ row with full name + attach timestamp (3.1)", () => {
    const dataWithLogistics: QuoteContextData = {
      ...baseData,
      logisticsAssignees: [
        {
          user_id: "u-mol-1",
          full_name: "Сергей Логистов",
          assigned_at: "2026-04-15T08:30:00Z",
        },
      ],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataWithLogistics}
        userRoles={["head_of_logistics"]}
      />,
    );

    const row = screen.getByTestId("context-panel-logistics-assignee");
    expect(row).toHaveTextContent("МОЛ");
    expect(row).toHaveTextContent("Сергей Логистов");
    // Timestamp formatted day/month + time, Europe/Moscow → 11:30 (UTC+3)
    expect(row.textContent).toMatch(/15\.04/);
    expect(row.textContent).toMatch(/11:30/);
  });

  it("renders МОТ row with full name + attach timestamp (4.1)", () => {
    const dataWithCustoms: QuoteContextData = {
      ...baseData,
      customsAssignees: [
        {
          user_id: "u-mot-1",
          full_name: "Анна Таможникова",
          assigned_at: "2026-04-16T05:00:00Z",
        },
      ],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataWithCustoms}
        userRoles={["head_of_customs"]}
      />,
    );

    const row = screen.getByTestId("context-panel-customs-assignee");
    expect(row).toHaveTextContent("МОТ");
    expect(row).toHaveTextContent("Анна Таможникова");
    expect(row.textContent).toMatch(/16\.04/);
    expect(row.textContent).toMatch(/08:00/); // UTC+3
  });

  it("renders multiple distinct МОЛ users on a multi-invoice quote", () => {
    const dataMulti: QuoteContextData = {
      ...baseData,
      logisticsAssignees: [
        {
          user_id: "u-mol-1",
          full_name: "Сергей Логистов",
          assigned_at: "2026-04-15T08:00:00Z",
        },
        {
          user_id: "u-mol-2",
          full_name: "Мария Логистова",
          assigned_at: "2026-04-16T08:00:00Z",
        },
      ],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataMulti}
        userRoles={["head_of_logistics"]}
      />,
    );

    const rows = screen.getAllByTestId("context-panel-logistics-assignee");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Сергей Логистов");
    expect(rows[1]).toHaveTextContent("Мария Логистова");
  });

  it("omits the timestamp line when assigned_at is null but still shows ФИО", () => {
    const dataNoStamp: QuoteContextData = {
      ...baseData,
      logisticsAssignees: [
        {
          user_id: "u-mol-1",
          full_name: "Сергей Логистов",
          assigned_at: null,
        },
      ],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataNoStamp}
        userRoles={["head_of_logistics"]}
      />,
    );

    const row = screen.getByTestId("context-panel-logistics-assignee");
    expect(row).toHaveTextContent("Сергей Логистов");
    // No date placeholders — the assignee row stays compact.
    expect(row.textContent).not.toMatch(/\d{2}\.\d{2}/);
  });

  it('falls back to "Нет участников" only when МОП, МОЛ, МОТ and transitions are all empty', () => {
    const empty: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    render(
      <ContextPanel quote={makeQuote()} data={empty} userRoles={["sales"]} />,
    );

    expect(screen.getByText("Нет участников")).toBeInTheDocument();
  });

  it('does not render "Нет участников" when only МОЛ is present', () => {
    const dataOnlyMol: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      logisticsAssignees: [
        {
          user_id: "u-mol-1",
          full_name: "Сергей Логистов",
          assigned_at: "2026-04-15T08:00:00Z",
        },
      ],
      customsAssignees: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataOnlyMol}
        userRoles={["head_of_logistics"]}
      />,
    );

    expect(screen.queryByText("Нет участников")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("context-panel-logistics-assignee"),
    ).toBeInTheDocument();
  });
});
