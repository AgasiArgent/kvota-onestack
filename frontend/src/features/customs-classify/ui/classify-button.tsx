"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

import { ClassifyModal } from "./classify-modal";

export interface ClassifyButtonProps {
  quoteItemId: string;
  initialName: string;
  initialBrand?: string;
  /**
   * Called with the chosen code when the user confirms in the modal.
   * Parent dialog typically uses this to update its form state without
   * re-fetching from the DB.
   */
  onSelected: (code: string) => void;
  disabled?: boolean;
  /** Override label. Defaults to "По названию". */
  label?: string;
}

/**
 * Compact trigger button that opens the classification modal.
 *
 * Designed to sit inline next to the manual hs_code input — small enough
 * not to crowd the form when both are visible.
 */
export function ClassifyButton({
  quoteItemId,
  initialName,
  initialBrand,
  onSelected,
  disabled,
  label = "По названию",
}: ClassifyButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        disabled={disabled || !initialName.trim()}
        className="gap-1.5"
        title={
          !initialName.trim()
            ? "Сначала заполните название товара"
            : "Подобрать код ТН ВЭД через Alta Express"
        }
      >
        <Sparkles size={14} />
        {label}
      </Button>
      <ClassifyModal
        open={open}
        onOpenChange={setOpen}
        quoteItemId={quoteItemId}
        initialName={initialName}
        initialBrand={initialBrand}
        onSelected={onSelected}
      />
    </>
  );
}
