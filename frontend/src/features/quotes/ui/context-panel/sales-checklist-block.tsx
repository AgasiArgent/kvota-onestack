"use client";

import { Badge } from "@/components/ui/badge";
import { Phone, Mail, UserCog } from "lucide-react";

export interface SalesChecklist {
  is_estimate: boolean;
  is_tender: boolean;
  direct_request: boolean;
  trading_org_request: boolean;
  equipment_description: string;
  completed_at: string | null;
  completed_by: string | null;
}

interface SalesChecklistBlockProps {
  checklist: SalesChecklist | null;
  contactPerson: {
    name: string;
    phone: string | null;
    email: string | null;
  } | null;
  salesManager: {
    id: string;
    full_name: string;
    phone: string | null;
    email: string | null;
  } | null;
  additionalInfo: string | null;
}

const REQUEST_TYPE_BADGES: {
  key: keyof Pick<
    SalesChecklist,
    "is_estimate" | "is_tender" | "direct_request" | "trading_org_request"
  >;
  label: string;
}[] = [
  { key: "is_estimate", label: "Проценка" },
  { key: "is_tender", label: "Тендер" },
  { key: "direct_request", label: "Прямой запрос" },
  { key: "trading_org_request", label: "Через торгующих" },
];

export function SalesChecklistBlock({
  checklist,
  contactPerson,
  salesManager,
  additionalInfo,
}: SalesChecklistBlockProps) {
  const activeBadges = checklist
    ? REQUEST_TYPE_BADGES.filter((b) => checklist[b.key])
    : [];

  const hasAnyContent =
    checklist || contactPerson || salesManager || additionalInfo;

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        Контекст продаж
      </h4>

      {/* Request type badges */}
      {activeBadges.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {activeBadges.map((b) => (
            <Badge
              key={b.key}
              variant="secondary"
              className="bg-amber-100 text-amber-700"
            >
              {b.label}
            </Badge>
          ))}
        </div>
      )}

      {/* Equipment description (from sales_checklist JSON) */}
      {checklist?.equipment_description && (
        <div className="rounded-md bg-muted/30 px-3 py-2 text-sm text-foreground whitespace-pre-wrap">
          {checklist.equipment_description}
        </div>
      )}

      {/* Additional info (quotes.additional_info column) */}
      {additionalInfo && (
        <div className="space-y-1">
          <span className="text-xs text-muted-foreground">Доп. информация</span>
          <div className="rounded-md bg-muted/30 px-3 py-2 text-sm text-foreground whitespace-pre-wrap">
            {additionalInfo}
          </div>
        </div>
      )}

      {/* Sales manager (responsible МОП) */}
      {salesManager && (
        <div className="space-y-1">
          <span className="text-xs text-muted-foreground">Ответственный МОП</span>
          <div className="flex items-center flex-wrap gap-x-4 gap-y-1 text-sm">
            <div className="flex items-center gap-1.5 text-foreground">
              <UserCog size={13} className="text-muted-foreground" />
              <span>{salesManager.full_name || "\u2014"}</span>
            </div>
            {salesManager.phone && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <Phone size={12} />
                <span className="tabular-nums">{salesManager.phone}</span>
              </div>
            )}
            {salesManager.email && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <Mail size={12} />
                <span>{salesManager.email}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {!hasAnyContent && (
        <p className="text-sm text-muted-foreground">
          Контекст продаж не заполнен
        </p>
      )}
    </div>
  );
}
