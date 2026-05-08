// @vitest-environment jsdom
/**
 * МОП-2 / МОП-3 regression: pin and delete actions in the note card's
 * dropdown must fire their callbacks.
 *
 * Root cause of the bug: the project's DropdownMenuItem is a Base UI
 * MenuPrimitive.Item, not a Radix item. Base UI's Item exposes `onClick`,
 * NOT `onSelect`. Earlier code wired `onSelect={onTogglePin}` and
 * `onSelect={onDelete}`, both of which were silently dropped — clicking
 * either entry closed the menu but ran nothing. These tests lock the
 * `onClick` wiring so a future refactor cannot regress.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { EntityNoteCard, type EntityNoteCardData } from "../ui/entity-note-card";

const FIXED_NOW = new Date("2026-05-05T12:00:00Z");

function makeNote(overrides: Partial<EntityNoteCardData> = {}): EntityNoteCardData {
  return {
    id: "note-1",
    body: "Hello world",
    authorRole: "sales",
    author: {
      id: "user-1",
      name: "МОП Иван",
      email: "ivan@example.com",
      avatarUrl: null,
    },
    visibleTo: ["sales"],
    pinned: false,
    createdAt: FIXED_NOW.toISOString(),
    ...overrides,
  };
}

describe("EntityNoteCard dropdown actions (МОП-2 / МОП-3)", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("invokes onDelete when «Удалить» is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    const onTogglePin = vi.fn();

    render(
      <EntityNoteCard
        note={makeNote()}
        canModify={true}
        onTogglePin={onTogglePin}
        onDelete={onDelete}
      />,
    );

    // Open the actions dropdown
    await user.click(
      screen.getByRole("button", { name: "Действия с заметкой" }),
    );

    // Click «Удалить»
    const deleteItem = await screen.findByTestId("entity-note-delete");
    await user.click(deleteItem);

    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith("note-1");
    expect(onTogglePin).not.toHaveBeenCalled();
  });

  it("invokes onTogglePin when «Закрепить» is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    const onTogglePin = vi.fn();

    render(
      <EntityNoteCard
        note={makeNote({ pinned: false })}
        canModify={true}
        onTogglePin={onTogglePin}
        onDelete={onDelete}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Действия с заметкой" }),
    );

    const pinItem = await screen.findByTestId("entity-note-toggle-pin");
    expect(pinItem).toHaveTextContent("Закрепить");
    await user.click(pinItem);

    expect(onTogglePin).toHaveBeenCalledTimes(1);
    expect(onTogglePin).toHaveBeenCalledWith("note-1");
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("invokes onTogglePin with «Открепить» label when note is already pinned", async () => {
    const user = userEvent.setup();
    const onTogglePin = vi.fn();

    render(
      <EntityNoteCard
        note={makeNote({ pinned: true })}
        canModify={true}
        onTogglePin={onTogglePin}
        onDelete={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Действия с заметкой" }),
    );

    const pinItem = await screen.findByTestId("entity-note-toggle-pin");
    expect(pinItem).toHaveTextContent("Открепить");
    await user.click(pinItem);

    expect(onTogglePin).toHaveBeenCalledWith("note-1");
  });

  it("hides the actions menu when canModify=false", () => {
    render(
      <EntityNoteCard
        note={makeNote()}
        canModify={false}
        onTogglePin={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole("button", { name: "Действия с заметкой" }),
    ).not.toBeInTheDocument();
  });

  /**
   * РОЛ Тест 07 #3.8 (cluster L-E): the author's full name was rendered
   * twice in each note card — once by the card's own header span and once
   * inside the `UserAvatarChip` which defaults to showing both the
   * avatar AND the user's name. The fix is to render the avatar in
   * `initialsOnly` mode so the card itself stays the single source of
   * truth for the name string.
   */
  it("renders the author's full name exactly once (not duplicated by the avatar chip)", () => {
    const note = makeNote({
      author: {
        id: "u-9",
        name: "Сидоров Алексей Викторович",
        email: "sidorov.a@example.com",
        avatarUrl: null,
      },
    });

    render(
      <EntityNoteCard
        note={note}
        canModify={false}
        onTogglePin={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const matches = screen.getAllByText("Сидоров Алексей Викторович");
    expect(matches).toHaveLength(1);
  });
});
