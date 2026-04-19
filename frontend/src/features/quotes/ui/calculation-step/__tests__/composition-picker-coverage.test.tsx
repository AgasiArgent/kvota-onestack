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
