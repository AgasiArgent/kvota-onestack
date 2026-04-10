"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Settings,
  Star,
} from "lucide-react";
import { toast } from "sonner";

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

import {
  listViews,
  setDefaultView,
  updateView,
  type TableView,
} from "@/entities/table-view";
import { canonicalizeState } from "@/shared/lib/data-table";

import { ManageViewsDialog } from "./manage-views-dialog";
import { SaveViewDialog, type SaveViewDialogMode } from "./save-view-dialog";
import type { SerializedTableState } from "./types";

interface ViewSelectorProps {
  tableKey: string;
  currentUserId: string;
  /** Currently active view id (from URL) or null for "no view selected". */
  activeViewId: string | null;
  /** Current serialized state used for save/update and modification detection. */
  currentState: SerializedTableState;
  /** Called when the user picks a view — the parent should populate the URL from view state. */
  onLoadView: (view: TableView) => void;
  /** Called when the user clears the active view — parent clears ?view= param. */
  onClearView: () => void;
}

/**
 * Dropdown selector for saved table views with full CRUD actions.
 *
 * Responsibilities:
 *  - Fetches personal views for (userId, tableKey) on mount.
 *  - Auto-loads the user's default view on first mount when no ?view= is set.
 *  - Renders a list of views with the active one highlighted.
 *  - Offers actions: Save as new, Update current (when modified),
 *    Set as default, Clear selection, Manage views.
 *  - Opens SaveViewDialog / ManageViewsDialog for multi-step flows.
 *
 * Modification detection: compares canonical JSON of current URL state to
 * the active view's stored state. "Update current" is only enabled when
 * the two diverge.
 */
export function ViewSelector({
  tableKey,
  currentUserId,
  activeViewId,
  currentState,
  onLoadView,
  onClearView,
}: ViewSelectorProps) {
  const [views, setViews] = useState<TableView[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [saveDialog, setSaveDialog] = useState<SaveViewDialogMode | null>(null);
  const [manageOpen, setManageOpen] = useState(false);
  const [autoLoadedDefault, setAutoLoadedDefault] = useState(false);

  const refreshViews = useCallback(async () => {
    const list = await listViews(tableKey, currentUserId);
    setViews(list);
    setLoaded(true);
    return list;
  }, [tableKey, currentUserId]);

  // Initial fetch
  useEffect(() => {
    void refreshViews();
  }, [refreshViews]);

  // Auto-load default view on first mount if no ?view= in URL
  useEffect(() => {
    if (!loaded || autoLoadedDefault || activeViewId !== null) return;
    const defaultView = views.find((v) => v.isDefault);
    if (defaultView) {
      onLoadView(defaultView);
    }
    setAutoLoadedDefault(true);
  }, [loaded, autoLoadedDefault, activeViewId, views, onLoadView]);

  const activeView = useMemo(
    () => views.find((v) => v.id === activeViewId) ?? null,
    [views, activeViewId]
  );

  /** True when activeView exists and current URL state diverges from it. */
  const isModified = useMemo(() => {
    if (!activeView) return false;
    const current = canonicalizeState(currentState);
    const view = canonicalizeState({
      filters: activeView.filters,
      sort: activeView.sort,
      visibleColumns: activeView.visibleColumns,
    });
    return current !== view;
  }, [activeView, currentState]);

  const existingNames = useMemo(() => views.map((v) => v.name), [views]);

  async function handleUpdateCurrent() {
    if (!activeView) return;
    try {
      const updated = await updateView(activeView.id, {
        filters: currentState.filters,
        sort: currentState.sort,
        visibleColumns: currentState.visibleColumns,
      });
      await refreshViews();
      toast.success(`Вид "${updated.name}" обновлён`);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось обновить вид"
      );
    }
  }

  async function handleSetDefault(view: TableView) {
    try {
      await setDefaultView(view.id);
      await refreshViews();
      toast.success(`Вид "${view.name}" назначен по умолчанию`);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось назначить вид по умолчанию"
      );
    }
  }

  async function handleViewsChanged() {
    const list = await refreshViews();
    // If the active view was deleted, clear it.
    if (activeViewId && !list.find((v) => v.id === activeViewId)) {
      onClearView();
    }
  }

  const triggerLabel = activeView
    ? activeView.name + (isModified ? " •" : "")
    : "Все";

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="outline" size="sm">
              <Eye size={14} />
              <span className="truncate max-w-[160px]">{triggerLabel}</span>
              <ChevronDown size={14} />
            </Button>
          }
        />
        <DropdownMenuContent className="w-60" align="start">
          <DropdownMenuGroup>
            <DropdownMenuLabel>Сохранённые виды</DropdownMenuLabel>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />

          {/* "All" (no view) item */}
          <DropdownMenuItem
            onClick={() => {
              onClearView();
            }}
          >
            <div className="flex items-center gap-2 flex-1">
              {activeViewId === null && <Check size={14} className="text-accent" />}
              {activeViewId !== null && <span className="w-3.5" />}
              <span>Все</span>
            </div>
          </DropdownMenuItem>

          {/* Saved views */}
          {views.length > 0 && <DropdownMenuSeparator />}
          {views.map((view) => {
            const isActive = view.id === activeViewId;
            return (
              <DropdownMenuItem
                key={view.id}
                onClick={() => onLoadView(view)}
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {isActive ? (
                    <Check size={14} className="text-accent" />
                  ) : (
                    <span className="w-3.5" />
                  )}
                  <span className="truncate flex-1">{view.name}</span>
                  {view.isDefault && (
                    <Star size={12} className="text-amber-500 shrink-0" />
                  )}
                </div>
              </DropdownMenuItem>
            );
          })}

          <DropdownMenuSeparator />

          {/* Save as new */}
          <DropdownMenuItem
            onClick={() => setSaveDialog({ kind: "create" })}
          >
            <Plus size={14} />
            Сохранить как новый вид
          </DropdownMenuItem>

          {/* Update current (only when modified) */}
          {activeView && isModified && (
            <DropdownMenuItem onClick={handleUpdateCurrent}>
              <RefreshCw size={14} />
              Обновить текущий вид
            </DropdownMenuItem>
          )}

          {/* Rename current */}
          {activeView && (
            <DropdownMenuItem
              onClick={() => setSaveDialog({ kind: "rename", view: activeView })}
            >
              <Pencil size={14} />
              Переименовать
            </DropdownMenuItem>
          )}

          {/* Set as default */}
          {activeView && !activeView.isDefault && (
            <DropdownMenuItem onClick={() => handleSetDefault(activeView)}>
              <Star size={14} />
              По умолчанию
            </DropdownMenuItem>
          )}

          <DropdownMenuSeparator />

          {/* Manage */}
          <DropdownMenuItem onClick={() => setManageOpen(true)}>
            <Settings size={14} />
            Управление видами
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Save / rename dialog */}
      {saveDialog && (
        <SaveViewDialog
          open={saveDialog !== null}
          onClose={() => setSaveDialog(null)}
          mode={saveDialog}
          tableKey={tableKey}
          userId={currentUserId}
          currentState={currentState}
          existingNames={existingNames}
          onSaved={async (view) => {
            await refreshViews();
            // On create, auto-load the newly created view.
            if (saveDialog.kind === "create") {
              onLoadView(view);
            }
          }}
        />
      )}

      {/* Manage views dialog */}
      <ManageViewsDialog
        open={manageOpen}
        onClose={() => setManageOpen(false)}
        views={views}
        onChanged={handleViewsChanged}
      />
    </>
  );
}
