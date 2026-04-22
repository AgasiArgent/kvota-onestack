"use client";

import { AppToaster } from "@/shared/ui/app-toaster";
import { RoutingTabs } from "./routing-tabs";
import { BrandsTab } from "./brands-tab";
import { GroupsTab } from "./groups-tab";
import { TenderTab } from "./tender-tab";
import { UnassignedTab } from "./unassigned-tab";
import type { RoutingTab } from "../model/types";
import type { BrandAssignment, GroupAssignment, TenderChainStep, UnassignedItem } from "../model/types";

interface Props {
  activeTab: RoutingTab;
  orgId: string;
  brandsData?: { assignments: BrandAssignment[]; unassignedBrands: string[] };
  groupsData?: { assignments: GroupAssignment[] };
  tenderData?: { steps: TenderChainStep[] };
  unassignedData?: { items: UnassignedItem[] };
}

export function RoutingPage({
  activeTab,
  orgId,
  brandsData,
  groupsData,
  tenderData,
  unassignedData,
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
      </RoutingTabs>
      <AppToaster />
    </>
  );
}
