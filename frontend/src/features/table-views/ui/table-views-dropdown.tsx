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
  DropdownMenuGroup,
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
 * View shape accepted by the dropdown. Real `TableView` rows from
 * `kvota.user_table_views` come through unchanged; synthetic «Системные»
 * presets (e.g. `CUSTOMS_SYSTEM_VIEWS`) must be adapted by the caller to
 * this shape and tagged with `is_system: true` so the dropdown renders
 * them in the «Системные» group above personal/shared rows.
 */
export type DropdownTableView = TableView & { readonly is_system?: boolean };

interface TableViewsDropdownProps {
  /**
   * All views available to this user, in any order. The dropdown groups them
   * internally into «Системные» (is_system === true), «Личные» (isShared
   * === false), and «Общие» (isShared === true). Synthetic system views
   * MUST be adapted by callers to the `DropdownTableView` shape — see
   * `customs-step.tsx` for the canonical conversion of `CUSTOMS_SYSTEM_VIEWS`.
   */
  views: readonly DropdownTableView[];
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

  const systemViews = useMemo(
    () => views.filter((v) => v.is_system === true),
    [views]
  );
  const personalViews = useMemo(
    () => views.filter((v) => v.is_system !== true && !v.isShared),
    [views]
  );
  const sharedViews = useMemo(
    () => views.filter((v) => v.is_system !== true && v.isShared),
    [views]
  );

  const activeView = useMemo(
    () => views.find((v) => v.id === activeViewId) ?? null,
    [views, activeViewId]
  );

  const triggerLabel = activeView ? activeView.name : "Все колонки";

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

          {systemViews.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
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
                      <span className="truncate">{view.name}</span>
                    </div>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuGroup>
            </>
          )}

          {personalViews.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
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
              </DropdownMenuGroup>
            </>
          )}

          {sharedViews.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
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
              </DropdownMenuGroup>
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
