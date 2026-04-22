"use client";

import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

/**
 * RoleBasedTabs — thin wrapper over shadcn Tabs that filters tabs by user role.
 *
 * A tab is visible if either:
 *   - `tab.roles` is omitted/empty (visible to everyone), or
 *   - at least one of `tab.roles` is present in `userRoles`.
 *
 * No custom markup/styles — defers entirely to shadcn Tabs primitives so
 * visuals stay consistent with the rest of the app.
 *
 * Data source: session.user.roles[] (string slugs like 'logistics',
 * 'head_of_logistics', 'customs', 'admin', ...).
 */

export interface RoleBasedTab {
  value: string;
  label: string;
  /**
   * Role slugs allowed to see this tab. If omitted or empty, tab is public.
   */
  roles?: string[];
  /** Optional trailing count pill ("Мои заявки · 12"). */
  count?: number | string;
  /** Optional trailing chip ("NEW" on admin routing). */
  badge?: ReactNode;
  content: ReactNode;
}

interface RoleBasedTabsProps {
  userRoles: string[];
  tabs: RoleBasedTab[];
  /** Controlled value — preferred for URL-backed tab state. */
  value?: string;
  /** Called when user switches tab. */
  onValueChange?: (value: string) => void;
  /** Uncontrolled initial value. Ignored if `value` is set. */
  defaultValue?: string;
  className?: string;
  listClassName?: string;
}

export function RoleBasedTabs({
  userRoles,
  tabs,
  value,
  onValueChange,
  defaultValue,
  className,
  listClassName,
}: RoleBasedTabsProps) {
  const visibleTabs = tabs.filter(
    (t) => !t.roles || t.roles.length === 0 || t.roles.some((r) => userRoles.includes(r)),
  );

  if (visibleTabs.length === 0) return null;

  const resolvedDefault =
    defaultValue && visibleTabs.some((t) => t.value === defaultValue)
      ? defaultValue
      : visibleTabs[0].value;

  return (
    <Tabs
      value={value}
      onValueChange={onValueChange}
      defaultValue={resolvedDefault}
      className={className}
    >
      <TabsList className={cn("h-auto", listClassName)}>
        {visibleTabs.map((tab) => (
          <TabsTrigger key={tab.value} value={tab.value} className="gap-2">
            <span>{tab.label}</span>
            {tab.count !== undefined && tab.count !== null && (
              <span
                className="tabular-nums text-xs text-text-muted data-[state=active]:text-accent"
                aria-hidden
              >
                · {tab.count}
              </span>
            )}
            {tab.badge && <span className="ml-1">{tab.badge}</span>}
          </TabsTrigger>
        ))}
      </TabsList>
      {visibleTabs.map((tab) => (
        <TabsContent key={tab.value} value={tab.value} className="mt-6">
          {tab.content}
        </TabsContent>
      ))}
    </Tabs>
  );
}
