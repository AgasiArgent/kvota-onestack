/**
 * jsdom-only test setup.
 *
 * Loaded by the "dom" project in `vitest.config.ts` (Phase 1a hotfix plan,
 * AD-2). The default node-env project does NOT load this file — node tests
 * stay free of DOM globals.
 *
 * Polyfills: Base UI components rely on browser APIs that jsdom does not
 * implement out of the box. We register minimal stubs so render flow does
 * not throw before the assertion phase.
 */
import "@testing-library/jest-dom/vitest";

// ResizeObserver — used by Base UI Floating UI for anchor measurement.
class ResizeObserverPolyfill {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver =
  globalThis.ResizeObserver ??
  (ResizeObserverPolyfill as unknown as typeof ResizeObserver);

// matchMedia — used by Tailwind responsive utilities + Base UI Menu width
// queries. jsdom never sets window.matchMedia.
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// IntersectionObserver — used by Base UI Tooltip and a few shadcn primitives.
if (typeof globalThis.IntersectionObserver === "undefined") {
  class IntersectionObserverPolyfill {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  }
  globalThis.IntersectionObserver =
    IntersectionObserverPolyfill as unknown as typeof IntersectionObserver;
}
