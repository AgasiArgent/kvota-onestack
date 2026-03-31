"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { StageDeadline } from "@/entities/settings";
import { upsertStageDeadlines } from "@/entities/settings";

const STAGE_LABELS: Record<string, string> = {
  pending_procurement: "Оценка закупок",
  pending_logistics: "Логистика",
  pending_customs: "Таможня",
  pending_logistics_and_customs: "Логистика и таможня",
  pending_sales_review: "Доработка менеджера",
  pending_quote_control: "Проверка КП",
  pending_approval: "Согласование",
  sent_to_client: "Отправлено клиенту",
  client_negotiation: "Торги",
  pending_spec_control: "Контроль спецификации",
  pending_signature: "Подписание",
};

const STAGE_ORDER = Object.keys(STAGE_LABELS);

interface StageDeadlinesFormProps {
  deadlines: StageDeadline[];
  orgId: string;
}

function buildInitialValues(deadlines: StageDeadline[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const stage of STAGE_ORDER) {
    const existing = deadlines.find((d) => d.stage === stage);
    map[stage] = existing ? String(existing.deadline_hours) : "48";
  }
  return map;
}

export function StageDeadlinesForm({ deadlines, orgId }: StageDeadlinesFormProps) {
  const [values, setValues] = useState(() => buildInitialValues(deadlines));
  const [isSaving, setIsSaving] = useState(false);

  function handleChange(stage: string, value: string) {
    setValues((prev) => ({ ...prev, [stage]: value }));
  }

  async function handleSave() {
    setIsSaving(true);
    try {
      const rows = STAGE_ORDER.map((stage) => ({
        stage,
        deadline_hours: parseInt(values[stage], 10) || 48,
      }));
      await upsertStageDeadlines(orgId, rows);
      toast.success("Дедлайны стадий сохранены");
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
        <CardTitle className="text-base">Дедлайны стадий</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Стадия</TableHead>
              <TableHead className="w-40">Норматив (часы)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {STAGE_ORDER.map((stage) => (
              <TableRow key={stage}>
                <TableCell className="font-medium">
                  {STAGE_LABELS[stage]}
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    min="1"
                    step="1"
                    value={values[stage]}
                    onChange={(e) => handleChange(stage, e.target.value)}
                    className="w-24"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

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
