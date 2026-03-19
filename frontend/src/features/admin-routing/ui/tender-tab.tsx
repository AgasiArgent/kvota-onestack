"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, ChevronUp, ChevronDown, Link2 } from "lucide-react";
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
  createTenderStep,
  deleteTenderStep,
  reorderTenderSteps,
} from "../api/routing-api";
import { TenderStepDialog } from "./tender-step-dialog";
import type { TenderChainStep } from "../model/types";

interface Props {
  steps: TenderChainStep[];
  orgId: string;
}

export function TenderTab({ steps, orgId }: Props) {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [reordering, setReordering] = useState(false);

  async function handleDialogSubmit(roleLabel: string, userId: string) {
    try {
      const nextOrder = steps.length > 0
        ? Math.max(...steps.map((s) => s.step_order)) + 1
        : 1;
      await createTenderStep(orgId, nextOrder, userId, roleLabel);
      toast.success("Шаг добавлен");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка добавления шага");
    }
  }

  async function handleDelete(stepId: string) {
    setDeletingId(stepId);
    try {
      await deleteTenderStep(stepId);
      toast.success("Шаг удалён");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка удаления");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleMoveUp(index: number) {
    if (index <= 0 || reordering) return;
    setReordering(true);
    try {
      await reorderTenderSteps(steps[index], steps[index - 1]);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка перемещения");
    } finally {
      setReordering(false);
    }
  }

  async function handleMoveDown(index: number) {
    if (index >= steps.length - 1 || reordering) return;
    setReordering(true);
    try {
      await reorderTenderSteps(steps[index], steps[index + 1]);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ошибка перемещения");
    } finally {
      setReordering(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text">Тендерная цепочка</h2>
          <p className="text-sm text-text-muted mt-1">
            Последовательность ответственных для тендерных сделок
          </p>
        </div>
        <Button
          size="sm"
          className="bg-accent text-white hover:bg-accent-hover"
          onClick={() => setDialogOpen(true)}
        >
          <Plus size={14} />
          Добавить шаг
        </Button>
      </div>

      {steps.length === 0 ? (
        <div className="py-12 text-center">
          <Link2 size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Цепочка не настроена</p>
          <p className="text-xs text-text-subtle">
            Добавьте шаги для определения маршрута тендерных заявок
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[60px]">#</TableHead>
              <TableHead>Роль</TableHead>
              <TableHead>Ответственный</TableHead>
              <TableHead className="w-[140px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {steps.map((step, index) => (
              <TableRow key={step.id}>
                <TableCell className="font-medium text-text-muted">{step.step_order}</TableCell>
                <TableCell className="font-medium">{step.role_label}</TableCell>
                <TableCell className="text-text-muted">{step.user_full_name ?? step.user_id}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleMoveUp(index)}
                      disabled={index === 0 || reordering}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-text-muted disabled:opacity-30"
                      title="Вверх"
                    >
                      <ChevronUp size={14} />
                    </button>
                    <button
                      onClick={() => handleMoveDown(index)}
                      disabled={index === steps.length - 1 || reordering}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-text-muted disabled:opacity-30"
                      title="Вниз"
                    >
                      <ChevronDown size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(step.id)}
                      disabled={deletingId === step.id}
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

      <TenderStepDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        orgId={orgId}
        onSubmit={handleDialogSubmit}
      />
    </div>
  );
}
