import { defineConfig } from "vitest/config";
import path from "path";

/**
 * Two-project setup (Phase 1a hotfix plan, AD-2).
 *
 * - "node": existing SSR + helper tests (1075+). Default vitest env, no DOM.
 * - "dom": opt-in jsdom tests for click flow + portal-mount verification.
 *   Files match `**\/*.dom.test.{ts,tsx}` — must be named with the `.dom.test.`
 *   suffix to be picked up. Loads `test-setup-jsdom.ts` for ResizeObserver /
 *   matchMedia / IntersectionObserver polyfills.
 *
 * Per-file `// @vitest-environment jsdom` docblocks are also honored inside
 * the dom project, but the filename glob is the canonical opt-in so dom-aware
 * tests are easy to discover via `find -name "*.dom.test.*"`.
 */
export default defineConfig({
  test: {
    globals: true,
    projects: [
      {
        extends: true,
        test: {
          name: "node",
          include: ["src/**/*.test.{ts,tsx}"],
          exclude: ["src/**/*.dom.test.{ts,tsx}"],
          environment: "node",
        },
      },
      {
        extends: true,
        test: {
          name: "dom",
          include: ["src/**/*.dom.test.{ts,tsx}"],
          environment: "jsdom",
          setupFiles: ["./test-setup-jsdom.ts"],
        },
      },
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
