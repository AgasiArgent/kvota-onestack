"use client";

/**
 * Dialog for editing a ghost node (admin only).
 *
 * Req 7.5 — "mark as shipped" sets `status='shipped'` without deleting
 * the row (audit trail). `node_id` and `slug` are immutable once created.
 */

import { useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  GhostStatus,
  JourneyGhostNode,
} from "@/entities/journey";
import { updateGhost, JOURNEY_QUERY_KEYS } from "@/entities/journey";
import { classifyGhostWriteError } from "./_ghost-dialog-helpers";

const GHOST_STATUSES: readonly { value: GhostStatus; label: string }[] = [
  { value: "proposed", label: "Предложен" },
  { value: "approved", label: "Утверждён" },
  { value: "in_progress", label: "В работе" },
  { value: "shipped", label: "Реализован" },
];

interface Props {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly ghost: JourneyGhostNode;
}

export function GhostEditDialog({ open, onOpenChange, ghost }: Props) {
  const qc = useQueryClient();
  const [title, setTitle] = useState(ghost.title);
  const [cluster, setCluster] = useState(ghost.cluster ?? "");
  const [proposedRoute, setProposedRoute] = useState(
    ghost.proposed_route ?? "",
  );
  const [status, setStatus] = useState<GhostStatus>(ghost.status);
  const [plannedIn, setPlannedIn] = useState(ghost.planned_in ?? "");
  const [submitting, setSubmitting] = useState(false);
  // Re-seed happens via remount: `ghost-action-menu.tsx` renders this
  // dialog only while `editOpen` is true, so a new `ghost` prop always
  // produces a fresh mount with the correct initial useState values.

  const routeValid =
    proposedRoute.length === 0 || proposedRoute.startsWith("/");
  const canSubmit = title.trim().length > 0 && routeValid && !submitting;

  const persist = async (patch: Partial<JourneyGhostNode>) => {
    setSubmitting(true);
    const { error } = await updateGhost(ghost.id, patch);
    setSubmitting(false);
    if (error) {
      const info = classifyGhostWriteError(error);
      toast.error(info.userMessage);
      return false;
    }
    qc.invalidateQueries({ queryKey: JOURNEY_QUERY_KEYS.nodes() });
    return true;
  };

  const onSubmit = async () => {
    if (!canSubmit) return;
    const ok = await persist({
      title: title.trim(),
      cluster: cluster.trim().length > 0 ? cluster.trim() : null,
      proposed_route:
        proposedRoute.trim().length > 0 ? proposedRoute.trim() : null,
      status,
      planned_in: plannedIn.trim().length > 0 ? plannedIn.trim() : null,
    });
    if (ok) {
      toast.success("Ghost-узел обновлён");
      onOpenChange(false);
    }
  };

  const onMarkShipped = async () => {
    const ok = await persist({ status: "shipped" });
    if (ok) {
      setStatus("shipped");
      toast.success("Узел отмечен как реализованный");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onOpenChange(false)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Редактировать ghost-узел</DialogTitle>
          <DialogDescription>
            <code>{ghost.node_id}</code> — идентификатор не меняется.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-edit-title">Заголовок *</Label>
            <Input
              id="ghost-edit-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-edit-cluster">Кластер</Label>
            <Input
              id="ghost-edit-cluster"
              value={cluster}
              onChange={(e) => setCluster(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-edit-route">Предлагаемый маршрут</Label>
            <Input
              id="ghost-edit-route"
              value={proposedRoute}
              onChange={(e) => setProposedRoute(e.target.value)}
              className={!routeValid ? "border-error" : undefined}
            />
            {!routeValid && (
              <p className="text-xs text-error">
                Маршрут должен начинаться с &laquo;/&raquo;.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-edit-status">Статус</Label>
            <Select
              value={status}
              onValueChange={(v) => setStatus(v as GhostStatus)}
            >
              <SelectTrigger id="ghost-edit-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GHOST_STATUSES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-edit-planned-in">Запланирован в</Label>
            <Input
              id="ghost-edit-planned-in"
              value={plannedIn}
              onChange={(e) => setPlannedIn(e.target.value)}
            />
          </div>

          {status !== "shipped" && (
            <div className="flex items-center justify-between rounded-md border border-border-light bg-surface px-3 py-2">
              <div className="text-xs text-text-subtle">
                Когда экран реализован — отметьте узел, он останется на канве
                с серым статусом.
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={onMarkShipped}
                disabled={submitting}
              >
                Отметить как shipped
              </Button>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button onClick={onSubmit} disabled={!canSubmit}>
            {submitting ? "Сохранение…" : "Сохранить"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
