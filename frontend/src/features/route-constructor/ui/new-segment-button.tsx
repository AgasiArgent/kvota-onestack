"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NewSegmentButtonProps {
  onClick: () => void;
  disabled?: boolean;
  className?: string;
}

/**
 * NewSegmentButton — end-cap CTA to append a new draft segment to the
 * current invoice. Kept as its own component so the placement (end of
 * the timeline vs. header toolbar) can be tweaked without touching the
 * timeline layout.
 */
export function NewSegmentButton({
  onClick,
  disabled,
  className,
}: NewSegmentButtonProps) {
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={onClick}
      disabled={disabled}
      className={cn("gap-2", className)}
    >
      <Plus size={14} strokeWidth={2} aria-hidden />
      Добавить сегмент
    </Button>
  );
}
