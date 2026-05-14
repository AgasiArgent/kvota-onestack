/**
 * Testing 2 row 7 (РОЛ + МВЭД) — the customs step must NOT render its own
 * «Ответственные» or «История» blocks. Those duplicated the right-side
 * context panel (participants) and the status rail (workflow history),
 * cluttering the page for customs viewers.
 *
 * The legacy `<CustomsInfoBlock>` component (file:
 * `customs-info-block.tsx`) was deleted as part of this cleanup; this
 * test pins down two regressions:
 *
 *   1. `customs-step.tsx` no longer imports `CustomsInfoBlock`.
 *   2. The deleted file does not get re-introduced silently.
 *
 * Full <CustomsStep /> mounting is avoided (Handsontable + Supabase),
 * matching the pattern used by `customs-step-cargo-summary.dom.test.tsx`
 * — a source-level smoke check is sufficient and stable.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const CUSTOMS_STEP_DIR = path.resolve(
  __dirname,
  "..",
);
const STEP_SOURCE = path.join(CUSTOMS_STEP_DIR, "customs-step.tsx");
const DELETED_INFO_BLOCK = path.join(CUSTOMS_STEP_DIR, "customs-info-block.tsx");

describe("Customs step — redundant blocks removed (Testing 2 row 7)", () => {
  it("does not import CustomsInfoBlock", () => {
    const source = fs.readFileSync(STEP_SOURCE, "utf8");
    expect(source).not.toMatch(/CustomsInfoBlock/);
    expect(source).not.toMatch(/customs-info-block/);
  });

  it("does not contain «Ответственные» or «История» section headings", () => {
    const source = fs.readFileSync(STEP_SOURCE, "utf8");
    // Russian headings used by the deleted block — guard against
    // accidental copy-paste reintroduction.
    expect(source).not.toContain("Ответственные");
    expect(source).not.toContain("История");
  });

  it("removes the legacy customs-info-block.tsx file", () => {
    expect(fs.existsSync(DELETED_INFO_BLOCK)).toBe(false);
  });
});
