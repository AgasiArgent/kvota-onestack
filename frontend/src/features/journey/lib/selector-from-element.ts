/**
 * Derive a stable CSS selector from a clicked DOM element.
 *
 * Used by the DOM picker (Task 21): when a user clicks an element inside the
 * preview iframe, we compute a selector string that will still match after
 * minor UI refactors. Priority order:
 *
 *   1. `data-testid`  → `[data-testid="..."]`         (most stable)
 *   2. `data-action`  → `[data-action="..."]`         (stable enough)
 *   3. `aria-label`   → `[aria-label="..."]`          (screen-reader text)
 *   4. fallback       → short CSS path (tag + :nth-child), up to 3 ancestors
 *
 * The implementation is ducktype-friendly — it only reads `getAttribute`,
 * `tagName`, and `parentElement` off the passed-in object. That keeps it
 * unit-testable without jsdom (the frontend workspace has none) while
 * still accepting real `Element` instances at runtime.
 *
 * The fallback deliberately produces short (<120 char) selectors: long CSS
 * paths are both fragile and useless in pin-tooltip copy.
 */

const FALLBACK_MAX_DEPTH = 3;
const MAX_SELECTOR_LENGTH = 120;

interface ElementLike {
  readonly tagName?: string;
  readonly getAttribute?: (name: string) => string | null;
  readonly parentElement?: ElementLike | null;
  /**
   * Test-only hint: 1-based position among siblings. When absent (real DOM),
   * we derive it from `parentElement.children` at runtime.
   */
  readonly _nthChild?: number;
}

/**
 * Escape a value for use inside a double-quoted CSS attribute selector.
 * Falls back to single-quote wrapping when the input itself contains a
 * double quote — simpler than CSS-escaping every special char.
 */
function quoteAttrValue(raw: string): string {
  if (!raw.includes('"')) return `"${raw}"`;
  if (!raw.includes("'")) return `'${raw}'`;
  // Both quotes present: escape the double quotes.
  return `"${raw.replace(/"/g, '\\"')}"`;
}

function nthChildOf(el: ElementLike): number {
  // Test fixture path.
  if (typeof el._nthChild === "number" && el._nthChild > 0) {
    return el._nthChild;
  }
  const parent = el.parentElement;
  if (!parent) return 1;
  // Real-DOM path: find index among element siblings.
  const parentNode = parent as unknown as { children?: ArrayLike<unknown> };
  const children = parentNode.children;
  if (!children) return 1;
  for (let i = 0; i < children.length; i++) {
    if ((children as ArrayLike<unknown>)[i] === (el as unknown)) {
      return i + 1;
    }
  }
  return 1;
}

function tagLower(el: ElementLike): string {
  const tag = el.tagName;
  if (!tag) return "";
  return tag.toLowerCase();
}

function buildShortCssPath(el: ElementLike, maxDepth: number): string {
  const parts: string[] = [];
  let cur: ElementLike | null | undefined = el;
  let depth = 0;
  while (cur && depth <= maxDepth) {
    const tag = tagLower(cur);
    if (!tag) break;
    const nth = nthChildOf(cur);
    parts.unshift(`${tag}:nth-child(${nth})`);
    cur = cur.parentElement ?? null;
    if (!cur) break;
    depth += 1;
  }
  if (parts.length === 0) return "";
  const joined = parts.join(" > ");
  return joined.length > MAX_SELECTOR_LENGTH
    ? parts[parts.length - 1]!
    : joined;
}

/**
 * Public entry point — returns an empty string for null / shapeless input
 * so callers can branch on falsiness.
 */
export function selectorFromElement(el: Element | ElementLike | null): string {
  if (!el) return "";
  const getAttr = el.getAttribute?.bind(el);
  if (getAttr) {
    const testid = getAttr("data-testid");
    if (testid) return `[data-testid=${quoteAttrValue(testid)}]`;

    const action = getAttr("data-action");
    if (action) return `[data-action=${quoteAttrValue(action)}]`;

    const aria = getAttr("aria-label");
    if (aria) return `[aria-label=${quoteAttrValue(aria)}]`;
  }

  // Fallback: short CSS path.
  return buildShortCssPath(el, FALLBACK_MAX_DEPTH);
}
