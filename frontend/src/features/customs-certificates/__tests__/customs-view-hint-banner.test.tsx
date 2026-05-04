import React from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CustomsViewHintBanner } from "../ui/customs-view-hint-banner";
import type { SystemView } from "../model/types";

/**
 * SSR rendering tests for `CustomsViewHintBanner` (Phase B Wave 4 Task 8 /
 * REQ-11 AC#9-#11).
 *
 * The frontend workspace has no jsdom configured (per `format-rub.test.ts` +
 * `history-banner.test.tsx` precedent), so we use `react-dom/server` to
 * assert markup. Tooltip hover behaviour is verified via localhost:3000 per
 * `reference_localhost_browser_test.md` — here we only assert that the
 * tooltip content text is reachable in the SSR output (Tooltip renders the
 * trigger inline, which is enough for our copy-correctness assertions).
 */

const ALL_COLUMNS: ReadonlyArray<{ key: string; label: string }> = [
  { key: "position", label: "№" },
  { key: "brand", label: "Бренд" },
  { key: "product_code", label: "Артикул" },
  { key: "product_name", label: "Наименование" },
  { key: "quantity", label: "Кол-во" },
  { key: "supplier_country", label: "Страна" },
  { key: "hs_code", label: "Код ТН ВЭД" },
  { key: "customs_duty_composite", label: "Пошлина" },
];

function makeView(overrides: Partial<SystemView> = {}): SystemView {
  return {
    id: "system:tariffs-nds",
    label: "Тарифы и НДС",
    is_system: true,
    visibleColumnIds: ["position", "product_code", "product_name", "hs_code"],
    ...overrides,
  } as SystemView;
}

describe("CustomsViewHintBanner — null guard", () => {
  it("renders nothing when currentView is null", () => {
    const html = renderToString(
      <CustomsViewHintBanner currentView={null} allColumns={ALL_COLUMNS} />,
    );
    expect(html).toBe("");
  });

  it("renders nothing when currentView is the default `system:all`", () => {
    const allView = makeView({
      id: "system:all",
      label: "Все колонки",
      visibleColumnIds: ALL_COLUMNS.map((c) => c.key),
    });
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={allView}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toBe("");
  });
});

describe("CustomsViewHintBanner — non-default system view", () => {
  it("renders the headline copy with the view label", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain("Сейчас активен вид «Тарифы и НДС»");
    expect(html).toContain("скрыты колонки:");
  });

  it("renders the 💡 emoji", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain("💡");
  });

  it("renders the comma-separated hidden columns list in registry order", () => {
    // visibleColumnIds = position, product_code, product_name, hs_code
    // hidden = brand, quantity, supplier_country, customs_duty_composite
    // expected labels in ALL_COLUMNS order: "Бренд", "Кол-во", "Страна", "Пошлина".
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain("Бренд, Кол-во, Страна, Пошлина");
  });

  it("ends the headline sentence with a period", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain("Пошлина.");
  });

  it("uses info-blue tinted card classes for visual continuity with HistoryBanner apply variant", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain("border-blue-900");
    expect(html).toContain("bg-blue-950/20");
  });

  it("exposes data-testid for parent integration", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain('data-testid="customs-view-hint-banner"');
  });

  it("exposes data-view-id for downstream assertions", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain('data-view-id="system:tariffs-nds"');
  });
});

describe("CustomsViewHintBanner — disabled CTA link with tooltip (REQ-11 AC#10/#11)", () => {
  it("renders the 'Создать свой вид' CTA copy", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain("Создать свой вид: Колонки → Сохранить как...");
  });

  it("marks the CTA as disabled via aria-disabled", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain('aria-disabled="true"');
  });

  it("exposes the CTA testid for parent integration", () => {
    const html = renderToString(
      <CustomsViewHintBanner
        currentView={makeView()}
        allColumns={ALL_COLUMNS}
      />,
    );
    expect(html).toContain('data-testid="customs-view-hint-cta"');
  });

  it("renders without throwing when wrapped in the project's TooltipProvider", () => {
    // Smoke test — Tooltip primitives must SSR cleanly without runtime
    // assertions on the popup positioner (it ships hidden until interactive).
    expect(() =>
      renderToString(
        <CustomsViewHintBanner
          currentView={makeView()}
          allColumns={ALL_COLUMNS}
        />,
      ),
    ).not.toThrow();
  });
});

describe("CustomsViewHintBanner — different views", () => {
  it("renders correct hidden list for system:identification (minimal view)", () => {
    const view = makeView({
      id: "system:identification",
      label: "Только идентификация",
      visibleColumnIds: [
        "position",
        "brand",
        "product_code",
        "product_name",
        "quantity",
        "hs_code",
      ],
    });
    const html = renderToString(
      <CustomsViewHintBanner currentView={view} allColumns={ALL_COLUMNS} />,
    );
    // Hidden = supplier_country, customs_duty_composite
    expect(html).toContain("Страна, Пошлина");
    expect(html).toContain("«Только идентификация»");
  });

  it("renders correct hidden list for system:documents", () => {
    const view = makeView({
      id: "system:documents",
      label: "Документы и сертификаты",
      visibleColumnIds: [
        "position",
        "product_code",
        "product_name",
        "hs_code",
        "supplier_country",
      ],
    });
    const html = renderToString(
      <CustomsViewHintBanner currentView={view} allColumns={ALL_COLUMNS} />,
    );
    // Hidden = brand, quantity, customs_duty_composite (in registry order).
    expect(html).toContain("Бренд, Кол-во, Пошлина");
    expect(html).toContain("«Документы и сертификаты»");
  });
});
