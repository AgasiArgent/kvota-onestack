"use client";

import { Settings } from "lucide-react";
import { Toaster } from "sonner";
import type { SettingsPageData } from "@/entities/settings";
import { CalcRatesForm } from "./calc-rates-form";

interface SettingsTabsProps {
  data: SettingsPageData;
  defaultTab: string;
}

export function SettingsTabs({ data }: SettingsTabsProps) {
  return (
    <div className="space-y-6">
      <Toaster position="top-right" richColors />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings size={24} className="text-accent" />
          <h1 className="text-2xl font-bold">Настройки</h1>
        </div>
        <span className="text-sm text-text-muted">{data.organization.name}</span>
      </div>

      {/* Single content: Calc rates */}
      <CalcRatesForm
        settings={data.calcSettings}
        orgId={data.organization.id}
      />
    </div>
  );
}
