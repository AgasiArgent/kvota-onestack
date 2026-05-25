// @vitest-environment jsdom
/**
 * Testing 2 row 61 — inline editable «Комментарий для распределения» panel on
 * the sales step.
 *
 * Acceptance:
 *   - Renders an editable textarea with the canonical Russian label for
 *     sales-tier viewers (admin / sales / head_of_sales).
 *   - On blur, debounces and calls `updateDistributionComment` with the
 *     trimmed value (or null when blank).
 *   - For read-only viewers (procurement / logistics / customs) the
 *     component renders the comment as a static panel when it carries
 *     content, and renders nothing at all when empty.
 *
 * The component is a thin client wrapper around the
 * `updateDistributionComment` server action — we mock the action so we can
 * inspect call args without spinning up a server.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ---------------------------------------------------------------------------
// Mocks (hoisted by vi.mock before component import)
// ---------------------------------------------------------------------------

const updateMock = vi.fn();

vi.mock("@/entities/quote/server-actions", () => ({
  updateDistributionComment: (quoteId: string, comment: string | null) =>
    updateMock(quoteId, comment),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { DistributionCommentInline } from "../distribution-comment-inline";

afterEach(() => {
  cleanup();
  updateMock.mockReset();
});

// ---------------------------------------------------------------------------
// Tests — editable path
// ---------------------------------------------------------------------------

describe("DistributionCommentInline — editable path", () => {
  it("renders the textarea with the canonical Russian label for sales", () => {
    render(
      <DistributionCommentInline
        quoteId="q-1"
        initialValue={null}
        canEdit={true}
      />,
    );

    const editor = screen.getByTestId("distribution-comment-inline");
    expect(editor).toBeInTheDocument();
    expect(editor).toHaveTextContent("Комментарий для распределения");

    const ta = screen.getByLabelText(/Комментарий для распределения/i);
    expect(ta.tagName).toBe("TEXTAREA");
  });

  it("seeds the textarea with the existing distribution_comment value", () => {
    render(
      <DistributionCommentInline
        quoteId="q-1"
        initialValue="Срочно к Алейне"
        canEdit={true}
      />,
    );

    const ta = screen.getByLabelText(
      /Комментарий для распределения/i,
    ) as HTMLTextAreaElement;
    expect(ta.value).toBe("Срочно к Алейне");
  });

  it("calls updateDistributionComment on blur with the trimmed value", async () => {
    updateMock.mockResolvedValueOnce({ success: true, value: "Срочно к Алейне" });
    const user = userEvent.setup();

    render(
      <DistributionCommentInline
        quoteId="q-1"
        initialValue={null}
        canEdit={true}
      />,
    );

    const ta = screen.getByLabelText(/Комментарий для распределения/i);
    await user.type(ta, "  Срочно к Алейне  ");
    await user.tab(); // blur

    await waitFor(() => {
      expect(updateMock).toHaveBeenCalled();
    });
    expect(updateMock).toHaveBeenCalledWith("q-1", "Срочно к Алейне");
  });

  it("calls updateDistributionComment with null when the user clears the field", async () => {
    updateMock.mockResolvedValueOnce({ success: true, value: null });
    const user = userEvent.setup();

    render(
      <DistributionCommentInline
        quoteId="q-1"
        initialValue="Старый комментарий"
        canEdit={true}
      />,
    );

    const ta = screen.getByLabelText(/Комментарий для распределения/i);
    await user.clear(ta);
    await user.tab(); // blur

    await waitFor(() => {
      expect(updateMock).toHaveBeenCalled();
    });
    expect(updateMock).toHaveBeenCalledWith("q-1", null);
  });

  it("does not fire a redundant save when the user blurs without changes", async () => {
    const user = userEvent.setup();

    render(
      <DistributionCommentInline
        quoteId="q-1"
        initialValue="Старый комментарий"
        canEdit={true}
      />,
    );

    const ta = screen.getByLabelText(/Комментарий для распределения/i);
    // Focus + blur with no edits should be a no-op.
    ta.focus();
    await user.tab();

    // Small wait to let any debounce fire (shouldn't here — no change).
    await new Promise((r) => setTimeout(r, 50));

    expect(updateMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Tests — read-only path
// ---------------------------------------------------------------------------

describe("DistributionCommentInline — read-only path", () => {
  it("renders the value as a static panel for non-editor roles when present", () => {
    render(
      <DistributionCommentInline
        quoteId="q-1"
        initialValue="Через сертифицированного перевозчика"
        canEdit={false}
      />,
    );

    const block = screen.getByTestId("distribution-comment-inline-readonly");
    expect(block).toBeInTheDocument();
    expect(block).toHaveTextContent("Комментарий для распределения");
    expect(block).toHaveTextContent("Через сертифицированного перевозчика");
    // No textarea / editor surface in read-only mode.
    expect(
      screen.queryByTestId("distribution-comment-inline"),
    ).not.toBeInTheDocument();
  });

  it("renders nothing when read-only and the value is empty", () => {
    render(
      <DistributionCommentInline
        quoteId="q-1"
        initialValue={null}
        canEdit={false}
      />,
    );

    expect(
      screen.queryByTestId("distribution-comment-inline-readonly"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("distribution-comment-inline"),
    ).not.toBeInTheDocument();
  });

  it("renders nothing when read-only and the value is whitespace-only", () => {
    render(
      <DistributionCommentInline
        quoteId="q-1"
        initialValue="   "
        canEdit={false}
      />,
    );

    expect(
      screen.queryByTestId("distribution-comment-inline-readonly"),
    ).not.toBeInTheDocument();
  });
});
