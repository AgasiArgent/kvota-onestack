"use client";

import { useMemo } from "react";
import { Plus, CheckCircle, Loader2, UserCheck, DollarSign } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { QuoteItemRow } from "@/entities/quote/queries";
import { isMoqViolation } from "./moq-warning";

type ProcurementSubStage = "assignment" | "pricing" | "ready";

function getSubStage(items: QuoteItemRow[]): ProcurementSubStage {
  if (items.length === 0) return "assignment";
  const allAssigned = items.every(
    (i) => i.assigned_procurement_user != null || i.is_unavailable === true
  );
  if (!allAssigned) return "assignment";
  const allPriced = items.every(
    (i) => i.purchase_price_original != null || i.is_unavailable === true
  );
  return allPriced ? "ready" : "pricing";
}

const SUB_STAGE_CONFIG: Record<ProcurementSubStage, { label: string; icon: typeof UserCheck; style: string }> = {
  assignment: { label: "Назначение", icon: UserCheck, style: "bg-amber-100 text-amber-700" },
  pricing: { label: "Оценка", icon: DollarSign, style: "bg-blue-100 text-blue-700" },
  ready: { label: "Готово к завершению", icon: CheckCircle, style: "bg-green-100 text-green-700" },
};

interface ProcurementActionBarProps {
  items: QuoteItemRow[];
  onCreateInvoice: () => void;
  onCompleteProcurement: () => void;
  completing?: boolean;
  procurementCompleted?: boolean;
}

export function ProcurementActionBar({
  items,
  onCreateInvoice,
  onCompleteProcurement,
  completing = false,
  procurementCompleted = false,
}: ProcurementActionBarProps) {
  const totalItems = items.length;
  const assignedUserCount = items.filter((i) => i.assigned_procurement_user != null).length;
  const assignedInvoiceCount = items.filter((i) => i.invoice_id != null).length;
  const readyCount = items.filter(
    (i) => i.purchase_price_original != null || i.is_unavailable === true
  ).length;
  const moqViolationCount = useMemo(
    () =>
      items.filter((i) =>
        isMoqViolation({
          quantity: i.quantity,
          min_order_quantity: i.min_order_quantity,
        })
      ).length,
    [items]
  );
  const incomplete = totalItems > 0 && readyCount < totalItems;
  const subStage = getSubStage(items);
  const stageConfig = SUB_STAGE_CONFIG[subStage];
  const StageIcon = stageConfig.icon;

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-3">
      {!procurementCompleted && (
        <Badge variant="outline" className={`gap-1 ${stageConfig.style}`}>
          <StageIcon size={12} />
          {stageConfig.label}
        </Badge>
      )}

      <Button
        size="sm"
        className="bg-accent text-white hover:bg-accent-hover"
        onClick={onCreateInvoice}
        disabled={procurementCompleted}
      >
        <Plus size={14} />
        Создать КП поставщику
      </Button>

      {procurementCompleted ? (
        <span className="inline-flex items-center gap-1.5 text-sm text-success font-medium">
          <CheckCircle size={14} />
          Закупка завершена
        </span>
      ) : (
        <Button
          size="sm"
          className="bg-success text-white hover:bg-success/90"
          disabled={completing}
          onClick={onCompleteProcurement}
        >
          {completing ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <CheckCircle size={14} />
          )}
          Завершить закупку
        </Button>
      )}

      {moqViolationCount > 0 && (
        <Badge
          variant="outline"
          className="ml-auto gap-1 bg-amber-100 text-amber-700 border-amber-200"
          title="Количество ниже минимального заказа поставщика"
        >
          ⚠ MOQ: {moqViolationCount}
        </Badge>
      )}

      <span
        className={`${
          moqViolationCount > 0 ? "" : "ml-auto"
        } text-sm tabular-nums ${
          incomplete ? "text-warning font-medium" : "text-muted-foreground"
        }`}
      >
        {readyCount}/{totalItems} готово | {assignedUserCount} назн. | {assignedInvoiceCount} в КП
      </span>
    </div>
  );
}
