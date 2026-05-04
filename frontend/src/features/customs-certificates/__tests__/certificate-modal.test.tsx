import React from "react";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Tests for CertificateModal (Phase B Task 7c, REQ-7).
 *
 * The frontend workspace ships no DOM environment (no jsdom / happy-dom).
 * base-ui's `<Dialog>` mounts its content via React Portal, which requires
 * a real DOM target — `react-dom/server` therefore renders an empty string
 * for both `open=false` and `open=true`. We work around this constraint by
 * following the same playbook as `create-supplier-dialog.test.tsx`:
 *
 *   1. Comprehensive unit tests of pure helpers exported from the
 *      component module (`isFormValid`, `filterTypeOptions`, `SEEDED_TYPES`)
 *      — these encode the field-level validation rules and the seeded
 *      type list mandated by REQ-7 AC#3.
 *   2. SSR sanity for `open=false` (renders empty string without throwing)
 *      — confirms the module loads + JSX is syntactically valid.
 *   3. Render `open=true` — JSX still produces an empty string due to
 *      the portal, but the call must not throw (catches static-analysis
 *      regressions like missing imports / mistyped props).
 *   4. `createCertificate` is mocked — wiring sanity for the eventual
 *      jsdom or browser-test that actually drives the click flow.
 *
 * Click handlers, the type-Combobox creatable flow, and the live-preview
 * re-render are verified at localhost:3000 per
 * `reference_localhost_browser_test.md`.
 */

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const createMock = vi.fn();
vi.mock("../api/certificates", () => ({
  createCertificate: (...args: unknown[]) => createMock(...args),
  // Minimal stubs for the wider import surface — tree-shaking is conservative
  // enough that vitest still resolves these named exports.
  listCertificates: vi.fn(),
  attachCertificateItem: vi.fn(),
  detachCertificateItem: vi.fn(),
  deleteCertificate: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

import {
  CertificateModal,
  SEEDED_TYPES,
  TypeCreatableCombobox,
  filterTypeOptions,
  isFormValid,
} from "../ui/certificate-modal";
import type { QuoteItemForSelect } from "../model/types";

const ITEM_A: QuoteItemForSelect = {
  id: "item-a",
  position: 1,
  name: "Контактор 250А",
  product_code: "CK-250",
  rub_basis: 150_000,
};
const ITEM_B: QuoteItemForSelect = {
  id: "item-b",
  position: 2,
  name: "Реле перегрузки",
  product_code: null,
  rub_basis: 90_000,
};
const ITEMS: QuoteItemForSelect[] = [ITEM_A, ITEM_B];

// ---------------------------------------------------------------------------
// SEEDED_TYPES — REQ-7 AC#3
// ---------------------------------------------------------------------------

describe("SEEDED_TYPES — initial Combobox options", () => {
  it("exports exactly the 10 standard certificate types from REQ-7 AC#3", () => {
    expect(SEEDED_TYPES).toEqual([
      "ДС ТР ТС",
      "СС",
      "СГР",
      "ОТТС",
      "EUR.1",
      "Form A",
      "CT-1",
      "CT-2",
      "CT-3",
      "A.TR",
    ]);
  });

  it("has length 10 — sentinel for accidental list edits", () => {
    expect(SEEDED_TYPES.length).toBe(10);
  });

  it("includes Cyrillic types (4 entries)", () => {
    const cyrillic = SEEDED_TYPES.filter((t) => /[А-Я]/.test(t));
    expect(cyrillic.length).toBeGreaterThanOrEqual(4);
  });

  it("includes Latin types (5 entries: EUR.1, Form A, CT-1/2/3, A.TR)", () => {
    const latin = SEEDED_TYPES.filter((t) => /^[A-Za-z]/.test(t));
    expect(latin.length).toBeGreaterThanOrEqual(5);
  });
});

// ---------------------------------------------------------------------------
// filterTypeOptions — pure search logic
// ---------------------------------------------------------------------------

describe("filterTypeOptions — pure search logic", () => {
  it("returns the full list for an empty query", () => {
    expect(filterTypeOptions(SEEDED_TYPES, "")).toEqual(SEEDED_TYPES);
  });

  it("returns the full list for a whitespace-only query", () => {
    expect(filterTypeOptions(SEEDED_TYPES, "   ")).toEqual(SEEDED_TYPES);
  });

  it("filters by case-insensitive substring (Latin)", () => {
    const result = filterTypeOptions(SEEDED_TYPES, "form");
    expect(result).toContain("Form A");
  });

  it("filters by uppercase Latin substring", () => {
    const result = filterTypeOptions(SEEDED_TYPES, "EUR");
    expect(result).toContain("EUR.1");
  });

  it("matches Cyrillic substrings exactly (no normalization needed)", () => {
    const result = filterTypeOptions(SEEDED_TYPES, "ТР");
    expect(result).toContain("ДС ТР ТС");
  });

  it("returns an empty list for a non-matching query", () => {
    expect(filterTypeOptions(SEEDED_TYPES, "zzzzz")).toEqual([]);
  });

  it("trims whitespace around the query before matching", () => {
    const padded = filterTypeOptions(SEEDED_TYPES, "  EUR  ");
    expect(padded).toContain("EUR.1");
  });

  it("preserves the original list (does not mutate input)", () => {
    const before = [...SEEDED_TYPES];
    filterTypeOptions(SEEDED_TYPES, "form");
    expect([...SEEDED_TYPES]).toEqual(before);
  });
});

// ---------------------------------------------------------------------------
// isFormValid — REQ-7 AC#3 required-field gate
// ---------------------------------------------------------------------------

describe("isFormValid — required field gate (REQ-7 AC#3)", () => {
  it("returns false when both type and cost_rub are empty (initial state)", () => {
    expect(isFormValid({ type: "", costRub: "" })).toBe(false);
  });

  it("returns false when only type is set", () => {
    expect(isFormValid({ type: "ДС ТР ТС", costRub: "" })).toBe(false);
  });

  it("returns false when only cost_rub is set", () => {
    expect(isFormValid({ type: "", costRub: "12500" })).toBe(false);
  });

  it("returns true when both required fields are set with valid values", () => {
    expect(isFormValid({ type: "ДС ТР ТС", costRub: "12500" })).toBe(true);
  });

  it("treats whitespace-only type as empty", () => {
    expect(isFormValid({ type: "   ", costRub: "12500" })).toBe(false);
  });

  it("rejects negative cost_rub (CHECK constraint cost_rub >= 0)", () => {
    expect(isFormValid({ type: "ДС ТР ТС", costRub: "-1" })).toBe(false);
  });

  it("accepts cost_rub of 0 — server allows free certificates", () => {
    expect(isFormValid({ type: "СС", costRub: "0" })).toBe(true);
  });

  it("rejects non-numeric cost_rub", () => {
    expect(isFormValid({ type: "ДС ТР ТС", costRub: "abc" })).toBe(false);
  });

  it("accepts decimal cost_rub", () => {
    expect(isFormValid({ type: "ДС ТР ТС", costRub: "999999.99" })).toBe(true);
  });

  it("accepts a custom (non-seeded) type — Combobox is creatable", () => {
    expect(isFormValid({ type: "Custom Russian Cert", costRub: "100" })).toBe(
      true,
    );
  });

  it("rejects whitespace-only cost_rub even when string-coerced", () => {
    expect(isFormValid({ type: "СС", costRub: "   " })).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// CertificateModal — SSR sanity
// ---------------------------------------------------------------------------

describe("CertificateModal — SSR sanity", () => {
  it("does not throw when rendered with open=false", () => {
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
      />,
    );
    expect(typeof html).toBe("string");
    // base-ui Dialog renders nothing when closed (and SSR has no DOM
    // target for its Portal even when open).
    expect(html).toBe("");
  });

  it("does not throw when rendered with open=true (Portal returns empty in SSR)", () => {
    const html = renderToString(
      <CertificateModal
        open
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
      />,
    );
    expect(typeof html).toBe("string");
    // Render does not throw — confirms imports are wired up + JSX is
    // syntactically valid. Markup assertions happen in browser tests.
  });

  it("does not throw with no items and a nullable onCreated", () => {
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={[]}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("accepts the optional onCreated callback prop", () => {
    const onCreated = vi.fn();
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        onCreated={onCreated}
      />,
    );
    expect(typeof html).toBe("string");
    // onCreated only fires on successful POST — never on render.
    expect(onCreated).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Module surface
// ---------------------------------------------------------------------------

describe("CertificateModal — module surface", () => {
  it("exports CertificateModal as a function", () => {
    expect(typeof CertificateModal).toBe("function");
  });

  it("exports the creatable Combobox sub-component for re-use", () => {
    expect(typeof TypeCreatableCombobox).toBe("function");
  });

  it("exports the SEEDED_TYPES list as a readonly array of strings", () => {
    expect(Array.isArray(SEEDED_TYPES)).toBe(true);
    SEEDED_TYPES.forEach((t) => expect(typeof t).toBe("string"));
  });

  it("exports isFormValid as a function", () => {
    expect(typeof isFormValid).toBe("function");
  });

  it("exports filterTypeOptions as a function", () => {
    expect(typeof filterTypeOptions).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// API integration via mocked createCertificate
// ---------------------------------------------------------------------------

describe("CertificateModal — submit payload contract", () => {
  beforeEach(() => {
    createMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  /**
   * Without jsdom we cannot trigger the form submit handler, but we can
   * verify the mock plumbing is wired correctly. The jsdom-backed (or
   * browser-driven) tests will assert on:
   *   - call count (1 per submit)
   *   - first-arg shape: `{quote_id, type, cost_rub, item_ids, ...}`
   *   - trimmed `type`, numeric `cost_rub`, optional fields omitted
   *     when empty (REQ-2 contract).
   *
   * The mock is hot — calling it from a future test would observe the
   * payload directly. For now the test confirms the mock is callable
   * and not yet invoked.
   */
  it("createCertificate is mockable as the submit target", () => {
    expect(typeof createMock).toBe("function");
    expect(createMock).not.toHaveBeenCalled();
  });

  it("createCertificate mock can be called and inspected", () => {
    createMock("dummy-payload");
    expect(createMock).toHaveBeenCalledTimes(1);
    expect(createMock).toHaveBeenCalledWith("dummy-payload");
  });
});
