// @vitest-environment jsdom
/**
 * CalcStepInfoCard — DOM rendering tests.
 *
 * Testing 2 rows 36 + 48: the calc-step info card surfaces per-invoice
 * logistics cost, customs duties + ТН ВЭД, and certifications above the
 * items table. The card is purely informational — its warning state
 * MUST NOT block the calc button.
 *
 * Test contract:
 *   1. Renders three sections (logistics, customs, certifications)
 *   2. Logistics is grouped per invoice with per-SEGMENT rows beneath
 *      (Row 48a): each segment shows [label] [cost] [transit_days дн].
 *      The "дн" chip hides when transit_days is null.
 *   3. Warning badge + non-blocking amber hint appear for unfilled invoices
 *   4. Customs row shows ТН ВЭД + duty %
 *   5. Certifications row shows type + cost + currency
 *
 * Network is stubbed via vi.fn() on global fetch — no real Supabase or
 * Python API is touched.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { CalcStepInfoCard } from "../calc-step-info-card";

// Shim createClient — the component only uses it for the JWT bearer token;
// when no session is returned the fetch still fires (without Authorization
// header). That's fine for the test path.
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: null } }),
    },
  }),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

interface MockShape {
  logistics_per_invoice?: Array<{
    invoice_id: string;
    invoice_number: string;
    segment_count: number;
    is_filled: boolean;
    missing_rates: string[];
    segments: Array<{
      segment_id: string;
      invoice_id: string;
      label: string;
      cost: number;
      currency: string;
      transit_days: number | null;
      missing_rate: boolean;
    }>;
  }>;
  customs?: Array<{
    item_id: string;
    brand: string | null;
    product_name: string | null;
    hs_code: string | null;
    customs_duty: number | null;
  }>;
  certifications?: Array<{
    id: string;
    type: string | null;
    display_name: string | null;
    cost: number;
    currency: string;
  }>;
}

function mockFetchOk(data: MockShape): void {
  globalThis.fetch = vi.fn(async () =>
    new Response(JSON.stringify({ success: true, data }), { status: 200 }),
  ) as unknown as typeof fetch;
}

describe("CalcStepInfoCard — happy path renders three sections", () => {
  beforeEach(() => {
    mockFetchOk({
      logistics_per_invoice: [
        {
          invoice_id: "inv-1",
          invoice_number: "INV-001",
          segment_count: 2,
          is_filled: true,
          missing_rates: [],
          segments: [
            {
              segment_id: "seg-1",
              invoice_id: "inv-1",
              label: "Китай · Шанхай → Россия · Москва",
              cost: 12000,
              currency: "RUB",
              transit_days: 14,
              missing_rate: false,
            },
            {
              segment_id: "seg-2",
              invoice_id: "inv-1",
              label: "Доставка по РФ",
              cost: 3500,
              currency: "RUB",
              transit_days: null,
              missing_rate: false,
            },
          ],
        },
        {
          invoice_id: "inv-2",
          invoice_number: "INV-002",
          segment_count: 0,
          is_filled: false,
          missing_rates: [],
          segments: [],
        },
      ],
      customs: [
        {
          item_id: "qi-1",
          brand: "Brand A",
          product_name: "Pump",
          hs_code: "8413701000",
          customs_duty: 5.0,
        },
      ],
      certifications: [
        {
          id: "cert-1",
          type: "ds",
          display_name: "ДС",
          cost: 8000,
          currency: "RUB",
        },
      ],
    });
  });

  it("renders all three section headings", async () => {
    render(<CalcStepInfoCard quoteId="q-1" />);

    expect(
      await screen.findByText("Логистика по инвойсам"),
    ).toBeInTheDocument();
    expect(screen.getByText("Пошлины и ТН ВЭД")).toBeInTheDocument();
    expect(screen.getByText("Сертификация")).toBeInTheDocument();
  });

  it("groups segment rows beneath the invoice with cost + days chip", async () => {
    render(<CalcStepInfoCard quoteId="q-1" />);

    await screen.findByText("Логистика по инвойсам");
    // Invoice sub-header present
    expect(screen.getByText("INV-001")).toBeInTheDocument();

    // Segment 1: label + cost (12 000 ₽) + "14 дн" chip
    const seg1 = screen.getByTestId("calc-step-info-logistics-segment-seg-1");
    expect(seg1.textContent).toContain("Китай · Шанхай → Россия · Москва");
    expect(seg1.textContent).toMatch(/12.000.*₽/);
    expect(seg1.textContent).toMatch(/14\s*дн/);

    // Segment 2: free-text label + cost; NO days chip (transit_days null)
    const seg2 = screen.getByTestId("calc-step-info-logistics-segment-seg-2");
    expect(seg2.textContent).toContain("Доставка по РФ");
    expect(seg2.textContent).toMatch(/3.500.*₽/);
    expect(seg2.textContent).not.toMatch(/дн/);

    // Supplier name is hidden — no supplier label leaks into the section.
    const section = screen.getByTestId("calc-step-info-logistics");
    expect(section.textContent).not.toMatch(/sup-1|поставщик/i);
  });

  it("renders a dash for a segment whose FX rate is missing", async () => {
    mockFetchOk({
      logistics_per_invoice: [
        {
          invoice_id: "inv-x",
          invoice_number: "INV-X",
          segment_count: 1,
          is_filled: false,
          missing_rates: ["CNY"],
          segments: [
            {
              segment_id: "seg-x",
              invoice_id: "inv-x",
              label: "Авто",
              cost: 0,
              currency: "EUR",
              transit_days: null,
              missing_rate: true,
            },
          ],
        },
      ],
      customs: [],
      certifications: [],
    });

    render(<CalcStepInfoCard quoteId="q-x" />);

    await screen.findByText("Логистика по инвойсам");
    const seg = screen.getByTestId("calc-step-info-logistics-segment-seg-x");
    expect(seg.textContent).toContain("Авто");
    expect(seg.textContent).toContain("—");
  });

  it("renders warning badge for unfilled invoice with helper text", async () => {
    render(<CalcStepInfoCard quoteId="q-1" logisticsHref="/quotes/q-1?step=logistics" />);

    await screen.findByText("Логистика по инвойсам");
    // Warning badge present on the unfilled row
    expect(
      screen.getByTestId("calc-step-info-logistics-warning-inv-2"),
    ).toBeInTheDocument();
    // Helper text mentions logistics step
    const unfilledRow = screen.getByTestId(
      "calc-step-info-logistics-row-inv-2",
    );
    expect(unfilledRow.textContent).toMatch(
      /Стоимость логистики не указана/,
    );
    // Hint that calc is NOT blocked
    expect(
      screen.getByTestId("calc-step-info-logistics-hint").textContent,
    ).toMatch(/Расчёт можно запустить/);
  });

  it("renders customs row with ТН ВЭД + duty %", async () => {
    render(<CalcStepInfoCard quoteId="q-1" />);

    await screen.findByText("Пошлины и ТН ВЭД");
    const row = screen.getByTestId("calc-step-info-customs-row-qi-1");
    // Brand + product name
    expect(row.textContent).toContain("Brand A");
    expect(row.textContent).toContain("Pump");
    // hs_code
    expect(row.textContent).toContain("8413701000");
    // Duty %
    expect(row.textContent).toContain("5%");
  });

  it("renders certificate with cost + currency", async () => {
    render(<CalcStepInfoCard quoteId="q-1" />);

    await screen.findByText("Сертификация");
    const row = screen.getByTestId("calc-step-info-cert-row-cert-1");
    expect(row.textContent).toContain("ДС");
    expect(row.textContent).toMatch(/8.000.*₽/);
  });
});

describe("CalcStepInfoCard — empty states", () => {
  it("renders empty messages when sections are empty", async () => {
    mockFetchOk({
      logistics_per_invoice: [],
      customs: [],
      certifications: [],
    });

    render(<CalcStepInfoCard quoteId="q-empty" />);

    expect(
      await screen.findByText("Нет инвойсов в этом КП."),
    ).toBeInTheDocument();
    expect(screen.getByText("Нет позиций в КП.")).toBeInTheDocument();
    expect(
      screen.getByText("Сертификаты не добавлены."),
    ).toBeInTheDocument();
  });
});

describe("CalcStepInfoCard — error states", () => {
  it("renders error message when the API returns non-success", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(
        JSON.stringify({
          success: false,
          error: { code: "NOT_FOUND", message: "Quote not found" },
        }),
        { status: 404 },
      ),
    ) as unknown as typeof fetch;

    render(<CalcStepInfoCard quoteId="q-missing" />);

    await waitFor(() => {
      expect(
        screen.getByTestId("calc-step-info-card-error"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("calc-step-info-card-error").textContent,
    ).toContain("Quote not found");
  });

  it("renders error message when fetch throws", async () => {
    globalThis.fetch = vi.fn(async () => {
      throw new Error("network down");
    }) as unknown as typeof fetch;

    render(<CalcStepInfoCard quoteId="q-1" />);

    await waitFor(() => {
      expect(
        screen.getByTestId("calc-step-info-card-error"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByTestId("calc-step-info-card-error").textContent,
    ).toContain("network down");
  });
});
