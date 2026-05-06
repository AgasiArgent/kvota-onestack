// @vitest-environment jsdom
/**
 * МОП-8 regression: customer profile must expose a section for the
 * customer's «Уставные документы» (founding docs). Earlier shape only
 * rendered Договоры + КП/Спецификации tabs and skipped founding docs
 * entirely.
 *
 * This test locks:
 *   1. The «Уставные документы» section renders by testid.
 *   2. Its upload button is wired to the documents endpoint.
 *   3. A separate «Файлы договоров» section also renders (МОП-7
 *      attachments live here once the contract modal saves them).
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const uploadCustomerDocumentMock = vi.fn();
const deleteCustomerDocumentMock = vi.fn();

vi.mock("@/entities/customer/mutations", async () => {
  const actual = await vi.importActual<
    typeof import("@/entities/customer/mutations")
  >("@/entities/customer/mutations");
  return {
    ...actual,
    uploadCustomerDocument: (...args: unknown[]) =>
      uploadCustomerDocumentMock(...args),
    deleteCustomerDocument: (...args: unknown[]) =>
      deleteCustomerDocumentMock(...args),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import { TabDocuments } from "../tab-documents";

describe("TabDocuments — Уставные документы section (МОП-8)", () => {
  beforeEach(() => {
    uploadCustomerDocumentMock.mockReset();
    deleteCustomerDocumentMock.mockReset();
    uploadCustomerDocumentMock.mockResolvedValue({
      id: "doc-1",
      original_filename: "ustav.pdf",
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders both Уставные документы and Файлы договоров sections", () => {
    render(
      <TabDocuments
        customerId="cust-1"
        quotes={[]}
        specs={[]}
        contracts={[]}
        contractDocs={[]}
        foundingDocs={[]}
      />,
    );

    expect(screen.getByTestId("section-founding-docs")).toBeInTheDocument();
    expect(screen.getByTestId("section-contract-docs")).toBeInTheDocument();
    expect(screen.getByText("Уставные документы")).toBeInTheDocument();
  });

  it("shows an empty state when no founding docs are attached", () => {
    render(
      <TabDocuments
        customerId="cust-1"
        quotes={[]}
        specs={[]}
        contracts={[]}
        contractDocs={[]}
        foundingDocs={[]}
      />,
    );

    const section = screen.getByTestId("section-founding-docs");
    expect(section).toHaveTextContent("Нет уставных документов");
  });

  it("lists existing founding documents with file name and size", () => {
    render(
      <TabDocuments
        customerId="cust-1"
        quotes={[]}
        specs={[]}
        contracts={[]}
        contractDocs={[]}
        foundingDocs={[
          {
            id: "doc-1",
            storage_path: "customers/c1/founding_docs/x.pdf",
            original_filename: "ustav-2026.pdf",
            file_size_bytes: 102400,
            mime_type: "application/pdf",
            description: null,
            created_at: "2026-04-01T00:00:00Z",
          },
        ]}
      />,
    );

    const section = screen.getByTestId("section-founding-docs");
    expect(section).toHaveTextContent("ustav-2026.pdf");
    expect(section).toHaveTextContent("100 КБ"); // 102400 / 1024
  });

  it("uploads to founding_docs when clicking the section's upload trigger", async () => {
    const user = userEvent.setup();
    render(
      <TabDocuments
        customerId="cust-1"
        quotes={[]}
        specs={[]}
        contracts={[]}
        contractDocs={[]}
        foundingDocs={[]}
      />,
    );

    const file = new File(["pdf"], "ustav.pdf", { type: "application/pdf" });
    const input = screen.getByTestId(
      "upload-input-founding-docs",
    ) as HTMLInputElement;
    await user.upload(input, file);

    expect(uploadCustomerDocumentMock).toHaveBeenCalledTimes(1);
    const [customerId, uploadedFile, docType] =
      uploadCustomerDocumentMock.mock.calls[0];
    expect(customerId).toBe("cust-1");
    expect((uploadedFile as File).name).toBe("ustav.pdf");
    expect(docType).toBe("founding_docs");
  });

  it("uploads to contract type when using the contract-docs section", async () => {
    const user = userEvent.setup();
    render(
      <TabDocuments
        customerId="cust-1"
        quotes={[]}
        specs={[]}
        contracts={[]}
        contractDocs={[]}
        foundingDocs={[]}
      />,
    );

    const file = new File(["pdf"], "contract.pdf", {
      type: "application/pdf",
    });
    const input = screen.getByTestId(
      "upload-input-contract-docs",
    ) as HTMLInputElement;
    await user.upload(input, file);

    expect(uploadCustomerDocumentMock).toHaveBeenCalledTimes(1);
    const [, , docType] = uploadCustomerDocumentMock.mock.calls[0];
    expect(docType).toBe("contract");
  });
});
