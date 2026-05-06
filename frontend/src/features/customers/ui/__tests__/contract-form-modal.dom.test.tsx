// @vitest-environment jsdom
/**
 * МОП-7 regression: the contract modal must accept a file attachment.
 *
 * Earlier shape supported only number/date/status/notes — РОП-test
 * step 5 reported «Файл нельзя добавить». This test covers:
 *
 *   1. The file input + «Выбрать файл» trigger render.
 *   2. After selecting a file, submitting the form calls
 *      `uploadCustomerDocument(customerId, file, "contract", description)`.
 *   3. Without a file, the upload helper is NOT called (no unwanted
 *      empty inserts into kvota.documents).
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const createContractMock = vi.fn();
const updateContractMock = vi.fn();
const uploadCustomerDocumentMock = vi.fn();

vi.mock("@/entities/customer/mutations", async () => {
  const actual = await vi.importActual<
    typeof import("@/entities/customer/mutations")
  >("@/entities/customer/mutations");
  return {
    ...actual,
    createContract: (...args: unknown[]) => createContractMock(...args),
    updateContract: (...args: unknown[]) => updateContractMock(...args),
    uploadCustomerDocument: (...args: unknown[]) =>
      uploadCustomerDocumentMock(...args),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

import { ContractFormModal } from "../contract-form-modal";

describe("ContractFormModal — file attachment (МОП-7)", () => {
  beforeEach(() => {
    createContractMock.mockReset();
    updateContractMock.mockReset();
    uploadCustomerDocumentMock.mockReset();
    createContractMock.mockResolvedValue({ id: "contract-1" });
    updateContractMock.mockResolvedValue(undefined);
    uploadCustomerDocumentMock.mockResolvedValue({
      id: "doc-1",
      original_filename: "contract.pdf",
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders a hidden file input and a «Выбрать файл» trigger", () => {
    render(
      <ContractFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
      />,
    );

    expect(screen.getByTestId("contract-file-pick")).toBeInTheDocument();
    expect(screen.getByTestId("contract-file-input")).toBeInTheDocument();
  });

  it("uploads the chosen file after creating the contract", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();

    render(
      <ContractFormModal
        open
        onClose={() => {}}
        onSaved={onSaved}
        customerId="cust-1"
      />,
    );

    // Fill the required field
    const numberField = screen.getByLabelText(/Номер договора/);
    await user.clear(numberField);
    await user.type(numberField, "Д-2026/077");

    // Pick a file
    const file = new File(["pdf-bytes"], "contract.pdf", {
      type: "application/pdf",
    });
    const fileInput = screen.getByTestId(
      "contract-file-input",
    ) as HTMLInputElement;
    await user.upload(fileInput, file);

    // The file pill replaces the trigger
    expect(screen.queryByTestId("contract-file-pick")).not.toBeInTheDocument();
    expect(screen.getByText(/contract\.pdf/)).toBeInTheDocument();

    // Submit
    await user.click(screen.getByRole("button", { name: /Сохранить/ }));

    await waitFor(() => {
      expect(createContractMock).toHaveBeenCalledTimes(1);
    });
    expect(createContractMock).toHaveBeenCalledWith(
      "cust-1",
      expect.objectContaining({ contract_number: "Д-2026/077" }),
    );

    await waitFor(() => {
      expect(uploadCustomerDocumentMock).toHaveBeenCalledTimes(1);
    });
    const [customerId, uploadedFile, docType, description] =
      uploadCustomerDocumentMock.mock.calls[0];
    expect(customerId).toBe("cust-1");
    expect(uploadedFile).toBeInstanceOf(File);
    expect((uploadedFile as File).name).toBe("contract.pdf");
    expect(docType).toBe("contract");
    expect(description).toContain("Д-2026/077");
  });

  it("does not call the upload helper when no file is chosen", async () => {
    const user = userEvent.setup();

    render(
      <ContractFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
      />,
    );

    await user.type(
      screen.getByLabelText(/Номер договора/),
      "Д-NO-FILE",
    );
    await user.click(screen.getByRole("button", { name: /Сохранить/ }));

    await waitFor(() => {
      expect(createContractMock).toHaveBeenCalledTimes(1);
    });
    expect(uploadCustomerDocumentMock).not.toHaveBeenCalled();
  });

  it("clears the pending file when the X button is clicked", async () => {
    const user = userEvent.setup();

    render(
      <ContractFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
      />,
    );

    const file = new File(["x"], "doc.pdf", { type: "application/pdf" });
    await user.upload(
      screen.getByTestId("contract-file-input") as HTMLInputElement,
      file,
    );
    expect(screen.getByText(/doc\.pdf/)).toBeInTheDocument();

    await user.click(screen.getByTestId("contract-file-clear"));
    expect(screen.queryByText(/doc\.pdf/)).not.toBeInTheDocument();
    expect(screen.getByTestId("contract-file-pick")).toBeInTheDocument();
  });
});
