import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";
import { findCountryByName } from "@/shared/ui/geo";

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

/**
 * MAJOR #5 — supplier country lookup must try RU then fall back to EN.
 *
 * The modal's supplier-select onChange reads `supplier.country` (free-text
 * in the legacy column) and calls findCountryByName to resolve ISO-2. Prior
 * behavior tried only RU, so English-stored values ("Germany", "Turkey")
 * silently produced no match and VAT autofetch never fired. The fix adds
 * `?? findCountryByName(supplier.country, "en")` as a second attempt.
 *
 * We test the resolver chain directly here because the onChange handler is
 * inline in a JSX element and not exported.
 */
describe("InvoiceCreateModal — supplier country resolver chain (MAJOR #5)", () => {
  function resolve(country: string) {
    return (
      findCountryByName(country, "ru") ?? findCountryByName(country, "en")
    );
  }

  it("resolves Russian country name on first lookup", () => {
    const match = resolve("Германия");
    expect(match?.code).toBe("DE");
  });

  it("falls back to English when RU lookup fails (Germany)", () => {
    const match = resolve("Germany");
    expect(match?.code).toBe("DE");
  });

  it("falls back to English when RU lookup fails (France)", () => {
    const match = resolve("France");
    expect(match?.code).toBe("FR");
  });

  it("falls back to English when RU lookup fails (Türkiye, ICU en name)", () => {
    // ICU returns "Türkiye" (UN-recognized name) for 'TR' in English, not
    // "Turkey". Suppliers stored with the legacy "Turkey" spelling still
    // won't match — that's a separate data-cleanup concern; this test
    // documents the actual en-locale resolution behavior.
    const match = resolve("Türkiye");
    expect(match?.code).toBe("TR");
  });

  it("returns undefined when neither RU nor EN matches (junk value)", () => {
    const match = resolve("Atlantis");
    expect(match).toBeUndefined();
  });
});
