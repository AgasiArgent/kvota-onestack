import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * jsdom-backed tests for CertificateModal EDIT mode (Phase B REQ-9 AC#7).
 *
 * The SSR-only `certificate-modal.test.tsx` cannot render the open modal
 * (base-ui `<Dialog>` portals into the DOM, which `react-dom/server` lacks),
 * so the actual pre-fill / submit / hidden-multi-select behaviour is verified
 * here under jsdom — mirroring the `*.dom.test.tsx` opt-in pattern
 * (`vitest.config.ts` "dom" project + `test-setup-jsdom.ts`).
 *
 * Verifies:
 *   1. With `editingCert` set + `open`, the form pre-fills every editable
 *      field from the cert.
 *   2. The position multi-select («Прикрепить к позициям») is HIDDEN in edit
 *      mode (fields-only scope).
 *   3. Submitting calls `updateCertificate(editingCert.id, input)` (NOT
 *      `createCertificate`) and fires `onUpdated` with the returned cert.
 */

const createMock = vi.fn();
const updateMock = vi.fn();
vi.mock("../api/certificates", () => ({
  createCertificate: (...args: unknown[]) => createMock(...args),
  updateCertificate: (...args: unknown[]) => updateMock(...args),
  listCertificates: vi.fn(),
  attachCertificateItem: vi.fn(),
  detachCertificateItem: vi.fn(),
  deleteCertificate: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

import { CertificateModal } from "../ui/certificate-modal";
import type { Certificate, QuoteItemForSelect } from "../model/types";

const ITEMS: QuoteItemForSelect[] = [
  { id: "item-a", position: 1, name: "Контактор 250А", product_code: "CK-250", rub_basis: 150_000 },
  { id: "item-b", position: 2, name: "Реле перегрузки", product_code: null, rub_basis: 90_000 },
];

const EDITING_CERT: Certificate = {
  id: "cert-1",
  quote_id: "quote-1",
  type: "ДС ТР ТС",
  number: "ЕАЭС N RU Д-CN.РА01.В.12345",
  issuer: "Сертэксперт ЦСМ",
  legal_doc: "ТР ТС 010/2011",
  issued_at: "2026-01-15",
  valid_until: "2027-01-14",
  cost_original: 18500,
  cost_currency: "RUB",
  cost_rub: 18500,
  notes: "Перевыпуск по сроку",
  display_name: null,
  is_custom_expense: false,
  created_at: "2026-01-15T10:00:00Z",
  updated_at: "2026-01-15T10:00:00Z",
  created_by: "user-1",
  attached_items: [],
};

describe("CertificateModal — EDIT mode (dom)", () => {
  beforeEach(() => {
    createMock.mockReset();
    updateMock.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the «Редактирование сертификата» title in edit mode", () => {
    render(
      <CertificateModal
        open
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        editingCert={EDITING_CERT}
        onUpdated={() => {}}
      />,
    );
    expect(screen.getByText("Редактирование сертификата")).toBeInTheDocument();
  });

  it("pre-fills every editable field from editingCert", () => {
    render(
      <CertificateModal
        open
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        editingCert={EDITING_CERT}
        onUpdated={() => {}}
      />,
    );

    // type — rendered as the Combobox trigger label.
    expect(screen.getByText("ДС ТР ТС")).toBeInTheDocument();
    // text/number/date fields — controlled inputs carry the cert values.
    expect(
      screen.getByDisplayValue("ЕАЭС N RU Д-CN.РА01.В.12345"),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("Сертэксперт ЦСМ")).toBeInTheDocument();
    expect(screen.getByDisplayValue("ТР ТС 010/2011")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2026-01-15")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2027-01-14")).toBeInTheDocument();
    expect(screen.getByDisplayValue("18500")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Перевыпуск по сроку")).toBeInTheDocument();
  });

  it("hides the position multi-select in edit mode (fields-only)", () => {
    render(
      <CertificateModal
        open
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        editingCert={EDITING_CERT}
        onUpdated={() => {}}
      />,
    );
    // The «Прикрепить к позициям» header only renders with the multi-select,
    // which is suppressed in edit mode.
    expect(screen.queryByText("Прикрепить к позициям")).not.toBeInTheDocument();
  });

  it("submitting calls updateCertificate(id, input) and fires onUpdated", async () => {
    const returned: Certificate = { ...EDITING_CERT, cost_original: 20000, cost_rub: 20000 };
    updateMock.mockResolvedValue({ success: true, data: returned });
    const onUpdated = vi.fn();

    render(
      <CertificateModal
        open
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        editingCert={EDITING_CERT}
        onUpdated={onUpdated}
      />,
    );

    fireEvent.click(screen.getByText("Сохранить"));

    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1));
    expect(createMock).not.toHaveBeenCalled();

    const [certId, input] = updateMock.mock.calls[0];
    expect(certId).toBe("cert-1");
    expect(input.type).toBe("ДС ТР ТС");
    expect(input.cost_original).toBe(18500);
    expect(input.cost_currency).toBe("RUB");
    // Positions are NOT part of the edit payload.
    expect(input).not.toHaveProperty("item_ids");
    expect(input).not.toHaveProperty("quote_id");

    await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(returned));
  });

  it("create mode still renders the multi-select and «Новый сертификат»", () => {
    render(
      <CertificateModal
        open
        onOpenChange={() => {}}
        quoteId="quote-1"
        items={ITEMS}
        onCreated={() => {}}
      />,
    );
    expect(screen.getByText("Новый сертификат")).toBeInTheDocument();
    expect(screen.getByText("Прикрепить к позициям")).toBeInTheDocument();
  });
});
