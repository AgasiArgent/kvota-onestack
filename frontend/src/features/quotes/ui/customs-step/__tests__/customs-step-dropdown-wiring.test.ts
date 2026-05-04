import { describe, expect, it } from "vitest";
import { promises as fs } from "node:fs";
import * as path from "node:path";

import { CUSTOMS_SYSTEM_VIEWS } from "../customs-views";

/**
 * Phase B Wave 5 hotfix — Bug 2 regression guard.
 *
 * Pre-hotfix `customs-step.tsx` mounted `<TableViewsDropdown>` with only
 * `views={...}` (the user_table_views server prop). The 4 virtual
 * `CUSTOMS_SYSTEM_VIEWS` were imported by `customs-handsontable.tsx`
 * (column filter) and `customs-view-hint-banner.tsx` (label resolver),
 * but **never reached the dropdown UI** — REQ-11 AC#4 violated.
 *
 * Symptom: dropdown listed only «Все колонки» + 2 generic actions; the
 * other 3 system views (Тарифы и НДС / Документы и сертификаты / Только
 * идентификация) were unreachable from the menu — only via raw URL.
 *
 * The frontend workspace ships no jsdom (vitest.config.ts), so this is a
 * source-string-scan test — same playbook as
 * `customs-item-dialog-certification.test.tsx`. The matching pure-function
 * coverage of `CUSTOMS_SYSTEM_VIEWS` itself stays in `customs-views.test.ts`.
 */

describe("customs-step.tsx — TableViewsDropdown wiring (Bug 2)", () => {
  it("imports CUSTOMS_SYSTEM_VIEWS from ./customs-views", async () => {
    const stepPath = path.resolve(
      __dirname,
      "..",
      "customs-step.tsx",
    );
    const src = await fs.readFile(stepPath, "utf-8");
    expect(src).toContain("CUSTOMS_SYSTEM_VIEWS");
    // customs-step.tsx must import the constant from ./customs-views.
    expect(src).toMatch(/from\s+["']\.\/customs-views["']/);
  });

  it("passes systemViews={CUSTOMS_SYSTEM_VIEWS} to <TableViewsDropdown>", async () => {
    const stepPath = path.resolve(
      __dirname,
      "..",
      "customs-step.tsx",
    );
    const src = await fs.readFile(stepPath, "utf-8");
    // The exact prop wiring — pre-hotfix this line did not exist.
    expect(src).toContain("systemViews={CUSTOMS_SYSTEM_VIEWS}");
  });

  it("dropdown renders the «Системные» group above personal/shared (REQ-11 AC#4)", async () => {
    const dropdownPath = path.resolve(
      __dirname,
      "..",
      "..",
      "..",
      "..",
      "..",
      "features",
      "table-views",
      "ui",
      "table-views-dropdown.tsx",
    );
    const src = await fs.readFile(dropdownPath, "utf-8");
    // The new group label must exist...
    expect(src).toContain("Системные");
    // ...and the «Системные» / «Личные» / «Общие» labels must appear in
    // that exact source order (REQ-11 AC#4 — the dropdown renders top-to-
    // bottom in the order the labels appear in the JSX). Comments above
    // the group blocks reference the same Russian strings; we strip them
    // by anchoring on `<DropdownMenuLabel>` text only.
    const labelOrder = (
      src.match(/<DropdownMenuLabel>([^<]+)<\/DropdownMenuLabel>/g) ?? []
    ).map((m) => m.replace(/<[^>]+>/g, "").trim());
    const sysIdx = labelOrder.indexOf("Системные");
    const personalIdx = labelOrder.indexOf("Личные");
    const sharedIdx = labelOrder.indexOf("Общие");
    expect(sysIdx).toBeGreaterThanOrEqual(0);
    expect(personalIdx).toBeGreaterThan(sysIdx);
    expect(sharedIdx).toBeGreaterThan(personalIdx);
  });

  it("dropdown accepts an optional systemViews prop typed {id, label}", async () => {
    const dropdownPath = path.resolve(
      __dirname,
      "..",
      "..",
      "..",
      "..",
      "..",
      "features",
      "table-views",
      "ui",
      "table-views-dropdown.tsx",
    );
    const src = await fs.readFile(dropdownPath, "utf-8");
    // The new prop must be on the props interface.
    expect(src).toMatch(/systemViews\?:\s*readonly\s+SystemViewOption\[\]/);
    // And the local exported shape must define id + label.
    expect(src).toMatch(/SystemViewOption[\s\S]*?id:\s*string/);
    expect(src).toMatch(/SystemViewOption[\s\S]*?label:\s*string/);
  });

  it("CUSTOMS_SYSTEM_VIEWS keeps the 4-entry order — sanity for the dropdown render order", () => {
    // Dropdown renders systemViews in array order (REQ-11 AC#4 — first
    // entry is «Все колонки» = system:all default per AC#7).
    expect(CUSTOMS_SYSTEM_VIEWS.map((v) => v.id)).toEqual([
      "system:all",
      "system:tariffs-nds",
      "system:documents",
      "system:identification",
    ]);
    expect(CUSTOMS_SYSTEM_VIEWS.map((v) => v.label)).toEqual([
      "Все колонки",
      "Тарифы и НДС",
      "Документы и сертификаты",
      "Только идентификация",
    ]);
  });
});
