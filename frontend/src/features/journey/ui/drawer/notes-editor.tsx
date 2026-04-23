"use client";

/**
 * Notes editor for Task 19.
 *
 * Uses an explicit "Сохранить" button rather than debounced autosave. Rationale:
 * autosave on every keystroke would trigger optimistic-concurrency conflicts
 * when the user pauses mid-sentence; the backend treats every PATCH as a
 * discrete intent, so one commit per user gesture gives predictable version
 * bumps and a clearer audit trail. The button is disabled until the text
 * differs from the persisted value, so the UX remains quiet during typing.
 *
 * Only rendered when the current user holds a NOTES writer role (Req 6.4 ∪ 6.5).
 */

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export interface NotesEditorProps {
  readonly value: string | null;
  readonly disabled?: boolean;
  readonly onSave: (next: string | null) => Promise<void> | void;
}

export function NotesEditor({ value, disabled, onSave }: NotesEditorProps) {
  // React pattern (“Storing information from previous renders”): derive
  // state from props by comparing the prior-prop snapshot during render
  // and calling `setState` to reset the draft when the server-authoritative
  // value changes identity (e.g. after a 409 refetched the node).
  const [draft, setDraft] = useState<string>(value ?? "");
  const [prevValue, setPrevValue] = useState<string | null>(value);
  if (prevValue !== value) {
    setPrevValue(value);
    setDraft(value ?? "");
  }

  const persisted = value ?? "";
  const dirty = draft !== persisted;

  const handleSave = () => {
    if (!dirty) return;
    // Convert empty string back to null so the column is cleared rather
    // than storing a zero-length string.
    const next = draft.trim() === "" ? null : draft;
    void onSave(next);
  };

  return (
    <div data-testid="notes-editor" className="flex flex-col gap-2">
      <Label htmlFor="journey-notes" className="text-xs text-text-subtle">
        Заметки
      </Label>
      <Textarea
        id="journey-notes"
        value={draft}
        disabled={disabled}
        onChange={(e) => setDraft(e.target.value)}
        rows={3}
        placeholder="Контекст, риски, TODO…"
      />
      <div className="flex justify-end">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={disabled || !dirty}
          onClick={handleSave}
        >
          Сохранить
        </Button>
      </div>
    </div>
  );
}
