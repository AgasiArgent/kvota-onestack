"use client";

import type { ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { WorkspaceTabBar } from "@/features/workspace-logistics/ui/workspace-tab-bar";

/**
 * Thin client wrapper that handles tab navigation. Parent server component
 * renders slot contents and passes them in via `children`.
 */

type Tab = "my" | "completed" | "unassigned" | "all";

interface WorkspaceLogisticsClientProps {
  userRoles: string[];
  activeTab: Tab;
  counts: { my: number; completed: number; unassigned?: number; all?: number };
  children: {
    my: ReactNode;
    completed: ReactNode;
    unassigned?: ReactNode;
    all?: ReactNode;
  };
  domain?: "logistics" | "customs";
}

export function WorkspaceLogisticsClient({
  userRoles,
  activeTab,
  counts,
  children,
  domain = "logistics",
}: WorkspaceLogisticsClientProps) {
  const router = useRouter();
  const pathname = usePathname();

  const setTab = (v: string) => {
    const params = new URLSearchParams();
    if (v !== "my") params.set("tab", v);
    const qs = params.toString();
    const base = pathname ?? "/";
    router.push(qs ? `${base}?${qs}` : base, { scroll: false });
  };

  return (
    <WorkspaceTabBar
      domain={domain}
      userRoles={userRoles}
      value={activeTab}
      onValueChange={setTab}
      counts={counts}
    >
      {children}
    </WorkspaceTabBar>
  );
}
