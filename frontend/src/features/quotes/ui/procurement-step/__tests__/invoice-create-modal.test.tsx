import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

/**
 * Task 76 — InvoiceCreateModal SSR sanity.
 *
 * The modal is a client component that relies on useRouter, Dialog+Portal,
 * and useEffect for VAT auto-fill. The frontend workspace has no DOM
 * (vitest + happy-dom/jsdom not wired), and @base-ui's Dialog skips its
 * Portal during SSR, so we cannot observe interaction-driven UI here.
 *
 * Semantic coverage of the new fetchSupplierVatRate helper (all four
 * outcome branches — domestic, export_zero_rated, unknown, null on error)
 * lives in frontend/src/entities/invoice/__tests__/queries.test.ts. This
 * file confirms the modal module loads cleanly with its new imports and
 * renders without throwing in the closed state.
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
    from: () => ({
      select: () => ({
        eq: () => ({ in: async () => ({ data: [], error: null }) }),
      }),
      update: () => ({ in: async () => ({ data: [], error: null }) }),
    }),
  }),
}));

vi.mock("@/entities/quote/mutations", () => ({
  createInvoice: vi.fn(async () => ({ id: "inv-1" })),
  assignItemsToInvoice: vi.fn(async () => undefined),
}));

import { InvoiceCreateModal } from "../invoice-create-modal";

describe("InvoiceCreateModal — module + closed-state (SSR sanity)", () => {
  it("exports as a function", () => {
    expect(typeof InvoiceCreateModal).toBe("function");
  });

  it("renders without throwing when open=false (Portal omitted during SSR)", () => {
    const html = renderToString(
      <InvoiceCreateModal
        open={false}
        onClose={() => {}}
        quoteId="q-1"
        idnQuote="Q-202604-0001"
        selectedItems={[]}
        suppliers={[]}
        buyerCompanies={[]}
      />
    );
    expect(typeof html).toBe("string");
  });
});
