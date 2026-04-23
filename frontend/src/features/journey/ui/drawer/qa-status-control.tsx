"use client";

/**
 * QA-status inline control for Task 19.
 *
 * Only rendered when the current user holds a QA writer role (Req 6.5 —
 * admin, quote_controller, spec_controller).
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { QaStatus } from "@/entities/journey";

const QA_OPTIONS: ReadonlyArray<{ value: QaStatus; label: string }> = [
  { value: "verified", label: "Проверено" },
  { value: "broken", label: "Сломано" },
  { value: "untested", label: "Не проверено" },
];

export interface QaStatusControlProps {
  readonly value: QaStatus | null;
  readonly disabled?: boolean;
  readonly onChange: (next: QaStatus) => void;
}

export function QaStatusControl({ value, disabled, onChange }: QaStatusControlProps) {
  return (
    <div
      data-testid="qa-status-control"
      className="flex items-center gap-2"
    >
      <Label htmlFor="journey-qa-status" className="w-24 text-xs text-text-subtle">
        QA
      </Label>
      <Select
        value={value ?? undefined}
        onValueChange={(next: string | null) => {
          if (next) onChange(next as QaStatus);
        }}
        disabled={disabled}
      >
        <SelectTrigger id="journey-qa-status" size="sm" className="w-[160px]">
          <SelectValue placeholder="—" />
        </SelectTrigger>
        <SelectContent>
          {QA_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
