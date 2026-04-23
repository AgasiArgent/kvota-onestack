/**
 * Ghost slug derivation + validation — pure-helper tests (no DOM).
 *
 * Req 7.2 states `node_id = ghost:<slug>` where slug is URL-safe and unique;
 * the frontend enforces (a) deterministic derivation from the title and
 * (b) strict kebab-case validation before dispatching the insert. The DB
 * UNIQUE constraint is the ultimate authority, but client-side validation
 * prevents obvious collisions and preserves a Russian-friendly input UX
 * via a minimal Cyrillic transliteration table.
 */

import { describe, it, expect } from "vitest";
import { deriveGhostSlug, validateGhostSlug } from "../_ghost-slug";

describe("deriveGhostSlug", () => {
  it("lowercases, replaces spaces with dashes, strips special chars", () => {
    expect(deriveGhostSlug("My Feature Name")).toBe("my-feature-name");
  });

  it("transliterates Cyrillic input and trims surrounding whitespace", () => {
    expect(deriveGhostSlug("   Две слова  ")).toBe("dve-slova");
  });

  it("collapses multiple separators and strips punctuation", () => {
    expect(deriveGhostSlug("Hello, World!!  Foo / bar")).toBe("hello-world-foo-bar");
  });

  it("preserves digits", () => {
    expect(deriveGhostSlug("Feature 2 v3")).toBe("feature-2-v3");
  });

  it("returns an empty string for titles with no latin/cyrillic/digit chars", () => {
    expect(deriveGhostSlug("—///—")).toBe("");
  });
});

describe("validateGhostSlug", () => {
  it("accepts strict kebab-case", () => {
    expect(validateGhostSlug("foo-bar")).toBe(true);
    expect(validateGhostSlug("a")).toBe(true);
    expect(validateGhostSlug("feature-2-v3")).toBe(true);
  });

  it("rejects uppercase or underscore separators", () => {
    expect(validateGhostSlug("Foo_Bar")).toBe(false);
    expect(validateGhostSlug("Foo-Bar")).toBe(false);
    expect(validateGhostSlug("foo_bar")).toBe(false);
  });

  it("rejects leading/trailing dashes", () => {
    expect(validateGhostSlug("-foo")).toBe(false);
    expect(validateGhostSlug("foo-")).toBe(false);
    expect(validateGhostSlug("-foo-")).toBe(false);
  });

  it("rejects double dashes and spaces", () => {
    expect(validateGhostSlug("foo--bar")).toBe(false);
    expect(validateGhostSlug("foo bar")).toBe(false);
  });

  it("rejects empty input", () => {
    expect(validateGhostSlug("")).toBe(false);
  });

  it("requires alphanumeric start and end", () => {
    expect(validateGhostSlug("1-foo")).toBe(true);
    expect(validateGhostSlug("foo-1")).toBe(true);
  });
});
