"use client";

/**
 * Inline editable «Комментарий для распределения» panel.
 *
 * Testing 2 row 61 (МОП / РОП «Нет поля 21.05.2026»): the field was technically
 * present in the «Передать в закупки» modal but buried below a mandatory
 * textarea — the tester didn't scroll. Once the quote leaves the draft stage
 * the modal becomes unreachable and the field turns read-only, so МОП / РОП
 * had no way to add or amend the hint.
 *
 * This component surfaces the same `kvota.quotes.sales_checklist.distribution_comment`
 * JSONB key as a first-class editor on the sales step — visible above the
 * positions grid, always editable for МОП / РОП / admin, autosaved on blur.
 *
 * The «Передать в закупки» modal still carries the field for back-compat;
 * both writers go through the same JSONB key, so opening the modal after
 * editing inline pre-populates the textarea with the inline value (via the
 * server fetch of `quote.sales_checklist`).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, MessageSquareText } from "lucide-react";
import { toast } from "sonner";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { updateDistributionComment } from "@/entities/quote/server-actions";

interface DistributionCommentInlineProps {
  quoteId: string;
  initialValue: string | null;
  /**
   * When false, the field renders as a read-only block (МОЗ / МОЛ / МОТ /
   * финансы и т.д.). When true (МОП / РОП / admin), it becomes an editable
   * textarea with autosave on blur and on debounced change.
   */
  canEdit: boolean;
}

const AUTOSAVE_DEBOUNCE_MS = 500;

export function DistributionCommentInline({
  quoteId,
  initialValue,
  canEdit,
}: DistributionCommentInlineProps) {
  const [value, setValue] = useState<string>(initialValue ?? "");
  const [saving, setSaving] = useState(false);
  // Track the last value we successfully persisted so we can skip a duplicate
  // save (blur after the debounced change already wrote the same value).
  const lastSavedRef = useRef<string>(initialValue ?? "");
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep local state in sync if the parent re-renders with a fresh server
  // value (e.g. after `router.refresh()` from the modal write path).
  useEffect(() => {
    const next = initialValue ?? "";
    // Only adopt the server value if the user isn't mid-edit on a different
    // string — otherwise we'd clobber their unsaved input.
    if (next !== lastSavedRef.current && next !== value) {
      setValue(next);
      lastSavedRef.current = next;
    }
    // We intentionally exclude `value` so external prop updates flow through
    // without fighting the controlled input on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialValue]);

  // Clean up any pending debounce when the component unmounts (prevents a
  // stale save firing after navigation).
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current !== null) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const persist = useCallback(
    async (nextRaw: string) => {
      const normalised = nextRaw.trim();
      // Compare against the last persisted value (also normalised) so empty
      // ↔ whitespace edits don't trigger duplicate writes.
      const lastNormalised = lastSavedRef.current.trim();
      if (normalised === lastNormalised) return;

      setSaving(true);
      try {
        const res = await updateDistributionComment(
          quoteId,
          normalised.length > 0 ? normalised : null,
        );
        if (!res.success) {
          toast.error(res.error ?? "Не удалось сохранить комментарий");
          return;
        }
        // Adopt server-canonical form (null → ""), then mirror it into the
        // controlled input so the displayed string matches what's persisted.
        const serverValue = res.value ?? "";
        lastSavedRef.current = serverValue;
        if (serverValue !== nextRaw) {
          setValue(serverValue);
        }
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось сохранить комментарий",
        );
      } finally {
        setSaving(false);
      }
    },
    [quoteId],
  );

  const scheduleDebouncedSave = useCallback(
    (next: string) => {
      if (debounceTimerRef.current !== null) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        debounceTimerRef.current = null;
        void persist(next);
      }, AUTOSAVE_DEBOUNCE_MS);
    },
    [persist],
  );

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const next = e.target.value;
    setValue(next);
    scheduleDebouncedSave(next);
  }

  function handleBlur() {
    // Flush any pending debounce immediately on blur so the user gets fast
    // feedback when they're "done" with the field.
    if (debounceTimerRef.current !== null) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
    void persist(value);
  }

  // Read-only render — used for МОЗ / МОЛ / МОТ / финансы и т.д. They already
  // see this comment on the context panel; surfacing it here keeps parity for
  // anyone scrolling the sales step without exposing edit affordance.
  if (!canEdit) {
    if (!value.trim()) return null;
    return (
      <div
        className="rounded-lg border border-border bg-muted/30 p-4 space-y-2"
        data-testid="distribution-comment-inline-readonly"
      >
        <div className="flex items-center gap-2">
          <MessageSquareText
            size={14}
            className="text-muted-foreground shrink-0"
          />
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Комментарий для распределения
          </h4>
        </div>
        <div className="rounded-md bg-card px-3 py-2 text-sm whitespace-pre-wrap break-words">
          {value}
        </div>
      </div>
    );
  }

  return (
    <div
      className="rounded-lg border border-border bg-muted/30 p-4 space-y-2"
      data-testid="distribution-comment-inline"
    >
      <div className="flex items-center justify-between gap-2">
        <Label
          htmlFor="distribution-comment-inline-textarea"
          className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide"
        >
          <MessageSquareText size={14} className="text-muted-foreground shrink-0" />
          Комментарий для распределения
        </Label>
        {saving && (
          <span
            className="flex items-center gap-1 text-[11px] text-muted-foreground"
            data-testid="distribution-comment-inline-saving"
          >
            <Loader2 size={12} className="animate-spin" />
            Сохранение…
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        Уточнения для МОЛ / МОТ — будут видны после отправки в закупки на канбан-карточке и в инфо-панели.
      </p>
      <Textarea
        id="distribution-comment-inline-textarea"
        value={value}
        onChange={handleChange}
        onBlur={handleBlur}
        placeholder="Опционально: например, «Срочно к Алейне» или «Лучше через сертифицированного перевозчика»"
        rows={2}
        className="bg-card"
      />
    </div>
  );
}
