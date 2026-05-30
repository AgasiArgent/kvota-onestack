"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Circle, FileText, Lock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * control-spec-workspace Req 6 — структурная сверка (manual checklist, no OCR).
 *
 * In the «На подписании» phase the controller compares the uploaded signed
 * scan (left, by reference) against the system values (right) and ticks each
 * row to confirm it matches. `scan_uploaded` is not a manual toggle — it is
 * auto-confirmed when the signed scan is present. «Пометить подписанной» stays
 * disabled until the scan is present AND every manual row is confirmed; the
 * parent gates the button off `onAllConfirmedChange`.
 *
 * Shape clones the spirit of `control-step/use-control-checks.ts`'s
 * `CheckResult`, but each row is a stateful manual confirmation rather than a
 * derived status.
 */
export type ReconCheckId =
  | "scan_uploaded"
  | "spec_number"
  | "contract"
  | "parties"
  | "totals"
  | "dates"
  | "signatory";

export interface ReconCheck {
  id: ReconCheckId;
  label: string;
  systemValue: string;
  confirmed: boolean;
}

export interface ReconciliationStripProps {
  /** Whether the signed scan is uploaded (drives the auto `scan_uploaded` row). */
  hasScan: boolean;
  /** System value rows (right column) the controller confirms against the scan. */
  values: {
    specNumber: string;
    contract: string;
    parties: string;
    totals: string;
    dates: string;
    signatory: string;
  };
  /** When false the rows render read-only (no toggling). */
  canConfirm: boolean;
  /**
   * Notifies the parent whether every gate is satisfied (scan present AND every
   * manual row confirmed) so it can enable «Пометить подписанной».
   */
  onAllConfirmedChange: (allConfirmed: boolean) => void;
}

// Manual rows the controller must tick (scan_uploaded is auto, excluded here).
const MANUAL_ROWS: { id: Exclude<ReconCheckId, "scan_uploaded">; label: string }[] = [
  { id: "spec_number", label: "Номер спецификации" },
  { id: "contract", label: "Договор" },
  { id: "parties", label: "Стороны" },
  { id: "totals", label: "Суммы" },
  { id: "dates", label: "Даты" },
  { id: "signatory", label: "Подписант" },
];

export function ReconciliationStrip({
  hasScan,
  values,
  canConfirm,
  onAllConfirmedChange,
}: ReconciliationStripProps) {
  // Manual confirmations keyed by row id. scan_uploaded is derived from hasScan.
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});

  const systemValueFor = useMemo<Record<string, string>>(
    () => ({
      spec_number: values.specNumber,
      contract: values.contract,
      parties: values.parties,
      totals: values.totals,
      dates: values.dates,
      signatory: values.signatory,
    }),
    [values],
  );

  const allManualConfirmed = MANUAL_ROWS.every((row) => confirmed[row.id]);
  const allConfirmed = hasScan && allManualConfirmed;

  useEffect(() => {
    onAllConfirmedChange(allConfirmed);
  }, [allConfirmed, onAllConfirmedChange]);

  function toggle(id: string) {
    if (!canConfirm) return;
    setConfirmed((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center gap-2">
        <FileText size={16} className="text-muted-foreground" />
        <h4 className="text-sm font-semibold">Структурная сверка</h4>
        <span className="ml-auto text-xs text-muted-foreground">
          Сверьте подписанный скан со значениями системы
        </span>
      </div>

      <div className="grid grid-cols-[1fr_auto] gap-x-4 text-xs text-muted-foreground">
        <span>Подписанный скан (визуальная проверка)</span>
        <span className="text-right">Значение в системе</span>
      </div>

      <div className="divide-y divide-border rounded-lg border border-border">
        {/* Auto row: scan uploaded */}
        <div className="flex items-center gap-3 px-3 py-2">
          {hasScan ? (
            <CheckCircle2 size={16} className="shrink-0 text-green-600" />
          ) : (
            <Circle size={16} className="shrink-0 text-muted-foreground" />
          )}
          <span className="text-sm">Скан загружен</span>
          <span
            className={cn(
              "ml-auto text-xs font-medium",
              hasScan ? "text-green-700" : "text-amber-600",
            )}
          >
            {hasScan ? "Загружен" : "Не загружен"}
          </span>
        </div>

        {/* Manual rows */}
        {MANUAL_ROWS.map((row) => {
          const isConfirmed = !!confirmed[row.id];
          return (
            <button
              key={row.id}
              type="button"
              onClick={() => toggle(row.id)}
              disabled={!canConfirm}
              aria-pressed={isConfirmed}
              aria-label={`Подтвердить: ${row.label}`}
              className={cn(
                "flex w-full items-center gap-3 px-3 py-2 text-left transition-colors",
                canConfirm ? "hover:bg-muted/50" : "cursor-default",
              )}
            >
              {canConfirm ? (
                isConfirmed ? (
                  <CheckCircle2 size={16} className="shrink-0 text-green-600" />
                ) : (
                  <Circle size={16} className="shrink-0 text-muted-foreground" />
                )
              ) : (
                <Lock size={14} className="shrink-0 text-muted-foreground" />
              )}
              <span className="text-sm">{row.label}</span>
              <span className="ml-auto max-w-[55%] truncate text-xs text-foreground">
                {systemValueFor[row.id] || "—"}
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
