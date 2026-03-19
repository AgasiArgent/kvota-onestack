"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Pencil, Users } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  createGroupAssignment,
  updateGroupAssignment,
  deleteGroupAssignment,
  fetchSalesGroups,
} from "../api/routing-api";
import { UserSelect } from "./user-select";
import { GroupAssignmentDialog } from "./group-assignment-dialog";
import type { GroupAssignment, SalesGroup } from "../model/types";

interface Props {
  assignments: GroupAssignment[];
  orgId: string;
}

export function GroupsTab({ assignments, orgId }: Props) {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUserId, setEditUserId] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [salesGroups, setSalesGroups] = useState<SalesGroup[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const groups = await fetchSalesGroups(orgId);
        if (!cancelled) setSalesGroups(groups);
      } catch (err) {
        console.error("Failed to fetch sales groups:", err);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [orgId]);

  const assignedGroupIds = new Set(assignments.map((a) => a.sales_group_id));
  const availableGroups = salesGroups.filter((g) => !assignedGroupIds.has(g.id));

  async function handleDialogSubmit(groupId: string, userId: string) {
    try {
      await createGroupAssignment(orgId, groupId, userId);
      toast.success("Правило группы создано");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка создания правила");
    }
  }

  async function saveEdit(assignmentId: string) {
    if (!editUserId) return;
    try {
      await updateGroupAssignment(assignmentId, editUserId, orgId);
      toast.success("Назначение обновлено");
      setEditingId(null);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка обновления");
    }
  }

  async function handleDelete(assignmentId: string) {
    setDeletingId(assignmentId);
    try {
      await deleteGroupAssignment(assignmentId, orgId);
      toast.success("Правило удалено");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка удаления");
    } finally {
      setDeletingId(null);
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("ru-RU");
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text">Назначения по группам</h2>
          <p className="text-sm text-text-muted mt-1">
            Группа продаж привязывается к менеджеру закупок
          </p>
        </div>
        <Button
          size="sm"
          className="bg-accent text-white hover:bg-accent-hover"
          onClick={() => setDialogOpen(true)}
          disabled={availableGroups.length === 0}
        >
          <Plus size={14} />
          Добавить правило
        </Button>
      </div>

      {assignments.length === 0 ? (
        <div className="py-12 text-center">
          <Users size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет правил маршрутизации по группам</p>
          <p className="text-xs text-text-subtle">
            Привяжите группы продаж к менеджерам закупок
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Группа продаж</TableHead>
              <TableHead>Менеджер закупок</TableHead>
              <TableHead>Дата создания</TableHead>
              <TableHead className="w-[100px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {assignments.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-medium">{a.sales_group_name ?? a.sales_group_id}</TableCell>
                <TableCell>
                  {editingId === a.id ? (
                    <div className="flex items-center gap-2 max-w-xs">
                      <UserSelect value={editUserId} onValueChange={setEditUserId} orgId={orgId} />
                      <Button size="sm" variant="outline" onClick={() => saveEdit(a.id)} disabled={!editUserId}>OK</Button>
                      <Button size="sm" variant="outline" onClick={() => setEditingId(null)}>X</Button>
                    </div>
                  ) : (
                    <span className="text-text-muted">{a.user_full_name ?? a.user_id}</span>
                  )}
                </TableCell>
                <TableCell className="text-text-muted">{formatDate(a.created_at)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => { setEditingId(a.id); setEditUserId(a.user_id); }}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-text-muted"
                      title="Изменить"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(a.id)}
                      disabled={deletingId === a.id}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-error"
                      title="Удалить"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <GroupAssignmentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        orgId={orgId}
        availableGroups={availableGroups}
        onSubmit={handleDialogSubmit}
      />
    </div>
  );
}
