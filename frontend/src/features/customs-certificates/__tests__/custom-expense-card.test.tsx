import React from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CustomExpenseCard } from "../ui/custom-expense-card";
import type { Certificate } from "../model/types";

/**
 * SSR rendering tests for `CustomExpenseCard` (Phase B Task 7a).
 *
 * Same SSR-only pattern as `certificate-card.test.tsx` — the workspace has
 * no jsdom; click handler invocation is verified via localhost browser
 * tests per `reference_localhost_browser_test.md`.
 */

const NBSP = " ";

function makeExpense(overrides: Partial<Certificate> = {}): Certificate {
  return {
    id: "exp-1",
    quote_id: "quote-1",
    type: "custom_expense",
    number: null,
    issuer: null,
    legal_doc: null,
    issued_at: null,
    valid_until: null,
    cost_rub: 15_000,
    notes: "Срочная экспертиза",
    display_name: "Услуги декларанта",
    is_custom_expense: true,
    created_at: "2026-04-22T10:00:00Z",
    updated_at: "2026-04-22T10:00:00Z",
    created_by: "user-1",
    attached_items: [
      { item_id: "item-1", share_rub: 7_500, share_percent: 50 },
      { item_id: "item-2", share_rub: 7_500, share_percent: 50 },
    ],
    ...overrides,
  };
}

describe("CustomExpenseCard — content rendering", () => {
  it("renders the «Расход» badge (NOT a cert type)", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain('data-testid="custom-expense-card-badge"');
    expect(html).toContain("Расход");
  });

  it("renders display_name (NOT type/number/legal_doc)", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("Услуги декларанта");
    // Custom expense rows MUST NOT leak the artificial "custom_expense"
    // sentinel in the type slot.
    expect(html).not.toContain("custom_expense");
  });

  it("formats cost via formatRub (NBSP separators + ₽ suffix)", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain(`15${NBSP}000${NBSP}₽`);
  });

  it("renders the «N из M» counter", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("2 из 4 позиций");
  });

  it("uses gray-bordered token classes (NOT emerald or destructive)", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("border-slate-700");
    expect(html).toContain("bg-slate-950/10");
    expect(html).not.toContain("border-emerald-900");
    // Container's outer class is exact substring; aria-invalid utility on
    // buttons doesn't match this prefix — so this assertion is safe even
    // with shadcn `<Button>` rendering `aria-invalid:border-destructive`.
    expect(html).not.toContain("rounded-md border border-destructive");
  });

  it("renders empty display_name without leaking «null»", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense({ display_name: null })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).not.toContain(">null<");
  });
});

describe("CustomExpenseCard — fields explicitly absent (REQ-10 AC#3)", () => {
  it("does NOT render valid_until row even if upstream sends one", () => {
    // REQ-10 AC#3 — even if upstream serializer leaks a date, the card
    // for is_custom_expense rows must hide it.
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense({
          // The model says custom expenses do not carry valid_until,
          // but we defend the UI from a malformed payload anyway.
          valid_until: "2027-04-12",
        })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    // Regex covers TZ shift to "11.04.2027" on negative-offset CI runners.
    expect(html).not.toMatch(/\d{2}\.04\.2027/);
    expect(html).not.toContain("Срок действия");
  });

  it("does NOT render the «№» / number row even if upstream sends one", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense({ number: "FAKE-123" })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).not.toContain("FAKE-123");
  });

  it("does NOT render the «(истёк)» suffix — custom expenses don't expire", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense({ valid_until: "2020-01-01" })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).not.toContain("(истёк)");
  });
});

describe("CustomExpenseCard — role-gated actions (REQ-9 AC#6)", () => {
  it("renders edit + delete buttons when canEdit=true", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain('data-testid="custom-expense-card-edit"');
    expect(html).toContain('data-testid="custom-expense-card-delete"');
    expect(html).toContain('aria-label="Редактировать расход"');
    expect(html).toContain('aria-label="Удалить расход"');
  });

  it("hides edit + delete buttons when canEdit=false", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense()}
        totalQuoteItems={4}
        canEdit={false}
      />,
    );
    expect(html).not.toContain('data-testid="custom-expense-card-edit"');
    expect(html).not.toContain('data-testid="custom-expense-card-delete"');
  });
});

describe("CustomExpenseCard — counter math edge cases", () => {
  it("renders «0 из 5» when no items are attached", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense({ attached_items: [] })}
        totalQuoteItems={5}
        canEdit
      />,
    );
    expect(html).toContain("0 из 5 позиций");
  });

  it("renders «3 из 3» when every position is covered", () => {
    const html = renderToString(
      <CustomExpenseCard
        expense={makeExpense({
          attached_items: [
            { item_id: "i1", share_rub: 5000, share_percent: 33.33 },
            { item_id: "i2", share_rub: 5000, share_percent: 33.33 },
            { item_id: "i3", share_rub: 5000, share_percent: 33.34 },
          ],
        })}
        totalQuoteItems={3}
        canEdit
      />,
    );
    expect(html).toContain("3 из 3 позиций");
  });
});
