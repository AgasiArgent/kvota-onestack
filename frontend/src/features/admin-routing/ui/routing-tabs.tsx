"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import type { RoutingTab } from "../model/types";

interface Props {
  activeTab: RoutingTab;
  children: React.ReactNode;
}

const TABS = [
  { key: "brands", label: "По брендам" },
  { key: "groups", label: "По группам" },
  { key: "tender", label: "Тендерные" },
  { key: "unassigned", label: "Нераспределённые" },
] as const;

export function RoutingTabs({ activeTab, children }: Props) {
  return (
    <div>
      <div className="flex gap-1 border-b border-border-light mb-6">
        {TABS.map((tab) => (
          <Link
            key={tab.key}
            href={`/admin/routing?tab=${tab.key}`}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === tab.key
                ? "border-accent text-accent"
                : "border-transparent text-text-muted hover:text-text hover:border-border"
            )}
          >
            {tab.label}
          </Link>
        ))}
      </div>
      {children}
    </div>
  );
}
