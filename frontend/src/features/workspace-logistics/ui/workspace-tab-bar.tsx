import type { ReactNode } from "react";
import { RoleBasedTabs, type RoleBasedTab } from "@/shared/ui";

/**
 * WorkspaceTabBar — wraps RoleBasedTabs with the 4 workspace views:
 *   - Мои заявки        (all users)
 *   - Завершённые       (all users)
 *   - Неназначенные     (head_of_logistics | head_of_customs | admin | top_manager)
 *   - Все заявки        (head_of_logistics | head_of_customs | admin | top_manager)
 *
 * head_of_logistics ↔ head_of_customs are dual-hat (PR #105): either head
 * role grants full access in BOTH domains. `domain` is kept on the props for
 * future per-domain UI variations but no longer narrows the role gate.
 */

interface WorkspaceTabBarProps {
  /** Kept for future per-domain UI variations; no longer narrows role gate. */
  domain?: "logistics" | "customs";
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
  userRoles,
  value,
  onValueChange,
  counts,
  children,
}: WorkspaceTabBarProps) {
  const headGuard = [
    "head_of_logistics",
    "head_of_customs",
    "admin",
    "top_manager",
  ];

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
