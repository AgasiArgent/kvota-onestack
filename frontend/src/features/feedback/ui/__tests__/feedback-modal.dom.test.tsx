// @vitest-environment jsdom
/**
 * Testing 2 row 49 — «Форма обратной связи» restructure.
 *
 * The single «Описание» textarea is split into three labeled fields
 * (Что делал / Что ожидал получить / Что получил) plus a searchable «Тип»
 * selector. Required: «Что делал» + «Что получил»; «Что ожидал» is optional.
 *
 * These tests pin the contract:
 *  1. The Тип selector + all three labeled fields render.
 *  2. Submitting with the required fields empty flags them (no silent fail)
 *     and does NOT call submitFeedback.
 *  3. A valid submit sends the structured payload (steps_taken / expected_result
 *     / actual_result), with «Что ожидал» allowed to be empty.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

const submitFeedbackMock = vi.fn();

vi.mock("../../api/submitFeedback", () => ({
  submitFeedback: (...args: unknown[]) => submitFeedbackMock(...args),
}));

vi.mock("../../lib/debugContext", () => ({
  collectDebugContext: () => ({
    url: "https://kvotaflow.ru/quotes/1",
    title: "Quote 1",
  }),
  installErrorInterceptors: () => {},
}));

import { FeedbackModal } from "../FeedbackModal";

function renderModal() {
  return render(
    <FeedbackModal
      open
      onClose={() => {}}
      onScreenshotRequest={() => {}}
      onClearScreenshot={() => {}}
      onSetScreenshot={() => {}}
    />,
  );
}

afterEach(() => {
  cleanup();
  submitFeedbackMock.mockReset();
});

describe("FeedbackModal — structured fields (Testing 2 row 49)", () => {
  it("renders the Тип selector and all three labeled fields", () => {
    renderModal();

    expect(screen.getByLabelText("Тип обращения")).toBeInTheDocument();
    expect(screen.getByLabelText("Что делал *")).toBeInTheDocument();
    expect(screen.getByLabelText("Что ожидал получить")).toBeInTheDocument();
    expect(screen.getByLabelText("Что получил *")).toBeInTheDocument();
  });

  it("flags missing required fields and does not submit", async () => {
    renderModal();

    submitFeedbackMock.mockResolvedValue({ success: true, shortId: "FB-X" });

    // Submit with everything empty.
    fireEvent.submit(screen.getByLabelText("Что делал *").closest("form")!);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /Что делал.*Что получил/,
      );
    });
    expect(submitFeedbackMock).not.toHaveBeenCalled();

    // Both required textareas are marked invalid.
    expect(screen.getByLabelText("Что делал *")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByLabelText("Что получил *")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("submits the structured payload when required fields are filled", async () => {
    renderModal();
    submitFeedbackMock.mockResolvedValue({ success: true, shortId: "FB-OK" });

    fireEvent.change(screen.getByLabelText("Что делал *"), {
      target: { value: "Нажал кнопку" },
    });
    fireEvent.change(screen.getByLabelText("Что получил *"), {
      target: { value: "Ничего не произошло" },
    });
    // «Что ожидал» intentionally left empty — it is optional.

    fireEvent.submit(screen.getByLabelText("Что делал *").closest("form")!);

    await waitFor(() => {
      expect(submitFeedbackMock).toHaveBeenCalledTimes(1);
    });

    const payload = submitFeedbackMock.mock.calls[0][0];
    expect(payload).toMatchObject({
      feedbackType: "bug",
      stepsTaken: "Нажал кнопку",
      expectedResult: "",
      actualResult: "Ничего не произошло",
    });
  });
});
