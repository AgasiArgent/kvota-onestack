"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CustomerAssignee } from "@/entities/customer/types";
import {
  addCustomerAssignee,
  removeCustomerAssignee,
} from "@/entities/customer/mutations";

interface Props {
  customerId: string;
  assignees: CustomerAssignee[];
  salesUsers: { id: string; full_name: string }[];
  canManage: boolean;
}

export function TabAssignees({ customerId, assignees, salesUsers, canManage }: Props) {
  const router = useRouter();
  const [selectedUserId, setSelectedUserId] = useState("");
  const [adding, setAdding] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const assignedUserIds = new Set(assignees.map((a) => a.user_id));
  const availableUsers = salesUsers.filter((u) => !assignedUserIds.has(u.id));

  async function handleAdd() {
    if (!selectedUserId) return;
    setAdding(true);
    try {
      await addCustomerAssignee(customerId, selectedUserId);
      setSelectedUserId("");
      router.refresh();
    } catch (err) {
      console.error("Failed to add assignee:", err);
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(userId: string) {
    setRemovingId(userId);
    try {
      await removeCustomerAssignee(customerId, userId);
      router.refresh();
    } catch (err) {
      console.error("Failed to remove assignee:", err);
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div className="space-y-6">
      {canManage && availableUsers.length > 0 && (
        <div className="flex items-end gap-3">
          <div className="w-72">
            <Select value={selectedUserId} onValueChange={(v: string | null) => setSelectedUserId(v ?? "")}>
              <SelectTrigger>
                <SelectValue placeholder="Выберите менеджера" />
              </SelectTrigger>
              <SelectContent>
                {availableUsers.map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    {user.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            size="sm"
            disabled={!selectedUserId || adding}
            onClick={handleAdd}
            className="bg-accent text-white hover:bg-accent-hover"
          >
            <Plus size={14} />
            Добавить
          </Button>
        </div>
      )}

      {assignees.length === 0 ? (
        <div className="py-12 text-center">
          <Users size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет закреплённых менеджеров</p>
          <p className="text-xs text-text-subtle">
            {canManage
              ? "Добавьте менеджеров, ответственных за этого клиента"
              : "Менеджеры пока не назначены"}
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Менеджер</TableHead>
              <TableHead>Назначен</TableHead>
              {canManage && <TableHead className="w-[60px]" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {assignees.map((assignee) => (
              <TableRow key={assignee.user_id}>
                <TableCell className="font-medium">{assignee.full_name}</TableCell>
                <TableCell className="text-text-muted">
                  {new Date(assignee.created_at).toLocaleDateString("ru-RU")}
                </TableCell>
                {canManage && (
                  <TableCell>
                    <button
                      onClick={() => handleRemove(assignee.user_id)}
                      disabled={removingId === assignee.user_id}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-error"
                      title="Убрать"
                    >
                      <Trash2 size={14} />
                    </button>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
