"use client";

/**
 * Impl-status inline control for Task 19.
 *
 * Only rendered when the current user holds an IMPL writer role (Req 6.4).
 * Mirrors the value → label mapping that the read-only badge used in Task 18
 * so the UI speaks the same Russian labels in both modes.
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { ImplStatus } from "@/entities/journey";

const IMPL_OPTIONS: ReadonlyArray<{ value: ImplStatus; label: string }> = [
  { value: "done", label: "Готово" },
  { value: "partial", label: "Частично" },
  { value: "missing", label: "Нет" },
];

export interface ImplStatusControlProps {
  readonly value: ImplStatus | null;
  readonly disabled?: boolean;
  readonly onChange: (next: ImplStatus) => void;
}

export function ImplStatusControl({ value, disabled, onChange }: ImplStatusControlProps) {
  return (
    <div
      data-testid="impl-status-control"
      className="flex items-center gap-2"
    >
      <Label htmlFor="journey-impl-status" className="w-24 text-xs text-text-subtle">
        Реализация
      </Label>
      <Select
        value={value ?? undefined}
        onValueChange={(next: string | null) => {
          if (next) onChange(next as ImplStatus);
        }}
        disabled={disabled}
      >
        <SelectTrigger id="journey-impl-status" size="sm" className="w-[160px]">
          <SelectValue placeholder="—" />
        </SelectTrigger>
        <SelectContent>
          {IMPL_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
