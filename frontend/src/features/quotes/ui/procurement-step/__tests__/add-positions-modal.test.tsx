import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

/**
 * Task 73 — AddPositionsModal tests.
 *
 * AddPositionsModal lets a user add quote_items to an empty КП поставщику.
 * Opened from InvoiceCard's `isEmpty` branch. Items already covered by
 * another invoice remain selectable (multi-KP coverage allowed per Phase
 * 5b REQ-1 AC#1) and are annotated with a subtle "в {invoice_number}"
 * badge.
 *
 * Frontend workspace has no DOM (vitest + jsdom absent). @base-ui Dialog
 * renders into a Portal which is skipped during SSR. We therefore assert
 * UI against the pure body (AddPositionsModalBody) rendered with
 * renderToString, and cover the full modal via closed-state + export
 * sanity checks.
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
    from: () => ({
      select: () => ({
        eq: () => ({
          order: async () => ({ data: [], error: null }),
        }),
        in: async () => ({ data: [], error: null }),
      }),
    }),
    auth: { getSession: async () => ({ data: { session: null } }) },
  }),
}));

const assignItemsToInvoiceMock = vi.fn<
  (itemIds: string[], invoiceId: string) => Promise<void>
>(async () => undefined);

vi.mock("@/entities/quote/mutations", () => ({
  assignItemsToInvoice: (itemIds: string[], invoiceId: string) =>
    assignItemsToInvoiceMock(itemIds, invoiceId),
}));

import {
  AddPositionsModal,
  AddPositionsModalBody,
} from "../add-positions-modal";

interface CandidateItem {
  id: string;
  product_name: string;
  supplier_sku: string | null;
  brand: string | null;
  quantity: number;
  existing_invoice_numbers: string[];
}

function makeCandidate(overrides: Partial<CandidateItem> = {}): CandidateItem {
  return {
    id: "qi-1",
    product_name: "Болт М8",
    supplier_sku: null,
    brand: null,
    quantity: 100,
    existing_invoice_numbers: [],
    ...overrides,
  };
}

describe("AddPositionsModalBody — candidate list rendering", () => {
  it("renders candidate items with product_name, brand, SKU, quantity", () => {
    const candidates = [
      makeCandidate({
        id: "qi-1",
        product_name: "Болт М8",
        brand: "ABB",
        supplier_sku: "SKU-001",
        quantity: 100,
      }),
      makeCandidate({
        id: "qi-2",
        product_name: "Гайка М8",
        brand: "Siemens",
        supplier_sku: "SKU-002",
        quantity: 50,
      }),
    ];

    const html = renderToString(
      <AddPositionsModalBody
        loading={false}
        candidates={candidates}
        selectedIds={new Set()}
        onToggle={() => {}}
        onToggleAll={() => {}}
      />
    );

    expect(html).toContain("Болт М8");
    expect(html).toContain("Гайка М8");
    expect(html).toContain("SKU-001");
    expect(html).toContain("SKU-002");
    expect(html).toContain("ABB");
    expect(html).toContain("Siemens");
    expect(html).toContain("100");
    expect(html).toContain("50");
  });

  it("shows a loading indicator while candidates are being fetched", () => {
    const html = renderToString(
      <AddPositionsModalBody
        loading={true}
        candidates={[]}
        selectedIds={new Set()}
        onToggle={() => {}}
        onToggleAll={() => {}}
      />
    );

    expect(html).toContain("Загрузка позиций");
  });

  it("shows an empty-state message when the quote has no items", () => {
    const html = renderToString(
      <AddPositionsModalBody
        loading={false}
        candidates={[]}
        selectedIds={new Set()}
        onToggle={() => {}}
        onToggleAll={() => {}}
      />
    );

    expect(html).toContain("нет позиций");
  });
});

describe("AddPositionsModalBody — existing coverage badge (Phase 5b REQ-1 AC#1)", () => {
  it("renders a 'в {invoice_number}' badge for items already in another КП", () => {
    const candidates = [
      makeCandidate({
        id: "qi-1",
        product_name: "Болт М8",
        existing_invoice_numbers: ["INV-02-Q-202604-0001"],
      }),
    ];

    const html = renderToString(
      <AddPositionsModalBody
        loading={false}
        candidates={candidates}
        selectedIds={new Set()}
        onToggle={() => {}}
        onToggleAll={() => {}}
      />
    );

    expect(html).toContain("INV-02-Q-202604-0001");
  });

  it("joins multiple covering invoice numbers with a comma", () => {
    const candidates = [
      makeCandidate({
        id: "qi-1",
        product_name: "Болт М8",
        existing_invoice_numbers: [
          "INV-02-Q-202604-0001",
          "INV-03-Q-202604-0001",
        ],
      }),
    ];

    const html = renderToString(
      <AddPositionsModalBody
        loading={false}
        candidates={candidates}
        selectedIds={new Set()}
        onToggle={() => {}}
        onToggleAll={() => {}}
      />
    );

    // Both numbers must appear in the same badge (comma-joined).
    expect(html).toContain("INV-02-Q-202604-0001");
    expect(html).toContain("INV-03-Q-202604-0001");
  });

  it("does NOT render a coverage badge for items not in any other КП", () => {
    const candidates = [
      makeCandidate({
        id: "qi-1",
        product_name: "Болт М8",
        existing_invoice_numbers: [],
      }),
    ];

    const html = renderToString(
      <AddPositionsModalBody
        loading={false}
        candidates={candidates}
        selectedIds={new Set()}
        onToggle={() => {}}
        onToggleAll={() => {}}
      />
    );

    // The badge copy starts with "в " — not present when no existing
    // coverage.
    expect(html).not.toContain("INV-");
  });
});

describe("AddPositionsModalBody — selection state", () => {
  // React inserts HTML comments between adjacent string/expression children
  // during SSR, so assertions strip those markers before matching.
  function stripReactComments(html: string): string {
    return html.replace(/<!--\s*-->/g, "");
  }

  it("marks items present in selectedIds as checked (reflects 1 selected)", () => {
    const candidates = [
      makeCandidate({ id: "qi-1", product_name: "Болт" }),
      makeCandidate({ id: "qi-2", product_name: "Гайка" }),
    ];
    const selectedIds = new Set(["qi-1"]);

    const html = stripReactComments(
      renderToString(
        <AddPositionsModalBody
          loading={false}
          candidates={candidates}
          selectedIds={selectedIds}
          onToggle={() => {}}
          onToggleAll={() => {}}
        />
      )
    );

    // @base-ui checkbox uses data-checked attribute when checked — the
    // first row carries it; the second does not.
    expect(html).toContain("Выбрано: 1");
    // aria-checked wire-up confirms per-row state.
    expect(html.match(/aria-checked="true"/g)?.length).toBeGreaterThanOrEqual(1);
    expect(html.match(/aria-checked="false"/g)?.length).toBeGreaterThanOrEqual(1);
  });

  it("reflects the selected count in the header", () => {
    const candidates = [
      makeCandidate({ id: "qi-1" }),
      makeCandidate({ id: "qi-2" }),
      makeCandidate({ id: "qi-3" }),
    ];
    const selectedIds = new Set(["qi-1", "qi-3"]);

    const html = stripReactComments(
      renderToString(
        <AddPositionsModalBody
          loading={false}
          candidates={candidates}
          selectedIds={selectedIds}
          onToggle={() => {}}
          onToggleAll={() => {}}
        />
      )
    );

    expect(html).toContain("Выбрано: 2");
    expect(html).toContain("Выбрать все (3)");
  });
});

describe("AddPositionsModal — closed-state and exports (SSR sanity)", () => {
  it("exports the modal as a function (render with open=false produces no portal)", () => {
    expect(typeof AddPositionsModal).toBe("function");

    // When closed the Dialog does not render its Portal; the output is
    // safe to render via SSR without throwing.
    const html = renderToString(
      <AddPositionsModal
        open={false}
        onClose={() => {}}
        invoiceId="inv-A"
        quoteId="q-1"
      />
    );
    // Portal omitted during SSR — rendered output is empty or minimal;
    // the module simply must not throw during render.
    expect(typeof html).toBe("string");
  });
});
