"use client";

import { useState } from "react";
import { ChevronDown, Save } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface PaymentTerms {
  phmb_advance_pct: number;
  phmb_payment_days: number;
  phmb_markup_pct: number;
}

interface PaymentTermsPanelProps {
  terms: PaymentTerms;
  onSave: (terms: PaymentTerms) => void;
  isSaving: boolean;
}

export function PaymentTermsPanel({
  terms,
  onSave,
  isSaving,
}: PaymentTermsPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [localTerms, setLocalTerms] = useState<PaymentTerms>(terms);

  const hasChanges =
    localTerms.phmb_advance_pct !== terms.phmb_advance_pct ||
    localTerms.phmb_payment_days !== terms.phmb_payment_days ||
    localTerms.phmb_markup_pct !== terms.phmb_markup_pct;

  function handleFieldChange(field: keyof PaymentTerms, value: string) {
    const numValue = parseFloat(value);
    if (isNaN(numValue)) return;
    setLocalTerms((prev) => ({ ...prev, [field]: numValue }));
  }

  function handleSave() {
    onSave(localTerms);
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border border-border-light rounded-lg bg-card">
        <CollapsibleTrigger
          className="flex items-center justify-between w-full px-5 py-3 text-left hover:bg-accent-subtle transition-colors rounded-lg"
        >
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-text">
              Условия оплаты
            </span>
            <span className="text-xs text-text-muted">
              Аванс {terms.phmb_advance_pct}% | Наценка{" "}
              {terms.phmb_markup_pct}% | Отсрочка {terms.phmb_payment_days} дн.
            </span>
          </div>
          <ChevronDown
            size={16}
            className={`text-text-muted transition-transform ${
              isOpen ? "rotate-180" : ""
            }`}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-5 pb-4 pt-2 border-t border-border-light">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-1.5">
                  Аванс, %
                </Label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={localTerms.phmb_advance_pct}
                  onChange={(e) =>
                    handleFieldChange("phmb_advance_pct", e.target.value)
                  }
                  className="tabular-nums"
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-1.5">
                  Срок оплаты, к.д.
                </Label>
                <Input
                  type="number"
                  min={0}
                  max={365}
                  step={1}
                  value={localTerms.phmb_payment_days}
                  onChange={(e) =>
                    handleFieldChange("phmb_payment_days", e.target.value)
                  }
                  className="tabular-nums"
                />
              </div>
              <div>
                <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted mb-1.5">
                  Наценка, %
                </Label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  value={localTerms.phmb_markup_pct}
                  onChange={(e) =>
                    handleFieldChange("phmb_markup_pct", e.target.value)
                  }
                  className="tabular-nums"
                />
              </div>
            </div>
            <div className="flex justify-end mt-4">
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!hasChanges || isSaving}
                className="bg-accent text-white hover:bg-accent-hover"
              >
                <Save size={16} />
                {isSaving ? "Сохранение..." : "Сохранить"}
              </Button>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
