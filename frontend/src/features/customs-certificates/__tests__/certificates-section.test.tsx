import React from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CertificatesSection } from "../ui/certificates-section";
import type { Certificate, QuoteItemForSelect } from "../model/types";

/**
 * SSR rendering tests for CertificatesSection (Phase B Task 7f / REQ-6).
 *
 * The frontend workspace has no jsdom configured, so we use
 * `react-dom/server` to assert markup. `useEffect` does not run in SSR —
 * tests therefore rely on the `initialCertificates` prop to seed the list,
 * which is the path Wave 4 Task 9 will use after server-side fetch.
 *
 * Click handlers (open modals, refresh) are integration-tested at
 * localhost:3000 per `reference_localhost_browser_test.md`.
 *
 * `formatRub` renders ru-RU with NBSP (U+00A0) thousand separators — match
 * exactly via the `NBSP` constant.
 */

const NBSP = " ";

function makeQuoteItem(
  overrides: Partial<QuoteItemForSelect> = {},
): QuoteItemForSelect {
  return {
    id: "item-1",
    position: 1,
    name: "Sample item",
    product_code: "SKU-1",
    rub_basis: 100_000,
    ...overrides,
  };
}

function makeCert(overrides: Partial<Certificate> = {}): Certificate {
  return {
    id: "cert-1",
    quote_id: "quote-1",
    type: "ДС ТР ТС",
    number: "EAEU-100",
    issuer: null,
    legal_doc: null,
    issued_at: null,
    // Far-future expiry so isCertExpired returns false in any test run.
    valid_until: "2099-12-31T12:00:00Z",
    cost_rub: 12500,
    notes: null,
    display_name: null,
    is_custom_expense: false,
    created_at: "2026-05-01T10:00:00Z",
    updated_at: "2026-05-01T10:00:00Z",
    created_by: null,
    attached_items: [
      { item_id: "item-1", share_rub: 12500, share_percent: 100 },
    ],
    ...overrides,
  };
}

function makeExpense(overrides: Partial<Certificate> = {}): Certificate {
  return makeCert({
    id: "expense-1",
    type: "custom_expense",
    is_custom_expense: true,
    display_name: "Услуги декларанта",
    valid_until: null,
    number: null,
    cost_rub: 5000,
    created_at: "2026-04-15T10:00:00Z",
    ...overrides,
  });
}

const ITEMS: QuoteItemForSelect[] = [
  makeQuoteItem({ id: "item-1", position: 1, name: "Item A" }),
  makeQuoteItem({ id: "item-2", position: 2, name: "Item B" }),
  makeQuoteItem({ id: "item-3", position: 3, name: "Item C" }),
];

describe("CertificatesSection — header + buttons", () => {
  it("renders the section title", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[]}
      />,
    );
    expect(html).toContain("Расходы по таможне");
  });

  it("renders both add buttons when canEdit=true", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[]}
      />,
    );
    expect(html).toContain("+ Добавить сертификат");
    expect(html).toContain("+ Добавить расход");
    expect(html).toContain('data-testid="customs-cert-add-button"');
    expect(html).toContain('data-testid="customs-expense-add-button"');
  });

  it("hides both add buttons when canEdit=false", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit={false}
        initialCertificates={[makeCert()]}
      />,
    );
    expect(html).not.toContain('data-testid="customs-cert-add-button"');
    expect(html).not.toContain('data-testid="customs-expense-add-button"');
    expect(html).not.toContain('data-testid="customs-cert-add-button-empty"');
  });
});

describe("CertificatesSection — empty state", () => {
  it("renders empty-state copy when initial list is empty and canEdit=true", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[]}
      />,
    );
    expect(html).toContain('data-testid="customs-cert-empty-state"');
    expect(html).toContain("Расходов нет");
    expect(html).toContain("Нажмите ➕ чтобы добавить сертификат или расход");
  });

  it("renders centered duplicate add buttons in empty state when canEdit=true", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[]}
      />,
    );
    expect(html).toContain('data-testid="customs-cert-add-button-empty"');
    expect(html).toContain('data-testid="customs-expense-add-button-empty"');
  });

  it("hides the centered duplicate buttons when canEdit=false", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit={false}
        initialCertificates={[]}
      />,
    );
    expect(html).toContain('data-testid="customs-cert-empty-state"');
    expect(html).not.toContain('data-testid="customs-cert-add-button-empty"');
  });

  it("does not render the empty state when certificates exist", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[makeCert()]}
      />,
    );
    expect(html).not.toContain('data-testid="customs-cert-empty-state"');
  });
});

describe("CertificatesSection — list rendering", () => {
  it("renders a cert card for is_custom_expense=false rows", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[makeCert()]}
      />,
    );
    expect(html).toContain('data-testid="customs-cert-card"');
    expect(html).toContain('data-cert-id="cert-1"');
    expect(html).toContain("ДС ТР ТС");
    expect(html).toContain("№EAEU-100");
    // Cost rendered via formatRub — NBSP separators.
    expect(html).toContain(`12${NBSP}500${NBSP}₽`);
    // Counter "1 из 3 позиций" (1 attached, 3 items in quote). React SSR
    // inserts <!-- --> comments between adjacent text nodes, so match the
    // numeric tokens via regex with optional comment whitespace.
    expect(html).toMatch(/1(?:<!-- -->)?\s*из\s*(?:<!-- -->)?3(?:<!-- -->)?\s*позиций/);
  });

  it("renders an expense card for is_custom_expense=true rows", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[makeExpense()]}
      />,
    );
    expect(html).toContain('data-testid="customs-expense-card"');
    expect(html).toContain("Расход");
    expect(html).toContain("Услуги декларанта");
    expect(html).toContain(`5${NBSP}000${NBSP}₽`);
  });

  it("does NOT render valid_until / type badge / number on expense card", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[makeExpense({ display_name: "Декларант X" })]}
      />,
    );
    // Expense card should NOT contain a date label "до" (valid_until).
    // The cert version uses "до DD.MM.YYYY" which wouldn't render here
    // because expense.valid_until is null and is_custom_expense=true.
    expect(html).not.toMatch(/до \d{2}\.\d{2}\.\d{4}/);
    // Expense card uses display_name, not type badge text "ДС ТР ТС".
    expect(html).not.toContain("ДС ТР ТС");
  });

  it("renders mixed list (cert + expense) in created_at DESC order", () => {
    const newer = makeCert({
      id: "cert-newer",
      created_at: "2026-05-15T10:00:00Z",
      number: "NEWER-1",
    });
    const older = makeExpense({
      id: "expense-older",
      created_at: "2026-04-01T10:00:00Z",
      display_name: "Older expense",
    });
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[older, newer]}
      />,
    );
    // Both cards present.
    expect(html).toContain("cert-newer");
    expect(html).toContain("expense-older");
    // Newer card appears before older in the rendered HTML (DESC sort).
    const idxNewer = html.indexOf("cert-newer");
    const idxOlder = html.indexOf("expense-older");
    expect(idxNewer).toBeLessThan(idxOlder);
    // List counter exposed for downstream tests.
    expect(html).toContain('data-cert-count="2"');
  });

  it("flags expired certs with data-expired=true and the destructive border", () => {
    const expired = makeCert({
      id: "cert-expired",
      valid_until: "2020-01-01T12:00:00Z",
    });
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[expired]}
      />,
    );
    expect(html).toContain('data-expired="true"');
    expect(html).toContain("border-destructive");
  });

  it("does not flag certs without valid_until as expired", () => {
    const perpetual = makeCert({
      id: "cert-perpetual",
      valid_until: null,
    });
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[perpetual]}
      />,
    );
    // Card present but flagged as not expired.
    expect(html).toContain('data-cert-id="cert-perpetual"');
    expect(html).toContain('data-expired="false"');
  });
});

describe("CertificatesSection — modal flag state", () => {
  it("starts with all modal flags closed", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[]}
      />,
    );
    expect(html).toContain('data-create-cert-open="false"');
    expect(html).toContain('data-create-expense-open="false"');
    expect(html).toContain('data-selected-cert-id=""');
  });

  it("exposes the section testid for downstream queries", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[]}
      />,
    );
    expect(html).toContain('data-testid="customs-certificates-section"');
  });
});

describe("CertificatesSection — initial fetch behaviour", () => {
  it("renders the loading placeholder when no initialCertificates is provided", () => {
    // useEffect does not run during SSR — the section starts in `null`
    // certs state, which renders the loading placeholder.
    const html = renderToString(
      <CertificatesSection quoteId="quote-1" items={ITEMS} canEdit />,
    );
    expect(html).toContain('data-testid="customs-cert-loading"');
    expect(html).toContain("Загрузка");
  });

  it("skips loading when initialCertificates prop is provided", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[]}
      />,
    );
    expect(html).not.toContain('data-testid="customs-cert-loading"');
  });
});
