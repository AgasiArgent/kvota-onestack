// @vitest-environment jsdom
/**
 * КПП «Файл КП поставщика» — supplier-offer file slot in the shared
 * <InvoiceFieldsForm>.
 *
 * Requirement (product owner): the file is OPTIONAL at create AND edit, but
 * MANDATORY to FINISH procurement (the backend complete-procurement gate
 * enforces that — MISSING_SUPPLIER_FILE / 422). This test pins the shared
 * field-form behaviour both the create modal and the edit card consume:
 *
 *   1. CREATE: picking a file stages it (onStagedFileChange) and shows its
 *      name; the field is never required to render/submit the form.
 *   2. EDIT: picking a file calls onUploadFile; an already-uploaded file shows
 *      its name with a remove affordance that calls onRemoveFile.
 *   3. The `error` slot (the completion 422) highlights the field (red border)
 *      AND surfaces the message — the no-silent-validation rule.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

// SearchableCombobox / geo comboboxes are portal/popover based — jsdom can't
// drive them. They're irrelevant to the file slot, so stub them to nothing.
vi.mock("@/shared/ui/searchable-combobox", () => ({
  SearchableCombobox: () => null,
}));
vi.mock("@/shared/ui/geo", async () => {
  const actual = await vi.importActual<typeof import("@/shared/ui/geo")>(
    "@/shared/ui/geo",
  );
  return {
    ...actual,
    CountryCombobox: () => null,
    CityAutocomplete: () => null,
  };
});
// The form's supplier-contact effect hits Supabase; with no supplier set it
// resolves to an empty list, but stub the client so nothing reaches network.
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({
        eq: () => ({ order: () => ({ order: () => Promise.resolve({ data: [], error: null }) }) }),
      }),
    }),
  }),
}));

import {
  InvoiceFieldsForm,
  type InvoiceFieldsValue,
} from "../invoice-fields-form";

const EMPTY_VALUE: InvoiceFieldsValue = {
  supplierId: null,
  buyerCompanyId: null,
  countryCode: null,
  city: "",
  pickupAddress: "",
  supplierContactId: null,
  incoterms: "",
  currency: "USD",
};

function pickFile(input: HTMLElement, name = "kp.pdf") {
  const file = new File(["dummy"], name, { type: "application/pdf" });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("InvoiceFieldsForm — supplier-offer file slot", () => {
  it("CREATE: stages the picked file and shows its name (optional, never blocks)", async () => {
    const onStagedFileChange = vi.fn();
    const { rerender } = render(
      <InvoiceFieldsForm
        mode="create"
        value={EMPTY_VALUE}
        onFieldSave={() => {}}
        suppliers={[]}
        buyerCompanies={[]}
        file={{ stagedFileName: null, onStagedFileChange }}
      />,
    );

    const input = screen.getByTestId("invoice-supplier-file-input");
    pickFile(input, "offer.pdf");

    expect(onStagedFileChange).toHaveBeenCalledTimes(1);
    expect(onStagedFileChange.mock.calls[0][0]).toBeInstanceOf(File);
    expect((onStagedFileChange.mock.calls[0][0] as File).name).toBe("offer.pdf");

    // Once the parent reflects the staged name, the form shows it.
    rerender(
      <InvoiceFieldsForm
        mode="create"
        value={EMPTY_VALUE}
        onFieldSave={() => {}}
        suppliers={[]}
        buyerCompanies={[]}
        file={{ stagedFileName: "offer.pdf", onStagedFileChange }}
      />,
    );
    expect(screen.getByText("offer.pdf")).toBeInTheDocument();
  });

  it("EDIT: picking a file calls onUploadFile", async () => {
    const onUploadFile = vi.fn();
    render(
      <InvoiceFieldsForm
        mode="edit"
        value={EMPTY_VALUE}
        onFieldSave={() => {}}
        suppliers={[]}
        buyerCompanies={[]}
        file={{ uploadedUrl: null, onUploadFile, onRemoveFile: () => {} }}
      />,
    );

    const input = screen.getByTestId("invoice-supplier-file-input");
    pickFile(input);
    expect(onUploadFile).toHaveBeenCalledTimes(1);
    expect((onUploadFile.mock.calls[0][0] as File).name).toBe("kp.pdf");
  });

  it("EDIT: an uploaded file shows its name and remove calls onRemoveFile", async () => {
    const onRemoveFile = vi.fn();
    render(
      <InvoiceFieldsForm
        mode="edit"
        value={EMPTY_VALUE}
        onFieldSave={() => {}}
        suppliers={[]}
        buyerCompanies={[]}
        file={{
          uploadedUrl: "https://example.test/invoices/inv-1/kp.pdf",
          onUploadFile: () => {},
          onRemoveFile,
        }}
      />,
    );

    expect(screen.getByText("kp.pdf")).toBeInTheDocument();
    fireEvent.click(
      screen.getByLabelText("Удалить файл КП поставщика"),
    );
    expect(onRemoveFile).toHaveBeenCalledTimes(1);
  });

  it("highlights the field and shows the message when the completion 422 error is set", async () => {
    render(
      <InvoiceFieldsForm
        mode="edit"
        value={EMPTY_VALUE}
        onFieldSave={() => {}}
        suppliers={[]}
        buyerCompanies={[]}
        file={{
          uploadedUrl: null,
          onUploadFile: () => {},
          onRemoveFile: () => {},
          error: "Загрузите файл КП поставщика перед завершением закупки",
        }}
      />,
    );

    // Message surfaced (named missing field).
    expect(
      screen.getByText(
        "Загрузите файл КП поставщика перед завершением закупки",
      ),
    ).toBeInTheDocument();
    // Field visually highlighted (red border) — no silent validation.
    const input = screen.getByTestId("invoice-supplier-file-input");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.className).toContain("border-destructive");
  });

  it("disables the picker while a save is in flight (busy)", async () => {
    render(
      <InvoiceFieldsForm
        mode="edit"
        value={EMPTY_VALUE}
        onFieldSave={() => {}}
        suppliers={[]}
        buyerCompanies={[]}
        file={{
          uploadedUrl: null,
          busy: true,
          onUploadFile: () => {},
          onRemoveFile: () => {},
        }}
      />,
    );
    await waitFor(() => {
      const input = screen.getByTestId(
        "invoice-supplier-file-input",
      ) as HTMLInputElement;
      expect(input.disabled).toBe(true);
    });
  });
});
