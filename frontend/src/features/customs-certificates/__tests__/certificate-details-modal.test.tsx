import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

import {
  CertificateDetailsBody,
  CertificateDetailsModal,
} from "../ui/certificate-details-modal";
import type { Certificate, QuoteItemForSelect } from "../model/types";

/**
 * Pure SSR rendering tests for CertificateDetailsModal (Phase B Task 7e /
 * REQ-9 AC#7). The frontend workspace has no jsdom — see
 * city-combobox.test.tsx for rationale — so we use `react-dom/server` to
 * assert markup.
 *
 * The shadcn `<Dialog>` component renders into a Portal at runtime, so
 * SSR yields an empty popup body. To still exercise our content we
 * render the exported `CertificateDetailsBody` directly — that's the
 * function that owns the field grid, audit row, and attachment table.
 * The `CertificateDetailsModal` wrapper itself is sanity-tested via
 * "renders without throwing when open=false / open=true" assertions.
 */

const NBSP = " ";

function makeCert(overrides: Partial<Certificate> = {}): Certificate {
  return {
    id: "cert-1",
    quote_id: "quote-1",
    type: "ДС ТР ТС",
    number: "EAEU-RU-001",
    issuer: "Орган РСТ",
    legal_doc: "ТР ТС 010/2011",
    issued_at: "2026-01-15",
    valid_until: "2029-01-15",
    cost_rub: 12500,
    notes: "Тестовое примечание",
    display_name: null,
    is_custom_expense: false,
    created_at: "2026-05-01T10:00:00Z",
    updated_at: "2026-05-01T10:00:00Z",
    created_by: "user-uuid-1",
    attached_items: [
      { item_id: "item-1", share_rub: 3750, share_percent: 30 },
      { item_id: "item-2", share_rub: 8750, share_percent: 70 },
    ],
    ...overrides,
  };
}

function makeItems(): QuoteItemForSelect[] {
  return [
    {
      id: "item-1",
      position: 1,
      name: "Cabel A12",
      product_code: "CB-A12",
      rub_basis: 150_000,
    },
    {
      id: "item-2",
      position: 2,
      name: "Cabel B34",
      product_code: "CB-B34",
      rub_basis: 350_000,
    },
  ];
}

// ---------------------------------------------------------------------------
// Modal wrapper sanity (Portal renders nothing in SSR)
// ---------------------------------------------------------------------------

describe("CertificateDetailsModal — module + closed-state (SSR sanity)", () => {
  it("exports as a function", () => {
    expect(typeof CertificateDetailsModal).toBe("function");
  });

  it("renders without throwing when open=false", () => {
    const html = renderToString(
      <CertificateDetailsModal
        open={false}
        onOpenChange={() => {}}
        cert={makeCert()}
        items={makeItems()}
      />,
    );
    expect(typeof html).toBe("string");
  });

  it("renders without throwing when open=true (portal still empty in SSR)", () => {
    const html = renderToString(
      <CertificateDetailsModal
        open={true}
        onOpenChange={() => {}}
        cert={makeCert()}
        items={makeItems()}
      />,
    );
    expect(typeof html).toBe("string");
  });
});

// ---------------------------------------------------------------------------
// Title
// ---------------------------------------------------------------------------

describe("CertificateDetailsBody — title", () => {
  it("renders the title from cert.type for non-expense", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert()}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("ДС ТР ТС");
  });

  it("renders title «Расход» for is_custom_expense=true", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({
          is_custom_expense: true,
          type: "custom_expense",
          display_name: "Услуги декларанта",
        })}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    // Title row replaced by «Расход»
    expect(html).toContain('data-testid="cert-details-title"');
    expect(html).toContain(">Расход<");
    // type "custom_expense" string MUST NOT leak as the title
    expect(html).not.toContain(">custom_expense<");
  });
});

// ---------------------------------------------------------------------------
// Read-only field grid (cert)
// ---------------------------------------------------------------------------

describe("CertificateDetailsBody — cert field grid", () => {
  it("renders all cert fields as read-only", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert()}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    // Field labels
    expect(html).toContain("Тип");
    expect(html).toContain("Номер");
    expect(html).toContain("Орган выдачи");
    expect(html).toContain("Регламент");
    expect(html).toContain("Дата выдачи");
    expect(html).toContain("Действует до");
    expect(html).toContain("Стоимость, ₽");
    // Values
    expect(html).toContain("EAEU-RU-001");
    expect(html).toContain("Орган РСТ");
    expect(html).toContain("ТР ТС 010/2011");
    expect(html).toContain("15.01.2026");
    expect(html).toContain("15.01.2029");
    expect(html).toContain(`12${NBSP}500`);
  });

  it("formats issued_at + valid_until via formatDateRussian", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({
          issued_at: "2026-01-15",
          valid_until: "2029-01-15",
        })}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("15.01.2026");
    expect(html).toContain("15.01.2029");
  });

  it("renders «—» for null fields gracefully", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({
          number: null,
          issuer: null,
          legal_doc: null,
          issued_at: null,
          valid_until: null,
          notes: null,
        })}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("—");
  });
});

// ---------------------------------------------------------------------------
// Read-only field grid (custom expense)
// ---------------------------------------------------------------------------

describe("CertificateDetailsBody — expense field grid", () => {
  it("renders display_name + cost_rub but NOT cert-only fields", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({
          is_custom_expense: true,
          type: "custom_expense",
          display_name: "Услуги декларанта",
          number: null,
          issuer: null,
          legal_doc: null,
          issued_at: null,
          valid_until: null,
        })}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("Название");
    expect(html).toContain("Услуги декларанта");
    expect(html).toContain("Сумма, ₽");
    // Cert-only field labels MUST be absent
    expect(html).not.toContain("Регламент");
    expect(html).not.toContain("Орган выдачи");
    expect(html).not.toContain("Действует до");
    expect(html).not.toContain("Дата выдачи");
  });
});

// ---------------------------------------------------------------------------
// Notes
// ---------------------------------------------------------------------------

describe("CertificateDetailsBody — notes", () => {
  it("renders notes block when notes is non-null", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({ notes: "Тестовое примечание" })}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("Примечание");
    expect(html).toContain("Тестовое примечание");
  });

  it("omits notes block when notes is null", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({ notes: null })}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).not.toContain('data-testid="cert-details-notes"');
  });
});

// ---------------------------------------------------------------------------
// Audit row (created_at + created_by)
// ---------------------------------------------------------------------------

describe("CertificateDetailsBody — audit row", () => {
  it("renders created_at formatted as DD.MM.YYYY", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({ created_at: "2026-05-01T10:00:00Z" })}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("01.05.2026");
  });

  it("renders raw created_by UUID when no resolver passed", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({ created_by: "user-uuid-xyz" })}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("user-uuid-xyz");
  });

  it("renders resolved email when resolver returns one", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({ created_by: "user-uuid-xyz" })}
        items={makeItems()}
        resolveCreatedBy={(id) =>
          id === "user-uuid-xyz" ? "ivan@example.com" : null
        }
        onClose={() => {}}
      />,
    );
    expect(html).toContain("ivan@example.com");
    expect(html).not.toContain("user-uuid-xyz");
  });

  it("renders «—» for created_by=null when resolver returns null", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert({ created_by: null })}
        items={makeItems()}
        resolveCreatedBy={() => null}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("—");
  });
});

// ---------------------------------------------------------------------------
// Attachment table
// ---------------------------------------------------------------------------

describe("CertificateDetailsBody — attachment table", () => {
  it("renders «Прикреплено к {N} позициям»", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: "item-1", share_rub: 3750, share_percent: 30 },
        { item_id: "item-2", share_rub: 8750, share_percent: 70 },
      ],
    });
    const html = renderToString(
      <CertificateDetailsBody
        cert={cert}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("Прикреплено к 2 позициям");
  });

  it("resolves item_id → «№N {name}» when items prop is supplied", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: "item-1", share_rub: 3750, share_percent: 30 },
      ],
    });
    const html = renderToString(
      <CertificateDetailsBody
        cert={cert}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("№1");
    expect(html).toContain("Cabel A12");
  });

  it("renders share_rub via formatRub with NBSP", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: "item-1", share_rub: 3750, share_percent: 30 },
      ],
    });
    const html = renderToString(
      <CertificateDetailsBody
        cert={cert}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain(`3${NBSP}750`);
    expect(html).toContain("30%");
  });

  it("falls back to UUID when items prop is omitted", () => {
    const cert = makeCert({
      attached_items: [
        { item_id: "uuid-orphan", share_rub: 100, share_percent: 100 },
      ],
    });
    const html = renderToString(
      <CertificateDetailsBody cert={cert} onClose={() => {}} />,
    );
    expect(html).toContain("uuid-orphan");
  });

  it("renders empty-table copy when attached_items is empty", () => {
    const cert = makeCert({ attached_items: [] });
    const html = renderToString(
      <CertificateDetailsBody
        cert={cert}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("Прикреплено к 0 позициям");
    expect(html).toContain("Нет привязанных позиций.");
  });
});

// ---------------------------------------------------------------------------
// Footer + read-only contract (no edit)
// ---------------------------------------------------------------------------

describe("CertificateDetailsBody — read-only contract", () => {
  it("renders «Закрыть» footer button", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert()}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("Закрыть");
  });

  it("does NOT render any input/textarea/select tags (REQ-9 AC#7 — no edit form)", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert()}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    // No edit fields — the spec is explicit (REQ-9 AC#7). Buttons are
    // allowed (footer Закрыть). HTML form inputs are not.
    expect(html).not.toMatch(/<input\b/);
    expect(html).not.toMatch(/<textarea\b/);
    expect(html).not.toMatch(/<select\b/);
  });

  it("does NOT render a «Сохранить» / «Save» button", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert()}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).not.toContain("Сохранить");
    expect(html).not.toContain(">Save<");
  });
});

// ---------------------------------------------------------------------------
// Testids
// ---------------------------------------------------------------------------

describe("CertificateDetailsBody — testids", () => {
  it("exposes data-testid for parent integration", () => {
    const html = renderToString(
      <CertificateDetailsBody
        cert={makeCert()}
        items={makeItems()}
        onClose={() => {}}
      />,
    );
    expect(html).toContain('data-testid="certificate-details-modal"');
    expect(html).toContain('data-testid="cert-details-fields"');
    expect(html).toContain('data-testid="cert-details-table"');
    expect(html).toContain('data-testid="cert-details-close"');
  });
});
