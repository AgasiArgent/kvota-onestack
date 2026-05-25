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
  procurementAssignees: [],
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
    procurementAssignees: [],
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

  it('falls back to "Нет участников" only when МОП, МОЗ, МОЛ, МОТ and transitions are all empty', () => {
    const empty: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [],
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
      procurementAssignees: [],
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

// ---------------------------------------------------------------------------
// Testing 2 row 1 (FB-260513-100622-47b6) — contact ФИО + address full text
// ---------------------------------------------------------------------------

describe("ContextPanel — contact full name in info panel (row 1)", () => {
  it("renders Имя Фамилия Отчество in the readonly contact span", () => {
    const quote = makeQuote({
      contact_person: {
        id: "ct-1",
        name: "Азиз",
        last_name: "Каримов",
        patronymic: "Рустамович",
        phone: "+7 999",
        email: "a@a.ru",
      },
    });

    render(
      <ContextPanel quote={quote} data={data} userRoles={["customs"]} />,
    );

    const readonly = screen.getByTestId("context-panel-contact-readonly");
    expect(readonly).toHaveTextContent("Азиз Каримов Рустамович");
  });

  it("falls back to just first name when last_name / patronymic are null", () => {
    const quote = makeQuote({
      contact_person: {
        id: "ct-1",
        name: "Азиз",
        last_name: null,
        patronymic: null,
        phone: null,
        email: null,
      },
    });

    render(
      <ContextPanel quote={quote} data={data} userRoles={["customs"]} />,
    );

    const readonly = screen.getByTestId("context-panel-contact-readonly");
    expect(readonly).toHaveTextContent("Азиз");
  });
});

// ---------------------------------------------------------------------------
// Testing 2 row 2 (FB-260513-100338-a778) — МОЗ + МОП date + separator
// ---------------------------------------------------------------------------

describe("ContextPanel — МОЗ + МОП date + history separator (row 2)", () => {
  it("renders МОП row with the quote.created_at attach timestamp", () => {
    const dataWithSales: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: {
        id: "u-mop",
        full_name: "Денис Рогачёв",
        phone: null,
        email: null,
      },
      participants: [],
      procurementAssignees: [],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    const quote = makeQuote({
      created_at: "2026-04-15T07:00:00Z",
    });

    render(
      <ContextPanel quote={quote} data={dataWithSales} userRoles={["sales"]} />,
    );

    const row = screen.getByTestId("context-panel-sales-manager");
    expect(row).toHaveTextContent("МОП");
    expect(row).toHaveTextContent("Денис Рогачёв");
    expect(row.textContent).toMatch(/15\.04/);
    expect(row.textContent).toMatch(/10:00/); // UTC+3
  });

  it("renders МОЗ row sourced from procurementAssignees", () => {
    const dataWithMoz: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [
        {
          user_id: "u-moz-1",
          full_name: "Екатерина Хусндинова",
          assigned_at: "2026-04-20T06:00:00Z",
        },
      ],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataWithMoz}
        userRoles={["head_of_procurement"]}
      />,
    );

    const row = screen.getByTestId("context-panel-procurement-assignee");
    expect(row).toHaveTextContent("МОЗ");
    expect(row).toHaveTextContent("Екатерина Хусндинова");
    expect(row.textContent).toMatch(/20\.04/);
  });

  it("renders «История переходов» heading separating active responsibles from log", () => {
    const dataWithTransitions: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: {
        id: "u-mop",
        full_name: "Денис Рогачёв",
        phone: null,
        email: null,
      },
      participants: [
        {
          id: "wt-1",
          actor_id: "u-mop",
          actor_role: "sales",
          actor_name: "Денис Рогачёв",
          from_status: "draft",
          to_status: "pending_procurement",
          created_at: "2026-04-15T09:00:00Z",
        },
      ],
      procurementAssignees: [],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataWithTransitions}
        userRoles={["sales"]}
      />,
    );

    expect(screen.getByText("История переходов")).toBeInTheDocument();
  });

  it("hides the «История переходов» heading when there are no transitions", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={data}
        userRoles={["sales"]}
      />,
    );

    expect(screen.queryByText("История переходов")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Testing 2 row 29 (FB-260514-220805-be23) — МОП «Контрольный список» surface
// ---------------------------------------------------------------------------
//
// МОП fills the checklist when transferring a quote to procurement. The
// payload lands on `kvota.quotes.sales_checklist` (JSONB) and is fetched in
// `fetchQuoteContextData`, but the rendering was orphaned during the April
// 2026 context-panel merge. These tests pin the surface: data present →
// render badges + description; empty payload → block hidden.

describe("ContextPanel — sales checklist visible on every step (Testing 2 row 29)", () => {
  it("renders all active request-type badges and equipment description", () => {
    const dataWithChecklist: QuoteContextData = {
      ...data,
      salesChecklist: {
        is_estimate: true,
        is_tender: true,
        direct_request: true,
        trading_org_request: true,
        equipment_description: "Сервер HP DL380 для серверной клиента в Москве",
        completed_at: "2026-05-14T10:00:00Z",
        completed_by: "user-1",
      },
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataWithChecklist}
        userRoles={["procurement"]}
      />,
    );

    const block = screen.getByTestId("context-panel-sales-checklist");
    expect(block).toBeInTheDocument();
    expect(block).toHaveTextContent("От МОП");
    expect(block).toHaveTextContent("Проценка");
    expect(block).toHaveTextContent("Тендер");
    expect(block).toHaveTextContent("Прямой запрос");
    expect(block).toHaveTextContent("Через торгующих");
    expect(block).toHaveTextContent(
      "Сервер HP DL380 для серверной клиента в Москве",
    );
  });

  it("renders only the selected badges (partial checklist)", () => {
    const dataPartial: QuoteContextData = {
      ...data,
      salesChecklist: {
        is_estimate: false,
        is_tender: true,
        direct_request: false,
        trading_org_request: false,
        equipment_description: "Срочный тендер",
        completed_at: null,
        completed_by: null,
      },
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataPartial}
        userRoles={["procurement"]}
      />,
    );

    const block = screen.getByTestId("context-panel-sales-checklist");
    expect(block).toHaveTextContent("Тендер");
    expect(block).not.toHaveTextContent("Проценка");
    expect(block).not.toHaveTextContent("Прямой запрос");
    expect(block).not.toHaveTextContent("Через торгующих");
    expect(block).toHaveTextContent("Срочный тендер");
  });

  it("hides the block entirely when checklist is null (legacy quote)", () => {
    render(
      <ContextPanel
        quote={makeQuote()}
        data={data}
        userRoles={["procurement"]}
      />,
    );

    expect(
      screen.queryByTestId("context-panel-sales-checklist"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("От МОП")).not.toBeInTheDocument();
  });

  it("hides the block when all checklist fields are empty", () => {
    const dataEmpty: QuoteContextData = {
      ...data,
      salesChecklist: {
        is_estimate: false,
        is_tender: false,
        direct_request: false,
        trading_org_request: false,
        equipment_description: "   ",
        completed_at: null,
        completed_by: null,
      },
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

  it("is visible to non-procurement roles too (logistics, customs, admin)", () => {
    const dataWithChecklist: QuoteContextData = {
      ...data,
      salesChecklist: {
        is_estimate: false,
        is_tender: false,
        direct_request: true,
        trading_org_request: false,
        equipment_description: "Описание для всех ролей",
        completed_at: null,
        completed_by: null,
      },
    };

    for (const role of ["logistics", "customs", "admin", "head_of_procurement"]) {
      const { unmount } = render(
        <ContextPanel
          quote={makeQuote()}
          data={dataWithChecklist}
          userRoles={[role]}
        />,
      );
      expect(
        screen.getByTestId("context-panel-sales-checklist"),
      ).toBeInTheDocument();
      unmount();
    }
  });
});

// ---------------------------------------------------------------------------
// Testing 2 row 79 (FB-260525) — «Назначен: DD.MM.YYYY HH:MM» on every
// active responsible row (МОП / МОЗ / МОЛ / МОТ).
// ---------------------------------------------------------------------------
//
// Tester РОЗ + СтМОЗ + МОЗ reported that the Участники inf-panel «не
// указывает дату и время распределения». The data was already on the row
// (`assigned_at`) but was rendered as a bare «DD.MM HH:MM» line with no
// semantic prefix and no year — testers reading the panel could not tell
// what the number meant. Fix: prefix with «Назначен:» and add the year so
// the moment is unambiguous from any pipeline step.

describe("ContextPanel — «Назначен:» label + year on assignee rows (row 79)", () => {
  const PREFIX = "Назначен:";

  it("renders МОЛ row with «Назначен: DD.MM.YYYY HH:MM»", () => {
    const dataMol: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [],
      logisticsAssignees: [
        {
          user_id: "u-mol-1",
          full_name: "Сергей Логистов",
          assigned_at: "2026-04-15T08:30:00Z",
        },
      ],
      customsAssignees: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataMol}
        userRoles={["head_of_logistics"]}
      />,
    );

    const row = screen.getByTestId("context-panel-logistics-assignee");
    expect(row).toHaveTextContent(PREFIX);
    // DD.MM.YYYY HH:MM — Europe/Moscow shifts 08:30 UTC → 11:30 MSK
    expect(row.textContent).toMatch(/Назначен:\s*15\.04\.2026[,\s]+11:30/);
  });

  it("renders МОТ row with «Назначен: DD.MM.YYYY HH:MM»", () => {
    const dataMot: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [],
      logisticsAssignees: [],
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
        data={dataMot}
        userRoles={["head_of_customs"]}
      />,
    );

    const row = screen.getByTestId("context-panel-customs-assignee");
    expect(row).toHaveTextContent(PREFIX);
    expect(row.textContent).toMatch(/Назначен:\s*16\.04\.2026[,\s]+08:00/);
  });

  it("renders МОЗ row with «Назначен: DD.MM.YYYY HH:MM»", () => {
    const dataMoz: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [
        {
          user_id: "u-moz-1",
          full_name: "Екатерина Закупщик",
          assigned_at: "2026-05-20T12:30:24Z",
        },
      ],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataMoz}
        userRoles={["head_of_procurement"]}
      />,
    );

    const row = screen.getByTestId("context-panel-procurement-assignee");
    expect(row).toHaveTextContent(PREFIX);
    expect(row.textContent).toMatch(/Назначен:\s*20\.05\.2026[,\s]+15:30/);
  });

  it("renders МОП row with «Назначен: …» sourced from quote.created_at", () => {
    const dataMop: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: {
        id: "u-mop",
        full_name: "Денис Рогачёв",
        phone: null,
        email: null,
      },
      participants: [],
      procurementAssignees: [],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    const quote = makeQuote({
      created_at: "2026-04-15T07:00:00Z",
    });

    render(
      <ContextPanel quote={quote} data={dataMop} userRoles={["sales"]} />,
    );

    const row = screen.getByTestId("context-panel-sales-manager");
    expect(row).toHaveTextContent(PREFIX);
    expect(row.textContent).toMatch(/Назначен:\s*15\.04\.2026[,\s]+10:00/);
  });

  it("renders each МОЗ user's «Назначен:» line independently on a multi-МОЗ quote", () => {
    const dataMulti: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [
        {
          user_id: "u-moz-a",
          full_name: "Закупщик А",
          assigned_at: "2026-05-20T12:30:00Z",
        },
        {
          user_id: "u-moz-b",
          full_name: "Закупщик Б",
          assigned_at: "2026-05-21T09:15:00Z",
        },
      ],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataMulti}
        userRoles={["head_of_procurement"]}
      />,
    );

    const rows = screen.getAllByTestId("context-panel-procurement-assignee");
    expect(rows).toHaveLength(2);
    // Each row carries its own «Назначен: …» line independently.
    expect(rows[0].textContent).toMatch(/Назначен:\s*20\.05\.2026[,\s]+15:30/);
    expect(rows[1].textContent).toMatch(/Назначен:\s*21\.05\.2026[,\s]+12:15/);
  });

  it("does not crash and shows ФИО without «Назначен:» line when assigned_at is null", () => {
    // Edge case from the task spec: legacy quotes that pre-date kanban
    // auto-advance and have no workflow_transitions row for the МОЗ leave
    // `assigned_at` as null. The row must still render ФИО — never crash —
    // and the date line is hidden (the task allows either hiding or a dash;
    // hiding keeps the panel compact, see the row 2 follow-up tests above).
    const dataNull: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [
        {
          user_id: "u-moz-legacy",
          full_name: "Старый Закупщик",
          assigned_at: null,
        },
      ],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataNull}
        userRoles={["head_of_procurement"]}
      />,
    );

    const row = screen.getByTestId("context-panel-procurement-assignee");
    expect(row).toHaveTextContent("Старый Закупщик");
    // No «Назначен:» when assigned_at is null — line is hidden, not stubbed.
    expect(row.textContent).not.toContain(PREFIX);
  });

  it("keeps the compact «DD.MM HH:MM» format (no year) in «История переходов» list", () => {
    // The history log lives in a constrained-width collapsed <details> with
    // an actor badge that already scopes the moment, so we intentionally
    // keep it on the compact format. This pins that we DON'T accidentally
    // surface the year in the history rows (which would push the badge off
    // the line on narrow viewports).
    const dataHistory: QuoteContextData = {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [
        {
          id: "wt-1",
          actor_id: "u-actor",
          actor_role: "sales",
          actor_name: "Денис Рогачёв",
          from_status: "draft",
          to_status: "pending_procurement",
          created_at: "2026-04-15T09:00:00Z",
        },
      ],
      procurementAssignees: [],
      logisticsAssignees: [],
      customsAssignees: [],
    };

    render(
      <ContextPanel
        quote={makeQuote()}
        data={dataHistory}
        userRoles={["sales"]}
      />,
    );

    const history = screen.getByTestId("context-panel-history");
    // Compact format: DD.MM HH:MM — no year, no «Назначен:» prefix.
    expect(history.textContent).toMatch(/15\.04\b/);
    expect(history.textContent).not.toMatch(/15\.04\.2026/);
    expect(history.textContent).not.toContain(PREFIX);
  });
});
