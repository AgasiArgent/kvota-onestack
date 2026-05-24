"use client";

/**
 * CurrencySelect — small, plain `<select>` dropdown showing the project's
 * supported currency codes (mirrors ``services/currency_service`` /
 * ``shared/lib/currencies``).
 *
 * Mirrors the inline pattern already used in
 * ``features/quotes/ui/procurement-step/invoice-create-modal.tsx``. Lifted
 * to shared/ui so additional surfaces (customs certificates, expenses) can
 * reuse it without duplicating the `<select><option>...` boilerplate or the
 * styling. Use the regular `<Label>` from `@/components/ui/label` above it
 * the same way invoice-create-modal does.
 */

import { cn } from "@/lib/utils";
import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies";

export interface CurrencySelectProps {
  /** Current ISO code. */
  value: string;
  /** Invoked with the new ISO code on change. */
  onChange: (next: string) => void;
  /** ARIA label for screen readers. Defaults to `"Валюта"`. */
  ariaLabel?: string;
  /** Optional id for `<Label htmlFor>` pairing. */
  id?: string;
  /** Disabled state. */
  disabled?: boolean;
  /** Extra Tailwind classes appended to the select's base styles. */
  className?: string;
}

const BASE_CLASSES =
  "w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent " +
  "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring";

export function CurrencySelect({
  value,
  onChange,
  ariaLabel = "Валюта",
  id,
  disabled = false,
  className,
}: CurrencySelectProps) {
  return (
    <select
      id={id}
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className={cn(BASE_CLASSES, className)}
    >
      {SUPPORTED_CURRENCIES.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </select>
  );
}
