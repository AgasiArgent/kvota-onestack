// @vitest-environment jsdom
/**
 * Testing 2 row 39 — «Таблица КПП»: opening the Контакт / Страна отгрузки
 * dropdown jumps the whole page to the top.
 *
 * Root cause: the popover content is portaled to the bottom of <body>. The
 * search box used the native `autoFocus` attribute, which React focuses with
 * a plain `.focus()` call — the browser then scrolls the (far-down-the-DOM)
 * portaled input into view, dragging the КПП page to the top.
 *
 * Fix: drop `autoFocus`; focus the search box imperatively with
 * `.focus({ preventScroll: true })` once the popover opens.
 *
 * This test pins the contract: when the popover opens, the search input is
 * focused AND every `focus()` call on it carries `{ preventScroll: true }`.
 * jsdom doesn't lay out / scroll, so we assert on the focus-call options
 * rather than on a scrollTop delta.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { SearchableCombobox } from "../searchable-combobox";

interface Row {
  id: string;
  name: string;
}

const ITEMS: Row[] = [
  { id: "a", name: "Альфа" },
  { id: "b", name: "Бета" },
];

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SearchableCombobox — popover focus does not scroll the page (Testing 2 row 39)", () => {
  it("focuses the search input with { preventScroll: true } when opened", async () => {
    const focusSpy = vi.spyOn(HTMLInputElement.prototype, "focus");

    render(
      <SearchableCombobox<Row>
        value={null}
        onChange={() => {}}
        items={ITEMS}
        getLabel={(r) => r.name}
        ariaLabel="Контакт поставщика"
        searchPlaceholder="Поиск контакта…"
      />,
    );

    // Open the popover by clicking the trigger button.
    fireEvent.click(screen.getByLabelText("Контакт поставщика"));

    // Search input mounts inside the portaled popover content.
    await waitFor(() => {
      expect(screen.getByLabelText("Поиск контакта…")).toBeInTheDocument();
    });

    // The input must have been focused...
    expect(focusSpy).toHaveBeenCalled();
    // ...and every focus() call must opt out of scroll-into-view.
    for (const call of focusSpy.mock.calls) {
      expect(call[0]).toMatchObject({ preventScroll: true });
    }
  });

  it("does not set the native autoFocus attribute on the search input", async () => {
    render(
      <SearchableCombobox<Row>
        value={null}
        onChange={() => {}}
        items={ITEMS}
        getLabel={(r) => r.name}
        ariaLabel="Контакт поставщика"
        searchPlaceholder="Поиск контакта…"
      />,
    );

    fireEvent.click(screen.getByLabelText("Контакт поставщика"));

    const input = (await screen.findByLabelText(
      "Поиск контакта…",
    )) as HTMLInputElement;
    // `autoFocus` is the scroll-causing path — it must be gone.
    expect(input.hasAttribute("autofocus")).toBe(false);
  });
});
