"use client";

import { useMemo, useState } from "react";
import { Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { CustomsAutofillSuggestion } from "../types";

interface AutofillBannerProps {
  totalItems: number;
  suggestions: CustomsAutofillSuggestion[];
  /** Called when user clicks "Принять все". Certificates checkbox must be
   *  checked; banner enforces this state and disables the button otherwise. */
  onAcceptAll: (suggestions: CustomsAutofillSuggestion[]) => void | Promise<void>;
  onDismiss?: () => void;
  pending?: boolean;
}

/**
 * Top-of-table banner announcing available autofill suggestions from history.
 * Requires explicit certificate-check confirmation before bulk-accept.
 */
export function AutofillBanner({
  totalItems,
  suggestions,
  onAcceptAll,
  onDismiss,
  pending = false,
}: AutofillBannerProps) {
  const [certsChecked, setCertsChecked] = useState(false);

  const sourceIdns = useMemo(() => {
    const seen = new Set<string>();
    const ordered: string[] = [];
    for (const s of suggestions) {
      const idn = s.source_quote_idn?.trim();
      if (idn && !seen.has(idn)) {
        seen.add(idn);
        ordered.push(idn);
      }
    }
    return ordered.slice(0, 3);
  }, [suggestions]);

  const canAccept = certsChecked && suggestions.length > 0 && !pending;

  return (
    <div
      role="status"
      className="mb-3 flex flex-col gap-3 rounded-md border border-accent/25 bg-accent/5 p-4 md:flex-row md:items-center"
    >
      <div className="flex items-start gap-3 md:flex-1">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
          <Sparkles size={16} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground">
            {suggestions.length} из {totalItems} позиций автозаполнены из истории
          </div>
          {sourceIdns.length > 0 && (
            <div className="mt-0.5 text-xs text-muted-foreground">
              Источники:{" "}
              {sourceIdns.map((idn, i) => (
                <span key={idn}>
                  <strong className="font-semibold text-foreground">{idn}</strong>
                  {i < sourceIdns.length - 1 ? ", " : ""}
                </span>
              ))}
              . Проверьте актуальность и примите.
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2 md:items-end">
        <label className="flex items-center gap-2 text-xs text-foreground">
          <Checkbox
            checked={certsChecked}
            onCheckedChange={(v) => setCertsChecked(v === true)}
            aria-label="Подтвердить актуальность сертификатов"
          />
          <span>
            <strong className="font-semibold">Сертификаты ДС/СС/СГР актуальны</strong>{" "}
            — проверил
          </span>
        </label>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => onAcceptAll(suggestions)}
            disabled={!canAccept}
          >
            Принять все и завершить
          </Button>
          {onDismiss && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onDismiss}
              aria-label="Скрыть"
            >
              <X size={14} />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
