"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Settings } from "lucide-react";
import { Toaster } from "sonner";
import { cn } from "@/lib/utils";
import type { SettingsPageData } from "@/entities/settings";
import { PhmbForm } from "./phmb-form";
import { BrandDiscountsTable } from "./brand-discounts-table";

interface Props {
  data: SettingsPageData;
  defaultTab: string;
}

const TABS = [
  { key: "markup", label: "Наценки PHMB" },
  { key: "discounts", label: "Скидки по брендам" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export function PhmbSettingsTabs({ data, defaultTab }: Props) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>(
    TABS.some((t) => t.key === defaultTab)
      ? (defaultTab as TabKey)
      : "markup"
  );

  function handleTabChange(tab: TabKey) {
    setActiveTab(tab);
    router.push(`/phmb/settings?tab=${tab}`, { scroll: false });
  }

  return (
    <div className="space-y-6">
      <Toaster position="top-right" richColors />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings size={24} className="text-accent" />
          <h1 className="text-2xl font-bold">Настройки PHMB</h1>
        </div>
        <span className="text-sm text-text-muted">{data.organization.name}</span>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border-light overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px whitespace-nowrap",
              activeTab === tab.key
                ? "border-accent text-accent"
                : "border-transparent text-text-muted hover:text-text hover:border-border"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "markup" && (
        <PhmbForm
          settings={data.phmbSettings}
          orgId={data.organization.id}
        />
      )}
      {activeTab === "discounts" && (
        <BrandDiscountsTable
          discounts={data.brandDiscounts}
          brandGroups={data.brandGroups}
          orgId={data.organization.id}
        />
      )}
    </div>
  );
}
