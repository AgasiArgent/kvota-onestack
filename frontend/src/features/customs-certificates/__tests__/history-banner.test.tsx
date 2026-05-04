import React from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HistoryBanner } from "../ui/history-banner";
import type { HistoryCertMatch } from "../model/types";

/**
 * SSR rendering tests for HistoryBanner (Phase B Task 7f / REQ-5).
 *
 * The frontend workspace has no jsdom configured (see other customs tests),
 * so we use `react-dom/server` to assert markup. Click interactions are
 * verified via localhost:3000 per `reference_localhost_browser_test.md`.
 *
 * `formatRub` renders ru-RU with NBSP (U+00A0) thousand separators — the
 * `NBSP` constant matches the convention from `format-rub.test.ts` so a
 * regression toward regular spaces fails fast.
 */

const NBSP = " ";

function makeMatch(overrides: Partial<HistoryCertMatch> = {}): HistoryCertMatch {
  return {
    cert_id: "cert-uuid-1",
    type: "ДС ТР ТС",
    number: "EAEU-001",
    issuer: "Сертэксперт ЦСМ",
    legal_doc: "ТР ТС 010/2011",
    // Use noon-UTC timestamps to avoid TZ shifting the rendered day on
    // negative-offset CI runners (matches `format-date.test.ts` precedent).
    issued_at: "2026-04-23T12:00:00Z",
    valid_until: "2027-04-23T12:00:00Z",
    cost_rub: 12500,
    created_at: "2026-04-23T12:00:00Z",
    source_quote_id: "quote-other",
    source_item_id: "item-other",
    is_actual: true,
    ...overrides,
  };
}

describe("HistoryBanner — null match", () => {
  it("renders nothing when match is null", () => {
    const html = renderToString(<HistoryBanner match={null} />);
    // SSR of a `null`-returning component produces an empty string.
    expect(html).toBe("");
  });
});

describe("HistoryBanner — apply variant (is_actual=true)", () => {
  it("renders the apply copy with type, number, issued date, and cost", () => {
    const html = renderToString(<HistoryBanner match={makeMatch()} />);
    expect(html).toContain("Возможно подойдёт сертификат");
    expect(html).toContain("ДС ТР ТС");
    expect(html).toContain("№EAEU-001");
    // formatDateRussian transforms ISO → DD.MM.YYYY (issued_at).
    expect(html).toContain("23.04.2026");
    // formatRub renders 12 500 ₽ with NBSP between thousands.
    expect(html).toContain(`12${NBSP}500${NBSP}₽`);
  });

  it("uses blue tinted card classes for the apply variant", () => {
    const html = renderToString(<HistoryBanner match={makeMatch()} />);
    expect(html).toContain("border-blue-900");
    expect(html).toContain("bg-blue-950/20");
  });

  it("renders the «Применить» button", () => {
    const html = renderToString(<HistoryBanner match={makeMatch()} />);
    expect(html).toContain("Применить");
  });

  it("does NOT render the «Создать новый» button on apply variant", () => {
    const html = renderToString(<HistoryBanner match={makeMatch()} />);
    expect(html).not.toContain("Создать новый");
  });

  it("exposes data-variant=apply for downstream assertions", () => {
    const html = renderToString(<HistoryBanner match={makeMatch()} />);
    expect(html).toContain('data-variant="apply"');
  });

  it("omits the number fragment when match.number is null", () => {
    const html = renderToString(
      <HistoryBanner match={makeMatch({ number: null })} />,
    );
    // No `№` glyph should appear in the headline copy.
    expect(html).not.toContain("№");
  });
});

describe("HistoryBanner — create-new variant (is_actual=false)", () => {
  it("renders the expired copy with valid_until date and cost", () => {
    const html = renderToString(
      <HistoryBanner
        match={makeMatch({
          is_actual: false,
          valid_until: "2026-01-01T12:00:00Z",
          cost_rub: 8500,
        })}
      />,
    );
    expect(html).toContain("Прежний сертификат истёк");
    expect(html).toContain("01.01.2026");
    expect(html).toContain(`8${NBSP}500${NBSP}₽`);
  });

  it("uses amber tinted card classes for the create-new variant", () => {
    const html = renderToString(
      <HistoryBanner match={makeMatch({ is_actual: false })} />,
    );
    expect(html).toContain("border-amber-900");
    expect(html).toContain("bg-amber-950/20");
  });

  it("renders the «Создать новый» button", () => {
    const html = renderToString(
      <HistoryBanner match={makeMatch({ is_actual: false })} />,
    );
    expect(html).toContain("Создать новый");
  });

  it("does NOT render the «Применить» button on create-new variant", () => {
    const html = renderToString(
      <HistoryBanner match={makeMatch({ is_actual: false })} />,
    );
    expect(html).not.toContain("Применить");
  });

  it("does NOT use blue card classes in create-new variant", () => {
    const html = renderToString(
      <HistoryBanner match={makeMatch({ is_actual: false })} />,
    );
    expect(html).not.toContain("border-blue-900");
  });

  it("exposes data-variant=create-new for downstream assertions", () => {
    const html = renderToString(
      <HistoryBanner match={makeMatch({ is_actual: false })} />,
    );
    expect(html).toContain('data-variant="create-new"');
  });
});

describe("HistoryBanner — dismiss button", () => {
  it("always renders the «×» dismiss button with aria-label", () => {
    const htmlActual = renderToString(<HistoryBanner match={makeMatch()} />);
    expect(htmlActual).toContain('aria-label="Скрыть подсказку"');

    const htmlExpired = renderToString(
      <HistoryBanner match={makeMatch({ is_actual: false })} />,
    );
    expect(htmlExpired).toContain('aria-label="Скрыть подсказку"');
  });
});

describe("HistoryBanner — click callbacks (functional smoke)", () => {
  it("creates handlers without throwing when callbacks are omitted", () => {
    // Optional callbacks — component must guard with `?.` so SSR doesn't
    // crash when consumers omit `onApply` / `onCreateNew` / `onDismiss`.
    expect(() =>
      renderToString(<HistoryBanner match={makeMatch()} />),
    ).not.toThrow();
    expect(() =>
      renderToString(<HistoryBanner match={makeMatch({ is_actual: false })} />),
    ).not.toThrow();
  });
});

describe("HistoryBanner — testid for parent integration", () => {
  it("exposes data-testid for the section parent to query", () => {
    const html = renderToString(<HistoryBanner match={makeMatch()} />);
    expect(html).toContain('data-testid="customs-cert-history-banner"');
  });
});
