"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CalcSettings } from "@/entities/settings";
import { upsertCalcSettings } from "@/entities/settings";

interface CalcRatesFormProps {
  settings: CalcSettings | null;
  orgId: string;
}

export function CalcRatesForm({ settings, orgId }: CalcRatesFormProps) {
  const [forexRisk, setForexRisk] = useState(
    settings?.rate_forex_risk?.toString() ?? ""
  );
  const [finComm, setFinComm] = useState(
    settings?.rate_fin_comm?.toString() ?? ""
  );
  const [loanRate, setLoanRate] = useState(
    settings?.rate_loan_interest_daily?.toString() ?? ""
  );
  const [isSaving, setIsSaving] = useState(false);

  async function handleSave() {
    setIsSaving(true);
    try {
      await upsertCalcSettings(orgId, {
        rate_forex_risk: parseFloat(forexRisk) || 0,
        rate_fin_comm: parseFloat(finComm) || 0,
        rate_loan_interest_daily: parseFloat(loanRate) || 0,
      });
      toast.success("Настройки расчёта сохранены");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка сохранения";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Параметры расчёта КП</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Валютный риск, %
            </Label>
            <Input
              type="number"
              step="0.01"
              value={forexRisk}
              onChange={(e) => setForexRisk(e.target.value)}
              placeholder="3.00"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Фин. комиссия, %
            </Label>
            <Input
              type="number"
              step="0.01"
              value={finComm}
              onChange={(e) => setFinComm(e.target.value)}
              placeholder="2.00"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Ставка займа (дн.), %
            </Label>
            <Input
              type="number"
              step="0.0001"
              value={loanRate}
              onChange={(e) => setLoanRate(e.target.value)}
              placeholder="0.0685"
            />
          </div>
        </div>

        <div className="pt-2">
          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="w-full md:w-auto bg-accent text-white hover:bg-accent-hover"
          >
            {isSaving ? "Сохранение..." : "Сохранить"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
