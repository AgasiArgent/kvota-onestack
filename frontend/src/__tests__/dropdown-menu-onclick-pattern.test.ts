/**
 * Regression guard: Track F (PR #117) found that Base UI's MenuPrimitive.Item
 * fires onClick, NOT onSelect (which is Radix-only). The bug pattern caused
 * silent dead handlers — the menu visually closed on click but the callback
 * never ran.
 *
 * This sweep test scans every TSX file under src/ that imports
 * DropdownMenuItem from "@/components/ui/dropdown-menu" and asserts no
 * `onSelect=` prop is wired onto a DropdownMenuItem JSX element. Any future
 * commit that re-introduces the Radix-style prop will fail this test before
 * it can ship to production.
 *
 * Out of scope: `onSelect` props on custom components (e.g. searchable
 * pickers, calendar day-pickers) — these are application-defined callbacks
 * unrelated to the Base UI menu primitive.
 */
import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

const SRC_ROOT = path.resolve(__dirname, "..");

function walkTsx(dir: string, acc: string[] = []): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === ".next") continue;
      walkTsx(full, acc);
    } else if (entry.isFile() && entry.name.endsWith(".tsx")) {
      acc.push(full);
    }
  }
  return acc;
}

/**
 * Scan a TSX source for `<DropdownMenuItem ... onSelect={...}>` patterns.
 * Matches across newlines (props commonly span multiple lines) but stops at
 * the closing `>` of the opening tag so we do not bleed into siblings.
 *
 * Returns line numbers (1-based) where the offending opener begins.
 */
function findOnSelectOnDropdownMenuItem(source: string): number[] {
  const matches: number[] = [];
  // /s flag = dot matches newline; /g for multiple instances per file.
  // Non-greedy [^>]*? would not allow newlines without /s; we use /s and
  // a negative-lookahead for `>` to scope to the opening tag.
  const opener = /<DropdownMenuItem\b((?:(?!\/?>)[\s\S])*?)\/?>/g;
  let match: RegExpExecArray | null;
  while ((match = opener.exec(source)) !== null) {
    const tagBody = match[1];
    if (/\bonSelect\s*=/.test(tagBody)) {
      // Convert offset to line number for human-readable failure messages.
      const upToMatch = source.slice(0, match.index);
      const lineNumber = upToMatch.split("\n").length;
      matches.push(lineNumber);
    }
  }
  return matches;
}

describe("DropdownMenuItem onClick pattern (Track F regression guard)", () => {
  const files = walkTsx(SRC_ROOT);

  it("scans at least one TSX file (sanity check)", () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it("never wires onSelect onto <DropdownMenuItem> (Base UI uses onClick)", () => {
    const offenders: string[] = [];
    for (const file of files) {
      const source = fs.readFileSync(file, "utf8");
      // Skip files that don't reference DropdownMenuItem at all — there is
      // nothing for the regex to match anyway, but this avoids spending CPU
      // on the slow multiline regex for the majority of the codebase.
      if (!source.includes("DropdownMenuItem")) continue;
      const lines = findOnSelectOnDropdownMenuItem(source);
      if (lines.length > 0) {
        const rel = path.relative(SRC_ROOT, file);
        for (const line of lines) {
          offenders.push(`${rel}:${line}`);
        }
      }
    }

    expect(
      offenders,
      `<DropdownMenuItem onSelect={...}> is a silent dead handler in Base UI. ` +
        `Use onClick={...} instead. Offending sites:\n  - ${offenders.join("\n  - ")}`,
    ).toEqual([]);
  });
});
