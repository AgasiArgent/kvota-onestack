// @vitest-environment jsdom
/**
 * Unit test for `preserveScroll`. Pins the contract that any caller can rely
 * on regardless of which post-mutation flow triggers a scroll reset:
 *
 *  1. snapshots window.scrollY before running `action`
 *  2. restores it via a two-rAF chain after the action settles
 *  3. no-ops when scrollY === 0 (no need to restore "the top")
 *  4. still restores when the action throws (finally block)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { preserveScroll } from "../scroll";

let rafQueue: Array<() => void> = [];
function flushRaf(): void {
  const q = rafQueue;
  rafQueue = [];
  q.forEach((fn) => fn());
}

beforeEach(() => {
  rafQueue = [];
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
    rafQueue.push(() => cb(performance.now()));
    return 0 as unknown as number;
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("preserveScroll", () => {
  it("restores window.scrollY after the action settles", async () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 480,
    });

    const action = vi.fn().mockResolvedValue(undefined);
    await preserveScroll(action);
    expect(action).toHaveBeenCalledTimes(1);

    // Two rAFs queued — drain both.
    flushRaf();
    flushRaf();

    expect(scrollToMock).toHaveBeenCalledTimes(1);
    const arg = scrollToMock.mock.calls[0][0] as ScrollToOptions;
    expect(arg.top).toBe(480);
    expect(arg.behavior).toBe("instant");
  });

  it("does not call scrollTo if the user was already at the top", async () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 0,
    });

    await preserveScroll(async () => undefined);
    flushRaf();
    flushRaf();

    expect(scrollToMock).not.toHaveBeenCalled();
  });

  it("still restores scroll when the action throws (finally branch)", async () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 240,
    });

    const action = vi.fn().mockRejectedValue(new Error("boom"));
    await expect(preserveScroll(action)).rejects.toThrow("boom");
    flushRaf();
    flushRaf();

    expect(scrollToMock).toHaveBeenCalledTimes(1);
    const arg = scrollToMock.mock.calls[0][0] as ScrollToOptions;
    expect(arg.top).toBe(240);
  });

  it("snapshots scrollY synchronously before the action runs", async () => {
    const scrollToMock = vi.fn();
    window.scrollTo = scrollToMock as unknown as typeof window.scrollTo;
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      writable: true,
      value: 600,
    });

    // The action moves scrollY (e.g. layout collapse during the awaited
    // server action would do this in production). `preserveScroll` must
    // remember the value BEFORE the action ran.
    const action = vi.fn().mockImplementation(async () => {
      Object.defineProperty(window, "scrollY", {
        configurable: true,
        value: 0,
      });
    });

    await preserveScroll(action);
    flushRaf();
    flushRaf();

    expect(scrollToMock).toHaveBeenCalledTimes(1);
    const arg = scrollToMock.mock.calls[0][0] as ScrollToOptions;
    expect(arg.top).toBe(600);
  });
});
