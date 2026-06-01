// @vitest-environment jsdom
/**
 * Testing 2 row 92 — /suppliers «Наличие поисковой строки. Наличие фильтров.»
 *
 * Pins the filter-bar contract:
 *  - a search input + Страна / МОЗ / Бренд / Статус searchable dropdowns render
 *  - picking a Страна / МОЗ / Бренд option navigates with that URL param
 *    (server-side filtering narrows the list across pages)
 *  - clearing a filter drops the param (back to «Все»)
 *  - «Сбросить все» shows only when a filter is active and wipes every param
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import { SuppliersFilterBar } from "../suppliers-filter-bar";
import type { SupplierFilterOptions } from "@/entities/supplier";

const navigate = vi.fn();

vi.mock("@/shared/lib/use-filter-navigation", () => ({
  useFilterNavigation: () => ({
    navigate,
    searchParams: new URLSearchParams(),
  }),
}));

const OPTIONS: SupplierFilterOptions = {
  countries: ["Германия", "Китай", "Россия"],
  assignees: [
    { id: "u-1", full_name: "Иванов Иван" },
    { id: "u-2", full_name: "Петров Пётр" },
  ],
  brands: ["Bosch", "Siemens", "SKF"],
};

function renderBar(overrides: Partial<React.ComponentProps<typeof SuppliersFilterBar>> = {}) {
  return render(
    <SuppliersFilterBar
      search=""
      country=""
      assignee=""
      brand=""
      status=""
      options={OPTIONS}
      {...overrides}
    />,
  );
}

beforeEach(() => {
  navigate.mockClear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SuppliersFilterBar — search + filters render (Testing 2 row 92)", () => {
  it("renders the search input and Страна/МОЗ/Бренд/Статус dropdowns", () => {
    renderBar();

    expect(
      screen.getByPlaceholderText("Поиск по названию / коду…"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Фильтр: Страна")).toBeInTheDocument();
    expect(screen.getByLabelText("Фильтр: МОЗ")).toBeInTheDocument();
    expect(screen.getByLabelText("Фильтр: Бренд")).toBeInTheDocument();
    expect(screen.getByLabelText("Фильтр: Статус")).toBeInTheDocument();
  });
});

describe("SuppliersFilterBar — selecting an option navigates with its URL param", () => {
  it("Страна → navigates with { country }", async () => {
    renderBar();
    fireEvent.click(screen.getByLabelText("Фильтр: Страна"));
    const option = await screen.findByText("Китай");
    fireEvent.click(option);

    expect(navigate).toHaveBeenCalledWith({ country: "Китай" });
  });

  it("МОЗ → navigates with the assignee user id", async () => {
    renderBar();
    fireEvent.click(screen.getByLabelText("Фильтр: МОЗ"));
    const option = await screen.findByText("Петров Пётр");
    fireEvent.click(option);

    expect(navigate).toHaveBeenCalledWith({ assignee: "u-2" });
  });

  it("Бренд → narrows by the picked brand", async () => {
    renderBar();
    fireEvent.click(screen.getByLabelText("Фильтр: Бренд"));
    const option = await screen.findByText("Siemens");
    fireEvent.click(option);

    expect(navigate).toHaveBeenCalledWith({ brand: "Siemens" });
  });

  it("Бренд search box narrows the option list before selecting", async () => {
    renderBar();
    fireEvent.click(screen.getByLabelText("Фильтр: Бренд"));
    const searchInput = await screen.findByLabelText("Поиск бренда...");
    fireEvent.change(searchInput, { target: { value: "skf" } });

    await waitFor(() => {
      expect(screen.getByText("SKF")).toBeInTheDocument();
      expect(screen.queryByText("Bosch")).not.toBeInTheDocument();
    });
  });
});

describe("SuppliersFilterBar — clearing restores «Все»", () => {
  it("clearing an active Страна filter drops the country param", () => {
    renderBar({ country: "Китай" });
    // The combobox renders an inline X clear affordance when a value is set.
    const clear = screen.getByLabelText("Очистить");
    fireEvent.pointerDown(clear);

    expect(navigate).toHaveBeenCalledWith({ country: undefined });
  });

  it("«Сбросить все» is hidden with no active filters and clears every param when shown", () => {
    const { rerender } = renderBar();
    expect(screen.queryByText("Сбросить все")).not.toBeInTheDocument();

    rerender(
      <SuppliersFilterBar
        search="насос"
        country="Китай"
        assignee="u-1"
        brand="Bosch"
        status="active"
        options={OPTIONS}
      />,
    );

    fireEvent.click(screen.getByText("Сбросить все"));
    expect(navigate).toHaveBeenCalledWith({
      q: undefined,
      country: undefined,
      assignee: undefined,
      brand: undefined,
      status: undefined,
    });
  });
});
