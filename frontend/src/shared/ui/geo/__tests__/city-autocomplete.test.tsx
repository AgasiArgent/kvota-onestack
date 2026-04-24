import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import {
  CityAutocomplete,
  fetchCityAutocomplete,
  shouldIssueFetch,
  filterByCountryCode,
  type CityAutocompleteItem,
} from "../city-autocomplete";

/**
 * No DOM test runner is configured in this workspace (see
 * country-combobox.test.tsx and city-combobox.test.tsx for rationale).
 * We therefore cover CityAutocomplete via:
 *
 *   1. React server renderer — verifies the disabled/placeholder states
 *      render correctly for the common prop configurations.
 *   2. Pure helpers (`shouldIssueFetch`, `filterByCountryCode`,
 *      `fetchCityAutocomplete`) — carry the debounce, country-filter, and
 *      network logic, testable without a DOM.
 *
 * Popover interaction (click-to-open, option select) is verified via a
 * localhost:3000 browser test per reference_localhost_browser_test.md.
 */

// ============================================================================
// Trigger rendering (SSR)
// ============================================================================

describe("CityAutocomplete — render (SSR)", () => {
  it("renders the default placeholder when a country is selected", () => {
    const html = renderToString(
      <CityAutocomplete value="" onChange={() => {}} countryCode="RU" />,
    );
    expect(html).toContain("Начните печатать название города");
  });

  it("renders the hint placeholder when countryCode is null", () => {
    const html = renderToString(
      <CityAutocomplete value="" onChange={() => {}} countryCode={null} />,
    );
    expect(html).toContain("Выберите страну");
  });

  it("renders the disabled attribute when countryCode is null", () => {
    const html = renderToString(
      <CityAutocomplete value="" onChange={() => {}} countryCode={null} />,
    );
    expect(html).toMatch(/disabled/);
  });

  it("renders the disabled attribute when disabled prop is true", () => {
    const html = renderToString(
      <CityAutocomplete
        value=""
        onChange={() => {}}
        countryCode="RU"
        disabled
      />,
    );
    expect(html).toMatch(/disabled/);
  });

  it("renders the current value in the input", () => {
    const html = renderToString(
      <CityAutocomplete
        value="Москва"
        onChange={() => {}}
        countryCode="RU"
      />,
    );
    expect(html).toContain('value="Москва"');
  });

  it("renders a custom placeholder when provided and country is set", () => {
    const html = renderToString(
      <CityAutocomplete
        value=""
        onChange={() => {}}
        countryCode="RU"
        placeholder="Город поставщика"
      />,
    );
    expect(html).toContain("Город поставщика");
  });

  it("countryCode=null overrides a custom placeholder with the hint", () => {
    const html = renderToString(
      <CityAutocomplete
        value=""
        onChange={() => {}}
        countryCode={null}
        placeholder="Город поставщика"
      />,
    );
    expect(html).toContain("Выберите страну");
    expect(html).not.toContain("Город поставщика");
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
    expect(shouldIssueFetch("Mo", 2)).toBe(true);
  });

  it("trims surrounding whitespace before counting characters", () => {
    expect(shouldIssueFetch("  B  ", 2)).toBe(false);
    expect(shouldIssueFetch("  Be  ", 2)).toBe(true);
  });

  it("respects a custom minQueryLength of 3", () => {
    expect(shouldIssueFetch("Be", 3)).toBe(false);
    expect(shouldIssueFetch("Ber", 3)).toBe(true);
  });
});

// ============================================================================
// filterByCountryCode — client-side filter (pure)
// ============================================================================

describe("filterByCountryCode", () => {
  const berlin: CityAutocompleteItem = {
    city: "Berlin",
    country_code: "DE",
    country_name_ru: "Германия",
    country_name_en: "Germany",
    display: "Berlin, Germany",
  };
  const paris: CityAutocompleteItem = {
    city: "Paris",
    country_code: "FR",
    country_name_ru: "Франция",
    country_name_en: "France",
    display: "Paris, France",
  };
  const moscow: CityAutocompleteItem = {
    city: "Moscow",
    country_code: "RU",
    country_name_ru: "Россия",
    country_name_en: "Russia",
    display: "Moscow, Russia",
  };

  it("keeps only rows matching the given code", () => {
    const result = filterByCountryCode([berlin, paris, moscow], "DE");
    expect(result).toEqual([berlin]);
  });

  it("is case-insensitive on the input code", () => {
    const result = filterByCountryCode([berlin, paris, moscow], "de");
    expect(result).toEqual([berlin]);
  });

  it("is case-insensitive on the item's country_code", () => {
    const lowercased: CityAutocompleteItem = { ...berlin, country_code: "de" };
    const result = filterByCountryCode([lowercased, paris], "DE");
    expect(result).toEqual([lowercased]);
  });

  it("returns the input unchanged when the filter code is empty", () => {
    const input = [berlin, paris];
    expect(filterByCountryCode(input, "")).toEqual(input);
  });

  it("returns an empty list when no items match", () => {
    expect(filterByCountryCode([berlin, paris], "RU")).toEqual([]);
  });
});

// ============================================================================
// fetchCityAutocomplete — server call + response normalization
// ============================================================================

describe("fetchCityAutocomplete (network + parse)", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("calls /api/geo/cities/search with q, limit, and country_code", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: [
          {
            city: "Moscow",
            country_code: "RU",
            country_name_ru: "Россия",
            country_name_en: "Russia",
            display: "Moscow, Russia",
          },
        ],
      }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    const result = await fetchCityAutocomplete("Mo", "RU", 10);

    expect(mockFetch).toHaveBeenCalledOnce();
    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("/api/geo/cities/search");
    expect(calledUrl).toContain("q=Mo");
    expect(calledUrl).toContain("limit=10");
    expect(calledUrl).toContain("country_code=RU");
    expect(result.ok).toBe(true);
  });

  it("omits country_code from the URL when it is an empty string", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: [] }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    await fetchCityAutocomplete("Mo", "", 10);

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain("country_code=");
  });

  it("routes DaData for RU country (via backend)", async () => {
    // The backend is responsible for routing — we assert the param is
    // forwarded so the backend can dispatch to DaData.
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: [
          {
            city: "Москва",
            country_code: "RU",
            country_name_ru: "Россия",
            country_name_en: "Russia",
            display: "Москва",
          },
        ],
      }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    await fetchCityAutocomplete("Мос", "RU", 10);

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("country_code=RU");
  });

  it("routes HERE for non-RU country (via backend)", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: [] }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    await fetchCityAutocomplete("Ber", "DE", 10);

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("country_code=DE");
  });

  it("passes credentials=include to forward the session cookie", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: [] }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    await fetchCityAutocomplete("Be", "DE", 10);

    const init = mockFetch.mock.calls[0][1] as RequestInit | undefined;
    expect(init?.credentials).toBe("include");
  });

  it("returns ok=true with an empty array when backend returns []", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: [] }),
    }) as unknown as typeof fetch;

    const result = await fetchCityAutocomplete("zzzzz", "RU", 10);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual([]);
    }
  });

  it("returns ok=false on a non-OK HTTP response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ success: false }),
    }) as unknown as typeof fetch;

    const result = await fetchCityAutocomplete("Be", "DE", 10);
    expect(result.ok).toBe(false);
  });

  it("returns ok=false when the fetch itself rejects", async () => {
    global.fetch = vi
      .fn()
      .mockRejectedValue(new Error("network down")) as unknown as typeof fetch;

    const result = await fetchCityAutocomplete("Be", "DE", 10);
    expect(result.ok).toBe(false);
  });

  it("returns ok=false on malformed body (missing success)", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [] }),
    }) as unknown as typeof fetch;

    const result = await fetchCityAutocomplete("Be", "DE", 10);
    expect(result.ok).toBe(false);
  });

  it("forwards the abort signal to the underlying fetch call", async () => {
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
    const pending = fetchCityAutocomplete("Be", "DE", 10, controller.signal);
    controller.abort();

    const result = await pending;
    expect(result.ok).toBe(false);
  });
});

// ============================================================================
// EN input → RU display (integration between fetch + filter)
// ============================================================================

describe("fetchCityAutocomplete — EN input returns canonical RU display name", () => {
  const originalFetch = global.fetch;
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("HERE response includes RU country name; English input is sent verbatim", async () => {
    // Scenario: user types "Berlin" (English) with Germany selected. The
    // backend forwards to HERE which returns country names bilingually; the
    // frontend surfaces `country_name_ru` alongside the city label.
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
        ],
      }),
    }) as unknown as typeof fetch;

    const result = await fetchCityAutocomplete("Berlin", "DE", 10);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data[0].city).toBe("Berlin");
      expect(result.data[0].country_name_ru).toBe("Германия");
    }
  });
});

// ============================================================================
// Non-DOM component smoke
// ============================================================================

describe("CityAutocomplete — onChange contract (non-DOM)", () => {
  it("can be rendered with a countryCode prop without throwing", () => {
    const onChange = vi.fn<(next: string) => void>();
    const element = (
      <CityAutocomplete value="" onChange={onChange} countryCode="RU" />
    );
    expect(() => renderToString(element)).not.toThrow();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("can be rendered with a null countryCode without throwing", () => {
    const onChange = vi.fn<(next: string) => void>();
    const element = (
      <CityAutocomplete value="" onChange={onChange} countryCode={null} />
    );
    expect(() => renderToString(element)).not.toThrow();
    expect(onChange).not.toHaveBeenCalled();
  });
});
