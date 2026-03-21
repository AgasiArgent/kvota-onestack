"use client";

import { useState } from "react";
import { ClipboardList, Clock, CheckCircle2, ChevronDown } from "lucide-react";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface WorkflowStatusBannerProps {
  workflowStatus: string;
  approvalTriggers: string[];
}

interface StatusAppearance {
  icon: typeof ClipboardList;
  label: string;
  bannerClass: string;
  iconClass: string;
}

function getStatusAppearance(status: string): StatusAppearance {
  switch (status) {
    case "pending_quote_control":
      return {
        icon: ClipboardList,
        label: "Требуется проверка",
        bannerClass: "bg-amber-50 text-amber-800 border border-amber-200",
        iconClass: "text-amber-600",
      };
    case "pending_approval":
      return {
        icon: Clock,
        label: "Ожидает согласования топ-менеджера",
        bannerClass: "bg-blue-50 text-blue-800 border border-blue-200",
        iconClass: "text-blue-600",
      };
    case "approved":
    case "sent_to_client":
    case "accepted":
      return {
        icon: CheckCircle2,
        label: "КП одобрено",
        bannerClass: "bg-green-50 text-green-800 border border-green-200",
        iconClass: "text-green-600",
      };
    default:
      return {
        icon: ClipboardList,
        label: status,
        bannerClass: "bg-muted text-muted-foreground border border-border",
        iconClass: "text-muted-foreground",
      };
  }
}

export function WorkflowStatusBanner({
  workflowStatus,
  approvalTriggers,
}: WorkflowStatusBannerProps) {
  const [triggersOpen, setTriggersOpen] = useState(false);
  const appearance = getStatusAppearance(workflowStatus);
  const Icon = appearance.icon;
  const hasTriggers = approvalTriggers.length > 0;

  return (
    <div className="space-y-2">
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg px-4 py-3",
          appearance.bannerClass
        )}
      >
        <Icon className={cn("size-5 shrink-0", appearance.iconClass)} />
        <span className="text-sm font-medium">{appearance.label}</span>
      </div>

      {hasTriggers && (
        <Collapsible open={triggersOpen} onOpenChange={setTriggersOpen}>
          <CollapsibleTrigger
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted"
            )}
          >
            <span>Причины согласования ({approvalTriggers.length})</span>
            <ChevronDown
              className={cn(
                "ml-auto size-3.5 transition-transform",
                triggersOpen && "rotate-180"
              )}
            />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <ul className="space-y-1 px-3 pb-2 pt-1">
              {approvalTriggers.map((trigger, index) => (
                <li
                  key={index}
                  className="flex items-start gap-2 text-xs text-muted-foreground"
                >
                  <span className="mt-1.5 block size-1 shrink-0 rounded-full bg-muted-foreground" />
                  {trigger}
                </li>
              ))}
            </ul>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}
