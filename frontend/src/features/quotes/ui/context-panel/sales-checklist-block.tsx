"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  ClipboardList,
  Loader2,
  Pencil,
  Check,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { updateDistributionComment } from "@/entities/quote/server-actions";

/**
 * Shape of the JSONB `kvota.quotes.sales_checklist` payload written by the
 * МОП «Передать в закупки» dialog (`transfer-dialog.tsx::handleSubmit` via
 * `submitToProcurementWithChecklist`).
 *
 * Testing 2 row 29 (FB-260514-220805-be23): МОП fills these fields when
 * transferring a quote to procurement; the procurement-side roles (МОЗ /
 * РОЗ / СтМОЗ) were seeing «Данных нет» because the rendering was orphaned
 * during the April 2026 context-panel merge (see commit 35ea2e44). The
 * fetch in `queries.ts::fetchQuoteContextData` was kept; this component is
 * the missing render surface, now wired back into `ContextPanel` so the
 * checklist is visible from procurement-onward without re-opening the
 * sales-step dialog.
 */
export interface SalesChecklist {
  is_estimate: boolean;
  is_tender: boolean;
  direct_request: boolean;
  trading_org_request: boolean;
  equipment_description: string;
  /**
   * Optional free-text note МОП can attach in the «Контрольный список» modal.
   * Surfaced on the «Нераспределено» kanban cards (logistics + customs) and
   * here on the context panel so МОЛ / МОТ can read the distribution hint
   * without re-opening the modal. Persisted to JSONB, null when empty.
   *
   * Marked optional because legacy quotes pre-dating the field carry a
   * sales_checklist JSONB without this key — readers fall through `?.trim()`
   * to "" and the hint surface is skipped.
   */
  distribution_comment?: string | null;
  completed_at: string | null;
  completed_by: string | null;
}

interface SalesChecklistBlockProps {
  checklist: SalesChecklist | null;
  /**
   * Testing 2 row 61: МОП / РОП need to amend the distribution_comment after
   * transfer (when the modal is unreachable). When true, this block renders
   * an edit affordance on the «Комментарий для распределения» line.
   *
   * Defaults to false so the existing read-only callers
   * (procurement / logistics / customs context panels) keep their current
   * behaviour without any prop change.
   */
  canEditDistributionComment?: boolean;
  /**
   * Quote id needed to wire the inline edit through to
   * `updateDistributionComment`. Required when `canEditDistributionComment`
   * is true; otherwise unused.
   */
  quoteId?: string;
}

const REQUEST_TYPE_BADGES: {
  key: keyof Pick<
    SalesChecklist,
    "is_estimate" | "is_tender" | "direct_request" | "trading_org_request"
  >;
  label: string;
}[] = [
  { key: "is_estimate", label: "Проценка" },
  { key: "is_tender", label: "Тендер" },
  { key: "direct_request", label: "Прямой запрос" },
  { key: "trading_org_request", label: "Через торгующих" },
];

/**
 * Returns true if the checklist carries any user-entered content. Used to
 * hide the entire block when the quote came through a path that never
 * populated `sales_checklist` (e.g., legacy quotes pre-dating the dialog).
 *
 * Tester edge case (Testing 2 row 29): "if all fields null → hide block".
 *
 * Testing 2 row 61: when the viewer can edit distribution_comment, we want
 * to keep the block visible even for an otherwise-empty checklist so the
 * edit affordance stays reachable. Callers that grant edit access pass
 * `includeEditableSlot=true`.
 */
export function hasSalesChecklistContent(
  checklist: SalesChecklist | null,
  options: { includeEditableSlot?: boolean } = {},
): checklist is SalesChecklist {
  if (!checklist) return options.includeEditableSlot ?? false;
  if (
    checklist.is_estimate ||
    checklist.is_tender ||
    checklist.direct_request ||
    checklist.trading_org_request
  ) {
    return true;
  }
  if (checklist.equipment_description?.trim().length > 0) {
    return true;
  }
  if ((checklist.distribution_comment?.trim().length ?? 0) > 0) {
    return true;
  }
  // Editable slot keeps the block alive even for an empty checklist so МОП /
  // РОП always have somewhere to add the hint after transfer.
  return options.includeEditableSlot ?? false;
}

export function SalesChecklistBlock({
  checklist,
  canEditDistributionComment = false,
  quoteId,
}: SalesChecklistBlockProps) {
  if (
    !hasSalesChecklistContent(checklist, {
      includeEditableSlot: canEditDistributionComment,
    })
  ) {
    return null;
  }

  const activeBadges = checklist
    ? REQUEST_TYPE_BADGES.filter((b) => checklist[b.key])
    : [];
  const description = checklist?.equipment_description?.trim() ?? "";

  return (
    <div
      className="space-y-2 min-w-0"
      data-testid="context-panel-sales-checklist"
    >
      <div className="flex items-center gap-2 mb-2">
        <ClipboardList size={14} className="text-muted-foreground" />
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          От МОП
        </h4>
      </div>

      {activeBadges.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {activeBadges.map((b) => (
            <Badge
              key={b.key}
              variant="secondary"
              className="bg-amber-100 text-amber-700"
            >
              {b.label}
            </Badge>
          ))}
        </div>
      )}

      {description && (
        <div className="space-y-1">
          <span className="text-xs text-muted-foreground">
            Описание оборудования
          </span>
          <div className="rounded-md bg-muted/30 px-3 py-2 text-sm text-foreground whitespace-pre-wrap break-words">
            {description}
          </div>
        </div>
      )}

      <DistributionCommentRow
        value={checklist?.distribution_comment ?? null}
        canEdit={canEditDistributionComment}
        quoteId={quoteId}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Distribution comment row — read-only by default, inline-edit for МОП / РОП
// ---------------------------------------------------------------------------

/**
 * Single «Комментарий для распределения» line. Three states:
 *   - readonly + has value → render value as before (existing behaviour).
 *   - readonly + empty → render nothing (parent block hidden by content gate).
 *   - canEdit → render value + «Изменить» button; clicking the button swaps in
 *     an inline textarea with save / cancel actions.
 *
 * Testing 2 row 61: after transfer, МОП / РОП lose access to the
 * «Передать в закупки» modal; this affordance restores edit capability without
 * reopening the modal.
 */
function DistributionCommentRow({
  value,
  canEdit,
  quoteId,
}: {
  value: string | null;
  canEdit: boolean;
  quoteId?: string;
}) {
  const trimmed = (value ?? "").trim();

  if (!canEdit) {
    // Legacy read-only path — render only when there's content. Returns
    // before any hook is called so existing test setups stay simple for
    // non-edit roles (procurement / logistics / customs etc.).
    if (!trimmed) return null;
    return (
      <div
        className="space-y-1"
        data-testid="context-panel-distribution-comment"
      >
        <span className="text-xs text-muted-foreground">
          Комментарий для распределения
        </span>
        <div className="rounded-md bg-muted/30 px-3 py-2 text-sm text-foreground whitespace-pre-wrap break-words">
          {trimmed}
        </div>
      </div>
    );
  }

  // Defer editor state to a dedicated component so its hooks only fire for
  // sales-tier viewers (admin / sales / head_of_sales). Keeps the read-only
  // path (every other role) hook-free.
  return (
    <DistributionCommentEditor
      value={value}
      quoteId={quoteId}
      initialTrimmed={trimmed}
    />
  );
}

function DistributionCommentEditor({
  value,
  quoteId,
  initialTrimmed,
}: {
  value: string | null;
  quoteId?: string;
  initialTrimmed: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(value ?? "");
  const [saving, setSaving] = useState(false);
  // Latest server-confirmed value — used so the read-only display reflects
  // the just-saved comment without waiting for the parent's
  // `revalidatePath` to round-trip. The server action revalidates the
  // route, so other consumers (sales-step inline editor, kanban card)
  // pick up the new value on their next navigation/refresh.
  const [displayValue, setDisplayValue] = useState<string>(initialTrimmed);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keep draft + display in sync with external value changes when not
  // actively editing (parent prop updates after navigation/refresh).
  useEffect(() => {
    if (!editing) {
      setDraft(value ?? "");
      setDisplayValue((value ?? "").trim());
    }
  }, [value, editing]);

  // Focus the textarea when entering edit mode so the user can start typing
  // immediately. Cursor lands at the end of existing content.
  useEffect(() => {
    if (editing && textareaRef.current) {
      const ta = textareaRef.current;
      ta.focus();
      const len = ta.value.length;
      ta.setSelectionRange(len, len);
    }
  }, [editing]);

  const trimmed = displayValue;

  const handleSave = useCallback(async () => {
    if (!quoteId) {
      toast.error("Не удалось определить КП для сохранения");
      return;
    }
    const normalised = draft.trim();
    if (normalised === displayValue) {
      setEditing(false);
      return;
    }
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
      toast.success("Комментарий обновлён");
      // Adopt server-canonical value locally so the read-only line updates
      // immediately. The server action's revalidatePath ensures other
      // consumers see the change on their next navigation.
      setDisplayValue((res.value ?? "").trim());
      setEditing(false);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось сохранить комментарий",
      );
    } finally {
      setSaving(false);
    }
  }, [draft, quoteId, displayValue]);

  const handleCancel = useCallback(() => {
    setDraft(displayValue);
    setEditing(false);
  }, [displayValue]);

  return (
    <div
      className="space-y-1"
      data-testid="context-panel-distribution-comment"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">
          Комментарий для распределения
        </span>
        {!editing && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => setEditing(true)}
            data-testid="context-panel-distribution-comment-edit"
          >
            <Pencil size={12} />
            {trimmed ? "Изменить" : "Добавить"}
          </Button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <Textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Опционально: уточнения для МОЛ / МОТ"
            rows={3}
            disabled={saving}
            data-testid="context-panel-distribution-comment-textarea"
          />
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              className="bg-accent text-white hover:bg-accent-hover"
              onClick={() => void handleSave()}
              disabled={saving}
              data-testid="context-panel-distribution-comment-save"
            >
              {saving ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Check size={12} />
              )}
              Сохранить
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              disabled={saving}
              data-testid="context-panel-distribution-comment-cancel"
            >
              <X size={12} />
              Отмена
            </Button>
          </div>
        </div>
      ) : trimmed ? (
        <div className="rounded-md bg-muted/30 px-3 py-2 text-sm text-foreground whitespace-pre-wrap break-words">
          {trimmed}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground italic">
          Не указан
        </p>
      )}
    </div>
  );
}
