"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { INCOTERMS_2020 } from "@/shared/lib/incoterms";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import { PaymentSegmentsBlock } from "./payment-segments-block";

const CURRENCIES = ["RUB", "USD", "EUR", "CNY"];
const DM_FEE_TYPES = [
  { value: "fixed", label: "Фикс." },
  { value: "percentage", label: "%" },
];
const DM_FEE_CURRENCIES = ["RUB", "USD", "EUR"];

interface CalculationFormProps {
  quote: QuoteDetailRow;
  savedVariables: Record<string, unknown> | null;
  formValues: Record<string, string>;
  onFieldChange: (key: string, value: string) => void;
}

export function CalculationForm({
  formValues,
  onFieldChange,
}: CalculationFormProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Section 1: Company & terms */}
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
            Компания и условия
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-3">
          <FormRow label="Инкотермс">
            <Select
              value={formValues.offer_incoterms}
              onValueChange={(v) => onFieldChange("offer_incoterms", v ?? "")}
            >
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INCOTERMS_2020.map((t) => (
                  <SelectItem key={t.code} value={t.code}>
                    {t.code} — {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormRow>

          <FormRow label="Валюта КП">
            <Select
              value={formValues.currency}
              onValueChange={(v) => onFieldChange("currency", v ?? "")}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CURRENCIES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormRow>
        </CardContent>
      </Card>

      {/* Section 2: Markup */}
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
            Наценка
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-3">
          <FormRow label="Наценка %">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  min={5}
                  max={100}
                  step={0.1}
                  value={formValues.markup}
                  onChange={(e) => onFieldChange("markup", e.target.value)}
                  className="w-20 text-right"
                />
                <span className="text-xs text-muted-foreground">%</span>
              </div>
              <span className="text-[10px] text-muted-foreground">
                Минимальная наценка — 5%
              </span>
            </div>
          </FormRow>
        </CardContent>
      </Card>

      {/* Section 3: Payment terms — multi-segment block (Testing 2 row 46,
          spec .kiro/specs/payment-segments-row-46/). Replaces single-anchor
          FormRows with 5 anchor rows + presets. */}
      <div className="lg:col-span-2">
        <PaymentSegmentsBlock
          values={{
            advance_from_client: formValues.advance_from_client,
            time_to_advance: formValues.time_to_advance,
            advance_on_loading: formValues.advance_on_loading,
            time_to_advance_loading: formValues.time_to_advance_loading,
            advance_on_going_to_country_destination:
              formValues.advance_on_going_to_country_destination,
            time_to_advance_going_to_country_destination:
              formValues.time_to_advance_going_to_country_destination,
            advance_on_customs_clearance: formValues.advance_on_customs_clearance,
            time_to_advance_on_customs_clearance:
              formValues.time_to_advance_on_customs_clearance,
            time_to_advance_on_receiving: formValues.time_to_advance_on_receiving,
          }}
          onFieldChange={onFieldChange}
        />
      </div>

      {/* Section 4: DM fee */}
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
            Вознаграждение ЛПР
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-3">
          <FormRow label="Тип">
            <Select
              value={formValues.dm_fee_type}
              onValueChange={(v) => onFieldChange("dm_fee_type", v ?? "")}
            >
              <SelectTrigger className="w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DM_FEE_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormRow>

          <FormRow label="Сумма">
            <div className="flex items-center gap-1">
              <Input
                type="number"
                min={0}
                step={0.01}
                value={formValues.dm_fee_value}
                onChange={(e) =>
                  onFieldChange("dm_fee_value", e.target.value)
                }
                className="w-24 text-right"
              />
              <Select
                value={formValues.dm_fee_currency}
                onValueChange={(v) =>
                  onFieldChange("dm_fee_currency", v ?? "")
                }
              >
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DM_FEE_CURRENCIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </FormRow>
          <p className="text-[11px] text-muted-foreground">
            Для % — валюта = валюте КП
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function FormRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <Label className="text-xs text-muted-foreground shrink-0 w-28">
        {label}
      </Label>
      {children}
    </div>
  );
}
