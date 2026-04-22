"use client";

import { useState } from "react";
import { Send, ChevronDown, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/**
 * EntityNoteComposer — textarea + visibility selector + Send button.
 *
 * Submits a new note via `onSubmit(body, visibleTo)`. Clears on success.
 * Supports Cmd/Ctrl+Enter shortcut.
 */

interface EntityNoteComposerProps {
  /** Role slugs the current user is allowed to address the note to. */
  visibilityOptions: Array<{ value: string; label: string }>;
  /** Default visible_to preset. Array of role slugs or ['*']. */
  defaultVisibleTo: string[];
  onSubmit: (body: string, visibleTo: string[]) => Promise<void> | void;
  placeholder?: string;
  busy?: boolean;
}

const DEFAULT_PRESETS: Array<{ key: string; label: string; value: string[] }> = [
  { key: "all", label: "Всем", value: ["*"] },
  { key: "logistics", label: "Логисту", value: ["logistics", "head_of_logistics"] },
  { key: "customs", label: "Таможне", value: ["customs", "head_of_customs"] },
  { key: "sales", label: "МОПу", value: ["sales", "head_of_sales"] },
  { key: "procurement", label: "МОЗу", value: ["procurement", "head_of_procurement"] },
];

function presetLabel(visibleTo: string[], options: EntityNoteComposerProps["visibilityOptions"]) {
  if (visibleTo.includes("*")) return "Всем";
  if (visibleTo.length === 1) {
    const opt = options.find((o) => o.value === visibleTo[0]);
    return opt?.label ?? visibleTo[0];
  }
  return `${visibleTo.length} ролей`;
}

export function EntityNoteComposer({
  visibilityOptions,
  defaultVisibleTo,
  onSubmit,
  placeholder = "Написать заметку…",
  busy = false,
}: EntityNoteComposerProps) {
  const [body, setBody] = useState("");
  const [visibleTo, setVisibleTo] = useState<string[]>(defaultVisibleTo);

  const canSubmit = body.trim().length > 0 && !busy;

  // Filter presets to only those whose roles are available in this entity context
  const allowedPresets = DEFAULT_PRESETS.filter(
    (p) => p.value.includes("*") || p.value.some((r) => visibilityOptions.some((o) => o.value === r)),
  );

  const submit = async () => {
    if (!canSubmit) return;
    await onSubmit(body.trim(), visibleTo);
    setBody("");
  };

  return (
    <div className="rounded-md border border-border-light bg-card p-3 space-y-2">
      <Textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            void submit();
          }
        }}
        placeholder={placeholder}
        rows={2}
        className="resize-none border-0 p-0 text-sm shadow-none focus-visible:ring-0"
        disabled={busy}
      />
      <div className="flex items-center justify-between gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-text-muted hover:text-text gap-1"
                disabled={busy}
              />
            }
          >
            {presetLabel(visibleTo, visibilityOptions)}
            <ChevronDown size={12} strokeWidth={2} aria-hidden />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-48">
            {allowedPresets.map((preset) => (
              <DropdownMenuItem
                key={preset.key}
                onSelect={() => setVisibleTo(preset.value)}
                className="gap-2"
              >
                <Check
                  size={14}
                  strokeWidth={2}
                  className={cn(
                    "text-accent",
                    JSON.stringify(preset.value) !== JSON.stringify(visibleTo) && "invisible",
                  )}
                  aria-hidden
                />
                {preset.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <Button
          size="sm"
          onClick={() => void submit()}
          disabled={!canSubmit}
          className="h-7 gap-1.5"
        >
          <Send size={12} strokeWidth={2.5} aria-hidden />
          <span>Отправить</span>
        </Button>
      </div>
    </div>
  );
}
