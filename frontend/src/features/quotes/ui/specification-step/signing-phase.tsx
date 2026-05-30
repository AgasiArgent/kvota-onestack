"use client";

import { useCallback, useState } from "react";
import { Check, Download, Loader2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { ReconciliationStrip } from "./reconciliation-strip";

/**
 * control-spec-workspace Req 6–7 — «На подписании» phase UI.
 *
 * Rendered once the quote has reached `pending_signature` (the requisites are
 * locked by the parent, which switches the 4 blocks to read-only). Hosts:
 *   1. Export PDF/DOCX + signed-scan upload (unchanged behaviour, lifted here).
 *   2. The manual `ReconciliationStrip` (structural reconciliation checklist).
 *   3. «Пометить подписанной» → `confirmSignatureAndCreateDeal`, enabled only
 *      when the scan is present AND every reconciliation row is confirmed.
 *
 * Extracted into its own component so `specification-step.tsx` stays well under
 * the 800-line file budget.
 */
export interface SigningPhaseProps {
  specId: string;
  canAct: boolean;
  hasScan: boolean;
  uploading: boolean;
  creatingDeal: boolean;
  onUploadScan: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onCreateDeal: () => void;
  exportPdfUrl: string;
  exportDocxUrl: string;
  reconciliationValues: {
    specNumber: string;
    contract: string;
    parties: string;
    totals: string;
    dates: string;
    signatory: string;
  };
}

export function SigningPhase({
  specId,
  canAct,
  hasScan,
  uploading,
  creatingDeal,
  onUploadScan,
  onCreateDeal,
  exportPdfUrl,
  exportDocxUrl,
  reconciliationValues,
}: SigningPhaseProps) {
  const [reconciled, setReconciled] = useState(false);

  // Stable identity so ReconciliationStrip's effect doesn't re-fire every
  // parent render.
  const handleAllConfirmedChange = useCallback((allConfirmed: boolean) => {
    setReconciled(allConfirmed);
  }, []);

  // «Пометить подписанной» gate (Req 7.1): scan present AND every manual
  // reconciliation row confirmed.
  const canMarkSigned = canAct && hasScan && reconciled;

  return (
    <div className="space-y-4">
      {/* Export + upload */}
      <Card className="p-5 space-y-4">
        <h4 className="text-sm font-semibold">Оформление спецификации</h4>

        {/* Step 1: Export */}
        <div className="flex items-start gap-3">
          <span
            className={cn(
              "flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold shrink-0",
              hasScan ? "bg-green-100 text-green-700" : "bg-accent/10 text-accent",
            )}
          >
            1
          </span>
          <div className="flex-1">
            <p className="text-sm font-medium">Скачать и отправить клиенту</p>
            <p className="text-xs text-muted-foreground mb-2">
              Экспортируйте спецификацию и отправьте на подпись
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(exportPdfUrl, "_blank")}
              >
                <Download size={14} />
                Скачать PDF
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(exportDocxUrl, "_blank")}
              >
                <Download size={14} />
                Скачать DOCX
              </Button>
            </div>
          </div>
        </div>

        <div className="border-t border-border" />

        {/* Step 2: Upload signed scan */}
        <div className="flex items-start gap-3">
          <span
            className={cn(
              "flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold shrink-0",
              hasScan ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground",
            )}
          >
            2
          </span>
          <div className="flex-1">
            <p className="text-sm font-medium">Загрузить подписанный скан</p>
            <p className="text-xs text-muted-foreground mb-2">
              После подписания клиентом загрузите скан
            </p>
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-4 text-center transition-colors",
                hasScan ? "border-green-200 bg-green-50" : "border-border hover:border-accent/50",
              )}
            >
              {hasScan ? (
                <div className="flex items-center justify-center gap-2 text-green-700">
                  <Check size={16} />
                  <span className="text-sm font-medium">Скан загружен</span>
                </div>
              ) : canAct ? (
                <label className="cursor-pointer inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-muted transition-colors">
                  {uploading ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Upload size={14} />
                  )}
                  Выбрать файл (PDF, JPG, PNG)
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    className="hidden"
                    data-testid={`signed-scan-input-${specId}`}
                    onChange={onUploadScan}
                  />
                </label>
              ) : (
                <span className="text-sm text-muted-foreground">Скан не загружен</span>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Structural reconciliation (Req 6) */}
      <ReconciliationStrip
        hasScan={hasScan}
        values={reconciliationValues}
        canConfirm={canAct}
        onAllConfirmedChange={handleAllConfirmedChange}
      />

      {/* Mark signed → create deal (Req 7) */}
      {canAct && (
        <div className="flex items-center justify-end">
          <Button
            onClick={onCreateDeal}
            disabled={!canMarkSigned || creatingDeal}
            className="bg-green-600 text-white hover:bg-green-700"
          >
            {creatingDeal ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Check size={14} />
            )}
            Пометить подписанной
          </Button>
        </div>
      )}
    </div>
  );
}
