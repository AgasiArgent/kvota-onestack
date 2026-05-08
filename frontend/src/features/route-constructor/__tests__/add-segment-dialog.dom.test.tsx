// @vitest-environment jsdom
/**
 * РОЛ Тест 07 #3.4 (cluster L-E, partial): «Добавить сегмент» must
 * surface the pickup address procurement entered for the invoice — not
 * just the empty Locations list. The full МОЗ-address sourcing requires
 * a DB-backed address book (out of scope for this fix); this test
 * locks the lightweight UX hint introduced in 2026-05-07.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AddSegmentDialog } from "../ui/add-segment-dialog";
import type { LocationOption } from "@/entities/location";

const LOC_RU_MOSCOW: LocationOption = {
  id: "loc-ru-moscow",
  country: "Россия",
  iso2: "RU",
  city: "Москва",
  type: "supplier",
};
const LOC_CN_SHANGHAI: LocationOption = {
  id: "loc-cn-shanghai",
  country: "Китай",
  iso2: "CN",
  city: "Шанхай",
  type: "hub",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AddSegmentDialog pickup hint (РОЛ Тест 07 #3.4)", () => {
  it("renders the procurement-entered pickup country/city", () => {
    render(
      <AddSegmentDialog
        open
        onOpenChange={vi.fn()}
        locations={[LOC_RU_MOSCOW, LOC_CN_SHANGHAI]}
        onSubmit={vi.fn(async () => undefined)}
        pickupHint={{ country: "Китай", city: "Шанхай" }}
      />,
    );

    const hint = screen.getByTestId("add-segment-pickup-hint");
    expect(hint.textContent).toContain("Китай");
    expect(hint.textContent).toContain("Шанхай");
  });

  it("offers a one-click apply when the pickup matches an existing Location", async () => {
    const user = userEvent.setup();
    render(
      <AddSegmentDialog
        open
        onOpenChange={vi.fn()}
        locations={[LOC_RU_MOSCOW, LOC_CN_SHANGHAI]}
        onSubmit={vi.fn(async () => undefined)}
        pickupHint={{ country: "Китай", city: "Шанхай" }}
      />,
    );

    const apply = screen.getByTestId("add-segment-pickup-hint-apply");
    await user.click(apply);

    // The "Откуда" combobox should now display the matched location.
    // SearchableCombobox renders the selected label inside its trigger.
    const fromTrigger = screen.getByLabelText(/Локация отправления/i);
    expect(fromTrigger.textContent ?? "").toMatch(/Шанхай|Китай/);
  });

  it("falls back to a guidance message when no Location matches the pickup", () => {
    render(
      <AddSegmentDialog
        open
        onOpenChange={vi.fn()}
        locations={[LOC_RU_MOSCOW]}
        onSubmit={vi.fn(async () => undefined)}
        pickupHint={{ country: "Турция", city: "Стамбул" }}
      />,
    );

    const hint = screen.getByTestId("add-segment-pickup-hint");
    expect(hint.textContent).toContain("Турция");
    expect(hint.textContent).toContain("Справочники");
    expect(
      screen.queryByTestId("add-segment-pickup-hint-apply"),
    ).toBeNull();
  });

  it("renders no hint when procurement has not entered a pickup address", () => {
    render(
      <AddSegmentDialog
        open
        onOpenChange={vi.fn()}
        locations={[LOC_RU_MOSCOW]}
        onSubmit={vi.fn(async () => undefined)}
        pickupHint={null}
      />,
    );

    expect(screen.queryByTestId("add-segment-pickup-hint")).toBeNull();
  });
});
