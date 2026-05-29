import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5c Task 14 — composition-picker coverage summary tests.
 *
 * Verifies that each alternative in the picker surfaces structural context
 * about how the supplier covers the quote_item:
 *   - 1:1 → no subtext (empty coverage_summary)
 *   - Split (1 qi → N ii) → "→ name ×ratio + ..." subtext
 *   - Merge (N qi → 1 ii) → "← name, ... объединены" subtext
 *   - Divergent markups on a merged alternative → warning icon rendered
 *
 * The component under test is the internal `CompositionItemRow` row
 * renderer, exported so this spec can exercise its output directly with
 * renderToString (same pattern as invoice-card.test.tsx / split-modal.test.tsx).
 * The outer `CompositionPicker` is a thin data-fetching shell around it.
 */

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: () => {},
    push: () => {},
    replace: () => {},
    back: () => {},
    forward: () => {},
    prefetch: () => {},
  }),
}));

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: null } }) },
  }),
}));

import { CompositionItemRow } from "../composition-picker";
import type {
  CompositionAlternative,
  CompositionItem,
} from "@/entities/quote/types";
import { buildHistoricalRateMap } from "@/entities/supplier/lib/historical-fx";

function makeAlt(
  overrides: Partial<CompositionAlternative> = {}
): CompositionAlternative {
  return {
    invoice_id: "inv-1",
    supplier_id: "sup-1",
    supplier_name: "Supplier A",
    supplier_country: "Germany",
    purchase_price_original: 10,
    purchase_currency: "EUR",
    base_price_vat: null,
    price_includes_vat: false,
    production_time_days: null,
    version: 1,
    frozen_at: null,
    coverage_summary: "",
    divergent_markups: false,
    ...overrides,
  };
}

function makeItem(
  alternatives: CompositionAlternative[],
  overrides: Partial<CompositionItem> = {}
): CompositionItem {
  return {
    quote_item_id: "qi-1",
    brand: "ACME",
    sku: "SKU-1",
    name: "Bolt",
    quantity: 100,
    selected_invoice_id: null,
    alternatives,
    ...overrides,
  };
}

/** Wrap the row in <table><tbody> so it's a valid DOM tree for renderToString. */
function renderRow(node: React.ReactElement): string {
  return renderToString(
    <table>
      <tbody>{node}</tbody>
    </table>
  );
}

describe("CompositionItemRow — coverage_summary subtext", () => {
  it("renders no coverage subtext for a 1:1 alternative (empty summary)", () => {
    const alt = makeAlt({
      invoice_id: "inv-a",
      supplier_name: "Supplier 1to1",
      coverage_summary: "",
    });
    const item = makeItem([alt, makeAlt({
      invoice_id: "inv-b",
      supplier_name: "Supplier Other",
      coverage_summary: "",
    })]);

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    // Supplier labels render, but no italic coverage subtext.
    expect(html).toContain("Supplier 1to1");
    expect(html).not.toContain("→ ");
    expect(html).not.toContain("← ");
    expect(html).not.toMatch(/italic[^"]*"[^>]*>[→←]/);
  });

  it("renders split coverage subtext '→ болт ×1 + шайба ×2'", () => {
    const splitAlt = makeAlt({
      invoice_id: "inv-split",
      supplier_name: "Supplier Split",
      coverage_summary: "→ болт ×1 + шайба ×2",
    });
    // Need 2+ alternatives for the picker to render radios
    const item = makeItem([
      splitAlt,
      makeAlt({ invoice_id: "inv-other", supplier_name: "Supplier Other" }),
    ]);

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    expect(html).toContain("→ болт ×1 + шайба ×2");
    expect(html).toContain("italic");
  });

  it("renders merge coverage subtext '← болт, гайка, шайба объединены'", () => {
    const mergeAlt = makeAlt({
      invoice_id: "inv-merge",
      supplier_name: "Supplier Merge",
      coverage_summary: "← болт, гайка, шайба объединены",
    });
    const item = makeItem([
      mergeAlt,
      makeAlt({ invoice_id: "inv-other", supplier_name: "Supplier Other" }),
    ]);

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    expect(html).toContain("← болт, гайка, шайба объединены");
  });

  it("renders subtext for the single-alternative branch too", () => {
    // When only one alternative exists the picker shows it in single-КП
    // mode — coverage_summary still appears so the user knows the
    // structure of that one supplier offer.
    const mergeAlt = makeAlt({
      invoice_id: "inv-merge",
      coverage_summary: "← болт, гайка объединены",
    });
    const item = makeItem([mergeAlt]);

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    expect(html).toContain("← болт, гайка объединены");
  });
});

describe("CompositionItemRow — divergent_markups warning", () => {
  it("renders warning icon when alt.divergent_markups is true", () => {
    const mergeAlt = makeAlt({
      invoice_id: "inv-merge",
      coverage_summary: "← болт, гайка объединены",
      divergent_markups: true,
    });
    const item = makeItem([
      mergeAlt,
      makeAlt({ invoice_id: "inv-other", supplier_name: "Supplier Other" }),
    ]);

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    // The warning icon uses lucide-react's AlertTriangle with an amber class
    // and an accessible label explaining the divergent markup behavior.
    expect(html).toContain(
      "Покрываемые позиции имеют разные наценки — применится первая"
    );
    expect(html).toContain("text-amber-500");
  });

  it("does NOT render warning icon when divergent_markups is false", () => {
    const mergeAlt = makeAlt({
      invoice_id: "inv-merge",
      coverage_summary: "← болт, гайка объединены",
      divergent_markups: false,
    });
    const item = makeItem([
      mergeAlt,
      makeAlt({ invoice_id: "inv-other", supplier_name: "Supplier Other" }),
    ]);

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    expect(html).not.toContain("Покрываемые позиции имеют разные наценки");
  });

  it("does NOT render warning for a 1:1 alternative (divergent_markups always false)", () => {
    const alt = makeAlt({
      invoice_id: "inv-a",
      coverage_summary: "",
      divergent_markups: false,
    });
    const item = makeItem([alt, makeAlt({ invoice_id: "inv-b" })]);

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    expect(html).not.toContain("разные наценки");
  });
});

// ---------------------------------------------------------------------------
// Testing 2 row 36 — Цена / Сумма columns + FX tooltip
// ---------------------------------------------------------------------------

describe("CompositionItemRow — Цена / Сумма columns", () => {
  it("renders the SELECTED КПП price in the Цена column", () => {
    const selectedAlt = makeAlt({
      invoice_id: "inv-sel",
      purchase_price_original: 12.5,
      purchase_currency: "EUR",
    });
    const item = makeItem(
      [selectedAlt, makeAlt({ invoice_id: "inv-other" })],
      { selected_invoice_id: "inv-sel", quantity: 4 }
    );

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    // ru-RU formats 12.50 as "12,50" — Цена cell shows the supplier-local price.
    expect(html).toContain("12,50 EUR");
  });

  it("renders Сумма = price × quantity for the selected КПП", () => {
    const selectedAlt = makeAlt({
      invoice_id: "inv-sel",
      purchase_price_original: 10,
      purchase_currency: "USD",
    });
    const item = makeItem([selectedAlt, makeAlt({ invoice_id: "inv-other" })], {
      selected_invoice_id: "inv-sel",
      quantity: 3,
    });

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    // 10 × 3 = 30.00 → "30,00 USD"
    expect(html).toContain("30,00 USD");
  });

  it("shows '—' in Цена/Сумма when no supplier is selected", () => {
    const item = makeItem(
      [
        makeAlt({ invoice_id: "inv-a", purchase_price_original: 99 }),
        makeAlt({ invoice_id: "inv-b" }),
      ],
      { selected_invoice_id: null }
    );

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    // Two em-dash cells (Цена + Сумма). The selected price (99) must NOT show.
    expect(html).toContain("—");
    expect(html).not.toContain("99,00");
  });

  it("shows '—' when the selected КПП has a null price", () => {
    const selectedAlt = makeAlt({
      invoice_id: "inv-sel",
      purchase_price_original: null,
      purchase_currency: "EUR",
    });
    const item = makeItem([selectedAlt, makeAlt({ invoice_id: "inv-other" })], {
      selected_invoice_id: "inv-sel",
    });

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    expect(html).toContain("—");
  });

  it("no longer renders the price inline in the Поставщики label (de-dup)", () => {
    // The price used to live in the supplier label; it now lives only in the
    // Цена column. With nothing selected it must appear zero or one time
    // (Цена cell shows "—", supplier label shows no price).
    const item = makeItem(
      [
        makeAlt({
          invoice_id: "inv-a",
          supplier_name: "ACME",
          purchase_price_original: 42,
          purchase_currency: "EUR",
        }),
        makeAlt({ invoice_id: "inv-b", supplier_name: "Other" }),
      ],
      { selected_invoice_id: null }
    );

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    // Supplier name still renders; its old inline "42,00 EUR" price does not.
    expect(html).toContain("ACME");
    expect(html).not.toContain("42,00 EUR");
  });

  it("adds a КП-equivalent tooltip when rates + kpCurrency + kpp_date are present", () => {
    const rates = buildHistoricalRateMap([
      { from_currency: "USD", rate: 90, fetched_at: "2026-01-15T00:00:00Z" },
      { from_currency: "EUR", rate: 100, fetched_at: "2026-01-15T00:00:00Z" },
    ]);
    const selectedAlt = makeAlt({
      invoice_id: "inv-sel",
      purchase_price_original: 9,
      purchase_currency: "EUR",
      kpp_date: "2026-02-01T00:00:00Z",
    });
    const item = makeItem([selectedAlt, makeAlt({ invoice_id: "inv-other" })], {
      selected_invoice_id: "inv-sel",
    });

    const html = renderRow(
      <CompositionItemRow
        item={item}
        disabled={false}
        rates={rates}
        kpCurrency="USD"
        onSelect={() => {}}
      />
    );

    // 9 EUR * 100 / 90 = 10 USD → tooltip "≈ 10 $ (по курсу на 01.02.2026)".
    expect(html).toContain("≈ 10 $");
    expect(html).toContain("по курсу на");
  });

  it("omits the tooltip when the historical rate is unavailable", () => {
    const rates = buildHistoricalRateMap([]); // empty — no rates at all
    const selectedAlt = makeAlt({
      invoice_id: "inv-sel",
      purchase_price_original: 9,
      purchase_currency: "EUR",
      kpp_date: "2026-02-01T00:00:00Z",
    });
    const item = makeItem([selectedAlt, makeAlt({ invoice_id: "inv-other" })], {
      selected_invoice_id: "inv-sel",
    });

    const html = renderRow(
      <CompositionItemRow
        item={item}
        disabled={false}
        rates={rates}
        kpCurrency="USD"
        onSelect={() => {}}
      />
    );

    // Price still renders, but no "≈" tooltip equivalent.
    expect(html).toContain("9,00 EUR");
    expect(html).not.toContain("≈");
  });
});

// ---------------------------------------------------------------------------
// Testing 2 row 85 — MOQ round-up effective-quantity indicator (Кол-во cell)
// ---------------------------------------------------------------------------

describe("CompositionItemRow — Кол-во MOQ round-up", () => {
  it("shows the MOQ-floored quantity + hint when the selected КПП MOQ exceeds ordered", () => {
    const selectedAlt = makeAlt({
      invoice_id: "inv-sel",
      purchase_price_original: 10,
      purchase_currency: "USD",
      minimum_order_quantity: 10,
    });
    const item = makeItem([selectedAlt, makeAlt({ invoice_id: "inv-other" })], {
      selected_invoice_id: "inv-sel",
      quantity: 5,
    });

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    // Effective quantity (10) and the read-only hint render; the ordered
    // amount appears in the explanatory title.
    expect(html).toContain("мин. заказ 10");
    expect(html).toContain("заказано 5");
    // Сумма reflects the MOQ-floored quantity (row 85), consistent with the
    // Кол-во cell and the COGS the engine computes: 10 (price) × 10 (effective)
    // = 100.00, NOT 10 × 5 (ordered).
    expect(html).toContain("100,00 USD");
  });

  it("shows the ordered quantity with no hint when MOQ is below ordered", () => {
    const selectedAlt = makeAlt({
      invoice_id: "inv-sel",
      minimum_order_quantity: 3,
    });
    const item = makeItem([selectedAlt, makeAlt({ invoice_id: "inv-other" })], {
      selected_invoice_id: "inv-sel",
      quantity: 8,
    });

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    expect(html).not.toContain("мин. заказ");
  });

  it("shows the ordered quantity with no hint when the selected КПП has no MOQ", () => {
    const selectedAlt = makeAlt({ invoice_id: "inv-sel" }); // MOQ undefined
    const item = makeItem([selectedAlt, makeAlt({ invoice_id: "inv-other" })], {
      selected_invoice_id: "inv-sel",
      quantity: 5,
    });

    const html = renderRow(
      <CompositionItemRow item={item} disabled={false} onSelect={() => {}} />
    );

    expect(html).not.toContain("мин. заказ");
  });
});
