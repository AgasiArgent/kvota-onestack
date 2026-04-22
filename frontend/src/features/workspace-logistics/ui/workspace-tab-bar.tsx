import type { ReactNode } from "react";
import { RoleBasedTabs, type RoleBasedTab } from "@/shared/ui";

/**
 * WorkspaceTabBar — wraps RoleBasedTabs with the 4 workspace views:
 *   - Мои заявки        (all users)
 *   - Завершённые       (all users)
 *   - Неназначенные     (head_of_logistics | head_of_customs | admin)
 *   - Все заявки        (head_of_logistics | head_of_customs | admin)
 *
 * Shared between /workspace/logistics and /workspace/customs — pass
 * `domain` to adjust RBAC for the "head" role slug.
 */

interface WorkspaceTabBarProps {
  domain: "logistics" | "customs";
  userRoles: string[];
  /** Current selected tab, controlled by the parent page from searchParams. */
  value: string;
  onValueChange: (value: string) => void;
  counts: {
    my: number;
    completed: number;
    unassigned?: number;
    all?: number;
  };
  children: {
    my: ReactNode;
    completed: ReactNode;
    unassigned?: ReactNode;
    all?: ReactNode;
  };
}

export function WorkspaceTabBar({
  domain,
  userRoles,
  value,
  onValueChange,
  counts,
  children,
}: WorkspaceTabBarProps) {
  const headRole = domain === "logistics" ? "head_of_logistics" : "head_of_customs";
  const headGuard = [headRole, "admin", "top_manager"];

  const tabs: RoleBasedTab[] = [
    {
      value: "my",
      label: "Мои заявки",
      count: counts.my,
      content: children.my,
    },
    {
      value: "completed",
      label: "Завершённые",
      count: counts.completed,
      content: children.completed,
    },
    {
      value: "unassigned",
      label: "Неназначенные",
      roles: headGuard,
      count: counts.unassigned ?? 0,
      content: children.unassigned ?? null,
    },
    {
      value: "all",
      label: "Все заявки",
      roles: headGuard,
      count: counts.all ?? 0,
      content: children.all ?? null,
    },
  ];

  return (
    <RoleBasedTabs
      userRoles={userRoles}
      tabs={tabs}
      value={value}
      onValueChange={onValueChange}
    />
  );
}
