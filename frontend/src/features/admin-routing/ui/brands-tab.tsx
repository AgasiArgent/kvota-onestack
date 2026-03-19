"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Pencil, Package, Tag } from "lucide-react";
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
  createBrandAssignment,
  updateBrandAssignment,
  deleteBrandAssignment,
} from "../api/routing-api";
import { UserSelect } from "./user-select";
import { BrandAssignmentDialog } from "./brand-assignment-dialog";
import type { BrandAssignment } from "../model/types";

interface Props {
  assignments: BrandAssignment[];
  unassignedBrands: string[];
  orgId: string;
}

export function BrandsTab({ assignments, unassignedBrands, orgId }: Props) {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogInitialBrand, setDialogInitialBrand] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUserId, setEditUserId] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  function openCreateDialog(brand?: string) {
    setDialogInitialBrand(brand ?? "");
    setDialogOpen(true);
  }

  async function handleDialogSubmit(brand: string, userId: string) {
    try {
      await createBrandAssignment(orgId, brand, userId);
      toast.success(`Бренд "${brand}" назначен`);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка назначения бренда");
    }
  }

  async function saveEdit(assignmentId: string) {
    if (!editUserId) return;
    try {
      await updateBrandAssignment(assignmentId, editUserId, orgId);
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
      await deleteBrandAssignment(assignmentId, orgId);
      toast.success("Назначение удалено");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка удаления");
    } finally {
      setDeletingId(null);
    }
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "\u2014";
    return new Date(dateStr).toLocaleDateString("ru-RU");
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text">Назначения по брендам</h2>
          <p className="text-sm text-text-muted mt-1">
            Каждый бренд закреплён за одним менеджером закупок
          </p>
        </div>
        <Button
          size="sm"
          className="bg-accent text-white hover:bg-accent-hover"
          onClick={() => openCreateDialog()}
        >
          <Plus size={14} />
          Назначить бренд
        </Button>
      </div>

      {assignments.length === 0 ? (
        <div className="py-12 text-center">
          <Package size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет назначений</p>
          <p className="text-xs text-text-subtle">
            Назначьте бренды менеджерам закупок для автоматической маршрутизации
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Бренд</TableHead>
              <TableHead>Менеджер закупок</TableHead>
              <TableHead>Дата назначения</TableHead>
              <TableHead className="w-[100px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {assignments.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-medium">{a.brand}</TableCell>
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

      {unassignedBrands.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wide mb-3">
            Неназначенные бренды
          </h3>
          <div className="flex flex-wrap gap-2">
            {unassignedBrands.map((brand) => (
              <button
                key={brand}
                onClick={() => openCreateDialog(brand)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border-light rounded-md hover:border-accent hover:text-accent transition-colors"
              >
                <Tag size={12} />
                {brand}
              </button>
            ))}
          </div>
        </div>
      )}

      <BrandAssignmentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        orgId={orgId}
        initialBrand={dialogInitialBrand}
        onSubmit={handleDialogSubmit}
      />
    </div>
  );
}
