// @vitest-environment jsdom
/**
 * control-spec-workspace PR2 — «На контроле» phase, 4 blocks.
 *
 * Verifies the spec-control screen renders the four blocks (Из расчёта,
 * Реквизиты, Условия спецификации, Контроль), that the requisite dropdowns
 * appear for an editing role, and that a non-editing role gets read-only
 * displays instead of inputs/comboboxes.
 *
 * The component fetches on mount (loadData) so every async dependency is
 * stubbed to resolve immediately; assertions wait via findBy* until the
 * loading spinner clears.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

// --- mocks ---------------------------------------------------------------

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("./mutations", () => ({
  confirmSignatureAndCreateDeal: vi.fn(),
}));

vi.mock("@/entities/quote", () => ({
  fetchSellerCompanies: vi.fn().mockResolvedValue([
    { id: "sc-1", name: "ООО Ромашка" },
    { id: "sc-2", name: "ООО Лютик" },
  ]),
}));

// Supabase client stub: a thin chainable builder. Terminal awaits resolve to
// the table-specific payload; intermediate chain links return `this`.
const LOCATIONS = [{ country: "Китай" }, { country: "Германия" }, { country: "Китай" }];

vi.mock("@/shared/lib/supabase/client", () => {
  function makeBuilder(table: string) {
    const builder: Record<string, unknown> = {};
    const chain = () => builder;
    builder.select = chain;
    builder.eq = chain;
    builder.is = chain;
    builder.order = chain;
    builder.limit = chain;
    builder.maybeSingle = () => Promise.resolve({ data: null, error: null });
    // `locations` query is awaited directly after `.eq(...)`; make the builder
    // thenable so `await supabase.from("locations").select().eq()` resolves.
    builder.then = (
      resolve: (v: { data: unknown; error: null }) => unknown,
    ) => {
      const data = table === "locations" ? LOCATIONS : [];
      return Promise.resolve({ data, error: null }).then(resolve);
    };
    return builder;
  }
  return {
    createClient: () => ({
      from: (table: string) => makeBuilder(table),
    }),
  };
});

import { SpecificationStep } from "./specification-step";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function makeQuote(): QuoteDetailRow {
  return {
    id: "q-1",
    idn_quote: "Q-202605-0001",
    organization_id: "org-1",
    customer_id: "cust-1",
    currency: "USD",
    total_quote_currency: 12345.67,
    total_with_vat_quote: 14814.8,
    total_profit_usd: 2000,
    exchange_rate_to_usd: 1,
    customer: { id: "cust-1", name: "Клиент Тест", inn: "7700000000" },
  } as unknown as QuoteDetailRow;
}

const ITEMS: QuoteItemRow[] = [];

function renderStep(roles: string[]) {
  return render(
    <SpecificationStep
      quote={makeQuote()}
      items={ITEMS}
      userRoles={roles}
      userId="user-1"
    />,
  );
}

describe("SpecificationStep — «На контроле» 4 blocks (PR2)", () => {
  it("renders all four block headings for an editing role", async () => {
    renderStep(["spec_controller"]);

    expect(await screen.findByText("Из расчёта")).toBeInTheDocument();
    expect(screen.getByText("Реквизиты")).toBeInTheDocument();
    expect(screen.getByText("Условия спецификации")).toBeInTheDocument();
    expect(screen.getByText("Контроль")).toBeInTheDocument();
  });

  it("shows calc figures formatted in the quote currency", async () => {
    renderStep(["spec_controller"]);

    // 12 345,67 $ (ru-RU grouping, USD symbol)
    expect(await screen.findByText(/12\s?345,67\s?\$/)).toBeInTheDocument();
  });

  it("renders the requisite dropdowns (searchable comboboxes) for an editing role", async () => {
    renderStep(["spec_controller"]);

    // SearchableCombobox triggers expose their placeholder text until selected.
    expect(await screen.findByText("Выберите юрлицо")).toBeInTheDocument();
    // Three country pickers all share the same placeholder.
    expect(screen.getAllByText("Выберите страну")).toHaveLength(3);
  });

  it("renders editable condition inputs for an editing role", async () => {
    renderStep(["spec_controller"]);

    expect(await screen.findByText("Условия спецификации")).toBeInTheDocument();
    // Срок действия text input is present (editable mode).
    expect(screen.getByPlaceholderText("30 дней")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Оборудование")).toBeInTheDocument();
  });

  it("hides inputs and shows read-only displays for a non-editing role", async () => {
    renderStep(["top_manager"]);

    // Blocks still render…
    expect(await screen.findByText("Реквизиты")).toBeInTheDocument();
    expect(screen.getByText("Условия спецификации")).toBeInTheDocument();

    // …but no editable affordances: no combobox placeholders, no condition inputs.
    expect(screen.queryByText("Выберите юрлицо")).not.toBeInTheDocument();
    expect(screen.queryByText("Выберите страну")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("30 дней")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Оборудование")).not.toBeInTheDocument();
  });

  it("shows the at-signing FX mode selector defaulting to cbr in the Контроль block", async () => {
    const { container } = renderStep(["spec_controller"]);

    // Контроль block heading + FX-mode selector label render.
    expect(await screen.findByText("Контроль")).toBeInTheDocument();
    expect(screen.getByText("Курс на подписании")).toBeInTheDocument();

    // Base UI Select keeps a hidden <input> for form integration; its value
    // reflects the default mode (cbr_on_payment_day) without opening the
    // portal-mounted listbox.
    const hiddenInput = container.querySelector(
      'input[value="cbr_on_payment_day"]',
    );
    expect(hiddenInput).not.toBeNull();
  });
});
