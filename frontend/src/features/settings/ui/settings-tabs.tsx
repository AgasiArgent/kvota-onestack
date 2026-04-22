"use client";

import { Settings } from "lucide-react";
import { AppToaster } from "@/shared/ui/app-toaster";
import type { SettingsPageData } from "@/entities/settings";
import { CalcRatesForm } from "./calc-rates-form";
import { StageDeadlinesForm } from "./stage-deadlines-form";

interface SettingsTabsProps {
  data: SettingsPageData;
  defaultTab: string;
}

export function SettingsTabs({ data }: SettingsTabsProps) {
  return (
    <div className="space-y-6">
      <AppToaster />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings size={24} className="text-accent" />
          <h1 className="text-2xl font-bold">Настройки</h1>
        </div>
        <span className="text-sm text-text-muted">{data.organization.name}</span>
      </div>

      {/* Calc rates */}
      <CalcRatesForm
        settings={data.calcSettings}
        orgId={data.organization.id}
      />

      {/* Stage deadlines */}
      <StageDeadlinesForm
        deadlines={data.stageDeadlines}
        orgId={data.organization.id}
      />
    </div>
  );
}
