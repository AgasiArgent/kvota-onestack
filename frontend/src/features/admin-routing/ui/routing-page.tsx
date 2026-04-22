"use client";

import { AppToaster } from "@/shared/ui/app-toaster";
import { RoutingTabs } from "./routing-tabs";
import { BrandsTab } from "./brands-tab";
import { GroupsTab } from "./groups-tab";
import { TenderTab } from "./tender-tab";
import { UnassignedTab } from "./unassigned-tab";
import { LogisticsTemplatesTab } from "./logistics-templates-tab";
import type {
  RoutingTab,
  BrandAssignment,
  GroupAssignment,
  TenderChainStep,
  UnassignedItem,
  LogisticsTemplateAdmin,
} from "../model/types";

interface Props {
  activeTab: RoutingTab;
  orgId: string;
  brandsData?: { assignments: BrandAssignment[]; unassignedBrands: string[] };
  groupsData?: { assignments: GroupAssignment[] };
  tenderData?: { steps: TenderChainStep[] };
  unassignedData?: { items: UnassignedItem[] };
  logisticsData?: { templates: LogisticsTemplateAdmin[] };
}

export function RoutingPage({
  activeTab,
  orgId,
  brandsData,
  groupsData,
  tenderData,
  unassignedData,
  logisticsData,
}: Props) {
  return (
    <>
      <RoutingTabs activeTab={activeTab}>
        {activeTab === "brands" && brandsData && (
          <BrandsTab
            assignments={brandsData.assignments}
            unassignedBrands={brandsData.unassignedBrands}
            orgId={orgId}
          />
        )}
        {activeTab === "groups" && groupsData && (
          <GroupsTab assignments={groupsData.assignments} orgId={orgId} />
        )}
        {activeTab === "tender" && tenderData && (
          <TenderTab steps={tenderData.steps} orgId={orgId} />
        )}
        {activeTab === "unassigned" && unassignedData && (
          <UnassignedTab items={unassignedData.items} orgId={orgId} />
        )}
        {activeTab === "logistics" && logisticsData && (
          <LogisticsTemplatesTab
            templates={logisticsData.templates}
            orgId={orgId}
          />
        )}
      </RoutingTabs>
      <AppToaster />
    </>
  );
}
