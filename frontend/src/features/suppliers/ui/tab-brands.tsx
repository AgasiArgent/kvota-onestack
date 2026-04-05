"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Star, StarOff, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { BrandAssignment } from "@/entities/supplier/types";
import {
  addBrandAssignment,
  deleteBrandAssignment,
  toggleBrandPrimary,
} from "@/entities/supplier/mutations";

interface Props {
  supplierId: string;
  brands: BrandAssignment[];
}

export function TabBrands({ supplierId, brands }: Props) {
  const router = useRouter();
  const [newBrand, setNewBrand] = useState("");
  const [isPrimary, setIsPrimary] = useState(false);
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  async function handleAdd(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = newBrand.trim();
    if (!trimmed) return;

    setAdding(true);
    try {
      await addBrandAssignment(supplierId, { brand: trimmed, is_primary: isPrimary });
      setNewBrand("");
      setIsPrimary(false);
      router.refresh();
    } catch (err) {
      console.error("Failed to add brand:", err);
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(assignmentId: string) {
    setDeletingId(assignmentId);
    try {
      await deleteBrandAssignment(assignmentId);
      router.refresh();
    } catch (err) {
      console.error("Failed to delete brand:", err);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleTogglePrimary(assignmentId: string, current: boolean) {
    setTogglingId(assignmentId);
    try {
      await toggleBrandPrimary(assignmentId, !current);
      router.refresh();
    } catch (err) {
      console.error("Failed to toggle primary:", err);
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <div className="space-y-6">
      {/* Add brand form */}
      <form onSubmit={handleAdd} className="flex items-end gap-3">
        <div className="flex-1 max-w-sm">
          <Input
            value={newBrand}
            onChange={(e) => setNewBrand(e.target.value)}
            placeholder="Название бренда"
          />
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={isPrimary}
            onChange={(e) => setIsPrimary(e.target.checked)}
            className="size-4 rounded accent-accent"
          />
          <span className="text-text">Основной</span>
        </label>
        <Button
          type="submit"
          size="sm"
          disabled={!newBrand.trim() || adding}
          className="bg-accent text-white hover:bg-accent-hover"
        >
          <Plus size={14} />
          Добавить
        </Button>
      </form>

      {/* Brands table */}
      {brands.length === 0 ? (
        <div className="py-12 text-center">
          <Package size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет привязанных брендов</p>
          <p className="text-xs text-text-subtle">Добавьте бренды, которые поставляет этот поставщик</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40%]">Бренд</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Заметки</TableHead>
              <TableHead className="w-[100px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {brands.map((brand) => (
              <TableRow key={brand.id}>
                <TableCell className="font-medium">{brand.brand}</TableCell>
                <TableCell>
                  {brand.is_primary && (
                    <Badge variant="default">Основной</Badge>
                  )}
                </TableCell>
                <TableCell className="text-text-muted max-w-[200px] truncate">
                  {brand.notes ?? "—"}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleTogglePrimary(brand.id, brand.is_primary)}
                      disabled={togglingId === brand.id}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-text-muted"
                      title={brand.is_primary ? "Убрать основной" : "Сделать основным"}
                    >
                      {brand.is_primary ? <StarOff size={14} /> : <Star size={14} />}
                    </button>
                    <button
                      onClick={() => handleDelete(brand.id)}
                      disabled={deletingId === brand.id}
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
    </div>
  );
}
