"use client";

import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { Pencil, Trash2, Plus, Search } from "lucide-react";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import type { BrandDiscount, BrandGroup } from "@/entities/settings";
import {
  updateBrandDiscount,
  deleteBrandDiscount,
  createBrandGroup,
  deleteBrandGroup,
} from "@/entities/settings";

interface BrandDiscountsTableProps {
  discounts: BrandDiscount[];
  brandGroups: BrandGroup[];
  orgId: string;
}

export function BrandDiscountsTable({
  discounts: initialDiscounts,
  brandGroups: initialGroups,
  orgId,
}: BrandDiscountsTableProps) {
  const [discounts, setDiscounts] = useState(initialDiscounts);
  const [groups, setGroups] = useState(initialGroups);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingRowId, setEditingRowId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string;
    type: "discount" | "group";
    name: string;
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [isCreatingGroup, setIsCreatingGroup] = useState(false);
  const [showGroupForm, setShowGroupForm] = useState(false);
  const editInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingRowId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingRowId]);

  const filteredDiscounts = discounts.filter((d) =>
    d.brand.toLowerCase().includes(searchQuery.toLowerCase())
  );

  function startEdit(discount: BrandDiscount) {
    setEditingRowId(discount.id);
    setEditValue(String(discount.discount_pct));
  }

  async function saveEdit() {
    const rowId = editingRowId;
    if (!rowId) return;
    const newPct = parseFloat(editValue);
    if (isNaN(newPct)) {
      setEditingRowId(null);
      return;
    }

    const prevDiscounts = [...discounts];
    setDiscounts((prev) =>
      prev.map((d) =>
        d.id === rowId ? { ...d, discount_pct: newPct } : d
      )
    );
    setEditingRowId(null);

    try {
      await updateBrandDiscount(rowId, newPct);
      toast.success("Скидка обновлена");
    } catch (err) {
      setDiscounts(prevDiscounts);
      const message =
        err instanceof Error ? err.message : "Ошибка обновления";
      toast.error(message);
    }
  }

  function cancelEdit() {
    setEditingRowId(null);
  }

  function handleEditKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      saveEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelEdit();
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);

    try {
      if (deleteTarget.type === "discount") {
        await deleteBrandDiscount(deleteTarget.id);
        setDiscounts((prev) => prev.filter((d) => d.id !== deleteTarget.id));
        toast.success("Скидка удалена");
      } else {
        await deleteBrandGroup(deleteTarget.id);
        setGroups((prev) => prev.filter((g) => g.id !== deleteTarget.id));
        toast.success("Группа удалена");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка удаления";
      toast.error(message);
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  }

  async function handleCreateGroup() {
    if (!newGroupName.trim()) return;
    setIsCreatingGroup(true);

    try {
      const group = await createBrandGroup(orgId, newGroupName.trim());
      setGroups((prev) => [...prev, group]);
      setNewGroupName("");
      setShowGroupForm(false);
      toast.success("Группа создана");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка создания";
      toast.error(message);
    } finally {
      setIsCreatingGroup(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Search */}
      <div className="relative">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle"
        />
        <Input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Поиск по бренду..."
          className="pl-9"
        />
      </div>

      {/* Discounts table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Бренд</TableHead>
            <TableHead>Классификация</TableHead>
            <TableHead className="w-[120px]">Скидка %</TableHead>
            <TableHead className="w-[80px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredDiscounts.length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} className="text-center text-text-muted py-8">
                {searchQuery
                  ? "Нет результатов поиска"
                  : "Нет записей о скидках"}
              </TableCell>
            </TableRow>
          ) : (
            filteredDiscounts.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="font-medium">{d.brand}</TableCell>
                <TableCell>{d.product_classification || "—"}</TableCell>
                <TableCell>
                  {editingRowId === d.id ? (
                    <Input
                      ref={editInputRef}
                      type="number"
                      step="0.01"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={saveEdit}
                      onKeyDown={handleEditKeyDown}
                      className="w-20 h-7"
                    />
                  ) : (
                    <span>{d.discount_pct}%</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => startEdit(d)}
                      className="p-1 rounded hover:bg-background text-text-subtle hover:text-text"
                      title="Редактировать"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() =>
                        setDeleteTarget({
                          id: d.id,
                          type: "discount",
                          name: d.brand,
                        })
                      }
                      className="p-1 rounded hover:bg-background text-text-subtle hover:text-destructive"
                      title="Удалить"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {/* Brand groups section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wide">
            Группы брендов
          </h3>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowGroupForm(true)}
          >
            <Plus size={14} className="mr-1" />
            Добавить группу
          </Button>
        </div>

        {showGroupForm && (
          <div className="flex items-center gap-2">
            <Input
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              placeholder="Название группы"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreateGroup();
                if (e.key === "Escape") {
                  setShowGroupForm(false);
                  setNewGroupName("");
                }
              }}
            />
            <Button
              onClick={handleCreateGroup}
              disabled={isCreatingGroup || !newGroupName.trim()}
              size="sm"
            >
              {isCreatingGroup ? "..." : "Создать"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowGroupForm(false);
                setNewGroupName("");
              }}
            >
              Отмена
            </Button>
          </div>
        )}

        {groups.length === 0 && !showGroupForm ? (
          <p className="text-sm text-text-muted">Нет групп брендов</p>
        ) : (
          <div className="space-y-1">
            {groups.map((g) => (
              <div
                key={g.id}
                className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-background"
              >
                <span className="text-sm font-medium">{g.name}</span>
                <button
                  onClick={() =>
                    setDeleteTarget({ id: g.id, type: "group", name: g.name })
                  }
                  className="p-1 rounded hover:bg-background text-text-subtle hover:text-destructive"
                  title="Удалить группу"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Подтвердите удаление</DialogTitle>
            <DialogDescription>
              {deleteTarget?.type === "discount"
                ? `Удалить скидку для бренда "${deleteTarget?.name}"?`
                : `Удалить группу "${deleteTarget?.name}"?`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              disabled={isDeleting}
            >
              Отмена
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Удаление..." : "Удалить"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
