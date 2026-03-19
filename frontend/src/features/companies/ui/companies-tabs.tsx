"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import type { CompanyTab } from "../model/types";

interface Props {
  activeTab: CompanyTab;
  children: React.ReactNode;
}

const TABS = [
  { key: "seller", label: "Юрлица-продажи" },
  { key: "buyer", label: "Юрлица-закупки" },
] as const;

export function CompaniesTabs({ activeTab, children }: Props) {
  return (
    <div>
      <div className="flex gap-1 border-b border-border-light mb-6">
        {TABS.map((tab) => (
          <Link
            key={tab.key}
            href={`/companies?tab=${tab.key}`}
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
