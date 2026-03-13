"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";

interface Props {
  customerId: string;
  children: React.ReactNode;
}

const TABS = [
  { key: "overview", label: "Обзор" },
  { key: "crm", label: "CRM" },
  { key: "documents", label: "Документы" },
  { key: "positions", label: "Позиции" },
] as const;

export type TabKey = (typeof TABS)[number]["key"];

export function CustomerTabs({ customerId, children }: Props) {
  const searchParams = useSearchParams();
  const activeTab = (searchParams?.get("tab") ?? "overview") as TabKey;

  return (
    <div>
      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {TABS.map((tab) => (
          <Link
            key={tab.key}
            href={`/customers/${customerId}?tab=${tab.key}`}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
              activeTab === tab.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
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
