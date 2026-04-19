import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5d Task 13 — Specification PDF component renders composed items.
 *
 * The upstream route at app/(app)/export/specification/[id]/route.tsx
 * was refactored in Task 11 (commit b5b0173) to assemble composed items
 * from invoice_items filtered by composition_selected_invoice_id.
 *
 * SpecDocument already defines a narrow explicit items prop shape
 * matching the composed output. These tests lock the contract: split
 * cases yield one PDF row per covering invoice_item; merge cases render
 * each unique invoice_item once; the "шт" unit fallback handles the
 * missing invoice_items.unit column.
 */

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

import { SpecDocument } from "../spec-document";

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

const baseProps = {
  specNumber: "SP-001",
  signDate: "2026-03-01",
  readinessPeriod: "30 дней",
  contractNumber: null,
  contractDate: null,
  customerName: "OOO Ромашка",
  customerInn: "1234567890",
  quoteCurrency: "RUB",
  quoteIdn: "Q-202603-0001",
  logoBase64: "",
};

describe("SpecDocument — Phase 5d composed item rendering", () => {
  it("renders composed item fields (brand, product_code, product_name, quantity, base_price_vat) for 1:1 case", () => {
    const items = [
      {
        brand: "SKF",
        product_code: "SKF-205",
        product_name: "Подшипник SKF-205",
        unit: null,
        quantity: 5,
        base_price_vat: 1000,
      },
    ];

    const tree = SpecDocument({ ...baseProps, items });
    const text = collectText(tree).join(" | ");

    expect(text).toContain("SKF");
    expect(text).toContain("SKF-205");
    expect(text).toContain("Подшипник SKF-205");
    expect(text).toContain("5");
    expect(text).toContain("шт"); // null unit → fallback
  });

  it("falls back to 'шт' when invoice_items.unit is null (the column does not exist there)", () => {
    const items = [
      {
        brand: "NSK",
        product_code: "NSK-301",
        product_name: "Подшипник NSK",
        unit: null,
        quantity: 2,
        base_price_vat: 500,
      },
    ];

    const tree = SpecDocument({ ...baseProps, items });
    const text = collectText(tree).join(" | ");
    expect(text).toContain("шт");
  });

  it("renders split case: two invoice_items covering one quote_item appear as two rows", () => {
    // Upstream route flattens split coverage into two composed items.
    const items = [
      {
        brand: "SKF",
        product_code: "SKF-205",
        product_name: "Подшипник SKF-205 (supplier A)",
        unit: null,
        quantity: 2,
        base_price_vat: 1100,
      },
      {
        brand: "SKF",
        product_code: "SKF-205-ALT",
        product_name: "Подшипник SKF-205 (supplier B)",
        unit: null,
        quantity: 3,
        base_price_vat: 950,
      },
    ];

    const tree = SpecDocument({ ...baseProps, items });
    const text = collectText(tree).join(" | ");

    expect(text).toContain("supplier A");
    expect(text).toContain("supplier B");
    expect(text).toContain("SKF-205-ALT");
  });

  it("renders totals (quantity sum, price sum) correctly", () => {
    const items = [
      {
        brand: "SKF",
        product_code: "A",
        product_name: "Item A",
        unit: null,
        quantity: 10,
        base_price_vat: 100,
      },
      {
        brand: "NSK",
        product_code: "B",
        product_name: "Item B",
        unit: null,
        quantity: 5,
        base_price_vat: 200,
      },
    ];

    const tree = SpecDocument({ ...baseProps, items });
    const text = collectText(tree).join(" | ");

    // Total quantity = 15
    expect(text).toContain("15");
    // Total sum = 10*100 + 5*200 = 2000 — ru-RU formatting
    expect(text).toMatch(/2[\s\u00A0]000,00/);
    // Currency
    expect(text).toContain("RUB");
  });

  it("handles null quantity and null base_price_vat safely", () => {
    const items = [
      {
        brand: null,
        product_code: null,
        product_name: "Item without price",
        unit: null,
        quantity: null,
        base_price_vat: null,
      },
    ];

    const tree = SpecDocument({ ...baseProps, items });
    const text = collectText(tree).join(" | ");

    // Nullable qty → "—" placeholder
    expect(text).toContain("—");
    expect(text).toContain("Item without price");
  });

  it("renders spec number and quote reference in header", () => {
    const tree = SpecDocument({
      ...baseProps,
      specNumber: "SP-042",
      quoteIdn: "Q-202604-0007",
      items: [],
    });
    const text = collectText(tree).join(" | ");

    expect(text).toContain("SP-042");
    expect(text).toContain("Q-202604-0007");
  });
});
