import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5d Task 13 — KP PDF component renders composed item shape.
 *
 * Migration 284 drops `base_price_vat`, `product_code`, `unit` from
 * quote_items. These prices/codes now live on invoice_items, selected
 * for the KP via each quote_item's composition_selected_invoice_id.
 *
 * This test asserts the component consumes a narrow composed-item
 * shape (not the wide `QuoteItemRow` type from `select("*")`). The
 * upstream /export/kp/[id]/route.tsx is responsible for assembling
 * the composed shape (out of scope for Task 13).
 */

// @react-pdf/renderer pulls in Buffer/stream machinery that we don't
// want to exercise. Stub it with primitives that pass children/props
// through so the tree can be walked.
vi.mock("@react-pdf/renderer", () => {
  const Stub =
    (tag: string) =>
    ({
      children,
      ...props
    }: {
      children?: unknown;
      [k: string]: unknown;
    }) => ({ type: tag, props: { ...props, children } });
  return {
    Document: Stub("Document"),
    Page: Stub("Page"),
    View: Stub("View"),
    Text: Stub("Text"),
    Image: Stub("Image"),
    Font: {
      register: vi.fn(),
      registerHyphenationCallback: vi.fn(),
    },
    StyleSheet: { create: (x: unknown) => x },
  };
});

import { KPDocument } from "../kp-document";

// Recursively collect all `Text` node string content from the element tree.
function collectText(node: unknown): string[] {
  if (node == null) return [];
  if (typeof node === "string") return [node];
  if (typeof node === "number") return [String(node)];
  if (Array.isArray(node)) return node.flatMap(collectText);
  if (typeof node === "object") {
    const n = node as { type?: unknown; props?: { children?: unknown } };
    const children = n.props?.children;
    return collectText(children);
  }
  return [];
}

interface KPTestQuote {
  id: string;
  idn_quote: string;
  quote_date: string | null;
  created_at: string;
  currency: string;
  delivery_city: string | null;
  delivery_country: string | null;
  delivery_address: string | null;
  incoterms: string | null;
  payment_terms: string | null;
  delivery_days: number | null;
  valid_until: string | null;
  manager_email: string | null;
  customer: { id: string; name: string; inn: string | null } | null;
  contact_person: {
    id: string;
    name: string;
    phone: string | null;
    email: string | null;
  } | null;
  created_by_profile: { id: string; full_name: string } | null;
}

const baseQuote: KPTestQuote = {
  id: "q-1",
  idn_quote: "Q-202603-0001",
  quote_date: "2026-03-01",
  created_at: "2026-03-01T10:00:00Z",
  currency: "RUB",
  delivery_city: "Москва",
  delivery_country: "Россия",
  delivery_address: null,
  incoterms: "DDP",
  payment_terms: "30 дней после поставки",
  delivery_days: 45,
  valid_until: "2026-04-01",
  manager_email: "sales@masterbearing.ru",
  customer: { id: "cust-1", name: "OOO Ромашка", inn: "1234567890" },
  contact_person: {
    id: "c-1",
    name: "Иван Петров",
    phone: "+7 (999) 123-45-67",
    email: "ivan@romashka.ru",
  },
  created_by_profile: { id: "u-1", full_name: "Менеджер Тест" },
};

describe("KPDocument — Phase 5d composed item rendering", () => {
  it("renders product_code, product_name, brand, quantity, base_price_vat from composed items (1:1 case)", () => {
    const items = [
      {
        id: "qi-1",
        brand: "SKF",
        product_code: "SKF-205",
        product_name: "Подшипник SKF-205",
        unit: null as string | null,
        quantity: 5,
        base_price_vat: 1000,
      },
    ];

    const tree = KPDocument({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quote: baseQuote as any,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      items: items as any,
      logoBase64: "data:image/png;base64,",
      vatRate: 22,
    });

    const text = collectText(tree).join(" | ");

    expect(text).toContain("SKF");
    expect(text).toContain("SKF-205");
    expect(text).toContain("Подшипник SKF-205");
    expect(text).toContain("5"); // quantity
    // Unit missing → fallback "шт"
    expect(text).toContain("шт");
  });

  it("falls back to 'шт' when item.unit is null (invoice_items has no unit column)", () => {
    const items = [
      {
        id: "qi-1",
        brand: "NSK",
        product_code: "NSK-301",
        product_name: "Подшипник NSK",
        unit: null,
        quantity: 1,
        base_price_vat: 500,
      },
    ];

    const tree = KPDocument({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quote: baseQuote as any,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      items: items as any,
      logoBase64: "",
    });

    const text = collectText(tree).join(" | ");
    expect(text).toContain("шт");
  });

  it("renders a split case: one quote_item covered by two invoice_items → two PDF rows", () => {
    // Split scenario: manager-position qi-1 has two invoice_item coverages
    // (different suppliers). The upstream route flattens coverage into two
    // composed items. The PDF renders them as two independent rows.
    const items = [
      {
        id: "ii-A",
        brand: "SKF",
        product_code: "SKF-205",
        product_name: "Подшипник SKF-205 (поставщик A)",
        unit: null,
        quantity: 2,
        base_price_vat: 1100,
      },
      {
        id: "ii-B",
        brand: "SKF",
        product_code: "SKF-205-ALT",
        product_name: "Подшипник SKF-205 (поставщик B)",
        unit: null,
        quantity: 3,
        base_price_vat: 950,
      },
    ];

    const tree = KPDocument({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quote: baseQuote as any,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      items: items as any,
      logoBase64: "",
      vatRate: 0,
    });

    const text = collectText(tree).join(" | ");
    expect(text).toContain("SKF-205");
    expect(text).toContain("SKF-205-ALT");
    expect(text).toContain("Подшипник SKF-205 (поставщик A)");
    expect(text).toContain("Подшипник SKF-205 (поставщик B)");
  });

  it("renders totals computed from base_price_vat × quantity", () => {
    const items = [
      {
        id: "qi-1",
        brand: "SKF",
        product_code: "A",
        product_name: "Item A",
        unit: null,
        quantity: 10,
        base_price_vat: 100,
      },
      {
        id: "qi-2",
        brand: "NSK",
        product_code: "B",
        product_name: "Item B",
        unit: null,
        quantity: 5,
        base_price_vat: 200,
      },
    ];

    const tree = KPDocument({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quote: baseQuote as any,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      items: items as any,
      logoBase64: "",
      vatRate: 0, // export: VAT = 0, totalWithVat = totalNoVat = 2000
    });

    const text = collectText(tree).join(" | ");
    // Total (10*100 + 5*200 = 2000) — formatted in ru-RU → "2 000,00"
    // Using non-breaking space + decimal comma
    expect(text).toMatch(/2[\s\u00A0]000,00/);
    // Total qty = 15
    expect(text).toContain("15");
  });

  it("handles empty items without crashing (totals render as — or 0,00)", () => {
    const tree = KPDocument({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quote: baseQuote as any,
      items: [],
      logoBase64: "",
    });

    const text = collectText(tree).join(" | ");
    expect(text).toContain("КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ");
    // No item rows, totals = 0
    expect(text).toMatch(/0,00/);
  });

  it("decouples prop shape from QuoteItemRow — accepts a narrow composed-item type", () => {
    // Contract: after Phase 5d, the KP PDF must not require DB-row-shaped
    // items. A minimal composed-item type (only the fields the PDF reads)
    // must satisfy the TypeScript compiler. This is a compile-time test —
    // if it compiles, it passes.
    const narrowItems: Array<{
      id: string;
      brand: string | null;
      product_code: string | null;
      product_name: string;
      unit: string | null;
      quantity: number | null;
      base_price_vat: number | null;
    }> = [
      {
        id: "qi-1",
        brand: "SKF",
        product_code: "SKF-205",
        product_name: "Подшипник",
        unit: null,
        quantity: 5,
        base_price_vat: 1000,
      },
    ];

    // If KPDocument's items prop is (or is widened to) a narrow composed
    // shape, this call compiles. If it still requires the legacy-wide
    // `QuoteItemRow` shape, this block fails type-check.
    const tree = KPDocument({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quote: baseQuote as any,
      items: narrowItems,
      logoBase64: "",
    });

    expect(tree).toBeTruthy();
  });
});
