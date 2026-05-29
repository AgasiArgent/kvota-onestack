// @vitest-environment jsdom
/**
 * Calc-step seller_company wiring (Testing 2 row 48b).
 *
 * Contract (CalculationStep):
 *   - On mount it loads the org's seller companies via fetchSellerCompanies.
 *   - Picking a company persists it via updateQuoteSellerCompany WITHOUT
 *     triggering a recalculation, and raises the «Изменён продавец» banner.
 *   - The banner is cleared once a calculation succeeds (onApplied from the
 *     action bar).
 *
 * The recalc itself is owned by the backend, which resolves the seller name
 * from quotes.seller_company_id (PR #274); we only verify the FE persists the
 * id and never calls /calculate as a side effect of the picker.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

const fetchSellerCompaniesMock = vi.fn();
const updateQuoteSellerCompanyMock = vi.fn();
vi.mock("@/entities/quote/mutations", () => ({
  fetchSellerCompanies: (...args: unknown[]) =>
    fetchSellerCompaniesMock(...args),
  updateQuoteSellerCompany: (...args: unknown[]) =>
    updateQuoteSellerCompanyMock(...args),
}));

const refreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

// The async coverage/calc-count loader in CalculationStep — return empty so
// it settles without touching real data.
const supabaseStub = {
  auth: {
    getSession: async () => ({
      data: { session: { access_token: "fake-token" } },
    }),
  },
  from: () => ({
    select: () => ({
      in: () => Promise.resolve({ data: [], error: null, count: 0 }),
    }),
  }),
};
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => supabaseStub,
}));

// Heavy children not under test — stub to keep the DOM small.
vi.mock("../composition-picker", () => ({
  CompositionPicker: () => null,
}));
vi.mock("../calc-step-info-card", () => ({
  CalcStepInfoCard: () => null,
}));
vi.mock("../calculation-results", () => ({
  CalculationResults: () => null,
}));
vi.mock("@/shared/ui/app-toaster", () => ({
  AppToaster: () => null,
}));

import { CalculationStep } from "../calculation-step";
import { toast } from "sonner";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";

const quote = {
  id: "q-1",
  organization_id: "org-1",
  seller_company_id: null,
  currency: "USD",
  workflow_status: "draft",
  total_quote_currency: null,
} as unknown as QuoteDetailRow;

const items: QuoteItemRow[] = [];

const originalFetch = global.fetch;

beforeEach(() => {
  fetchSellerCompaniesMock.mockReset();
  fetchSellerCompaniesMock.mockResolvedValue([
    { id: "sc-1", name: "ООО Альфа" },
    { id: "sc-2", name: "ООО Бета" },
  ]);
  updateQuoteSellerCompanyMock.mockReset();
  updateQuoteSellerCompanyMock.mockResolvedValue(undefined);
  refreshMock.mockReset();
});

afterEach(() => {
  cleanup();
  global.fetch = originalFetch;
});

function mockCalculateOk(): void {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ success: true }),
  }) as unknown as typeof fetch;
}

/**
 * base-ui Select commits when the highlighted option receives
 * click→pointerdown→pointerup→click (a bare click only highlights it).
 */
function selectSellerOption(optionText: string) {
  fireEvent.click(screen.getByLabelText("Наше юрлицо"));
  const option = screen
    .getAllByRole("option")
    .find((el) => el.textContent === optionText);
  if (!option) throw new Error(`option not found: ${optionText}`);
  fireEvent.click(option);
  fireEvent.pointerDown(option);
  fireEvent.pointerUp(option);
  fireEvent.click(option);
}

async function renderStep() {
  render(
    <CalculationStep
      quote={quote}
      items={items}
      userRoles={["sales"]}
      savedVariables={null}
    />,
  );
  // Wait for the seller companies to load and the picker to mount.
  await screen.findByText("Наше юрлицо");
}

describe("CalculationStep — seller_company persist + banner (row 48b)", () => {
  it("loads seller companies for the quote's organization on mount", async () => {
    await renderStep();
    expect(fetchSellerCompaniesMock).toHaveBeenCalledWith("org-1");
  });

  it("persists the chosen company and shows the recalc banner — without calling /calculate", async () => {
    const fetchSpy = vi.fn();
    global.fetch = fetchSpy as unknown as typeof fetch;

    await renderStep();

    selectSellerOption("ООО Альфа");

    // Persisted via the focused mutation, not via a recalc.
    await waitFor(() =>
      expect(updateQuoteSellerCompanyMock).toHaveBeenCalledWith("q-1", "sc-1"),
    );

    // Banner appears prompting the user to recalc.
    expect(
      screen.getByText(
        "Изменён продавец — нажмите Пересчитать чтобы применить новую ставку НДС",
      ),
    ).toBeInTheDocument();

    // The picker must NOT auto-trigger a calculation.
    const calculateCalled = fetchSpy.mock.calls.some(([url]) =>
      String(url).includes("/calculate"),
    );
    expect(calculateCalled).toBe(false);
  });

  it("clears the banner after a successful recalculation", async () => {
    mockCalculateOk();
    await renderStep();

    selectSellerOption("ООО Бета");

    await screen.findByText(
      "Изменён продавец — нажмите Пересчитать чтобы применить новую ставку НДС",
    );

    // Click «Рассчитать» — on success onApplied clears the banner.
    fireEvent.click(screen.getByRole("button", { name: /Рассчитать/ }));

    await waitFor(() =>
      expect(
        screen.queryByText(
          "Изменён продавец — нажмите Пересчитать чтобы применить новую ставку НДС",
        ),
      ).toBeNull(),
    );
  });

  it("rolls back the selection and banner when the persist fails", async () => {
    vi.mocked(toast.error).mockClear();
    updateQuoteSellerCompanyMock.mockRejectedValueOnce(new Error("persist failed"));
    await renderStep();

    selectSellerOption("ООО Альфа");

    await waitFor(() =>
      expect(updateQuoteSellerCompanyMock).toHaveBeenCalledWith("q-1", "sc-1"),
    );

    // Persist failed: the error is surfaced and the recalc banner is rolled
    // back — the picker must never be left showing a seller that a later
    // Пересчитать won't apply (it would resolve the unchanged persisted id).
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Не удалось сохранить юрлицо"),
    );
    expect(
      screen.queryByText(
        "Изменён продавец — нажмите Пересчитать чтобы применить новую ставку НДС",
      ),
    ).toBeNull();
  });
});
