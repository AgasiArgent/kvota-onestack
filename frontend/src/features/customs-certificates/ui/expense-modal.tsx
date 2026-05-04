"use client";

/**
 * «Новый расход» — simplified modal for the "Свой расход" branch
 * (Phase B Task 7c, REQ-10).
 *
 * Mirror of `CertificateModal` minus the certificate-only fields. REQ-10
 * AC#3 explicitly excludes `type` / `number` / `issuer` / `legal_doc` /
 * `issued_at` / `valid_until` — they remain `NULL` in the DB row. The
 * server still stores the row in `kvota.quote_certificates`, with the
 * branch toggled by `is_custom_expense=true` and `type='custom_expense'`
 * (REQ-10 AC#4).
 *
 * Form fields (REQ-10 AC#2):
 *   - `display_name` — REQUIRED text input.
 *   - `notes`        — optional textarea.
 *   - `cost_rub`     — REQUIRED numeric (≥ 0) with «₽» suffix.
 *   - PositionsMultiSelect + LivePreviewPanel (identical to REQ-7).
 *
 * Submit calls `createCertificate(...)` with the REQ-10 AC#4 body shape:
 * `{quote_id, display_name, notes?, cost_rub, is_custom_expense: true,
 * type: "custom_expense", item_ids}`.
 *
 * Test framework constraint: same as `certificate-modal.tsx` — no jsdom.
 * Pure helpers (`isExpenseFormValid`) are exported and unit-tested in
 * `__tests__/expense-modal.test.tsx`. JSX exercised via SSR; click flow
 * verified at localhost:3000.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import type {
  Certificate,
  CreateCertificateInput,
  QuoteItemForSelect,
} from "../model/types";
import { createCertificate } from "../api/certificates";
import { LivePreviewPanel } from "./live-preview-panel";
import { PositionsMultiSelect } from "./positions-multi-select";

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit testing without a DOM environment.
// ---------------------------------------------------------------------------

/**
 * Form is submittable iff REQUIRED fields are non-empty + valid:
 *  - `display_name` non-empty after trim (REQ-10 AC#2 — REQUIRED).
 *  - `cost_rub` is a finite number `>= 0` (REQ-10 AC#2 — REQUIRED).
 *
 * Optional fields (`notes`) and the multi-select count are all
 * unconstrained — the server allows zero attachments (REQ-2 AC#11).
 */
export function isExpenseFormValid(input: {
  displayName: string;
  costRub: string;
}): boolean {
  if (!input.displayName.trim()) return false;
  if (input.costRub.trim() === "") return false;
  const cost = Number(input.costRub);
  if (!Number.isFinite(cost)) return false;
  if (cost < 0) return false;
  return true;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface ExpenseModalProps {
  /** Open state — controlled by the parent. */
  open: boolean;
  /** Invoked when the user closes the modal (Cancel, Escape, post-success). */
  onOpenChange: (open: boolean) => void;
  /** UUID of the parent quote — server validates `item_ids[]` against this. */
  quoteId: string;
  /** Selectable positions in the current quote. */
  items: QuoteItemForSelect[];
  /** Optional callback fired with the freshly-created custom-expense row. */
  onCreated?: (cert: Certificate) => void;
}

const DISPLAY_NAME_FIELD = "display_name";
const COST_FIELD = "cost_rub";

export function ExpenseModal({
  open,
  onOpenChange,
  quoteId,
  items,
  onCreated,
}: ExpenseModalProps) {
  const [displayName, setDisplayName] = useState("");
  const [notes, setNotes] = useState("");
  const [costRub, setCostRub] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [errorField, setErrorField] = useState<string | null>(null);

  const wasOpenRef = useRef(false);
  useEffect(() => {
    if (open && !wasOpenRef.current) {
      setDisplayName("");
      setNotes("");
      setCostRub("");
      setSelectedIds([]);
      setSubmitting(false);
      setErrorField(null);
    }
    wasOpenRef.current = open;
  }, [open]);

  const selectedItems = useMemo(
    () => items.filter((it) => selectedIds.includes(it.id)),
    [items, selectedIds],
  );
  const certCost = Number(costRub) || 0;
  const canSubmit =
    isExpenseFormValid({ displayName, costRub }) && !submitting;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setErrorField(null);

    const input: CreateCertificateInput = {
      quote_id: quoteId,
      // REQ-10 AC#4 — stored shape on the server.
      type: "custom_expense",
      is_custom_expense: true,
      display_name: displayName.trim(),
      cost_rub: Number(costRub),
      item_ids: selectedIds,
    };
    if (notes.trim()) input.notes = notes.trim();

    try {
      const res = await createCertificate(input);
      if (!res.success) {
        const message = res.error?.message ?? "Не удалось создать расход";
        toast.error(message);
        const field =
          (res.error as { field?: string } | undefined)?.field ?? null;
        setErrorField(field);
        return;
      }

      const cert = res.data as Certificate | undefined;
      if (cert) {
        onCreated?.(cert);
      }
      onOpenChange(false);
    } catch (err) {
      console.error("[ExpenseModal] submit failed", err);
      const message =
        err instanceof Error ? err.message : "Не удалось создать расход";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onOpenChange(false);
      }}
    >
      <DialogContent
        className="sm:max-w-3xl"
        data-slot="expense-modal"
      >
        <DialogHeader>
          <DialogTitle>Новый расход</DialogTitle>
        </DialogHeader>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4"
          aria-label="Форма создания расхода"
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
            {/* LEFT — form (60%) */}
            <div className="flex flex-col gap-3 md:col-span-3">
              {/* display_name */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="expense-display-name"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Название <span className="text-error">*</span>
                </Label>
                <Input
                  id="expense-display-name"
                  value={displayName}
                  onChange={(e) => {
                    setDisplayName(e.target.value);
                    if (errorField === DISPLAY_NAME_FIELD) setErrorField(null);
                  }}
                  placeholder="Услуги декларанта, дополнительная экспертиза…"
                  aria-invalid={
                    errorField === DISPLAY_NAME_FIELD || undefined
                  }
                  className={cn(
                    errorField === DISPLAY_NAME_FIELD && "border-destructive",
                  )}
                  autoFocus
                />
              </fieldset>

              {/* notes */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="expense-notes"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Описание
                </Label>
                <Textarea
                  id="expense-notes"
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Описание услуги…"
                />
              </fieldset>

              {/* cost_rub */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="expense-cost-rub"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Стоимость <span className="text-error">*</span>
                </Label>
                <div className="relative">
                  <Input
                    id="expense-cost-rub"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="0.01"
                    value={costRub}
                    onChange={(e) => {
                      setCostRub(e.target.value);
                      if (errorField === COST_FIELD) setErrorField(null);
                    }}
                    aria-invalid={errorField === COST_FIELD || undefined}
                    className={cn(
                      "pr-7",
                      errorField === COST_FIELD && "border-destructive",
                    )}
                    placeholder="0"
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-text-muted">
                    ₽
                  </span>
                </div>
              </fieldset>
            </div>

            {/* RIGHT — multi-select + live preview (40%) */}
            <div className="flex flex-col gap-3 md:col-span-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Прикрепить к позициям
              </div>
              <PositionsMultiSelect
                items={items}
                selectedIds={selectedIds}
                onChange={setSelectedIds}
              />
              <LivePreviewPanel
                selectedItems={selectedItems}
                certCost={certCost}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              variant="default"
              disabled={!canSubmit}
              data-slot="expense-submit"
            >
              {submitting ? "Сохранение…" : "Сохранить"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
