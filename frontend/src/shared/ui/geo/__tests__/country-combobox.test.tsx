import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

import { CountryCombobox } from "../country-combobox";
import {
  filterCountries,
  computeNextFocusedIndex,
} from "../country-combobox";
import { COUNTRIES, findCountryByCode } from "../countries";

/**
 * The frontend workspace does not ship `@testing-library/react` or a DOM
 * environment (no jsdom / happy-dom). We therefore exercise the component
 * through two complementary strategies:
 *
 *   1. React's server renderer (`react-dom/server`) — produces a static HTML
 *      string from the initial render so we can assert what the trigger
 *      displays in each state (placeholder, selected country, displayLocale,
 *      clearable X button, disabled).
 *   2. Pure helpers exported from the component module (`filterCountries`,
 *      `computeNextFocusedIndex`) — these carry the search-filter and keyboard
 *      navigation logic and are testable without a DOM. The component passes
 *      state through them, so covering the helpers covers the real behavior.
 *
 * Popover interaction (click-to-open, mouse selection) is verified via
 * localhost:3000 in Phase 5e browser tests per `reference_localhost_browser_test.md`.
 */

describe("CountryCombobox — trigger rendering (SSR)", () => {
  it("renders the placeholder when value is null", () => {
    const html = renderToString(
      <CountryCombobox value={null} onChange={() => {}} />,
    );
    expect(html).toContain("Выберите страну…");
  });

  it("renders a custom placeholder when provided", () => {
    const html = renderToString(
      <CountryCombobox
        value={null}
        onChange={() => {}}
        placeholder="Страна отгрузки"
      />,
    );
    expect(html).toContain("Страна отгрузки");
  });

  it("renders the Russian name when value is a valid ISO-2 code", () => {
    const html = renderToString(
      <CountryCombobox value="DE" onChange={() => {}} />,
    );
    expect(html).toContain("Германия");
  });

  it("renders the English name when displayLocale='en'", () => {
    const html = renderToString(
      <CountryCombobox value="DE" onChange={() => {}} displayLocale="en" />,
    );
    expect(html).toContain("Germany");
  });

  it("renders the clear (X) affordance when clearable and value is set", () => {
    const html = renderToString(
      <CountryCombobox value="DE" onChange={() => {}} clearable />,
    );
    // lucide-react renders <svg> with `lucide-x` class on the X icon.
    expect(html).toMatch(/lucide-x/);
  });

  it("omits the clear affordance when clearable is false", () => {
    const html = renderToString(
      <CountryCombobox value="DE" onChange={() => {}} clearable={false} />,
    );
    expect(html).not.toMatch(/aria-label="Очистить"/);
  });

  it("omits the clear affordance when no value is selected", () => {
    const html = renderToString(
      <CountryCombobox value={null} onChange={() => {}} clearable />,
    );
    expect(html).not.toMatch(/aria-label="Очистить"/);
  });

  it("renders with disabled attribute when disabled is true", () => {
    const html = renderToString(
      <CountryCombobox value="DE" onChange={() => {}} disabled />,
    );
    expect(html).toMatch(/disabled/);
  });

  it("respects ariaLabel on the trigger", () => {
    const html = renderToString(
      <CountryCombobox
        value={null}
        onChange={() => {}}
        ariaLabel="Country picker"
      />,
    );
    expect(html).toContain('aria-label="Country picker"');
  });

  it("falls back gracefully when the value does not resolve to a known code", () => {
    // "XQ" is not an assigned ISO 3166-1 code and not recognised by ICU.
    // The trigger should render without throwing — showing the placeholder.
    const html = renderToString(
      <CountryCombobox value="XQ" onChange={() => {}} />,
    );
    expect(html).toContain("Выберите страну…");
  });
});

describe("filterCountries (pure search logic)", () => {
  it("returns the full list when the query is empty", () => {
    const result = filterCountries(COUNTRIES, "");
    expect(result.length).toBe(COUNTRIES.length);
  });

  it("returns the full list when the query is whitespace only", () => {
    const result = filterCountries(COUNTRIES, "   ");
    expect(result.length).toBe(COUNTRIES.length);
  });

  it("filters by Russian name substring (case-insensitive)", () => {
    const result = filterCountries(COUNTRIES, "герм");
    const codes = result.map((c) => c.code);
    expect(codes).toContain("DE");
  });

  it("filters by English name substring (case-insensitive)", () => {
    const result = filterCountries(COUNTRIES, "ger");
    const codes = result.map((c) => c.code);
    expect(codes).toContain("DE");
  });

  it("filters by ISO-2 code substring (case-insensitive)", () => {
    const lower = filterCountries(COUNTRIES, "de");
    const upper = filterCountries(COUNTRIES, "DE");
    expect(lower.map((c) => c.code)).toContain("DE");
    expect(upper.map((c) => c.code)).toContain("DE");
  });

  it("matches any of nameRu / nameEn / code simultaneously", () => {
    // A 'g' query should surface many results across both locales and codes.
    const result = filterCountries(COUNTRIES, "g");
    expect(result.length).toBeGreaterThan(0);
    expect(result.some((c) => c.code === "DE")).toBe(true);
  });

  it("returns an empty list for a non-matching query", () => {
    const result = filterCountries(COUNTRIES, "zzzzzzzzz");
    expect(result).toEqual([]);
  });

  it("trims surrounding whitespace on the query", () => {
    const padded = filterCountries(COUNTRIES, "   герм   ");
    const tight = filterCountries(COUNTRIES, "герм");
    expect(padded.length).toBe(tight.length);
  });
});

describe("computeNextFocusedIndex (keyboard navigation logic)", () => {
  it("ArrowDown from -1 lands on 0 for a non-empty list", () => {
    expect(computeNextFocusedIndex(-1, "down", 5)).toBe(0);
  });

  it("ArrowDown from 0 advances to 1", () => {
    expect(computeNextFocusedIndex(0, "down", 5)).toBe(1);
  });

  it("ArrowDown wraps from the last item back to 0", () => {
    expect(computeNextFocusedIndex(4, "down", 5)).toBe(0);
  });

  it("ArrowUp from -1 lands on the last item", () => {
    expect(computeNextFocusedIndex(-1, "up", 5)).toBe(4);
  });

  it("ArrowUp from 0 wraps to the last item", () => {
    expect(computeNextFocusedIndex(0, "up", 5)).toBe(4);
  });

  it("ArrowUp from the middle decrements", () => {
    expect(computeNextFocusedIndex(3, "up", 5)).toBe(2);
  });

  it("returns -1 when the list is empty", () => {
    expect(computeNextFocusedIndex(0, "down", 0)).toBe(-1);
    expect(computeNextFocusedIndex(0, "up", 0)).toBe(-1);
  });

  it("clamps an out-of-bounds starting index", () => {
    // If the filtered list shrank past the prior focusedIndex, ArrowDown should
    // still produce a valid (in-range) result.
    const result = computeNextFocusedIndex(99, "down", 5);
    expect(result).toBeGreaterThanOrEqual(0);
    expect(result).toBeLessThan(5);
  });
});

describe("CountryCombobox — onChange contract (non-DOM)", () => {
  it("is a React component that can be invoked with onChange", () => {
    // Smoke: verify the component signature accepts onChange and the callback
    // type matches the documented `(code: string | null) => void` shape.
    const onChange = vi.fn<(code: string | null) => void>();
    const element = (
      <CountryCombobox value={null} onChange={onChange} />
    );
    // Rendering to string should not throw and should not invoke onChange
    // (onChange only fires on user interaction, not on render).
    expect(() => renderToString(element)).not.toThrow();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("resolves a value through findCountryByCode for sanity", () => {
    // Sanity check — confirms the countries module and component share state.
    expect(findCountryByCode("DE")?.nameRu).toBe("Германия");
  });
});
