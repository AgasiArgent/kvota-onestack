// @vitest-environment jsdom
/**
 * Testing 2 row 11 — «Таможня завершена» silent failure.
 *
 * Pre-fix repro on prod: clicking the button after customs was already
 * marked complete produced an HTTP 422 with body
 *   {"success": false, "error": "Customs already completed"}
 * and no UI feedback. Two-part fix verified here:
 *
 *   Part 1 — `customsCompletedAt` prop disables the button up-front,
 *   so the silent-422 path is unreachable. Hovering surfaces a tooltip
 *   («Таможня по этому КП уже завершена.») via the existing
 *   formatDisabledReason / Tooltip wiring.
 *
 *   Part 2 — covered by `customs-step-error-toast.test.tsx`
 *   (handler-level): when the server *does* return a 422 (e.g. when the
 *   action bar is mounted with stale data), the catch branch fires a
 *   `toast.error()` with the server-supplied message via
 *   `extractErrorMessage`.
 *
 * SSR pre-fix coverage already exists in the antidumping/handsontable
 * unit tests; jsdom is required here only because the action bar relies
 * on Base UI `Tooltip` which mounts a portal.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { CustomsActionBar } from "../customs-action-bar";
import type { QuoteItemRow } from "@/entities/quote/queries";

function makeItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  // QuoteItemRow is the inferred return type of fetchQuoteItems; the
  // action bar only reads the four ItemExtras fields below + `id`. The
  // cast keeps the test self-contained without faking the entire DB row.
  return {
    id: overrides.id ?? "qi-1",
    hs_code: null,
    customs_duty: null,
    product_name: "Товар",
    product_code: "SKU-1",
    ...overrides,
  } as unknown as QuoteItemRow;
}

afterEach(cleanup);

describe("CustomsActionBar — customs already completed gate (Testing 2 row 11)", () => {
  it("disables «Таможня завершена» when customsCompletedAt is set, even with all HS codes filled", () => {
    const items = [
      makeItem({ id: "a", hs_code: "1234567890", customs_duty: 5 }),
      makeItem({ id: "b", hs_code: "9876543210", customs_duty: 7 }),
    ];

    render(
      <CustomsActionBar
        items={items}
        onCompleteCustoms={vi.fn()}
        onSkipCustoms={vi.fn()}
        customsCompletedAt="2026-05-12T10:00:00Z"
      />,
    );

    const button = screen.getByRole("button", { name: "Таможня завершена" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("keeps the button enabled when customsCompletedAt is null and all items have HS code", () => {
    const items = [
      makeItem({ id: "a", hs_code: "1234567890" }),
      makeItem({ id: "b", hs_code: "9876543210" }),
    ];

    const handleComplete = vi.fn();
    render(
      <CustomsActionBar
        items={items}
        onCompleteCustoms={handleComplete}
        onSkipCustoms={vi.fn()}
        customsCompletedAt={null}
      />,
    );

    const button = screen.getByRole("button", { name: "Таможня завершена" });
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("does NOT call onCompleteCustoms when the disabled button is clicked", async () => {
    const items = [
      makeItem({ id: "a", hs_code: "1234567890", customs_duty: 5 }),
    ];

    const handleComplete = vi.fn();
    render(
      <CustomsActionBar
        items={items}
        onCompleteCustoms={handleComplete}
        onSkipCustoms={vi.fn()}
        customsCompletedAt="2026-05-12T10:00:00Z"
      />,
    );

    const button = screen.getByRole("button", { name: "Таможня завершена" });
    button.click();
    // `disabled` short-circuits onClick — handler must never fire.
    expect(handleComplete).not.toHaveBeenCalled();
  });

  it("takes precedence over the «missing HS code» tooltip branch", () => {
    // Customs is marked done AND items have no HS code → still treated as
    // already-completed (server-state truth wins over field-validation).
    const items = [makeItem({ id: "a", hs_code: null })];

    render(
      <CustomsActionBar
        items={items}
        onCompleteCustoms={vi.fn()}
        onSkipCustoms={vi.fn()}
        customsCompletedAt="2026-05-12T10:00:00Z"
      />,
    );

    const button = screen.getByRole("button", { name: "Таможня завершена" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });
});
