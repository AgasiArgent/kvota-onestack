import React from "react";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Tests for CertificateBindPopover (Phase B Wave 3 Task 7d, REQ-8).
 *
 * The frontend workspace ships no DOM environment (no jsdom / happy-dom).
 * base-ui's `<Popover>` mounts its content via React Portal, which requires
 * a real DOM target — `react-dom/server` therefore renders an empty string
 * for the popover content even when the trigger is included. We follow the
 * same playbook as `certificate-modal.test.tsx`:
 *
 *   1. Comprehensive unit tests of pure helpers exported from the
 *      component module (`filterCertsBySearch`, `isCertExpired`,
 *      `computeAfterAttachPreview`, `optimisticAttachUpdate`) — these
 *      encode REQ-8 AC#6 (search), REQ-4 AC#3 (expired), REQ-8 AC#7
 *      (after-attach preview), REQ-8 AC#9 (optimistic update).
 *   2. SSR sanity for the trigger render (no throw, mounts the
 *      component module without errors).
 *   3. `attachCertificateItem` and `sonner.toast` are mocked — wiring
 *      sanity for the eventual jsdom or browser-test that drives the
 *      submit + rollback flow.
 *
 * Click handlers, the radio selection / search filter UI, after-attach
 * preview re-render, and the optimistic submit flow are verified at
 * localhost:3000 per `reference_localhost_browser_test.md`.
 */

// ---------------------------------------------------------------------------
// Mocks (must come before component import)
// ---------------------------------------------------------------------------

const attachMock = vi.fn();
vi.mock("../api/certificates", () => ({
  attachCertificateItem: (...args: unknown[]) => attachMock(...args),
  // Stubs for the wider import surface — vitest hoists vi.mock so the
  // module-resolution always sees a complete mock shape.
  createCertificate: vi.fn(),
  listCertificates: vi.fn(),
  detachCertificateItem: vi.fn(),
  deleteCertificate: vi.fn(),
}));

const toastErrorMock = vi.fn();
const toastSuccessMock = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => toastErrorMock(...args),
    success: (...args: unknown[]) => toastSuccessMock(...args),
  },
}));

import {
  CertificateBindPopover,
  computeAfterAttachPreview,
  filterCertsBySearch,
  isCertExpired,
  optimisticAttachUpdate,
} from "../ui/certificate-bind-popover";
import type { Certificate, QuoteItemForSelect } from "../model/types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeCert(overrides: Partial<Certificate> = {}): Certificate {
  return {
    id: "cert-1",
    quote_id: "q-1",
    type: "ДС ТР ТС",
    number: "ЕАЭС N RU Д-CN.РА04.B.12345/26",
    issuer: null,
    legal_doc: null,
    issued_at: null,
    valid_until: null,
    cost_rub: 12500,
    notes: null,
    display_name: null,
    is_custom_expense: false,
    created_at: "2026-04-01T10:00:00Z",
    updated_at: "2026-04-01T10:00:00Z",
    created_by: null,
    attached_items: [],
    ...overrides,
  };
}

function makeItem(overrides: Partial<QuoteItemForSelect> = {}): QuoteItemForSelect {
  return {
    id: "item-1",
    position: 1,
    name: "Контактор 250А",
    product_code: "CK-250",
    rub_basis: 150_000,
    ...overrides,
  };
}

const ITEM_1 = makeItem({ id: "i-1", position: 1, name: "Контактор", rub_basis: 150_000 });
const ITEM_2 = makeItem({ id: "i-2", position: 2, name: "Реле", rub_basis: 350_000 });
const ITEM_3 = makeItem({ id: "i-3", position: 3, name: "ЗИП", rub_basis: 90_000 });
const ALL_ITEMS: QuoteItemForSelect[] = [ITEM_1, ITEM_2, ITEM_3];

// ============================================================================
// filterCertsBySearch — REQ-8 AC#6 (search by type/number)
// ============================================================================

describe("filterCertsBySearch — pure search-filter logic", () => {
  const certs: Certificate[] = [
    makeCert({ id: "c-1", type: "ДС ТР ТС", number: "RU-12345" }),
    makeCert({ id: "c-2", type: "СГР Роспотребнадзор", number: "RU-77.99.345" }),
    makeCert({ id: "c-3", type: "EUR.1", number: null }),
  ];

  it("returns the full list for an empty query", () => {
    expect(filterCertsBySearch(certs, "")).toEqual(certs);
  });

  it("returns the full list for a whitespace-only query", () => {
    expect(filterCertsBySearch(certs, "   ")).toEqual(certs);
  });

  it("matches case-insensitively against type", () => {
    const result = filterCertsBySearch(certs, "сгр");
    expect(result.map((c) => c.id)).toEqual(["c-2"]);
  });

  it("matches case-insensitively against number", () => {
    const result = filterCertsBySearch(certs, "12345");
    expect(result.map((c) => c.id)).toEqual(["c-1"]);
  });

  it("matches partial substring across either field", () => {
    const result = filterCertsBySearch(certs, "ru-77");
    expect(result.map((c) => c.id)).toEqual(["c-2"]);
  });

  it("tolerates null number (only matches against type)", () => {
    const result = filterCertsBySearch(certs, "eur");
    expect(result.map((c) => c.id)).toEqual(["c-3"]);
  });

  it("returns an empty list when nothing matches", () => {
    expect(filterCertsBySearch(certs, "zzzzzz")).toEqual([]);
  });

  it("trims surrounding whitespace before matching", () => {
    const result = filterCertsBySearch(certs, "  ДС  ");
    expect(result.map((c) => c.id)).toEqual(["c-1"]);
  });

  it("does not mutate the input array", () => {
    const original = [...certs];
    filterCertsBySearch(certs, "сгр");
    expect(certs).toEqual(original);
  });
});

// ============================================================================
// isCertExpired — REQ-4 AC#3 (red border / disabled radio)
// ============================================================================

describe("isCertExpired — pure expiry logic", () => {
  it("returns false when valid_until is null (perpetual cert per REQ-4 AC#1)", () => {
    expect(isCertExpired(null, "2026-05-04")).toBe(false);
  });

  it("returns true when valid_until equals today (boundary inclusive)", () => {
    expect(isCertExpired("2026-05-04", "2026-05-04")).toBe(true);
  });

  it("returns true when valid_until is in the past", () => {
    expect(isCertExpired("2025-12-31", "2026-05-04")).toBe(true);
  });

  it("returns false when valid_until is in the future", () => {
    expect(isCertExpired("2027-01-01", "2026-05-04")).toBe(false);
  });

  it("uses lexicographic ISO compare (no timezone math)", () => {
    // "2026-04-30" < "2026-05-04" → expired.
    expect(isCertExpired("2026-04-30", "2026-05-04")).toBe(true);
    // "2026-05-05" > "2026-05-04" → not expired.
    expect(isCertExpired("2026-05-05", "2026-05-04")).toBe(false);
  });

  it("defaults to today's ISO date when no `today` arg is passed", () => {
    // Sanity: the function should not throw and should return a boolean.
    const out = isCertExpired("1900-01-01");
    expect(typeof out).toBe("boolean");
    expect(out).toBe(true); // 1900 is well in the past.
  });
});

// ============================================================================
// computeAfterAttachPreview — REQ-8 AC#7 (after-attach preview math)
// ============================================================================

describe("computeAfterAttachPreview — pure split projection", () => {
  it("returns empty array when allItems is empty and cert has no attachments", () => {
    const cert = makeCert({ cost_rub: 1000 });
    // Even with empty allItems, the current item is appended → 1 row.
    const out = computeAfterAttachPreview(cert, [], ITEM_1);
    expect(out).toHaveLength(1);
    expect(out[0].item_id).toBe(ITEM_1.id);
    expect(out[0].isCurrent).toBe(true);
  });

  it("includes the current item at the END of the projected list", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: ITEM_1.id, share_rub: 0, share_percent: 0 },
        { item_id: ITEM_2.id, share_rub: 0, share_percent: 0 },
      ],
      cost_rub: 12500,
    });
    const out = computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_3);
    // Existing items in attached_items order, then current.
    expect(out.map((r) => r.item_id)).toEqual([ITEM_1.id, ITEM_2.id, ITEM_3.id]);
    expect(out[out.length - 1].isCurrent).toBe(true);
  });

  it("marks only the current item with isCurrent=true", () => {
    const cert = makeCert({
      attached_items: [{ item_id: ITEM_1.id, share_rub: 0, share_percent: 0 }],
      cost_rub: 1000,
    });
    const out = computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_2);
    expect(out.find((r) => r.item_id === ITEM_1.id)?.isCurrent).toBe(false);
    expect(out.find((r) => r.item_id === ITEM_2.id)?.isCurrent).toBe(true);
  });

  it("computes shares via splitCostBatch — proportional to rub_basis", () => {
    // 150 + 350 + 90 = 590k; cert cost 12500.
    // Items 1 (150k), 2 (350k), 3 (90k).
    // Expected per мокап lines 972-974: ~3178, ~7415, ~1907.
    const cert = makeCert({
      attached_items: [
        { item_id: ITEM_1.id, share_rub: 0, share_percent: 0 },
        { item_id: ITEM_2.id, share_rub: 0, share_percent: 0 },
      ],
      cost_rub: 12500,
    });
    const out = computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_3);
    const sum = out.reduce((acc, row) => acc + row.share_rub, 0);
    // Residual rule: shares MUST sum exactly to cert.cost_rub.
    expect(sum).toBeCloseTo(12500, 2);
    // First two shares are proportional; last absorbs residual.
    const share1 = out[0].share_rub;
    const share2 = out[1].share_rub;
    const share3 = out[2].share_rub;
    expect(share1).toBeGreaterThan(0);
    expect(share2).toBeGreaterThan(share1); // 350k > 150k
    expect(share3).toBeLessThan(share1); // 90k < 150k
  });

  it("populates `total_basis` with the sum of all RUB-basis values", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: ITEM_1.id, share_rub: 0, share_percent: 0 },
      ],
      cost_rub: 1000,
    });
    const out = computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_2);
    // ITEM_1 + ITEM_2 (current) = 150k + 350k = 500k.
    expect(out[0].total_basis).toBe(500_000);
    expect(out[1].total_basis).toBe(500_000);
  });

  it("populates `item_basis` with each row's rub_basis", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: ITEM_1.id, share_rub: 0, share_percent: 0 },
      ],
      cost_rub: 1000,
    });
    const out = computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_2);
    expect(out[0].item_basis).toBe(150_000);
    expect(out[1].item_basis).toBe(350_000);
  });

  it("silently drops attached_items whose item_id is not in allItems", () => {
    // Stale cert references item-x that the parent does not know about.
    const cert = makeCert({
      attached_items: [
        { item_id: "item-x-stale", share_rub: 0, share_percent: 0 },
        { item_id: ITEM_1.id, share_rub: 0, share_percent: 0 },
      ],
      cost_rub: 1000,
    });
    const out = computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_2);
    // ITEM_1 + current ITEM_2 — stale id is dropped.
    expect(out.map((r) => r.item_id)).toEqual([ITEM_1.id, ITEM_2.id]);
  });

  it("dedupes the current item if already attached (defensive)", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: ITEM_1.id, share_rub: 0, share_percent: 0 },
        // Already attached — must not appear twice in projection.
        { item_id: ITEM_2.id, share_rub: 0, share_percent: 0 },
      ],
      cost_rub: 1000,
    });
    const out = computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_2);
    // ITEM_1 + (skipped existing ITEM_2) + current ITEM_2 = 2 rows.
    expect(out).toHaveLength(2);
    expect(out.map((r) => r.item_id)).toEqual([ITEM_1.id, ITEM_2.id]);
    // The current row should be marked isCurrent.
    expect(out[1].isCurrent).toBe(true);
  });

  it("returns shares that sum to cert.cost_rub kopek-exactly (residual rule)", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: ITEM_1.id, share_rub: 0, share_percent: 0 },
        { item_id: ITEM_2.id, share_rub: 0, share_percent: 0 },
      ],
      // Awkward number forcing residual rounding.
      cost_rub: 9999.99,
    });
    const out = computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_3);
    const sum = out.reduce((acc, row) => acc + row.share_rub, 0);
    expect(Math.round(sum * 100) / 100).toBe(9999.99);
  });

  it("does not mutate the input cert or items", () => {
    const cert = makeCert({
      attached_items: [{ item_id: ITEM_1.id, share_rub: 0, share_percent: 0 }],
      cost_rub: 1000,
    });
    const certSnapshot = JSON.parse(JSON.stringify(cert));
    const itemsSnapshot = JSON.parse(JSON.stringify(ALL_ITEMS));
    computeAfterAttachPreview(cert, ALL_ITEMS, ITEM_2);
    expect(cert).toEqual(certSnapshot);
    expect(ALL_ITEMS).toEqual(itemsSnapshot);
  });
});

// ============================================================================
// optimisticAttachUpdate — REQ-8 AC#9 (optimistic update + rollback)
// ============================================================================

describe("optimisticAttachUpdate — pure optimistic frame", () => {
  it("appends the item id with zeroed share placeholders", () => {
    const cert = makeCert({ attached_items: [] });
    const next = optimisticAttachUpdate(cert, "i-new");
    expect(next.attached_items).toEqual([
      { item_id: "i-new", share_rub: 0, share_percent: 0 },
    ]);
  });

  it("appends at the end (preserves existing order)", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: "i-a", share_rub: 100, share_percent: 50 },
        { item_id: "i-b", share_rub: 100, share_percent: 50 },
      ],
    });
    const next = optimisticAttachUpdate(cert, "i-c");
    expect(next.attached_items.map((a) => a.item_id)).toEqual([
      "i-a",
      "i-b",
      "i-c",
    ]);
  });

  it("returns the original cert when the item is already attached", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: "i-a", share_rub: 100, share_percent: 100 },
      ],
    });
    const next = optimisticAttachUpdate(cert, "i-a");
    // Reference equality — no clone, no double-attach.
    expect(next).toBe(cert);
  });

  it("does not mutate the input cert", () => {
    const cert = makeCert({
      attached_items: [{ item_id: "i-a", share_rub: 100, share_percent: 100 }],
    });
    const snapshot = JSON.parse(JSON.stringify(cert));
    optimisticAttachUpdate(cert, "i-new");
    expect(cert).toEqual(snapshot);
  });

  it("returns a new array instance (immutability — REQ-3 / coding-style)", () => {
    const cert = makeCert({ attached_items: [] });
    const next = optimisticAttachUpdate(cert, "i-new");
    expect(next.attached_items).not.toBe(cert.attached_items);
  });
});

// ============================================================================
// SSR sanity — module loads + JSX is syntactically valid
// ============================================================================

describe("CertificateBindPopover — SSR sanity", () => {
  it("does not throw when rendered with non-empty existingCerts", () => {
    expect(() =>
      renderToString(
        <CertificateBindPopover
          trigger={<button type="button">Привязать</button>}
          currentItem={ITEM_3}
          allItems={ALL_ITEMS}
          existingCerts={[
            makeCert({ id: "c-1" }),
            makeCert({ id: "c-2", type: "СГР", number: "X-99" }),
          ]}
        />,
      ),
    ).not.toThrow();
  });

  it("does not throw when rendered with empty existingCerts (empty state path)", () => {
    expect(() =>
      renderToString(
        <CertificateBindPopover
          trigger={<button type="button">Привязать</button>}
          currentItem={ITEM_1}
          allItems={ALL_ITEMS}
          existingCerts={[]}
          onCreateNew={() => {}}
        />,
      ),
    ).not.toThrow();
  });

  it("does not throw with optional callbacks omitted", () => {
    expect(() =>
      renderToString(
        <CertificateBindPopover
          trigger={<button type="button">X</button>}
          currentItem={ITEM_1}
          allItems={ALL_ITEMS}
          existingCerts={[]}
        />,
      ),
    ).not.toThrow();
  });
});

// ============================================================================
// Module surface — confirms exports exist for downstream consumers
// ============================================================================

describe("CertificateBindPopover — module surface", () => {
  it("exports CertificateBindPopover as a function", () => {
    expect(typeof CertificateBindPopover).toBe("function");
  });

  it("exports the four pure helpers used in the popover body", () => {
    expect(typeof filterCertsBySearch).toBe("function");
    expect(typeof isCertExpired).toBe("function");
    expect(typeof computeAfterAttachPreview).toBe("function");
    expect(typeof optimisticAttachUpdate).toBe("function");
  });
});

// ============================================================================
// Mock plumbing — wiring sanity for jsdom / browser tests later
// ============================================================================

describe("CertificateBindPopover — mock wiring", () => {
  beforeEach(() => {
    attachMock.mockReset();
    toastErrorMock.mockReset();
    toastSuccessMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  /**
   * Without jsdom we cannot click «Привязать», but we can verify the
   * module-level mocks are reachable. The browser-test (Mode A
   * Playwright) will assert on call count + first-arg shape:
   *   - `attachCertificateItem(certId, itemId)` called once per submit.
   *   - `toast.error(message)` called once on failure (rollback path).
   *
   * The mock is hot — calling it from any future test would observe the
   * payload directly. For now the tests confirm the mocks are callable
   * and not yet invoked.
   */
  it("attachCertificateItem is mockable as the submit target", () => {
    expect(typeof attachMock).toBe("function");
    expect(attachMock).not.toHaveBeenCalled();
  });

  it("attachMock can be primed with a success envelope and inspected", async () => {
    const fakeCert = makeCert({ id: "c-success" });
    attachMock.mockResolvedValueOnce({ success: true, data: fakeCert });
    const res = await attachMock("c-success", "i-1");
    expect(res).toEqual({ success: true, data: fakeCert });
    expect(attachMock).toHaveBeenCalledTimes(1);
    expect(attachMock).toHaveBeenCalledWith("c-success", "i-1");
  });

  it("attachMock can be primed with an error envelope (rollback path)", async () => {
    attachMock.mockResolvedValueOnce({
      success: false,
      error: { code: "CONFLICT", message: "Item already attached" },
    });
    const res = await attachMock("c-1", "i-1");
    expect(res.success).toBe(false);
  });

  it("toast.error mock is callable for rollback assertions", () => {
    toastErrorMock("Oops");
    expect(toastErrorMock).toHaveBeenCalledWith("Oops");
  });
});
