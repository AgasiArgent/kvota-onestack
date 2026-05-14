// @vitest-environment jsdom
/**
 * Testing 2 row 11 — «Таможня завершена» silent failure.
 *
 * Pre-fix repro on prod: clicking the button after customs was already
 * marked complete produced an HTTP 422 with body
 *   {"success": false, "error": "Customs already completed"}
 * and no UI feedback. Three-part fix verified here:
 *
 *   Part 1 — `customsCompletedAt` prop disables the button up-front,
 *   so the silent-422 path is unreachable. Hovering surfaces a tooltip
 *   («Таможня по этому КП уже завершена.») via the existing
 *   formatDisabledReason / Tooltip wiring.
 *
 *   Part 2 (this batch) — when `customsCompletedAt` is set we replace
 *   the disabled-but-green Button with a static Badge. The disabled
 *   filled-success Button still read as "clickable/active" to testers,
 *   who clicked it and reported «горит, ничего не происходит». A Badge
 *   has no button affordance so the done state is unambiguous.
 *
 *   Part 3 — covered by `customs-step-error-toast.test.tsx`
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
  it("renders static «Таможня завершена» badge (no button) when customsCompletedAt is set", () => {
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

    // Button must NOT render — testers misread the disabled-but-green
    // button as clickable.
    expect(
      screen.queryByRole("button", { name: "Таможня завершена" }),
    ).toBeNull();

    // Badge replaces the button.
    const badge = screen.getByTestId("customs-completed-badge");
    expect(badge.textContent).toMatch(/Таможня завершена/);
    // Sanity: the Check icon is rendered inside the badge.
    expect(badge.querySelector("svg")).not.toBeNull();
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
    // No badge when the bar is still in "to do" state.
    expect(screen.queryByTestId("customs-completed-badge")).toBeNull();
  });

  it("does NOT expose an onClick handler via the completion badge", () => {
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

    // The badge is a plain <span>, not a button — clicking it must not
    // invoke onCompleteCustoms.
    const badge = screen.getByTestId("customs-completed-badge");
    (badge as HTMLElement).click();
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

    expect(
      screen.queryByRole("button", { name: "Таможня завершена" }),
    ).toBeNull();
    expect(screen.getByTestId("customs-completed-badge")).toBeTruthy();
  });
});
