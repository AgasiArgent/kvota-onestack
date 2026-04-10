"use client";

import { useState } from "react";
import { Loader2, Pencil, Star, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import {
  deleteView,
  setDefaultView,
  updateView,
  type TableView,
} from "@/entities/table-view";

import { SaveViewDialog } from "./save-view-dialog";

interface ManageViewsDialogProps {
  open: boolean;
  onClose: () => void;
  views: readonly TableView[];
  onChanged: () => void;
}

/**
 * Dialog that lists all the user's saved views for the current table with
 * rename, set-as-default, and delete actions per row. Deletion shows an
 * inline confirmation step before calling the mutation.
 */
export function ManageViewsDialog({
  open,
  onClose,
  views,
  onChanged,
}: ManageViewsDialogProps) {
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(
    null
  );
  const [renamingView, setRenamingView] = useState<TableView | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function handleDelete(view: TableView) {
    setBusyId(view.id);
    try {
      await deleteView(view.id);
      toast.success(`Вид "${view.name}" удалён`);
      setConfirmingDeleteId(null);
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Не удалось удалить вид");
    } finally {
      setBusyId(null);
    }
  }

  async function handleSetDefault(view: TableView) {
    if (view.isDefault) {
      // Toggle off — clear the default flag.
      setBusyId(view.id);
      try {
        await updateView(view.id, { isDefault: false });
        toast.success(`Вид "${view.name}" больше не по умолчанию`);
        onChanged();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Не удалось обновить вид");
      } finally {
        setBusyId(null);
      }
      return;
    }

    setBusyId(view.id);
    try {
      await setDefaultView(view.id);
      toast.success(`Вид "${view.name}" назначен по умолчанию`);
      onChanged();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось назначить вид по умолчанию"
      );
    } finally {
      setBusyId(null);
    }
  }

  // Existing names excluding the one being renamed (so the same name can be kept).
  const existingNames = renamingView
    ? views.filter((v) => v.id !== renamingView.id).map((v) => v.name)
    : views.map((v) => v.name);

  return (
    <>
      <Dialog open={open && renamingView === null} onOpenChange={(val) => !val && onClose()}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Управление видами</DialogTitle>
            <DialogDescription>
              Переименовывайте, удаляйте и настраивайте сохранённые виды.
            </DialogDescription>
          </DialogHeader>

          {views.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              У вас пока нет сохранённых видов
            </div>
          ) : (
            <div className="flex flex-col gap-1 max-h-[50vh] overflow-y-auto">
              {views.map((view) => {
                const isConfirming = confirmingDeleteId === view.id;
                const isBusy = busyId === view.id;
                return (
                  <div
                    key={view.id}
                    className="flex items-center gap-2 rounded-lg border border-border px-3 py-2"
                  >
                    <span className="truncate flex-1 text-sm" title={view.name}>
                      {view.name}
                    </span>
                    {view.isDefault && (
                      <Star size={12} className="text-amber-500 shrink-0" />
                    )}

                    {isConfirming ? (
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">Удалить?</span>
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => setConfirmingDeleteId(null)}
                          disabled={isBusy}
                        >
                          Отмена
                        </Button>
                        <Button
                          variant="destructive"
                          size="xs"
                          onClick={() => handleDelete(view)}
                          disabled={isBusy}
                        >
                          {isBusy && <Loader2 size={12} className="animate-spin" />}
                          Удалить
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => handleSetDefault(view)}
                          disabled={isBusy}
                          title={view.isDefault ? "Снять по умолчанию" : "Сделать видом по умолчанию"}
                        >
                          <Star
                            size={14}
                            className={view.isDefault ? "text-amber-500 fill-amber-500" : ""}
                          />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => setRenamingView(view)}
                          disabled={isBusy}
                          title="Переименовать"
                        >
                          <Pencil size={14} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => setConfirmingDeleteId(view.id)}
                          disabled={isBusy}
                          title="Удалить"
                        >
                          <Trash2 size={14} className="text-destructive" />
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              Закрыть
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Nested rename dialog. The parent dialog is hidden (by `open && renamingView === null`)
          while this one is open to avoid double modal stacking. */}
      {renamingView && (
        <SaveViewDialog
          open={true}
          onClose={() => setRenamingView(null)}
          mode={{ kind: "rename", view: renamingView }}
          tableKey={renamingView.tableKey}
          userId={renamingView.userId}
          currentState={{
            filters: renamingView.filters,
            sort: renamingView.sort,
            visibleColumns: renamingView.visibleColumns,
          }}
          existingNames={existingNames}
          onSaved={() => {
            setRenamingView(null);
            onChanged();
          }}
        />
      )}
    </>
  );
}
