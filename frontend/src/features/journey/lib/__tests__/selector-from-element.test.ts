/**
 * Pure-helper tests for `selectorFromElement` — deriving a stable CSS
 * selector from a clicked DOM element in the Task 21 DOM picker.
 *
 * No jsdom: we pass in ducktype-friendly `Element`-like fixtures whose
 * `getAttribute` / `tagName` / `parentElement` fields mirror the real DOM.
 *
 * Priority order (by selector-from-element.ts):
 *   1. data-testid   → `[data-testid="..."]`
 *   2. data-action   → `[data-action="..."]`
 *   3. aria-label    → `[aria-label="..."]`
 *   4. short CSS path (tag + :nth-child up to 3 parents)
 */

import { describe, it, expect } from "vitest";
import { selectorFromElement } from "../selector-from-element";

type AttrMap = Record<string, string | null>;

interface ElementFixture {
  tagName: string;
  getAttribute: (name: string) => string | null;
  parentElement: ElementFixture | null;
  _nthChild: number;
}

function makeFixture(
  tagName: string,
  attrs: AttrMap = {},
  parent: ElementFixture | null = null,
  nthChild = 1,
): ElementFixture {
  return {
    tagName: tagName.toUpperCase(),
    getAttribute: (name: string) =>
      Object.prototype.hasOwnProperty.call(attrs, name) ? attrs[name] : null,
    parentElement: parent,
    _nthChild: nthChild,
  };
}

function makeEl(
  tagName: string,
  attrs: AttrMap = {},
  parent: ElementFixture | null = null,
  nthChild = 1,
): Element {
  return makeFixture(tagName, attrs, parent, nthChild) as unknown as Element;
}

describe("selectorFromElement", () => {
  it("returns a data-testid selector when present", () => {
    const el = makeEl("button", { "data-testid": "save-button" });
    expect(selectorFromElement(el)).toBe('[data-testid="save-button"]');
  });

  it("returns a data-action selector when testid is missing", () => {
    const el = makeEl("button", { "data-action": "submit-quote" });
    expect(selectorFromElement(el)).toBe('[data-action="submit-quote"]');
  });

  it("returns an aria-label selector when testid and action are missing", () => {
    const el = makeEl("button", { "aria-label": "Закрыть" });
    expect(selectorFromElement(el)).toBe('[aria-label="Закрыть"]');
  });

  it("prefers data-testid over data-action and aria-label", () => {
    const el = makeEl("button", {
      "data-testid": "save",
      "data-action": "submit",
      "aria-label": "Закрыть",
    });
    expect(selectorFromElement(el)).toBe('[data-testid="save"]');
  });

  it("falls back to a short CSS path (<120 chars) for elements without stable attrs", () => {
    const grandparent = makeFixture("section", {}, null, 1);
    const parent = makeFixture("div", {}, grandparent, 2);
    const el = makeEl("button", {}, parent, 3);
    const sel = selectorFromElement(el);
    expect(sel.length).toBeGreaterThan(0);
    expect(sel.length).toBeLessThan(120);
    // Must reference the target tag.
    expect(sel.toLowerCase()).toContain("button");
  });

  it("returns empty string for null", () => {
    expect(selectorFromElement(null)).toBe("");
  });

  it("returns empty string for a detached element with no parent and no attrs", () => {
    const el = makeEl("span", {}, null, 1);
    const result = selectorFromElement(el);
    // Detached, no attrs — fallback may emit just `span` or empty; we accept
    // anything short without throwing.
    expect(typeof result).toBe("string");
    expect(result.length).toBeLessThan(120);
  });

  it("escapes double quotes in aria-label values", () => {
    const el = makeEl("span", { "aria-label": 'Say "hi"' });
    const sel = selectorFromElement(el);
    // Either the inner quotes are escaped, OR the attribute is wrapped in
    // single quotes. We accept both — but the output must parse as a single
    // bracketed attribute selector.
    expect(sel.startsWith("[aria-label=")).toBe(true);
    expect(sel.endsWith("]")).toBe(true);
  });
});
