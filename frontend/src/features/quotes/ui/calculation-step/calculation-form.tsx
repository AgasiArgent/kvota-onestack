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
import type { QuoteDetailRow } from "@/entities/quote/queries";

const SALE_TYPES = [
  { value: "поставка", label: "Поставка" },
  { value: "транзит", label: "Транзит" },
];

const INCOTERMS = ["DDP", "DAP", "CIF", "FOB", "EXW"];
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
          <FormRow label="Тип сделки">
            <Select
              value={formValues.offer_sale_type}
              onValueChange={(v) => onFieldChange("offer_sale_type", v ?? "")}
            >
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SALE_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormRow>

          <FormRow label="Инкотермс">
            <Select
              value={formValues.offer_incoterms}
              onValueChange={(v) => onFieldChange("offer_incoterms", v ?? "")}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INCOTERMS.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
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
            <div className="flex items-center gap-1">
              <Input
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={formValues.markup}
                onChange={(e) => onFieldChange("markup", e.target.value)}
                className="w-20 text-right"
              />
              <span className="text-xs text-muted-foreground">%</span>
            </div>
          </FormRow>
        </CardContent>
      </Card>

      {/* Section 3: Payment terms */}
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
            Условия оплаты
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-3">
          <FormRow label="Аванс клиента">
            <div className="flex items-center gap-1">
              <Input
                type="number"
                min={0}
                max={100}
                step={1}
                value={formValues.advance_from_client}
                onChange={(e) =>
                  onFieldChange("advance_from_client", e.target.value)
                }
                className="w-16 text-right"
              />
              <span className="text-xs text-muted-foreground">%</span>
            </div>
          </FormRow>

          <FormRow label="До аванса">
            <div className="flex items-center gap-1">
              <Input
                type="number"
                min={0}
                value={formValues.time_to_advance}
                onChange={(e) =>
                  onFieldChange("time_to_advance", e.target.value)
                }
                className="w-16 text-right"
              />
              <span className="text-xs text-muted-foreground">дн.</span>
            </div>
          </FormRow>

          <FormRow label="До расчёта">
            <div className="flex items-center gap-1">
              <Input
                type="number"
                min={0}
                value={formValues.time_to_advance_on_receiving}
                onChange={(e) =>
                  onFieldChange(
                    "time_to_advance_on_receiving",
                    e.target.value
                  )
                }
                className="w-16 text-right"
              />
              <span className="text-xs text-muted-foreground">дн.</span>
            </div>
          </FormRow>
        </CardContent>
      </Card>

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
