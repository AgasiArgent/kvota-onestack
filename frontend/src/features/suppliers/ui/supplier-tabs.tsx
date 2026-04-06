"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";

interface Tab {
  key: string;
  label: string;
}

interface Props {
  supplierId: string;
  activeTab?: string;
  tabs?: Tab[];
  children: React.ReactNode;
}

const DEFAULT_TABS: Tab[] = [
  { key: "overview", label: "Обзор" },
  { key: "brands", label: "Бренды" },
  { key: "contacts", label: "Контакты" },
  { key: "positions", label: "Позиции" },
  { key: "assignees", label: "Менеджеры" },
];

export function SupplierTabs({ supplierId, activeTab: activeTabProp, tabs, children }: Props) {
  const searchParams = useSearchParams();
  const visibleTabs = tabs ?? DEFAULT_TABS;
  const activeTab = activeTabProp ?? searchParams?.get("tab") ?? "overview";

  return (
    <div>
      <div className="flex gap-1 border-b border-border-light mb-6">
        {visibleTabs.map((tab) => (
          <Link
            key={tab.key}
            href={`/suppliers/${supplierId}?tab=${tab.key}`}
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
