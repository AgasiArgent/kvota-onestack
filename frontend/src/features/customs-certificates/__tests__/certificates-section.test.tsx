import React from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CertificatesSection } from "../ui/certificates-section";
import type { Certificate, QuoteItemForSelect } from "../model/types";

/**
 * SSR rendering tests for CertificatesSection (Phase B Task 7f / REQ-6
 * + Wave 4 Task 9 — sibling-component + modal-mount wiring).
 *
 * The frontend workspace has no jsdom configured, so we use
 * `react-dom/server` to assert markup. `useEffect` does not run in SSR —
 * tests therefore rely on the `initialCertificates` prop to seed the list,
 * which is the path the parent `customs-step.tsx` uses after server-side
 * fetch.
 *
 * Click handlers (open modals, refresh) are integration-tested at
 * localhost:3000 per `reference_localhost_browser_test.md`. The SSR
 * tests below assert that the modal *mount points* are present and the
 * sibling card components are wired (their distinctive `data-testid`s
 * appear in the output) — full interaction flow is browser-only.
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
    // Far-future expiry so the expired branch never fires in stable tests.
    valid_until: "2099-12-31",
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

describe("CertificatesSection — list rendering via sibling components", () => {
  it("renders a CertificateCard for is_custom_expense=false rows", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[makeCert()]}
      />,
    );
    // Sibling-component testid (NOT the inline placeholder).
    expect(html).toContain('data-testid="certificate-card"');
    expect(html).toContain('data-testid="certificate-card-type"');
    expect(html).toContain("ДС ТР ТС");
    expect(html).toContain("№EAEU-100");
    // Cost rendered via formatRub — NBSP separators.
    expect(html).toContain(`12${NBSP}500${NBSP}₽`);
    // Counter "1 из 3 позиций" (1 attached, 3 items in quote).
    expect(html).toContain("1 из 3 позиций");
  });

  it("renders a CustomExpenseCard for is_custom_expense=true rows", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[makeExpense()]}
      />,
    );
    expect(html).toContain('data-testid="custom-expense-card"');
    expect(html).toContain('data-testid="custom-expense-card-badge"');
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
    // Expense card never shows the cert-only «Срок действия» row.
    expect(html).not.toContain("Срок действия");
    // Expense card uses `display_name`, not the cert «ДС ТР ТС» badge.
    expect(html).not.toContain("ДС ТР ТС");
    // Sibling testid mismatch — must be expense, not certificate.
    expect(html).not.toContain('data-testid="certificate-card-type"');
  });

  it("hides edit/delete buttons on cards when canEdit=false", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit={false}
        initialCertificates={[makeCert()]}
      />,
    );
    // Card itself still renders (read-only consumers must see the data).
    expect(html).toContain('data-testid="certificate-card"');
    // ...but the action buttons are absent.
    expect(html).not.toContain('data-testid="certificate-card-edit"');
    expect(html).not.toContain('data-testid="certificate-card-delete"');
  });

  it("renders edit + delete buttons on cards when canEdit=true", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[makeCert()]}
      />,
    );
    expect(html).toContain('data-testid="certificate-card-edit"');
    expect(html).toContain('data-testid="certificate-card-delete"');
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
    // Both cards present (search by their distinctive text).
    expect(html).toContain("NEWER-1");
    expect(html).toContain("Older expense");
    // Newer card appears before older in the rendered HTML (DESC sort).
    const idxNewer = html.indexOf("NEWER-1");
    const idxOlder = html.indexOf("Older expense");
    expect(idxNewer).toBeLessThan(idxOlder);
    // List counter exposed for downstream tests.
    expect(html).toContain('data-cert-count="2"');
  });

  it("uses the destructive border on expired certs (delegated to CertificateCard)", () => {
    const expired = makeCert({
      id: "cert-expired",
      valid_until: "2020-01-01",
    });
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[expired]}
      />,
    );
    // The sibling CertificateCard owns the expired branch — assert that the
    // section delegates rendering by checking for the card's destructive
    // container class (matches the prefix exactly to avoid false positives
    // on shadcn `aria-invalid:border-destructive` button utilities).
    expect(html).toContain("rounded-md border border-destructive");
  });
});

describe("CertificatesSection — modal mount points (Wave 4 Task 9)", () => {
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

  it("renders the deleting-id flag empty on initial render", () => {
    const html = renderToString(
      <CertificatesSection
        quoteId="quote-1"
        items={ITEMS}
        canEdit
        initialCertificates={[makeCert()]}
      />,
    );
    expect(html).toContain('data-deleting-id=""');
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
