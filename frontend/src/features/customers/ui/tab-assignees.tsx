"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Users, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const [search, setSearch] = useState("");
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedName, setSelectedName] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const assignedUserIds = new Set(assignees.map((a) => a.user_id));
  const availableUsers = salesUsers.filter((u) => !assignedUserIds.has(u.id));
  const filteredUsers = availableUsers.filter((u) =>
    u.full_name.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(user: { id: string; full_name: string }) {
    setSelectedUserId(user.id);
    setSelectedName(user.full_name);
    setSearch(user.full_name);
    setDropdownOpen(false);
  }

  async function handleAdd() {
    if (!selectedUserId) return;
    setAdding(true);
    try {
      await addCustomerAssignee(customerId, selectedUserId);
      setSelectedUserId("");
      setSelectedName("");
      setSearch("");
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
        <div className="flex items-center gap-3">
          <div className="relative w-80" ref={wrapperRef}>
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle" />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setDropdownOpen(true);
                if (selectedName && e.target.value !== selectedName) {
                  setSelectedUserId("");
                  setSelectedName("");
                }
              }}
              onFocus={() => setDropdownOpen(true)}
              placeholder="Поиск менеджера..."
              className="h-9 text-sm pl-9"
            />
            {dropdownOpen && filteredUsers.length > 0 && (
              <div className="absolute z-50 top-full mt-1 w-full bg-white border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
                {filteredUsers.map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    onClick={() => handleSelect(user)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-sidebar transition-colors"
                  >
                    {user.full_name}
                  </button>
                ))}
              </div>
            )}
            {dropdownOpen && search && filteredUsers.length === 0 && (
              <div className="absolute z-50 top-full mt-1 w-full bg-white border border-border rounded-md shadow-lg px-3 py-2 text-sm text-text-muted">
                Не найдено
              </div>
            )}
          </div>
          <Button
            size="sm"
            disabled={!selectedUserId || adding}
            onClick={handleAdd}
            className="bg-accent text-white hover:bg-accent-hover shrink-0"
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
