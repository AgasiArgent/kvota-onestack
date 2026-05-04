"use client";

/**
 * «Новый сертификат» — full-form modal for creating a customs certificate
 * with multi-position attach and live-preview cost split (Phase B Task 7c).
 *
 * Covers REQ-7 AC#1..#11:
 *   - Title «Новый сертификат» on create.
 *   - Two-column layout (form ~60% / preview ~40%) on desktop, single-column
 *     under 768px (Tailwind `md:` breakpoint).
 *   - 8 form fields top-to-bottom in REQ-7 AC#3 order: type / number / issuer
 *     / legal_doc / issued_at / valid_until / cost_rub / notes.
 *   - `type` is a searchable creatable Combobox seeded with the 10 standard
 *     options from REQ-7 AC#3 (`SEEDED_TYPES`); user may type a custom value.
 *   - PositionsMultiSelect (REQ-7 AC#4) + LivePreviewPanel (REQ-7 AC#5) on
 *     the right side share-derived from selected items via the cost-split
 *     helper (Task 6 re-export).
 *   - Submit calls `createCertificate(input)` from `../api/certificates.ts`.
 *   - Success → `onCreated(cert)` fires + modal closes via `onOpenChange(false)`.
 *   - Error → toast (sonner) + modal stays open with field values intact.
 *
 * Test framework constraint: no jsdom. Pure helpers (`isFormValid`,
 * `filterTypeOptions`, the createable-combobox pure logic from
 * `TypeCreatableCombobox.tsx`) are exported and unit-tested in
 * `__tests__/certificate-modal.test.tsx`. JSX is exercised via SSR
 * snapshot. Click-flow verification happens at localhost:3000 per
 * `reference_localhost_browser_test.md`.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Search, X } from "lucide-react";
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
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
// Seeded constants (REQ-7 AC#3 — 10 standard certificate types)
// ---------------------------------------------------------------------------

/**
 * Initial options for the `type` Combobox. The Combobox is `creatable` —
 * if the user types a value not in this list the form accepts it and the
 * server stores it as-is.
 */
export const SEEDED_TYPES: readonly string[] = [
  "ДС ТР ТС",
  "СС",
  "СГР",
  "ОТТС",
  "EUR.1",
  "Form A",
  "CT-1",
  "CT-2",
  "CT-3",
  "A.TR",
];

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit testing without a DOM environment.
// ---------------------------------------------------------------------------

/**
 * Form is submittable iff REQUIRED fields are non-empty + valid:
 *  - `type` non-empty after trim (REQ-7 AC#3 type is REQUIRED).
 *  - `cost_rub` is a finite number `>= 0` (REQ-7 AC#3 cost_rub REQUIRED).
 *
 * Optional fields (number, issuer, legal_doc, issued_at, valid_until,
 * notes) and the multi-select count are all unconstrained — the user
 * can save a cert with zero attached items (server allows it; matches
 * REQ-2 AC#11 «may be empty»).
 */
export function isFormValid(input: {
  type: string;
  costRub: string;
}): boolean {
  if (!input.type.trim()) return false;
  if (input.costRub.trim() === "") return false;
  const cost = Number(input.costRub);
  if (!Number.isFinite(cost)) return false;
  if (cost < 0) return false;
  return true;
}

/**
 * Case-insensitive substring filter for the type Combobox options.
 * Returns the full list for empty/whitespace-only queries.
 */
export function filterTypeOptions(
  options: readonly string[],
  query: string,
): readonly string[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return options;
  return options.filter((opt) => opt.toLowerCase().includes(needle));
}

// ---------------------------------------------------------------------------
// Inline creatable Combobox — REQ-7 AC#3 + AC#9 (searchable + creatable).
// ---------------------------------------------------------------------------
//
// The shared `SearchableCombobox` (`frontend/src/shared/ui/searchable-combobox.tsx`)
// is selection-only — it cannot accept a custom value typed in the search
// input. REQ-7 AC#3 explicitly allows the user to enter a non-seeded value,
// so we inline a small creatable variant here. The component is exported as
// a named function so other Phase-B sub-tasks (e.g. Edit flow in Task 10)
// can re-use it without lifting it to `shared/ui/` prematurely.

interface TypeCreatableComboboxProps {
  /** Currently committed value (free-form string). */
  value: string;
  /** Invoked with the new value on commit (select / create / typed-Enter). */
  onChange: (next: string) => void;
  /** Seeded suggestion list — typically `SEEDED_TYPES`. */
  options: readonly string[];
  /** Trigger placeholder when value is empty. Default: «Выберите или введите тип». */
  placeholder?: string;
  /** Marks the trigger with a destructive border when validation fails. */
  invalid?: boolean;
  /** ARIA label for the trigger button. */
  ariaLabel?: string;
}

/**
 * Searchable + creatable Combobox for the `type` field. Behavior:
 *  - Typing in the search filters seeded options case-insensitively.
 *  - Pressing Enter (or clicking «Создать "{query}"» row) commits a
 *    custom value not present in the seeded list.
 *  - Clicking a seeded row commits that exact value.
 *  - Escape / click-outside closes the popover without committing.
 */
export function TypeCreatableCombobox({
  value,
  onChange,
  options,
  placeholder = "Выберите или введите тип",
  invalid = false,
  ariaLabel = "Тип сертификата",
}: TypeCreatableComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () => filterTypeOptions(options, query),
    [options, query],
  );

  const trimmedQuery = query.trim();
  const showCreate =
    trimmedQuery.length > 0 &&
    !options.some(
      (opt) => opt.toLowerCase() === trimmedQuery.toLowerCase(),
    );

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next) setQuery("");
  }

  function commit(nextValue: string) {
    onChange(nextValue);
    setOpen(false);
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      if (filtered.length > 0) {
        commit(filtered[0]);
      } else if (showCreate) {
        commit(trimmedQuery);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={ariaLabel}
            className={cn(
              "inline-flex h-8 w-full items-center justify-between gap-2 rounded-lg border bg-background px-2.5 py-1 text-sm",
              "hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              "aria-expanded:bg-muted",
              invalid ? "border-destructive" : "border-input",
            )}
          >
            <span
              className={cn(
                "truncate",
                value ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {value || placeholder}
            </span>
            <ChevronsUpDown size={14} className="text-muted-foreground/60" />
          </button>
        }
      />
      <PopoverContent className="w-72 p-0" side="bottom" align="start">
        <div className="flex flex-col">
          <div className="border-b border-border p-2">
            <div className="relative">
              <Search
                className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                size={14}
              />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder="Поиск или новый тип..."
                className="h-7 pl-7 text-xs"
                autoFocus
                aria-label="Поиск типа сертификата"
              />
              {query.length > 0 && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Очистить поиск"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          <div
            className="overflow-y-auto py-1"
            style={{ maxHeight: 240 }}
            data-slot="type-options-list"
          >
            {filtered.length === 0 && !showCreate ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Ничего не найдено
              </div>
            ) : (
              <>
                {filtered.map((opt) => {
                  const isSelected = opt === value;
                  return (
                    <button
                      type="button"
                      key={opt}
                      onClick={() => commit(opt)}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs",
                        "hover:bg-muted/50",
                      )}
                    >
                      <span className="flex w-3 shrink-0 justify-center text-accent">
                        {isSelected && <Check size={12} />}
                      </span>
                      <span className="flex-1 truncate text-foreground">
                        {opt}
                      </span>
                    </button>
                  );
                })}
                {showCreate && (
                  <button
                    type="button"
                    onClick={() => commit(trimmedQuery)}
                    className={cn(
                      "flex w-full items-center gap-2 border-t border-border px-3 py-1.5 text-left text-xs text-info",
                      "hover:bg-muted/50",
                    )}
                    data-slot="type-create-row"
                  >
                    <span className="flex w-3 shrink-0 justify-center">+</span>
                    <span className="flex-1 truncate">
                      Создать «{trimmedQuery}»
                    </span>
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface CertificateModalProps {
  /** Open state — controlled by the parent. */
  open: boolean;
  /**
   * Invoked when the user closes the modal (Cancel, Escape, click overlay,
   * post-success). The parent decides whether to also clear residual state.
   */
  onOpenChange: (open: boolean) => void;
  /** UUID of the parent quote — server validates `item_ids[]` against this. */
  quoteId: string;
  /** Selectable positions in the current quote (passed to multi-select). */
  items: QuoteItemForSelect[];
  /**
   * Optional callback fired with the freshly-created certificate after a
   * successful POST. Parents typically use this to optimistically append
   * the cert to a local list or trigger a re-fetch.
   */
  onCreated?: (cert: Certificate) => void;
  /**
   * Optional pre-fill values applied on the rising edge of `open`.
   *
   * Used by REQ-5 AC#9 / REQ-7 AC#3 — when the cost-aware history banner
   * surfaces an expired match, clicking «Создать новый» opens the modal
   * pre-filled with the prior `type` and `cost_rub` so the customs
   * specialist can re-issue the document without re-typing identical
   * fields. The user still enters fresh `number` / `issued_at` /
   * `valid_until`. Both fields are independently optional.
   */
  preset?: { type?: string; cost_rub?: number };
  /**
   * Optional list of item ids ticked in the multi-select on the rising
   * edge of `open`. Used by REQ-8 — when the per-item dialog's
   * «Создать новый» action opens the modal, the current item is
   * pre-selected so the user only needs to confirm.
   */
  preSelectedItemIds?: string[];
}

const TYPE_FIELD_NAME = "type";
const COST_FIELD_NAME = "cost_rub";

export function CertificateModal({
  open,
  onOpenChange,
  quoteId,
  items,
  onCreated,
  preset,
  preSelectedItemIds,
}: CertificateModalProps) {
  const [type, setType] = useState("");
  const [number, setNumber] = useState("");
  const [issuer, setIssuer] = useState("");
  const [legalDoc, setLegalDoc] = useState("");
  const [issuedAt, setIssuedAt] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [costRub, setCostRub] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  /**
   * `errorField` matches `error.field` from the server envelope when set,
   * so we can highlight the offending field with `aria-invalid` + the
   * destructive border. Cleared on the next field edit.
   */
  const [errorField, setErrorField] = useState<string | null>(null);

  // Reset all form state when the modal opens. Mirrors `create-customer-dialog`
  // — closing the modal does not clear state immediately, so re-opening with a
  // fresh slate requires this on `open` rising-edge.
  //
  // `preset` and `preSelectedItemIds` are applied on the same rising-edge so
  // the pre-fill survives the reset that would otherwise clear them. Editing
  // the prefilled value mid-session won't be clobbered — `wasOpenRef` ensures
  // we only reset when going from closed → open, not on every render.
  const wasOpenRef = useRef(false);
  useEffect(() => {
    if (open && !wasOpenRef.current) {
      setType(preset?.type ?? "");
      setNumber("");
      setIssuer("");
      setLegalDoc("");
      setIssuedAt("");
      setValidUntil("");
      setCostRub(
        preset?.cost_rub != null && Number.isFinite(preset.cost_rub)
          ? String(preset.cost_rub)
          : "",
      );
      setNotes("");
      setSelectedIds(preSelectedItemIds ?? []);
      setSubmitting(false);
      setErrorField(null);
    }
    wasOpenRef.current = open;
  }, [open, preset, preSelectedItemIds]);

  const selectedItems = useMemo(
    () => items.filter((it) => selectedIds.includes(it.id)),
    [items, selectedIds],
  );
  const certCost = Number(costRub) || 0;
  const canSubmit =
    isFormValid({ type, costRub }) && !submitting;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setErrorField(null);

    const input: CreateCertificateInput = {
      quote_id: quoteId,
      type: type.trim(),
      cost_rub: Number(costRub),
      item_ids: selectedIds,
    };
    if (number.trim()) input.number = number.trim();
    if (issuer.trim()) input.issuer = issuer.trim();
    if (legalDoc.trim()) input.legal_doc = legalDoc.trim();
    if (issuedAt) input.issued_at = issuedAt;
    if (validUntil) input.valid_until = validUntil;
    if (notes.trim()) input.notes = notes.trim();

    try {
      const res = await createCertificate(input);
      if (!res.success) {
        const message = res.error?.message ?? "Не удалось создать сертификат";
        toast.error(message);
        // Server may include `field` on validation errors — record it so
        // the next render shows a destructive border on the offending input.
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
      console.error("[CertificateModal] submit failed", err);
      const message =
        err instanceof Error ? err.message : "Не удалось создать сертификат";
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
        data-slot="certificate-modal"
      >
        <DialogHeader>
          <DialogTitle>Новый сертификат</DialogTitle>
        </DialogHeader>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4"
          aria-label="Форма создания сертификата"
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
            {/* LEFT — form (60%) */}
            <div className="flex flex-col gap-3 md:col-span-3">
              {/* type */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="cert-type"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Тип <span className="text-error">*</span>
                </Label>
                <TypeCreatableCombobox
                  value={type}
                  onChange={(next) => {
                    setType(next);
                    if (errorField === TYPE_FIELD_NAME) setErrorField(null);
                  }}
                  options={SEEDED_TYPES}
                  invalid={errorField === TYPE_FIELD_NAME}
                />
              </fieldset>

              {/* number */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="cert-number"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Номер
                </Label>
                <Input
                  id="cert-number"
                  value={number}
                  onChange={(e) => setNumber(e.target.value)}
                  placeholder="ЕАЭС N RU Д-CN.…"
                  className="font-mono text-xs"
                />
              </fieldset>

              {/* issuer */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="cert-issuer"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Орган сертификации
                </Label>
                <Input
                  id="cert-issuer"
                  value={issuer}
                  onChange={(e) => setIssuer(e.target.value)}
                  placeholder="Сертэксперт ЦСМ"
                />
              </fieldset>

              {/* legal_doc */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="cert-legal-doc"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Регламент
                </Label>
                <Input
                  id="cert-legal-doc"
                  value={legalDoc}
                  onChange={(e) => setLegalDoc(e.target.value)}
                  placeholder="ТР ТС 010/2011"
                />
              </fieldset>

              {/* issued_at */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="cert-issued-at"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Дата выдачи
                </Label>
                <Input
                  id="cert-issued-at"
                  type="date"
                  value={issuedAt}
                  onChange={(e) => setIssuedAt(e.target.value)}
                />
              </fieldset>

              {/* valid_until */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="cert-valid-until"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Действителен до
                </Label>
                <Input
                  id="cert-valid-until"
                  type="date"
                  value={validUntil}
                  onChange={(e) => setValidUntil(e.target.value)}
                />
                <p className="text-xs text-text-muted">
                  Оставьте пустым для бессрочного
                </p>
              </fieldset>

              {/* cost_rub */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="cert-cost-rub"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Стоимость <span className="text-error">*</span>
                </Label>
                <div className="relative">
                  <Input
                    id="cert-cost-rub"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="0.01"
                    value={costRub}
                    onChange={(e) => {
                      setCostRub(e.target.value);
                      if (errorField === COST_FIELD_NAME) setErrorField(null);
                    }}
                    aria-invalid={errorField === COST_FIELD_NAME || undefined}
                    className={cn(
                      "pr-7",
                      errorField === COST_FIELD_NAME && "border-destructive",
                    )}
                    placeholder="0"
                  />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-text-muted">
                    ₽
                  </span>
                </div>
              </fieldset>

              {/* notes */}
              <fieldset className="flex flex-col gap-1.5">
                <Label
                  htmlFor="cert-notes"
                  className="text-xs font-semibold uppercase tracking-wide text-text-muted"
                >
                  Заметки
                </Label>
                <Textarea
                  id="cert-notes"
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Дополнительные сведения о сертификате…"
                />
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
              data-slot="cert-submit"
            >
              {submitting ? "Сохранение…" : "Сохранить"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
