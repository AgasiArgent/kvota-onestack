import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

import {
  CertificateCoverageList,
  type AttachedCertView,
} from "../ui/certificate-coverage-list";
import type { Certificate } from "../model/types";

/**
 * Pure SSR rendering tests for CertificateCoverageList (Phase B Task 7e /
 * REQ-9). The frontend workspace has no jsdom configured (see
 * city-combobox.test.tsx for the rationale), so we use `react-dom/server`
 * to assert on markup. Click interactions are verified via localhost:3000
 * per `reference_localhost_browser_test.md` — but we DO assert prop
 * thread-through on `data-*` attributes the component sets.
 */

const NBSP = " ";

function makeCert(overrides: Partial<Certificate> = {}): Certificate {
  return {
    id: "cert-1",
    quote_id: "quote-1",
    type: "ДС ТР ТС",
    number: "EAEU-001",
    issuer: null,
    legal_doc: null,
    issued_at: null,
    valid_until: null,
    cost_rub: 12500,
    notes: null,
    display_name: null,
    is_custom_expense: false,
    created_at: "2026-05-01T10:00:00Z",
    updated_at: "2026-05-01T10:00:00Z",
    created_by: "user-1",
    attached_items: [],
    ...overrides,
  };
}

function makeAttached(
  cert: Certificate,
  share_rub: number,
  share_percent: number,
): AttachedCertView {
  return { cert, share_rub, share_percent };
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe("CertificateCoverageList — empty state", () => {
  it("renders nothing when attachedCerts is empty", () => {
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[]}
        totalQuoteItems={5}
        canUnbind={true}
      />,
    );
    // null render → empty string
    expect(html).toBe("");
  });
});

// ---------------------------------------------------------------------------
// Cert card (is_custom_expense=false)
// ---------------------------------------------------------------------------

describe("CertificateCoverageList — cert card", () => {
  it("renders emerald border for non-expense, non-expired cert", () => {
    const cert = makeCert();
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain("border-emerald-900");
    expect(html).toContain("bg-emerald-950/10");
    expect(html).not.toContain("border-red-900");
  });

  it("renders type badge + «Покрыта общим сертификатом» copy", () => {
    const cert = makeCert({ type: "ДС ТР ТС 010/2011" });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain("ДС ТР ТС 010/2011");
    expect(html).toContain("Покрыта общим сертификатом");
  });

  it("renders sub-row with number, share_rub, share_percent", () => {
    const cert = makeCert({ number: "EAEU-RU-001" });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain("EAEU-RU-001");
    // formatRub uses NBSP for thousand separators
    expect(html).toContain(`3${NBSP}750`);
    expect(html).toContain("30%");
  });

  it("includes proportional copy when itemRubBasis + totalRubBasis are passed", () => {
    const cert = makeCert();
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        itemRubBasis={150_000}
        totalRubBasis={500_000}
        canUnbind={true}
      />,
    );
    expect(html).toContain("пропорционально стоимости");
    expect(html).toContain(`150${NBSP}000`);
    expect(html).toContain(`500${NBSP}000`);
  });

  it("omits proportional copy when bases are not passed", () => {
    const cert = makeCert();
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).not.toContain("пропорционально стоимости");
  });

  it("renders «Открыть сертификат» footer button", () => {
    const cert = makeCert();
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain("Открыть сертификат");
  });
});

// ---------------------------------------------------------------------------
// Expired cert (RED border priority)
// ---------------------------------------------------------------------------

describe("CertificateCoverageList — expired (RED priority)", () => {
  it("uses red border when valid_until is in the past, overriding emerald", () => {
    const cert = makeCert({ valid_until: "2020-01-01" });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain("border-red-900");
    expect(html).toContain('data-expired="true"');
    // emerald MUST NOT bleed through
    expect(html).not.toContain("border-emerald-900");
  });

  it("treats valid_until=null as never-expired", () => {
    const cert = makeCert({ valid_until: null });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).not.toContain("border-red-900");
    expect(html).toContain('data-expired="false"');
  });

  it("renders «истёк {date}» hint when expired", () => {
    const cert = makeCert({ valid_until: "2020-06-15" });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain("истёк");
    expect(html).toContain("15.06.2020");
  });

  it("renders «действует до {date}» hint when not expired", () => {
    // Use a far future date so the test does not flake at year boundaries.
    const cert = makeCert({ valid_until: "2099-12-31" });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain("действует до");
    expect(html).toContain("31.12.2099");
  });
});

// ---------------------------------------------------------------------------
// Custom-expense card (gray)
// ---------------------------------------------------------------------------

describe("CertificateCoverageList — custom expense card", () => {
  it("renders gray border instead of emerald for is_custom_expense", () => {
    const cert = makeCert({
      is_custom_expense: true,
      type: "custom_expense",
      number: null,
      display_name: "Услуги декларанта",
    });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 5000, 25)]}
        totalQuoteItems={4}
        canUnbind={true}
      />,
    );
    expect(html).toContain("border-neutral-700");
    expect(html).not.toContain("border-emerald-900");
    expect(html).toContain('data-custom-expense="true"');
  });

  it("renders «Расход» badge + display_name", () => {
    const cert = makeCert({
      is_custom_expense: true,
      type: "custom_expense",
      display_name: "Услуги декларанта",
    });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 5000, 25)]}
        totalQuoteItems={4}
        canUnbind={true}
      />,
    );
    expect(html).toContain("Расход");
    expect(html).toContain("Услуги декларанта");
    // No cert-specific copy
    expect(html).not.toContain("Покрыта общим сертификатом");
  });

  it("renders «Подробнее» footer button (NOT «Открыть сертификат»)", () => {
    const cert = makeCert({
      is_custom_expense: true,
      type: "custom_expense",
      display_name: "Услуги декларанта",
    });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 5000, 25)]}
        totalQuoteItems={4}
        canUnbind={true}
      />,
    );
    expect(html).toContain("Подробнее");
    expect(html).not.toContain("Открыть сертификат");
  });

  it("omits the proportional copy on expense cards (REQ-9 AC#3)", () => {
    const cert = makeCert({
      is_custom_expense: true,
      type: "custom_expense",
      display_name: "Услуги декларанта",
    });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 5000, 25)]}
        totalQuoteItems={4}
        itemRubBasis={150_000}
        totalRubBasis={500_000}
        canUnbind={true}
      />,
    );
    expect(html).not.toContain("пропорционально стоимости");
  });
});

// ---------------------------------------------------------------------------
// Role-gated unbind
// ---------------------------------------------------------------------------

describe("CertificateCoverageList — role-gated unbind", () => {
  it("renders «Отвязать» when canUnbind=true", () => {
    const cert = makeCert();
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain("Отвязать");
  });

  it("hides «Отвязать» when canUnbind=false (read-only role)", () => {
    const cert = makeCert();
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={false}
      />,
    );
    expect(html).not.toContain("Отвязать");
    // The «Открыть сертификат» button is still there
    expect(html).toContain("Открыть сертификат");
  });

  it("hides «Отвязать» on expense cards too when canUnbind=false", () => {
    const cert = makeCert({
      is_custom_expense: true,
      type: "custom_expense",
      display_name: "Услуги декларанта",
    });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 5000, 25)]}
        totalQuoteItems={4}
        canUnbind={false}
      />,
    );
    expect(html).not.toContain("Отвязать");
  });
});

// ---------------------------------------------------------------------------
// Multiple cards stacked
// ---------------------------------------------------------------------------

describe("CertificateCoverageList — multiple cards", () => {
  it("renders one card per attached cert", () => {
    const certA = makeCert({ id: "a", number: "A-001" });
    const certB = makeCert({
      id: "b",
      is_custom_expense: true,
      type: "custom_expense",
      display_name: "Услуги декларанта",
    });
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[
          makeAttached(certA, 1000, 50),
          makeAttached(certB, 1000, 50),
        ]}
        totalQuoteItems={2}
        canUnbind={true}
      />,
    );
    // Both copies appear
    expect(html).toContain("A-001");
    expect(html).toContain("Услуги декларанта");
    // Two distinct cards (count occurrences of testid)
    const cards = html.match(/data-testid="certificate-coverage-card"/g);
    expect(cards).not.toBeNull();
    expect(cards!.length).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// Container testid for parent integration
// ---------------------------------------------------------------------------

describe("CertificateCoverageList — testid", () => {
  it("exposes data-testid on the container", () => {
    const cert = makeCert();
    const html = renderToString(
      <CertificateCoverageList
        itemId="item-1"
        attachedCerts={[makeAttached(cert, 3750, 30)]}
        totalQuoteItems={3}
        canUnbind={true}
      />,
    );
    expect(html).toContain('data-testid="certificate-coverage-list"');
    expect(html).toContain('data-testid="certificate-coverage-card"');
    expect(html).toContain('data-testid="cert-coverage-open-details"');
    expect(html).toContain('data-testid="cert-coverage-unbind"');
  });
});
