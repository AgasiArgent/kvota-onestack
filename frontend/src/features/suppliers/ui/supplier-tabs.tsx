"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";

interface Props {
  supplierId: string;
  activeTab?: string;
  children: React.ReactNode;
}

const TABS = [
  { key: "overview", label: "Обзор" },
  { key: "brands", label: "Бренды" },
  { key: "contacts", label: "Контакты" },
] as const;

export type TabKey = (typeof TABS)[number]["key"];

export function SupplierTabs({ supplierId, activeTab: activeTabProp, children }: Props) {
  const searchParams = useSearchParams();
  const activeTab = (activeTabProp ?? searchParams?.get("tab") ?? "overview") as TabKey;

  return (
    <div>
      <div className="flex gap-1 border-b border-border-light mb-6">
        {TABS.map((tab) => (
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
