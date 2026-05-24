import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";

import { EMPTY_PROPOSAL } from "@/entities/kp-proposal";

// ---------------------------------------------------------------------------
// Mocks — toast + the Server Action wrapper.
// ---------------------------------------------------------------------------
vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

const { downloadKpPdfMock } = vi.hoisted(() => ({
  downloadKpPdfMock: vi.fn(),
}));
vi.mock("../api/render-pdf-action", () => ({
  downloadKpPdf: downloadKpPdfMock,
}));

import { toast } from "sonner";

import { DownloadKpPdfButton } from "./download-button";

afterEach(() => {
  cleanup();
  downloadKpPdfMock.mockReset();
  (toast.error as ReturnType<typeof vi.fn>).mockReset();
});

beforeEach(() => {
  // Sane default: stay pending forever unless a test overrides it. That
  // lets the "pending" assertion observe the spinner without races.
  downloadKpPdfMock.mockImplementation(() => new Promise(() => {}));
});

describe("DownloadKpPdfButton (dom)", () => {
  it("renders with the Russian label and default (enabled) state", () => {
    // Override the default forever-pending mock: don't fire the click here,
    // so we just observe the initial render.
    render(<DownloadKpPdfButton data={EMPTY_PROPOSAL} />);

    const button = screen.getByRole("button", { name: /Сохранить PDF/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it("disables the button and shows a spinner while pending", () => {
    render(<DownloadKpPdfButton data={EMPTY_PROPOSAL} />);
    const button = screen.getByRole("button", { name: /Сохранить PDF/i });

    fireEvent.click(button);

    // After click the pending state should kick in (mock never resolves).
    expect(button).toBeDisabled();
    // Spinner is the Loader2 svg — rendered with aria-hidden, look for the
    // animate-spin class which is unique to the spinner glyph.
    expect(button.querySelector(".animate-spin")).not.toBeNull();
  });

  it("calls toast.error with the mapped message on an error envelope", async () => {
    downloadKpPdfMock.mockResolvedValueOnce({
      ok: false,
      code: "RENDER_ERROR",
      message: "ignored",
      requestId: "req-xyz-9",
    });

    render(<DownloadKpPdfButton data={EMPTY_PROPOSAL} />);
    const button = screen.getByRole("button", { name: /Сохранить PDF/i });

    fireEvent.click(button);

    // Let the microtask queue + the transition settle.
    await vi.waitFor(() => {
      expect(toast.error).toHaveBeenCalledTimes(1);
    });

    expect(toast.error).toHaveBeenCalledWith(
      "Не удалось сгенерировать PDF, попробуйте ещё раз (ID: req-xyz-9)",
    );
  });
});
