"use client";

import dynamic from "next/dynamic";
import type { ProcurementEditorItem } from "./procurement-handsontable";

export type { ProcurementEditorItem } from "./procurement-handsontable";

const ProcurementHandsontable = dynamic(
  () =>
    import("./procurement-handsontable").then((m) => ({
      default: m.ProcurementHandsontable,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Загрузка...
      </div>
    ),
  }
);

interface ProcurementItemsEditorProps {
  items: ProcurementEditorItem[];
  invoiceId: string;
  procurementCompleted: boolean;
}

export function ProcurementItemsEditor({
  items,
  invoiceId,
  procurementCompleted,
}: ProcurementItemsEditorProps) {
  return (
    <ProcurementHandsontable
      items={items}
      invoiceId={invoiceId}
      procurementCompleted={procurementCompleted}
    />
  );
}
