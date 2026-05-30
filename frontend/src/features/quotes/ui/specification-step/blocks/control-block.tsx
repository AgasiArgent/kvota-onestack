"use client";

import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";

export type SigningFxMode = "cbr_on_payment_day" | "fixed";

const FX_MODE_LABELS: Record<SigningFxMode, string> = {
  cbr_on_payment_day: "По курсу ЦБ на день оплаты",
  fixed: "Фиксированный курс",
};

export interface ControlBlockProps {
  canEdit: boolean;

  signingFxMode: SigningFxMode;
  onSigningFxModeChange: (mode: SigningFxMode) => void;
  signingFxRate: string;
  onSigningFxRateChange: (value: string) => void;

  /** Display name (or id) of the responsible controller — current user. */
  controllerLabel: string;
  /** Control date display (set server-side on «Отправить на подписание»). */
  controlDate: string | null;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" });
}

/**
 * Block «Контроль» — Req 4.1–4.5.
 *
 * At-signing FX selector (`signing_fx_mode` / `signing_fx_rate`), responsible
 * controller (current user), and the control-date field (actually set in the
 * «Отправить на подписание» transition — PR3; here it is display-only).
 */
export function ControlBlock({
  canEdit,
  signingFxMode,
  onSigningFxModeChange,
  signingFxRate,
  onSigningFxRateChange,
  controllerLabel,
  controlDate,
}: ControlBlockProps) {
  return (
    <Card className="p-4 space-y-3">
      <h4 className="text-sm font-semibold">Контроль</h4>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Signing FX mode */}
        <div>
          <Label className="text-xs text-muted-foreground">Курс на подписании</Label>
          {canEdit ? (
            <Select
              value={signingFxMode}
              onValueChange={(v) => onSigningFxModeChange((v as SigningFxMode) ?? "cbr_on_payment_day")}
            >
              <SelectTrigger className="h-8 text-sm mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cbr_on_payment_day">
                  {FX_MODE_LABELS.cbr_on_payment_day}
                </SelectItem>
                <SelectItem value="fixed">{FX_MODE_LABELS.fixed}</SelectItem>
              </SelectContent>
            </Select>
          ) : (
            <p className="text-sm mt-1">{FX_MODE_LABELS[signingFxMode]}</p>
          )}
        </div>

        {/* Fixed rate (only when mode === 'fixed') */}
        {signingFxMode === "fixed" && (
          <div>
            <Label className="text-xs text-muted-foreground">Фиксированный курс</Label>
            {canEdit ? (
              <Input
                type="number"
                step="0.0001"
                value={signingFxRate}
                onChange={(e) => onSigningFxRateChange(e.target.value)}
                placeholder="0.0000"
                className="h-8 text-sm mt-1"
              />
            ) : (
              <p className="text-sm mt-1">{signingFxRate || "—"}</p>
            )}
          </div>
        )}

        <div>
          <span className="text-xs text-muted-foreground">Ответственный контролёр</span>
          <p className="text-sm">{controllerLabel}</p>
        </div>

        <div>
          <span className="text-xs text-muted-foreground">Дата контроля</span>
          <p className="text-sm">{formatDate(controlDate)}</p>
        </div>
      </div>
    </Card>
  );
}
