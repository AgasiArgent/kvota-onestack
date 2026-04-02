"use client";

import { Badge } from "@/components/ui/badge";
import { Phone, Mail, User } from "lucide-react";

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
  salesManager: { id: string; full_name: string } | null;
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
}: SalesChecklistBlockProps) {
  const activeBadges = checklist
    ? REQUEST_TYPE_BADGES.filter((b) => checklist[b.key])
    : [];

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

      {/* Equipment description */}
      {checklist?.equipment_description && (
        <div className="rounded-md bg-muted/30 px-3 py-2 text-sm text-foreground">
          {checklist.equipment_description}
        </div>
      )}

      {/* Contact person */}
      {contactPerson && (
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <User size={13} />
            <span>{contactPerson.name}</span>
          </div>
          {contactPerson.phone && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Phone size={12} />
              <span className="tabular-nums">{contactPerson.phone}</span>
            </div>
          )}
          {contactPerson.email && (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Mail size={12} />
              <span>{contactPerson.email}</span>
            </div>
          )}
        </div>
      )}

      {/* Sales manager */}
      {salesManager && (
        <div className="text-sm text-muted-foreground">
          МОП: <span className="text-foreground">{salesManager.full_name}</span>
        </div>
      )}

      {!checklist && !contactPerson && !salesManager && (
        <p className="text-sm text-muted-foreground">
          Чеклист продаж не заполнен
        </p>
      )}
    </div>
  );
}
