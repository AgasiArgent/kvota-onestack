"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { PhmbSettings } from "@/entities/settings";
import { upsertPhmbSettings } from "@/entities/settings";

interface PhmbFormProps {
  settings: PhmbSettings | null;
  orgId: string;
}

function toStr(val: number | undefined | null): string {
  return val != null ? String(val) : "";
}

function pctOf(value: string, base: string): string {
  const v = parseFloat(value);
  const b = parseFloat(base);
  if (!b || isNaN(v)) return "0.00";
  return ((v / b) * 100).toFixed(2);
}

export function PhmbForm({ settings, orgId }: PhmbFormProps) {
  const [basePricePerPallet, setBasePricePerPallet] = useState(
    toStr(settings?.base_price_per_pallet)
  );
  const [logisticsPerPallet, setLogisticsPerPallet] = useState(
    toStr(settings?.logistics_price_per_pallet)
  );
  const [customsHandling, setCustomsHandling] = useState(
    toStr(settings?.customs_handling_cost)
  );
  const [exchangeRateInsurance, setExchangeRateInsurance] = useState(
    toStr(settings?.exchange_rate_insurance_pct)
  );
  const [financialTransit, setFinancialTransit] = useState(
    toStr(settings?.financial_transit_pct)
  );
  const [customsInsurance, setCustomsInsurance] = useState(
    toStr(settings?.customs_insurance_pct)
  );
  const [markupPct, setMarkupPct] = useState(
    toStr(settings?.default_markup_pct)
  );
  const [advancePct, setAdvancePct] = useState(
    toStr(settings?.default_advance_pct)
  );
  const [paymentDays, setPaymentDays] = useState(
    toStr(settings?.default_payment_days)
  );
  const [deliveryDays, setDeliveryDays] = useState(
    toStr(settings?.default_delivery_days)
  );

  const [isSaving, setIsSaving] = useState(false);

  // Bidirectional markup <-> margin
  const markupNum = parseFloat(markupPct) || 0;
  const marginPct =
    markupNum > 0
      ? ((markupNum / (100 + markupNum)) * 100).toFixed(2)
      : "0.00";

  function handleMarginChange(val: string) {
    const margin = parseFloat(val);
    if (isNaN(margin) || margin >= 100) return;
    const markup = margin > 0 ? (margin / (100 - margin)) * 100 : 0;
    setMarkupPct(markup.toFixed(2));
  }

  async function handleSave() {
    setIsSaving(true);
    try {
      await upsertPhmbSettings(orgId, {
        base_price_per_pallet: parseFloat(basePricePerPallet) || 0,
        logistics_price_per_pallet: parseFloat(logisticsPerPallet) || 0,
        customs_handling_cost: parseFloat(customsHandling) || 0,
        exchange_rate_insurance_pct: parseFloat(exchangeRateInsurance) || 0,
        financial_transit_pct: parseFloat(financialTransit) || 0,
        customs_insurance_pct: parseFloat(customsInsurance) || 0,
        default_markup_pct: parseFloat(markupPct) || 0,
        default_advance_pct: parseFloat(advancePct) || 0,
        default_payment_days: parseInt(paymentDays) || 0,
        default_delivery_days: parseInt(deliveryDays) || 0,
      });
      toast.success("Настройки PHMB сохранены");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка сохранения";
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Base pallet price */}
      <Card className="border-accent/20 bg-accent-subtle/30">
        <CardContent className="pt-4">
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Базовая стоимость паллета (знаменатель)
            </Label>
            <Input
              type="number"
              step="0.01"
              value={basePricePerPallet}
              onChange={(e) => setBasePricePerPallet(e.target.value)}
              placeholder="50000"
            />
            <p className="text-xs text-text-subtle">
              Все накладные расходы делятся на эту сумму для получения процентных
              коэффициентов.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left: overhead costs */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Накладные расходы</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <OverheadField
              label="Логистика на паллет, USD"
              value={logisticsPerPallet}
              onChange={setLogisticsPerPallet}
              pct={pctOf(logisticsPerPallet, basePricePerPallet)}
            />
            <OverheadField
              label="Таможенное оформление, USD"
              value={customsHandling}
              onChange={setCustomsHandling}
              pct={pctOf(customsHandling, basePricePerPallet)}
            />
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Страхование валютного курса, %
              </Label>
              <Input
                type="number"
                step="0.01"
                value={exchangeRateInsurance}
                onChange={(e) => setExchangeRateInsurance(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Финансовый транзит, %
              </Label>
              <Input
                type="number"
                step="0.01"
                value={financialTransit}
                onChange={(e) => setFinancialTransit(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Таможенная страховка, %
              </Label>
              <Input
                type="number"
                step="0.01"
                value={customsInsurance}
                onChange={(e) => setCustomsInsurance(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Right: default values */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Значения по умолчанию</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Наценка, %
              </Label>
              <Input
                type="number"
                step="0.01"
                value={markupPct}
                onChange={(e) => setMarkupPct(e.target.value)}
              />
            </div>

            {/* Markup <-> Margin calculator */}
            <div className="rounded-lg bg-background p-3 border border-border-light">
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-muted">Маржа, %</span>
                <Input
                  type="number"
                  step="0.01"
                  value={marginPct}
                  onChange={(e) => handleMarginChange(e.target.value)}
                  className="w-24 text-right"
                />
              </div>
              <p className="text-xs text-text-subtle mt-1">
                Наценка {markupPct || "0"}% = Маржа {marginPct}%
              </p>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Аванс, %
              </Label>
              <Input
                type="number"
                step="0.01"
                value={advancePct}
                onChange={(e) => setAdvancePct(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Срок оплаты, дней
              </Label>
              <Input
                type="number"
                step="1"
                value={paymentDays}
                onChange={(e) => setPaymentDays(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Срок поставки, дней
              </Label>
              <Input
                type="number"
                step="1"
                value={deliveryDays}
                onChange={(e) => setDeliveryDays(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      <div>
        <Button
          onClick={handleSave}
          disabled={isSaving}
          className="w-full md:w-auto bg-accent text-white hover:bg-accent-hover"
        >
          {isSaving ? "Сохранение..." : "Сохранить"}
        </Button>
      </div>
    </div>
  );
}

function OverheadField({
  label,
  value,
  onChange,
  pct,
}: {
  label: string;
  value: string;
  onChange: (val: string) => void;
  pct: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </Label>
      <div className="flex items-center gap-2">
        <Input
          type="number"
          step="0.01"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1"
        />
        <span className="text-sm text-accent font-medium whitespace-nowrap min-w-[60px] text-right">
          {pct}%
        </span>
      </div>
    </div>
  );
}
