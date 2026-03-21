"use client";

import { useState, useCallback } from "react";
import { ChevronRight, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  CustomsDeclaration,
  CustomsDeclarationItem,
} from "@/entities/customs-declaration";

const ruFmt = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 0,
});

const ruFmt2 = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatRub(v: number | null): string {
  if (v === null || v === 0) return "—";
  return ruFmt.format(v);
}

function formatRub2(v: number | null): string {
  if (v === null || v === 0) return "—";
  return ruFmt2.format(v);
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

interface Props {
  declarations: CustomsDeclaration[];
  allItems: Record<string, CustomsDeclarationItem[]>;
}

export function DeclarationsTable({ declarations, allItems }: Props) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleRow = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between bg-gradient-to-br from-slate-50 to-slate-100 border border-border-light rounded-xl px-6 py-5">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-semibold text-text-primary">
            Таможенные декларации (ДТ)
          </span>
          <Badge variant="secondary" className="bg-violet-100 text-violet-700">
            {declarations.length}
          </Badge>
        </div>
        <Button
          size="sm"
          className="bg-accent text-white hover:bg-accent-hover"
          onClick={() => {
            // Placeholder for upload functionality
          }}
        >
          <Upload size={16} />
          Загрузить ДТ
        </Button>
      </div>

      {/* Table */}
      <div className="bg-white border border-border-light rounded-xl shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8" />
              <TableHead>Номер ДТ</TableHead>
              <TableHead>Дата</TableHead>
              <TableHead>Отправитель</TableHead>
              <TableHead>Внутр. ссылка</TableHead>
              <TableHead className="text-right">Там. стоимость, руб.</TableHead>
              <TableHead className="text-right">Пошлина, руб.</TableHead>
              <TableHead className="text-right">Сбор, руб.</TableHead>
              <TableHead className="text-center">Позиций</TableHead>
              <TableHead>Совпадения</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {declarations.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={10}
                  className="text-center py-12 text-text-subtle"
                >
                  Декларации ещё не загружены
                </TableCell>
              </TableRow>
            )}
            {declarations.map((d) => {
              const isExpanded = expandedIds.has(d.id);
              const items = allItems[d.id] ?? [];

              return (
                <DeclarationRow
                  key={d.id}
                  declaration={d}
                  items={items}
                  isExpanded={isExpanded}
                  onToggle={toggleRow}
                />
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function DeclarationRow({
  declaration: d,
  items,
  isExpanded,
  onToggle,
}: {
  declaration: CustomsDeclaration;
  items: CustomsDeclarationItem[];
  isExpanded: boolean;
  onToggle: (id: string) => void;
}) {
  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-slate-50"
        onClick={() => onToggle(d.id)}
      >
        <TableCell className="w-8 px-3">
          <ChevronRight
            size={14}
            className={`text-text-subtle transition-transform duration-200 ${
              isExpanded ? "rotate-90" : ""
            }`}
          />
        </TableCell>
        <TableCell className="font-medium text-accent">
          {d.regnum || "—"}
        </TableCell>
        <TableCell className="text-text-muted tabular-nums">
          {formatDate(d.declaration_date)}
        </TableCell>
        <TableCell className="text-text-muted max-w-[200px] truncate">
          {d.sender_name || "—"}
        </TableCell>
        <TableCell className="text-text-muted">
          {d.internal_ref || "—"}
        </TableCell>
        <TableCell className="text-right tabular-nums">
          {formatRub(d.total_customs_value_rub)}
        </TableCell>
        <TableCell className="text-right tabular-nums">
          {formatRub(d.total_duty_rub)}
        </TableCell>
        <TableCell className="text-right tabular-nums">
          {formatRub(d.total_fee_rub)}
        </TableCell>
        <TableCell className="text-center tabular-nums">
          {d.item_count}
        </TableCell>
        <TableCell>
          {d.matched_count > 0 ? (
            <span className="inline-flex items-center rounded-md bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
              {d.matched_count}/{d.item_count} совпад.
            </span>
          ) : (
            <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
              Нет совпадений
            </span>
          )}
        </TableCell>
      </TableRow>

      {/* Expanded items sub-table */}
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={10} className="p-0 bg-slate-50/50">
            <ItemsSubTable items={items} />
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function ItemsSubTable({ items }: { items: CustomsDeclarationItem[] }) {
  if (items.length === 0) {
    return (
      <div className="px-6 py-4 text-sm text-text-subtle">
        Позиции не найдены
      </div>
    );
  }

  return (
    <div className="px-4 py-2 overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="text-[11px]">
            <TableHead className="py-1.5">Блок.поз.</TableHead>
            <TableHead className="py-1.5">SKU</TableHead>
            <TableHead className="py-1.5">Описание</TableHead>
            <TableHead className="py-1.5">Бренд</TableHead>
            <TableHead className="py-1.5">Код ТН ВЭД</TableHead>
            <TableHead className="py-1.5">Кол-во</TableHead>
            <TableHead className="py-1.5 text-right">Ст-ть инвойса</TableHead>
            <TableHead className="py-1.5 text-right">Там. ст-ть, руб.</TableHead>
            <TableHead className="py-1.5 text-right">Пошлина, руб.</TableHead>
            <TableHead className="py-1.5 text-right">Сбор, руб.</TableHead>
            <TableHead className="py-1.5 text-right">НДС, руб.</TableHead>
            <TableHead className="py-1.5">Сделка</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id} className="text-xs">
              <TableCell className="py-1.5">
                {item.block_number ?? ""}.{item.item_number ?? ""}
              </TableCell>
              <TableCell className="py-1.5">{item.sku || "—"}</TableCell>
              <TableCell className="py-1.5 max-w-[200px] truncate">
                {item.description || "—"}
              </TableCell>
              <TableCell className="py-1.5">{item.brand || "—"}</TableCell>
              <TableCell className="py-1.5 tabular-nums">
                {item.hs_code || "—"}
              </TableCell>
              <TableCell className="py-1.5 tabular-nums">
                {formatRub2(item.quantity)}{" "}
                {item.unit || ""}
              </TableCell>
              <TableCell className="py-1.5 text-right tabular-nums">
                {formatRub2(item.invoice_cost)}{" "}
                {item.invoice_currency || ""}
              </TableCell>
              <TableCell className="py-1.5 text-right tabular-nums">
                {formatRub2(item.customs_value_rub)}
              </TableCell>
              <TableCell className="py-1.5 text-right tabular-nums">
                {formatRub2(item.duty_amount_rub)}
              </TableCell>
              <TableCell className="py-1.5 text-right tabular-nums">
                {formatRub2(item.fee_amount_rub)}
              </TableCell>
              <TableCell className="py-1.5 text-right tabular-nums">
                {formatRub2(item.vat_amount_rub)}
              </TableCell>
              <TableCell className="py-1.5">
                {item.deal_id ? (
                  <a
                    href={`/finance/${item.deal_id}`}
                    className="text-accent hover:underline text-xs"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Сделка
                  </a>
                ) : (
                  <span className="text-text-subtle">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
