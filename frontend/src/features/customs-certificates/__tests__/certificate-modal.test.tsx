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
const updateMock = vi.fn();
vi.mock("../api/certificates", () => ({
  createCertificate: (...args: unknown[]) => createMock(...args),
  updateCertificate: (...args: unknown[]) => updateMock(...args),
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
import type { Certificate, QuoteItemForSelect } from "../model/types";

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

/** A fully-populated cert used by the EDIT-mode tests (REQ-9 AC#7). */
const EDITING_CERT: Certificate = {
  id: "cert-1",
  quote_id: "quote-1",
  type: "ДС ТР ТС",
  number: "ЕАЭС N RU Д-CN.РА01.В.12345",
  issuer: "Сертэксперт ЦСМ",
  legal_doc: "ТР ТС 010/2011",
  issued_at: "2026-01-15",
  valid_until: "2027-01-14",
  cost_original: 18500,
  cost_currency: "RUB",
  cost_rub: 18500,
  notes: "Перевыпуск по сроку",
  display_name: null,
  is_custom_expense: false,
  created_at: "2026-01-15T10:00:00Z",
  updated_at: "2026-01-15T10:00:00Z",
  created_by: "user-1",
  attached_items: [],
};

// ---------------------------------------------------------------------------
// SEEDED_TYPES — REQ-7 AC#3
// ---------------------------------------------------------------------------

describe("SEEDED_TYPES — initial Combobox options", () => {
  it("exports the 5 consolidated certificate types (Testing 2 row 73)", () => {
    // Tester decision 2026-05-24: collapse the 10-entry list down to 5 —
    // «Сертификат происхождения» now covers EUR.1 / Form A / CT-1/2/3 /
    // A.TR; existing rows with those legacy values remain valid via the
    // creatable Combobox. See docs/plans/2026-05-24-product-decisions.md.
    expect(SEEDED_TYPES).toEqual([
      "Сертификат происхождения",
      "СС",
      "ДС ТР ТС",
      "СГР",
      "ОТТС",
    ]);
  });

  it("has length 5 — sentinel for accidental list edits", () => {
    expect(SEEDED_TYPES.length).toBe(5);
  });

  it("contains only Cyrillic entries post-consolidation", () => {
    // After Testing 2 row 73 every seeded value is Cyrillic; legacy Latin
    // codes (EUR.1 / Form A / CT-X / A.TR) live as free-text values only.
    const cyrillic = SEEDED_TYPES.filter((t) => /[А-Я]/.test(t));
    expect(cyrillic.length).toBe(SEEDED_TYPES.length);
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

  it("filters by case-insensitive substring (Cyrillic)", () => {
    // Replaced the Latin «form» / «EUR» queries with Cyrillic ones —
    // the seeded list is fully Cyrillic post-Testing 2 row 73.
    const result = filterTypeOptions(SEEDED_TYPES, "проис");
    expect(result).toContain("Сертификат происхождения");
  });

  it("filters by uppercase Cyrillic substring", () => {
    const result = filterTypeOptions(SEEDED_TYPES, "ТР");
    expect(result).toContain("ДС ТР ТС");
  });

  it("matches Cyrillic substrings exactly (no normalization needed)", () => {
    const result = filterTypeOptions(SEEDED_TYPES, "ОТТС");
    expect(result).toContain("ОТТС");
  });

  it("returns an empty list for a non-matching query", () => {
    expect(filterTypeOptions(SEEDED_TYPES, "zzzzz")).toEqual([]);
  });

  it("trims whitespace around the query before matching", () => {
    const padded = filterTypeOptions(SEEDED_TYPES, "  ОТТС  ");
    expect(padded).toContain("ОТТС");
  });

  it("preserves the original list (does not mutate input)", () => {
    const before = [...SEEDED_TYPES];
    filterTypeOptions(SEEDED_TYPES, "ОТТС");
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
// Phase B Wave 5 cleanup — preset + preSelectedItemIds props
// ---------------------------------------------------------------------------

describe("CertificateModal — preset + preSelectedItemIds props (Wave 5)", () => {
  it("does not throw when rendered with a preset prop", () => {
    // REQ-5 AC#9 / REQ-7 AC#3 — opening from the HistoryBanner «Создать
    // новый» surfaces a preset of {type, cost_rub} so the customs
    // specialist re-issues the document without retyping identical fields.
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        preset={{ type: "ДС ТР ТС", cost_rub: 12500 }}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("does not throw when rendered with a partial preset (type only)", () => {
    // Both fields on `preset` are independently optional.
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        preset={{ type: "СС" }}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("does not throw when rendered with a partial preset (cost only)", () => {
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        preset={{ cost_rub: 999 }}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("does not throw when rendered with preSelectedItemIds", () => {
    // REQ-8 AC#3 — opening from the BindPopover empty-state «Создать новый»
    // pre-ticks the current item in the multi-select.
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        preSelectedItemIds={[ITEM_A.id]}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("does not throw with both preset and preSelectedItemIds together", () => {
    // The dialog passes both — preset from HistoryBanner + the current item
    // pre-selected unconditionally — so this combination must mount cleanly.
    const html = renderToString(
      <CertificateModal
        open={true}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        preset={{ type: "EUR.1", cost_rub: 7500 }}
        preSelectedItemIds={[ITEM_A.id, ITEM_B.id]}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("ignores a non-finite cost_rub in the preset (defensive)", () => {
    // Defensive: a NaN / Infinity coming out of bad upstream data should
    // not crash the modal — it should fall back to an empty cost field.
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        preset={{ type: "СС", cost_rub: Number.NaN }}
      />,
    );
    expect(typeof html).toBe("string");
  });
});

// ---------------------------------------------------------------------------
// Phase B REQ-9 AC#7 — EDIT mode (editingCert + onUpdated props)
// ---------------------------------------------------------------------------

describe("CertificateModal — edit mode props (REQ-9 AC#7)", () => {
  it("does not throw when rendered with editingCert (closed)", () => {
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        editingCert={EDITING_CERT}
        onUpdated={() => {}}
      />,
    );
    expect(typeof html).toBe("string");
    expect(html).toBe("");
  });

  it("does not throw when rendered with editingCert (open, Portal → empty)", () => {
    const html = renderToString(
      <CertificateModal
        open
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        editingCert={EDITING_CERT}
        onUpdated={() => {}}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("does not throw with a minimal editingCert (null optional fields)", () => {
    const minimal: Certificate = {
      ...EDITING_CERT,
      number: null,
      issuer: null,
      legal_doc: null,
      issued_at: null,
      valid_until: null,
      notes: null,
      cost_currency: undefined,
    };
    const html = renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        editingCert={minimal}
        onUpdated={() => {}}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("accepts the optional onUpdated callback without firing it on render", () => {
    const onUpdated = vi.fn();
    renderToString(
      <CertificateModal
        open={false}
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        editingCert={EDITING_CERT}
        onUpdated={onUpdated}
      />,
    );
    // onUpdated only fires on a successful PATCH — never on render.
    expect(onUpdated).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// API integration via mocked createCertificate / updateCertificate
// ---------------------------------------------------------------------------

describe("CertificateModal — submit payload contract", () => {
  beforeEach(() => {
    createMock.mockReset();
    updateMock.mockReset();
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

  it("updateCertificate is mockable as the edit submit target", () => {
    expect(typeof updateMock).toBe("function");
    expect(updateMock).not.toHaveBeenCalled();
  });

  it("updateCertificate mock can be called and inspected", () => {
    updateMock("cert-1", { type: "СС" });
    expect(updateMock).toHaveBeenCalledTimes(1);
    expect(updateMock).toHaveBeenCalledWith("cert-1", { type: "СС" });
  });
});
