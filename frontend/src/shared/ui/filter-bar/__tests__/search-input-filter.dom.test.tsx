// @vitest-environment jsdom
/**
 * SearchInputFilter — debounced URL-backed text search (Testing 2 row 66).
 *
 * Pins the contract:
 *  - the input renders with the requested placeholder
 *  - typing updates the LOCAL input value immediately
 *  - the parent `onChange` is NOT called synchronously — only after debounceMs
 *  - clear (✕) button drops the value to null without waiting for debounce
 *  - an external `value` change (e.g. URL reset from «Сбросить все») resyncs
 *    the visible input
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, act } from "@testing-library/react";

import { SearchInputFilter } from "../search-input-filter";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("SearchInputFilter — renders with placeholder + initial value", () => {
  it("uses the supplied placeholder when no value is set", () => {
    render(
      <SearchInputFilter
        value={null}
        onChange={() => {}}
        placeholder="Поиск по IDN…"
      />,
    );
    expect(screen.getByPlaceholderText("Поиск по IDN…")).toBeInTheDocument();
  });

  it("hydrates the visible input from the committed URL value", () => {
    render(
      <SearchInputFilter
        value="Q-202605"
        onChange={() => {}}
        placeholder="Поиск по IDN…"
      />,
    );
    const input = screen.getByPlaceholderText(
      "Поиск по IDN…",
    ) as HTMLInputElement;
    expect(input.value).toBe("Q-202605");
  });
});

describe("SearchInputFilter — debounced onChange (Testing 2 row 66)", () => {
  it("does not call onChange on the first keystroke — waits for the debounce", () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(
      <SearchInputFilter
        value={null}
        onChange={onChange}
        debounceMs={300}
        placeholder="Поиск по IDN…"
      />,
    );

    const input = screen.getByPlaceholderText(
      "Поиск по IDN…",
    ) as HTMLInputElement;

    act(() => {
      fireEvent.change(input, { target: { value: "Q" } });
    });

    // Local value updates synchronously…
    expect(input.value).toBe("Q");
    // …but the parent has NOT been notified yet.
    expect(onChange).not.toHaveBeenCalled();

    // Advance just under the debounce window — still no commit.
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(onChange).not.toHaveBeenCalled();

    // Cross the threshold — now the parent receives the trimmed value.
    act(() => {
      vi.advanceTimersByTime(2);
    });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith("Q");
  });

  it("collapses rapid keystrokes into a single onChange call", () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(
      <SearchInputFilter
        value={null}
        onChange={onChange}
        debounceMs={300}
        placeholder="Поиск по IDN…"
      />,
    );

    const input = screen.getByPlaceholderText(
      "Поиск по IDN…",
    ) as HTMLInputElement;

    // Three keystrokes within the debounce window.
    act(() => {
      fireEvent.change(input, { target: { value: "Q" } });
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    act(() => {
      fireEvent.change(input, { target: { value: "Q-2" } });
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    act(() => {
      fireEvent.change(input, { target: { value: "Q-202605" } });
    });

    // Nothing committed yet.
    expect(onChange).not.toHaveBeenCalled();

    // Settle the debounce.
    act(() => {
      vi.advanceTimersByTime(301);
    });

    // Exactly one commit, with the final value.
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith("Q-202605");
  });

  it("sends null when the input is cleared by typing (empty string)", () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    render(
      <SearchInputFilter
        value="Q-202605"
        onChange={onChange}
        debounceMs={300}
        placeholder="Поиск по IDN…"
      />,
    );

    const input = screen.getByPlaceholderText(
      "Поиск по IDN…",
    ) as HTMLInputElement;

    act(() => {
      fireEvent.change(input, { target: { value: "" } });
    });
    act(() => {
      vi.advanceTimersByTime(301);
    });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});

describe("SearchInputFilter — clear button", () => {
  it("clear ✕ button drops the value immediately (no debounce)", () => {
    const onChange = vi.fn();
    render(
      <SearchInputFilter
        value="Q-202605"
        onChange={onChange}
        placeholder="Поиск по IDN…"
      />,
    );

    const clearButton = screen.getByLabelText("Очистить поиск");
    fireEvent.click(clearButton);

    // The clear button is the synchronous reset path — fires once with null.
    expect(onChange).toHaveBeenCalledWith(null);

    // And the visible input is wiped.
    const input = screen.getByPlaceholderText(
      "Поиск по IDN…",
    ) as HTMLInputElement;
    expect(input.value).toBe("");
  });

  it("does not render the clear button when the input is empty", () => {
    render(
      <SearchInputFilter
        value={null}
        onChange={() => {}}
        placeholder="Поиск по IDN…"
      />,
    );

    expect(screen.queryByLabelText("Очистить поиск")).not.toBeInTheDocument();
  });
});

describe("SearchInputFilter — external URL reset re-syncs the visible input", () => {
  it("re-renders with the new committed value when the URL changes from outside", () => {
    const { rerender } = render(
      <SearchInputFilter
        value="Q-202605"
        onChange={() => {}}
        placeholder="Поиск по IDN…"
      />,
    );

    const input = screen.getByPlaceholderText(
      "Поиск по IDN…",
    ) as HTMLInputElement;
    expect(input.value).toBe("Q-202605");

    // Simulate «Сбросить все» — parent flushes the URL key, value becomes null.
    rerender(
      <SearchInputFilter
        value={null}
        onChange={() => {}}
        placeholder="Поиск по IDN…"
      />,
    );

    expect(input.value).toBe("");
  });
});
