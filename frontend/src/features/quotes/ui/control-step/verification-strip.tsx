"use client";

import { useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, ChevronDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type { CheckResult } from "./use-control-checks";

const STATUS_CONFIG = {
  ok: {
    icon: CheckCircle2,
    iconClass: "text-green-600",
    hoverBg: "hover:bg-green-50",
  },
  warning: {
    icon: AlertTriangle,
    iconClass: "text-amber-500",
    hoverBg: "hover:bg-amber-50",
  },
  error: {
    icon: XCircle,
    iconClass: "text-red-500",
    hoverBg: "hover:bg-red-50",
  },
  info: {
    icon: Info,
    iconClass: "text-blue-500",
    hoverBg: "hover:bg-blue-50",
  },
} as const;

interface VerificationStripProps {
  checks: CheckResult[];
}

export function VerificationStrip({ checks }: VerificationStripProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  function handleToggle(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  return (
    <Card>
      <CardContent>
        <div className="flex flex-wrap gap-1">
          {checks.map((check) => {
            const config = STATUS_CONFIG[check.status];
            const Icon = config.icon;
            const isExpanded = expandedId === check.id;

            return (
              <Collapsible
                key={check.id}
                open={isExpanded}
                onOpenChange={() => handleToggle(check.id)}
              >
                <div className="w-full">
                  <CollapsibleTrigger
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                      config.hoverBg
                    )}
                  >
                    <Icon className={cn("size-4 shrink-0", config.iconClass)} />
                    <span className="text-sm text-foreground">{check.label}</span>
                    <span className="text-xs text-muted-foreground">{check.value}</span>
                    {check.details && (
                      <ChevronDown
                        className={cn(
                          "ml-auto size-3.5 text-muted-foreground transition-transform",
                          isExpanded && "rotate-180"
                        )}
                      />
                    )}
                  </CollapsibleTrigger>
                  {check.details && (
                    <CollapsibleContent>
                      <div className="px-3 pb-2 pt-1 text-xs text-muted-foreground">
                        {check.details}
                      </div>
                    </CollapsibleContent>
                  )}
                </div>
              </Collapsible>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
