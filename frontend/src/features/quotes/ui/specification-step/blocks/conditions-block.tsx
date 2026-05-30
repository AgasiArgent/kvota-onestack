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

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" });
}

export interface ConditionsBlockProps {
  canEdit: boolean;

  signDate: string;
  onSignDateChange: (value: string) => void;

  validityPeriod: string;
  onValidityPeriodChange: (value: string) => void;

  // readiness_period is composed from number + dayType (existing pattern)
  readinessPeriod: string;
  onReadinessPeriodChange: (value: string) => void;
  dayType: string;
  onDayTypeChange: (value: string) => void;

  logisticsPeriod: string;
  onLogisticsPeriodChange: (value: string) => void;

  cargoType: string;
  onCargoTypeChange: (value: string) => void;

  deliveryCityRussia: string;
  onDeliveryCityRussiaChange: (value: string) => void;

  /** Read-only composed readiness value (for display mode). */
  readinessDisplay: string | null;
}

function ReadOnly({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs text-muted-foreground">{label}</span>
      <p className="text-sm">{value || "—"}</p>
    </div>
  );
}

/**
 * Block «Условия спецификации» — Req 3.1–3.4.
 *
 * Maps onto existing specification columns. Renders read-only when the user
 * lacks edit rights (Req 11.2/11.3).
 */
export function ConditionsBlock({
  canEdit,
  signDate,
  onSignDateChange,
  validityPeriod,
  onValidityPeriodChange,
  readinessPeriod,
  onReadinessPeriodChange,
  dayType,
  onDayTypeChange,
  logisticsPeriod,
  onLogisticsPeriodChange,
  cargoType,
  onCargoTypeChange,
  deliveryCityRussia,
  onDeliveryCityRussiaChange,
  readinessDisplay,
}: ConditionsBlockProps) {
  if (!canEdit) {
    return (
      <Card className="p-4 space-y-3">
        <h4 className="text-sm font-semibold">Условия спецификации</h4>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <ReadOnly label="Дата подписания" value={formatDate(signDate || null)} />
          <ReadOnly label="Срок действия" value={validityPeriod} />
          <ReadOnly label="Срок готовности" value={readinessDisplay ?? ""} />
          <ReadOnly label="Срок логистики" value={logisticsPeriod} />
          <ReadOnly label="Тип груза" value={cargoType} />
          <ReadOnly label="Город доставки (РФ)" value={deliveryCityRussia} />
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-4 space-y-3">
      <h4 className="text-sm font-semibold">Условия спецификации</h4>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <Label className="text-xs text-muted-foreground">Дата подписания</Label>
          <Input
            type="date"
            value={signDate}
            onChange={(e) => onSignDateChange(e.target.value)}
            className="h-8 text-sm mt-1"
          />
        </div>
        <div>
          <Label className="text-xs text-muted-foreground">Срок действия</Label>
          <Input
            value={validityPeriod}
            onChange={(e) => onValidityPeriodChange(e.target.value)}
            placeholder="30 дней"
            className="h-8 text-sm mt-1"
          />
        </div>

        {/* readiness_period = number + dayType */}
        <div className="grid grid-cols-2 gap-2 sm:col-span-2">
          <div>
            <Label className="text-xs text-muted-foreground">Срок готовности</Label>
            <Input
              type="number"
              value={readinessPeriod}
              onChange={(e) => onReadinessPeriodChange(e.target.value)}
              placeholder="45"
              className="h-8 text-sm mt-1"
            />
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">Тип дней</Label>
            <Select value={dayType} onValueChange={(v) => onDayTypeChange(v ?? "рабочих дней")}>
              <SelectTrigger className="h-8 text-xs mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="рабочих дней">рабочих дней</SelectItem>
                <SelectItem value="календарных дней">календарных дней</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div>
          <Label className="text-xs text-muted-foreground">Срок логистики</Label>
          <Input
            value={logisticsPeriod}
            onChange={(e) => onLogisticsPeriodChange(e.target.value)}
            placeholder="20 дней"
            className="h-8 text-sm mt-1"
          />
        </div>
        <div>
          <Label className="text-xs text-muted-foreground">Тип груза</Label>
          <Input
            value={cargoType}
            onChange={(e) => onCargoTypeChange(e.target.value)}
            placeholder="Оборудование"
            className="h-8 text-sm mt-1"
          />
        </div>
        <div className="sm:col-span-2">
          <Label className="text-xs text-muted-foreground">Город доставки (РФ)</Label>
          <Input
            value={deliveryCityRussia}
            onChange={(e) => onDeliveryCityRussiaChange(e.target.value)}
            placeholder="Москва"
            className="h-8 text-sm mt-1"
          />
        </div>
      </div>
    </Card>
  );
}
