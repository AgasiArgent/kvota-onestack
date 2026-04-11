import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import {
  CityCombobox,
  fetchCitySearch,
  shouldIssueFetch,
  type CityComboboxValue,
  type CitySearchState,
} from "../city-combobox";

/**
 * The frontend workspace does not ship `@testing-library/react` or a DOM
 * environment (no jsdom / happy-dom). We therefore follow the same pattern as
 * `country-combobox.test.tsx`:
 *
 *   1. React's server renderer (`react-dom/server`) — asserts the trigger
 *      renders correctly in each state (placeholder, selected city,
 *      disabled).
 *   2. Pure helpers exported from the component module (`fetchCitySearch`,
 *      `shouldIssueFetch`) — carry the debounce gating and fetch logic,
 *      testable without a DOM. The component binds them to JSX state; testing
 *      the helpers covers the real behavior.
 *
 * Debounce timing and popover interaction (click-to-open, option select) are
 * verified via localhost:3000 in Phase 5e browser tests per
 * `reference_localhost_browser_test.md`.
 */

// ============================================================================
// Trigger rendering (SSR)
// ============================================================================

describe("CityCombobox — trigger rendering (SSR)", () => {
  it("renders the placeholder when value is null", () => {
    const html = renderToString(
      <CityCombobox value={null} onChange={() => {}} />,
    );
    expect(html).toContain("Начните печатать название города");
  });

  it("renders a custom placeholder when provided", () => {
    const html = renderToString(
      <CityCombobox
        value={null}
        onChange={() => {}}
        placeholder="Город отгрузки"
      />,
    );
    expect(html).toContain("Город отгрузки");
  });

  it("renders the selected city display when value is set", () => {
    const value: CityComboboxValue = {
      city: "Berlin",
      country_code: "DE",
      country_name_ru: "Германия",
      country_name_en: "Germany",
      display: "Berlin, Germany",
    };
    const html = renderToString(
      <CityCombobox value={value} onChange={() => {}} />,
    );
    expect(html).toContain("Berlin, Germany");
  });

  it("renders with disabled attribute when disabled is true", () => {
    const html = renderToString(
      <CityCombobox value={null} onChange={() => {}} disabled />,
    );
    expect(html).toMatch(/disabled/);
  });
});

// ============================================================================
// shouldIssueFetch — debounce gating logic (pure)
// ============================================================================

describe("shouldIssueFetch (pure gating logic)", () => {
  it("returns false for an empty query", () => {
    expect(shouldIssueFetch("", 2)).toBe(false);
  });

  it("returns false for a whitespace-only query", () => {
    expect(shouldIssueFetch("   ", 2)).toBe(false);
  });

  it("returns false when the query is shorter than minQueryLength", () => {
    expect(shouldIssueFetch("B", 2)).toBe(false);
  });

  it("returns true when the query meets minQueryLength", () => {
    expect(shouldIssueFetch("Be", 2)).toBe(true);
  });

  it("returns true when the query exceeds minQueryLength", () => {
    expect(shouldIssueFetch("Berlin", 2)).toBe(true);
  });

  it("respects a custom minQueryLength of 3", () => {
    expect(shouldIssueFetch("Be", 3)).toBe(false);
    expect(shouldIssueFetch("Ber", 3)).toBe(true);
  });

  it("trims surrounding whitespace before counting characters", () => {
    expect(shouldIssueFetch("  B  ", 2)).toBe(false);
    expect(shouldIssueFetch("  Be  ", 2)).toBe(true);
  });
});

// ============================================================================
// fetchCitySearch — server call + response normalization (pure async)
// ============================================================================

describe("fetchCitySearch (network + parse)", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("calls the /api/geo/cities/search endpoint with q and limit", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: [
          {
            city: "Berlin",
            country_code: "DE",
            country_name_ru: "Германия",
            country_name_en: "Germany",
            display: "Berlin, Germany",
          },
        ],
      }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    const result = await fetchCitySearch("Berlin", 10);

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("/api/geo/cities/search");
    expect(calledUrl).toContain("q=Berlin");
    expect(calledUrl).toContain("limit=10");

    // Forwards session cookie for legacy auth
    const init = mockFetch.mock.calls[0][1] as RequestInit | undefined;
    expect(init?.credentials).toBe("include");
  });

  it("returns the list on a successful response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: [
          {
            city: "Berlin",
            country_code: "DE",
            country_name_ru: "Германия",
            country_name_en: "Germany",
            display: "Berlin, Germany",
          },
          {
            city: "Stuttgart",
            country_code: "DE",
            country_name_ru: "Германия",
            country_name_en: "Germany",
            display: "Stuttgart, Germany",
          },
        ],
      }),
    }) as unknown as typeof fetch;

    const result = await fetchCitySearch("Be", 10);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toHaveLength(2);
      expect(result.data[0].city).toBe("Berlin");
    }
  });

  it("returns an empty-success result when the backend returns an empty array", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: [] }),
    }) as unknown as typeof fetch;

    const result = await fetchCitySearch("zzzzz", 10);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual([]);
    }
  });

  it("returns an error result on a non-OK HTTP response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ success: false, error: { code: "X" } }),
    }) as unknown as typeof fetch;

    const result = await fetchCitySearch("Berlin", 10);
    expect(result.ok).toBe(false);
  });

  it("returns an error result when fetch rejects (network error)", async () => {
    global.fetch = vi
      .fn()
      .mockRejectedValue(new Error("network down")) as unknown as typeof fetch;

    const result = await fetchCitySearch("Berlin", 10);
    expect(result.ok).toBe(false);
  });

  it("returns an error result when the backend payload is malformed", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: false, error: { code: "BOOM" } }),
    }) as unknown as typeof fetch;

    const result = await fetchCitySearch("Berlin", 10);
    expect(result.ok).toBe(false);
  });

  it("forwards an abort signal to the underlying fetch call", async () => {
    const mockFetch = vi.fn().mockImplementation((_url, init) => {
      const signal: AbortSignal | undefined = init?.signal;
      return new Promise((_resolve, reject) => {
        if (signal) {
          signal.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        }
      });
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    const controller = new AbortController();
    const pending = fetchCitySearch("Berlin", 10, controller.signal);
    controller.abort();

    const result = await pending;
    // Aborted fetch -> treated as error (or ignored by caller)
    expect(result.ok).toBe(false);
  });
});

// ============================================================================
// CityCombobox — component smoke (non-DOM)
// ============================================================================

describe("CityCombobox — onChange contract (non-DOM)", () => {
  it("is a React component that can be invoked with onChange", () => {
    const onChange = vi.fn<(next: CityComboboxValue | null) => void>();
    const element = <CityCombobox value={null} onChange={onChange} />;
    expect(() => renderToString(element)).not.toThrow();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("is a React component that can be invoked with onCountryChange", () => {
    const onChange = vi.fn<(next: CityComboboxValue | null) => void>();
    const onCountryChange = vi.fn<(code: string | null) => void>();
    const element = (
      <CityCombobox
        value={null}
        onChange={onChange}
        onCountryChange={onCountryChange}
      />
    );
    expect(() => renderToString(element)).not.toThrow();
    expect(onCountryChange).not.toHaveBeenCalled();
  });
});

// ============================================================================
// Type smoke — CitySearchState union
// ============================================================================

describe("CitySearchState type", () => {
  it("supports an idle state", () => {
    const s: CitySearchState = { kind: "idle" };
    expect(s.kind).toBe("idle");
  });

  it("supports a loading state", () => {
    const s: CitySearchState = { kind: "loading" };
    expect(s.kind).toBe("loading");
  });

  it("supports a success state with items", () => {
    const s: CitySearchState = {
      kind: "success",
      items: [
        {
          city: "Berlin",
          country_code: "DE",
          country_name_ru: "Германия",
          country_name_en: "Germany",
          display: "Berlin, Germany",
        },
      ],
    };
    expect(s.kind).toBe("success");
    if (s.kind === "success") {
      expect(s.items).toHaveLength(1);
    }
  });

  it("supports an error state", () => {
    const s: CitySearchState = { kind: "error" };
    expect(s.kind).toBe("error");
  });
});
