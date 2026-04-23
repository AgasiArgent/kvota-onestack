"use client";

/**
 * Impl & QA status filter groups (Req 4.10 — status filtering).
 *
 * Each row is a checkbox; checked = INCLUDED (default). Toggling off
 * appends the value to `*StatusesExcluded` on the filter state.
 */

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  ALL_IMPL_FILTER_VALUES,
  ALL_QA_FILTER_VALUES,
  type ImplFilterValue,
  type QaFilterValue,
} from "../../lib/use-journey-filter";

const IMPL_LABELS_RU: Record<ImplFilterValue, string> = {
  done: "Готово",
  partial: "Частично",
  missing: "Отсутствует",
  unset: "Не задано",
};

const QA_LABELS_RU: Record<QaFilterValue, string> = {
  verified: "Проверено",
  broken: "Сломано",
  untested: "Не тестировано",
  unset: "Не задано",
};

interface ImplProps {
  readonly excluded: readonly ImplFilterValue[];
  readonly onToggle: (value: ImplFilterValue) => void;
}

export function ImplStatusFilter({ excluded, onToggle }: ImplProps) {
  const excludedSet = new Set<ImplFilterValue>(excluded);
  return (
    <div className="flex flex-col gap-2" data-testid="journey-impl-filter">
      <span className="text-xs text-text-subtle">Impl-статус</span>
      {ALL_IMPL_FILTER_VALUES.map((value) => {
        const id = `journey-impl-${value}`;
        const checked = !excludedSet.has(value);
        return (
          <div key={value} className="flex items-center gap-2">
            <Checkbox
              id={id}
              checked={checked}
              onCheckedChange={() => onToggle(value)}
              data-testid={`journey-impl-filter-${value}`}
            />
            <Label htmlFor={id} className="text-sm text-text cursor-pointer">
              {IMPL_LABELS_RU[value]}
            </Label>
          </div>
        );
      })}
    </div>
  );
}

interface QaProps {
  readonly excluded: readonly QaFilterValue[];
  readonly onToggle: (value: QaFilterValue) => void;
}

export function QaStatusFilter({ excluded, onToggle }: QaProps) {
  const excludedSet = new Set<QaFilterValue>(excluded);
  return (
    <div className="flex flex-col gap-2" data-testid="journey-qa-filter">
      <span className="text-xs text-text-subtle">QA-статус</span>
      {ALL_QA_FILTER_VALUES.map((value) => {
        const id = `journey-qa-${value}`;
        const checked = !excludedSet.has(value);
        return (
          <div key={value} className="flex items-center gap-2">
            <Checkbox
              id={id}
              checked={checked}
              onCheckedChange={() => onToggle(value)}
              data-testid={`journey-qa-filter-${value}`}
            />
            <Label htmlFor={id} className="text-sm text-text cursor-pointer">
              {QA_LABELS_RU[value]}
            </Label>
          </div>
        );
      })}
    </div>
  );
}
