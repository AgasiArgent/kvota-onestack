// @vitest-environment jsdom
/**
 * control-spec-workspace PR3 — two-phase «На контроле» → «На подписании».
 *
 * Covers task 3.4:
 *  - «Отправить на подписание» is blocked (and names the gaps) when the
 *    required requisites (договор / наше юрлицо) are missing.
 *  - In the `pending_signature` phase the 4 requisite blocks are read-only.
 *  - The ReconciliationStrip gates «Пометить подписанной»: disabled until the
 *    scan is present AND every manual reconciliation row is confirmed.
 *
 * The component fetches on mount; the supabase client is stubbed to return a
 * spec row so the signing-phase UI renders. `sendSpecToSignature` and
 * `confirmSignatureAndCreateDeal` are mocked to observe calls.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

// --- mocks ---------------------------------------------------------------

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const sendSpecToSignature = vi.fn().mockResolvedValue(undefined);
vi.mock("@/entities/quote/mutations", () => ({
  sendSpecToSignature: (id: string) => sendSpecToSignature(id),
}));

const confirmSignatureAndCreateDeal = vi.fn().mockResolvedValue({
  deal_number: "D-1",
  invoices_created: 0,
});
vi.mock("./mutations", () => ({
  confirmSignatureAndCreateDeal: (id: string) =>
    confirmSignatureAndCreateDeal(id),
}));

vi.mock("@/entities/quote", () => ({
  fetchSellerCompanies: vi.fn().mockResolvedValue([]),
}));

// Spec row returned by the `specifications` query. Mutated per test before
// render to flip scan presence / requisite fill.
let specRow: Record<string, unknown> | null = null;

vi.mock("@/shared/lib/supabase/client", () => {
  function makeBuilder(table: string) {
    const builder: Record<string, unknown> = {};
    const chain = () => builder;
    builder.select = chain;
    builder.insert = chain;
    builder.update = chain;
    builder.eq = chain;
    builder.is = chain;
    builder.order = chain;
    builder.limit = chain;
    builder.maybeSingle = () =>
      Promise.resolve({
        data: table === "specifications" ? specRow : null,
        error: null,
      });
    builder.single = () =>
      Promise.resolve({ data: { id: "spec-1" }, error: null });
    builder.then = (resolve: (v: { data: unknown; error: null }) => unknown) =>
      Promise.resolve({ data: [], error: null }).then(resolve);
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
  specRow = null;
});

function makeQuote(workflowStatus: string): QuoteDetailRow {
  return {
    id: "q-1",
    idn_quote: "Q-202605-0001",
    organization_id: "org-1",
    customer_id: "cust-1",
    currency: "USD",
    workflow_status: workflowStatus,
    stage_entered_at: "2026-05-30T10:00:00Z",
    total_quote_currency: 1000,
    total_with_vat_quote: 1200,
    total_profit_usd: 200,
    exchange_rate_to_usd: 1,
    customer: { id: "cust-1", name: "Клиент Тест", inn: "7700000000" },
  } as unknown as QuoteDetailRow;
}

const ITEMS: QuoteItemRow[] = [];

function renderStep(workflowStatus: string, roles: string[] = ["spec_controller"]) {
  return render(
    <SpecificationStep
      quote={makeQuote(workflowStatus)}
      items={ITEMS}
      userRoles={roles}
      userId="user-1"
    />,
  );
}

describe("SpecificationStep — «Отправить на подписание» validation (Req 5)", () => {
  it("blocks the transition and names the missing requisites", async () => {
    const { toast } = await import("sonner");
    // Control phase with an existing spec but no contract / seller.
    specRow = {
      id: "spec-1",
      quote_id: "q-1",
      status: "draft",
      specification_number: "SP-202605-0001",
      contract_id: null,
      seller_company_id: null,
      signed_scan_url: null,
    };

    renderStep("pending_spec_control");

    const sendBtn = await screen.findByRole("button", {
      name: "Отправить на подписание",
    });
    fireEvent.click(sendBtn);

    // Transition must NOT fire, and the toast must name the missing fields.
    expect(sendSpecToSignature).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("Договор"),
    );
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("Наше юрлицо"),
    );
  });
});

describe("SpecificationStep — «На подписании» phase (Req 6–7)", () => {
  it("renders requisite blocks read-only (no editable comboboxes)", async () => {
    specRow = {
      id: "spec-1",
      quote_id: "q-1",
      status: "approved",
      specification_number: "SP-202605-0001",
      contract_id: null,
      seller_company_id: null,
      signed_scan_url: null,
    };

    renderStep("pending_signature");

    // Blocks still render…
    expect(await screen.findByText("Реквизиты")).toBeInTheDocument();
    // …but the requisites are locked: no combobox placeholders, no draft button.
    expect(screen.queryByText("Выберите юрлицо")).not.toBeInTheDocument();
    expect(screen.queryByText("Выберите страну")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Сохранить черновик" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Отправить на подписание" }),
    ).not.toBeInTheDocument();
  });

  it("disables «Пометить подписанной» until scan present AND all rows confirmed", async () => {
    specRow = {
      id: "spec-1",
      quote_id: "q-1",
      status: "approved",
      specification_number: "SP-202605-0001",
      contract_id: null,
      seller_company_id: null,
      signed_scan_url: "https://example.com/scan.pdf",
    };

    renderStep("pending_signature");

    const markBtn = await screen.findByRole("button", {
      name: "Пометить подписанной",
    });
    // Scan present but no manual confirmations yet → disabled.
    expect(markBtn).toBeDisabled();

    // Confirm every manual reconciliation row.
    const rows = screen.getAllByRole("button", { name: /^Подтвердить:/ });
    expect(rows.length).toBe(6);
    rows.forEach((row) => fireEvent.click(row));

    // Now all gates satisfied → enabled.
    expect(markBtn).not.toBeDisabled();
  });

  it("keeps «Пометить подписанной» disabled when scan is missing", async () => {
    specRow = {
      id: "spec-1",
      quote_id: "q-1",
      status: "approved",
      specification_number: "SP-202605-0001",
      contract_id: null,
      seller_company_id: null,
      signed_scan_url: null,
    };

    renderStep("pending_signature");

    const markBtn = await screen.findByRole("button", {
      name: "Пометить подписанной",
    });
    // Confirm all manual rows, but no scan → still disabled.
    const rows = screen.getAllByRole("button", { name: /^Подтвердить:/ });
    rows.forEach((row) => fireEvent.click(row));

    expect(markBtn).toBeDisabled();
  });
});
