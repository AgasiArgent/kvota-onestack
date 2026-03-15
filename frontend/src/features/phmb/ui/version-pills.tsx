"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface VersionPillsProps {
  quoteId: string;
  currentLabel: string;
}

/**
 * Version pills for PHMB workspace.
 *
 * TODO: PHMB versioning requires a dedicated DB table or migration to add
 * phmb_advance_pct/phmb_payment_days/phmb_markup_pct to quote_versions.
 * Currently shows a single "v1" pill as a placeholder.
 * When the migration is done, this component should:
 * - Accept versions: PhmbVersion[], activeVersionId, onSwitch, onCreate
 * - Render pills for each version with active state
 * - "+" button to create a new version (copies current items + terms)
 */
export function VersionPills({ currentLabel }: VersionPillsProps) {
  const [versions] = useState([{ id: "current", label: currentLabel || "v1" }]);

  function handleCreateVersion() {
    toast.info("Версионирование PHMB будет доступно после миграции БД.");
  }

  return (
    <div className="flex items-center gap-1.5">
      {versions.map((v) => (
        <button
          key={v.id}
          type="button"
          className="px-3 py-1 text-xs font-semibold rounded-md bg-accent text-white"
        >
          {v.label}
        </button>
      ))}
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0 text-text-muted hover:text-text"
        onClick={handleCreateVersion}
      >
        <Plus size={14} />
      </Button>
    </div>
  );
}
