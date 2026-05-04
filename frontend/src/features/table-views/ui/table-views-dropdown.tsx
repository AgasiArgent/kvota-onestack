"use client";

import { useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  Eye,
  Plus,
  Settings,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type { TableView } from "@/entities/table-view";

import {
  TableViewsSettingsDialog,
  type AvailableColumn,
} from "./table-views-settings-dialog";

/**
 * Minimal shape for a virtual, client-side "system" view rendered in its
 * own «Системные» group at the top of the dropdown. Different from
 * {@link TableView} (which represents real `user_table_views` rows) — system
 * views never round-trip to the database. The customs registry uses
 * `SystemView` from `@/features/customs-certificates`; this local shape is
 * the structural intersection so the dropdown stays decoupled from any
 * particular feature module.
 */
export interface SystemViewOption {
  /** Synthetic ID (e.g. `system:all`); collisions with UUID rows impossible. */
  readonly id: string;
  /** Russian label rendered in the menu. */
  readonly label: string;
}

interface TableViewsDropdownProps {
  /** All views available to this user (personal + org-shared) for the table. */
  views: readonly TableView[];
  /**
   * Optional virtual "system" views rendered above personal/shared in their
   * own «Системные» group (REQ-11 AC#4). Synthetic IDs (e.g. `system:all`)
   * do not collide with UUID rows in `user_table_views`, so URL persistence
   * (`?customs_view=<id>`) keeps working without a DB migration.
   */
  systemViews?: readonly SystemViewOption[];
  /** Currently selected view id, or null to show all columns. */
  activeViewId: string | null;
  /** Called when the user selects a different view (or clears selection). */
  onViewChange: (viewId: string | null) => void;
  /** Called after the settings dialog saves, so the parent can refresh views. */
  onViewsRefresh: () => void;
  tableKey: string;
  availableColumns: readonly AvailableColumn[];
  /** Acting user id — passed through to the settings dialog for mutations. */
  userId: string;
  /** Acting user's organization id — required for shared-view mutations. */
  orgId: string;
  /** Whether the current user may create/edit shared views. */
  canCreateShared: boolean;
}

/**
 * Dropdown that lists the current user's personal views plus the org's
 * shared views for a given registry. The active view's name appears in the
 * trigger; "Все колонки" resets to the default (no view) state.
 *
 * Actions at the bottom:
 *  - "Настроить колонки…" (edit the active view, or opens for the default
 *    view if no view is active)
 *  - "Новое представление…" (create a fresh view)
 */
export function TableViewsDropdown({
  views,
  systemViews = [],
  activeViewId,
  onViewChange,
  onViewsRefresh,
  tableKey,
  availableColumns,
  userId,
  orgId,
  canCreateShared,
}: TableViewsDropdownProps) {
  const [dialogState, setDialogState] = useState<
    | { kind: "closed" }
    | { kind: "create" }
    | { kind: "edit"; view: TableView }
  >({ kind: "closed" });

  const personalViews = useMemo(
    () => views.filter((v) => !v.isShared),
    [views]
  );
  const sharedViews = useMemo(() => views.filter((v) => v.isShared), [views]);

  const activeView = useMemo(
    () => views.find((v) => v.id === activeViewId) ?? null,
    [views, activeViewId]
  );
  // Resolve the trigger label across both groups — system views first so
  // their Russian label wins when the active id is synthetic
  // (`system:tariffs-nds`, etc.). Falls back to TableView.name, then to the
  // «Все колонки» default when nothing matches.
  const activeSystemView = useMemo(
    () => systemViews.find((v) => v.id === activeViewId) ?? null,
    [systemViews, activeViewId]
  );

  const triggerLabel =
    activeSystemView?.label ?? activeView?.name ?? "Все колонки";

  function handleOpenSettings() {
    if (activeView) {
      setDialogState({ kind: "edit", view: activeView });
    } else {
      setDialogState({ kind: "create" });
    }
  }

  const dialogOpen = dialogState.kind !== "closed";
  const dialogInitial = dialogState.kind === "edit" ? dialogState.view : undefined;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="outline" size="sm">
              <Eye size={14} />
              <span className="truncate max-w-[180px]">{triggerLabel}</span>
              <ChevronDown size={14} />
            </Button>
          }
        />
        <DropdownMenuContent className="w-64" align="start">
          {/* «Системные» group — REQ-11 AC#4. Rendered ONLY when the parent
              passes `systemViews`; otherwise the generic «Все колонки → null»
              row below is the clear-filter affordance. When system views
              ARE wired, the first system view (typically `system:all`) is
              the canonical «Все колонки» preset — REQ-11 AC#7. */}
          {systemViews.length > 0 ? (
            <>
              <DropdownMenuLabel>Системные</DropdownMenuLabel>
              {systemViews.map((view) => (
                <DropdownMenuItem
                  key={view.id}
                  onClick={() => onViewChange(view.id)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {view.id === activeViewId ? (
                      <Check size={14} className="text-accent" />
                    ) : (
                      <span className="inline-block w-3.5" />
                    )}
                    <span className="truncate">{view.label}</span>
                  </div>
                </DropdownMenuItem>
              ))}
            </>
          ) : (
            <DropdownMenuItem onClick={() => onViewChange(null)}>
              <div className="flex items-center gap-2 flex-1">
                {activeViewId === null ? (
                  <Check size={14} className="text-accent" />
                ) : (
                  <span className="inline-block w-3.5" />
                )}
                <span>Все колонки</span>
              </div>
            </DropdownMenuItem>
          )}

          {personalViews.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Личные</DropdownMenuLabel>
              {personalViews.map((view) => (
                <DropdownMenuItem
                  key={view.id}
                  onClick={() => onViewChange(view.id)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {view.id === activeViewId ? (
                      <Check size={14} className="text-accent" />
                    ) : (
                      <span className="inline-block w-3.5" />
                    )}
                    <span className="truncate">{view.name}</span>
                  </div>
                </DropdownMenuItem>
              ))}
            </>
          )}

          {sharedViews.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Общие</DropdownMenuLabel>
              {sharedViews.map((view) => (
                <DropdownMenuItem
                  key={view.id}
                  onClick={() => onViewChange(view.id)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {view.id === activeViewId ? (
                      <Check size={14} className="text-accent" />
                    ) : (
                      <span className="inline-block w-3.5" />
                    )}
                    <Users size={12} className="text-muted-foreground shrink-0" />
                    <span className="truncate">{view.name}</span>
                  </div>
                </DropdownMenuItem>
              ))}
            </>
          )}

          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={handleOpenSettings}>
            <Settings size={14} />
            Настроить колонки…
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setDialogState({ kind: "create" })}>
            <Plus size={14} />
            Новое представление…
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <TableViewsSettingsDialog
        open={dialogOpen}
        onOpenChange={(next) => {
          if (!next) setDialogState({ kind: "closed" });
        }}
        initial={dialogInitial}
        tableKey={tableKey}
        availableColumns={availableColumns}
        userId={userId}
        orgId={orgId}
        canCreateShared={canCreateShared}
        onSaved={onViewsRefresh}
      />
    </>
  );
}
