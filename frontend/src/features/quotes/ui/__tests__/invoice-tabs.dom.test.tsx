// @vitest-environment jsdom
/**
 * РОЛ Тест 07 #3.2 (cluster L-A, CRITICAL): clicks on КПП chips must
 * (a) fire onInvoiceChange and (b) reflect a visible selected state.
 *
 * Root cause of the original bug: the underlying tabs component was
 * migrated from Radix UI to Base UI without updating Tailwind selectors.
 * Radix marks the active trigger with `data-state="active"`; Base UI
 * uses `data-active` (no value). Earlier styles targeted
 * `data-[state=active]:*` and `data-[selected]:*` — neither matches a
 * Base UI active tab, so clicks fired but the selected state was
 * invisible. Logistician's workflow blocked.
 *
 * These tests lock both behaviours: the change callback fires AND
 * `data-active` lands on the new trigger.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { InvoiceTabs, type InvoiceTabItem } from "../invoice-tabs";

const ITEMS: InvoiceTabItem[] = [
  { id: "inv-a", displayName: "INV-001 · Shanghai Industries", status: "in_progress", subLabel: "5 поз" },
  { id: "inv-b", displayName: "INV-002 · Hangzhou Co", status: "pending", subLabel: "3 поз" },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("InvoiceTabs (РОЛ Тест 07 #3.2)", () => {
  it("fires onInvoiceChange when a different chip is clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(
      <InvoiceTabs
        invoices={ITEMS}
        activeInvoiceId="inv-a"
        onInvoiceChange={onChange}
      />,
    );

    const second = screen.getByRole("tab", { name: /INV-002/i });
    await user.click(second);

    expect(onChange).toHaveBeenCalledTimes(1);
    // Base UI's onValueChange signature is (value, eventDetails) — we only
    // care that the new invoice id arrived as the first argument.
    expect(onChange.mock.calls[0][0]).toBe("inv-b");
  });

  it("marks the active chip with data-active so Tailwind data-[active]:* selectors can target it", () => {
    render(
      <InvoiceTabs
        invoices={ITEMS}
        activeInvoiceId="inv-b"
        onInvoiceChange={vi.fn()}
      />,
    );

    const active = screen.getByRole("tab", { name: /INV-002/i });
    const inactive = screen.getByRole("tab", { name: /INV-001/i });

    // Base UI sets data-active="" on active triggers and omits the
    // attribute entirely on inactive ones — Tailwind `data-[active]:*`
    // selectors target this.
    expect(active.hasAttribute("data-active")).toBe(true);
    expect(inactive.hasAttribute("data-active")).toBe(false);
  });

  it("applies the active-state Tailwind classes via data-[active]:* selectors", () => {
    render(
      <InvoiceTabs
        invoices={ITEMS}
        activeInvoiceId="inv-b"
        onInvoiceChange={vi.fn()}
      />,
    );

    const active = screen.getByRole("tab", { name: /INV-002/i });
    // The trigger className must include `data-[active]:bg-card` or an
    // equivalent active-state Tailwind class. Earlier code used
    // `data-[state=active]:*` which never matched Base UI's data attr.
    // We assert the className text rather than computed style because
    // jsdom does not evaluate Tailwind utility classes.
    expect(active.className).toMatch(/data-\[active\]:/);
    expect(active.className).not.toMatch(/data-\[state=active\]:/);
  });
});
