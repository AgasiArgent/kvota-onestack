import React from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CertificateCard } from "../ui/certificate-card";
import type { Certificate } from "../model/types";

/**
 * SSR rendering tests for `CertificateCard` (Phase B Task 7a).
 *
 * The frontend workspace has no jsdom configured (per `format-rub.test.ts`
 * + `history-banner.test.tsx` precedent), so we use `react-dom/server` to
 * assert markup. Click interactions are verified via localhost:3000 per
 * `reference_localhost_browser_test.md` — here we only verify that the
 * action buttons exist (or are absent) under the right role gate.
 */

const NBSP = " ";

function makeCert(overrides: Partial<Certificate> = {}): Certificate {
  return {
    id: "cert-1",
    quote_id: "quote-1",
    type: "ДС ТР ТС",
    number: "ЕАЭС N RU Д-CN.РА04.B.12345/26",
    issuer: "ЦСМ «Сертэксперт»",
    legal_doc: "ТР ТС 010/2011",
    issued_at: "2026-04-01",
    valid_until: "2027-04-12",
    cost_rub: 12_500,
    notes: null,
    display_name: null,
    is_custom_expense: false,
    created_at: "2026-04-22T10:00:00Z",
    updated_at: "2026-04-22T10:00:00Z",
    created_by: "user-1",
    attached_items: [
      { item_id: "item-1", share_rub: 3_750, share_percent: 30 },
      { item_id: "item-2", share_rub: 8_750, share_percent: 70 },
    ],
    ...overrides,
  };
}

describe("CertificateCard — content rendering", () => {
  it("renders the type badge", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("ДС ТР ТС");
    expect(html).toContain('data-testid="certificate-card-type"');
  });

  it("renders the number with the «№» prefix", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("№ЕАЭС N RU Д-CN.РА04.B.12345/26");
  });

  it("formats cost via formatRub (NBSP separators + ₽ suffix)", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain(`12${NBSP}500${NBSP}₽`);
  });

  it("renders the «N из M» counter", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("2 из 4 позиций");
  });

  it("renders valid_until via formatDateRussian (DD.MM.YYYY)", () => {
    // Note: `formatDateRussian` is timezone-aware (uses local-time getters),
    // so a bare `2027-04-12` ISO date can shift to `11.04.2027` on
    // negative-offset runners. We assert the regex for stability across CI
    // timezones; the day component is what mattered for the test scenario.
    const html = renderToString(
      <CertificateCard
        cert={makeCert()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toMatch(/Срок действия: \d{2}\.04\.2027/);
  });

  it("hides the valid_until row when the field is NULL", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({ valid_until: null })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).not.toContain('data-testid="certificate-card-valid-until"');
  });

  it("hides the «№» line when the certificate has no number", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({ number: null })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    // The badge with the type is always present — the number line is gone.
    expect(html).not.toMatch(/№<\/span>/);
  });
});

describe("CertificateCard — expired (REQ-4 AC#3)", () => {
  it("uses the destructive border + bg when valid_until is in the past", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({ valid_until: "2020-01-01" })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    // Match the container's exact class prefix to avoid colliding with the
    // shadcn button `aria-invalid:border-destructive` utility.
    expect(html).toContain("rounded-md border border-destructive");
    expect(html).toContain("bg-destructive/5");
  });

  it("does NOT render emerald classes when expired (visual priority)", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({ valid_until: "2020-01-01" })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).not.toContain("border-emerald-900");
    expect(html).not.toContain("bg-emerald-950/10");
  });

  it("renders the «(истёк)» suffix next to the date when expired", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({ valid_until: "2020-01-01" })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("(истёк)");
  });

  it("uses emerald classes for an actual (future) certificate", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({ valid_until: "2099-12-31" })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("border-emerald-900");
    expect(html).toContain("bg-emerald-950/10");
    // Container is NOT the destructive variant — but shadcn buttons emit
    // `aria-invalid:border-destructive` so we look for the container prefix.
    expect(html).not.toContain("rounded-md border border-destructive");
  });

  it("treats NULL valid_until as «бессрочный» — emerald, no «(истёк)»", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({ valid_until: null })}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain("border-emerald-900");
    expect(html).not.toContain("(истёк)");
  });
});

describe("CertificateCard — role-gated actions (REQ-9 AC#6)", () => {
  it("renders edit + delete buttons when canEdit=true", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert()}
        totalQuoteItems={4}
        canEdit
      />,
    );
    expect(html).toContain('data-testid="certificate-card-edit"');
    expect(html).toContain('data-testid="certificate-card-delete"');
    expect(html).toContain('aria-label="Редактировать сертификат"');
    expect(html).toContain('aria-label="Удалить сертификат"');
  });

  it("hides edit + delete buttons when canEdit=false", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert()}
        totalQuoteItems={4}
        canEdit={false}
      />,
    );
    expect(html).not.toContain('data-testid="certificate-card-edit"');
    expect(html).not.toContain('data-testid="certificate-card-delete"');
  });
});

describe("CertificateCard — counter math edge cases", () => {
  it("renders «0 из 5» when no items are attached", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({ attached_items: [] })}
        totalQuoteItems={5}
        canEdit
      />,
    );
    expect(html).toContain("0 из 5 позиций");
  });

  it("renders «3 из 3» when every position is covered", () => {
    const html = renderToString(
      <CertificateCard
        cert={makeCert({
          attached_items: [
            { item_id: "i1", share_rub: 100, share_percent: 33.33 },
            { item_id: "i2", share_rub: 100, share_percent: 33.33 },
            { item_id: "i3", share_rub: 100, share_percent: 33.34 },
          ],
        })}
        totalQuoteItems={3}
        canEdit
      />,
    );
    expect(html).toContain("3 из 3 позиций");
  });
});
