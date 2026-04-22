"use client";

import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface AutofillSparkleProps {
  sourceQuoteIdn?: string | null;
  sourceCreatedAt?: string | null;
  className?: string;
}

/**
 * Inline marker for autofilled customs cells.
 * Renders a small sparkle icon with a tooltip citing the source Q-number.
 */
export function AutofillSparkle({
  sourceQuoteIdn,
  sourceCreatedAt,
  className,
}: AutofillSparkleProps) {
  const tooltip = buildTooltip(sourceQuoteIdn, sourceCreatedAt);
  return (
    <span
      className={cn("inline-flex items-center text-accent", className)}
      title={tooltip}
      aria-label={tooltip}
    >
      <Sparkles size={12} strokeWidth={2} />
    </span>
  );
}

function buildTooltip(idn?: string | null, createdAt?: string | null): string {
  const src = idn && idn.length > 0 ? `КП ${idn}` : "истории";
  if (!createdAt) return `Автозаполнено из ${src}`;
  const d = new Date(createdAt);
  if (Number.isNaN(d.getTime())) return `Автозаполнено из ${src}`;
  const formatted = d.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return `Автозаполнено из ${src} (${formatted})`;
}
