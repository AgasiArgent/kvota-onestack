"use client";

/**
 * Dialog for creating a new ghost node (admin only).
 *
 * Reqs 7.1, 7.2, 7.3: admin CUD; `node_id = ghost:<slug>`; slug unique.
 * Slug is auto-derived from the title but the user may override (strict
 * kebab-case). DB-side UNIQUE collision (Postgres 23505) maps to a
 * toast via `classifyGhostWriteError`.
 */

import { useMemo, useState } from "react";
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
import type { GhostStatus } from "@/entities/journey";
import { createGhost, JOURNEY_QUERY_KEYS } from "@/entities/journey";
import {
  buildGhostPayload,
  classifyGhostWriteError,
} from "./_ghost-dialog-helpers";
import { deriveGhostSlug, validateGhostSlug } from "./_ghost-slug";

const GHOST_STATUSES: readonly { value: GhostStatus; label: string }[] = [
  { value: "proposed", label: "Предложен" },
  { value: "approved", label: "Утверждён" },
  { value: "in_progress", label: "В работе" },
  { value: "shipped", label: "Реализован" },
];

interface Props {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly userId: string;
}

export function GhostCreateDialog({ open, onOpenChange, userId }: Props) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [cluster, setCluster] = useState("");
  const [proposedRoute, setProposedRoute] = useState("");
  const [status, setStatus] = useState<GhostStatus>("proposed");
  const [plannedIn, setPlannedIn] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Reset on close happens via the caller unmounting this component (see
  // `ghost-list-manager.tsx`, which only renders the dialog while `open`);
  // no useEffect needed.

  const derivedSlug = useMemo(() => deriveGhostSlug(title), [title]);
  const effectiveSlug = slugTouched ? slug : derivedSlug;
  const slugValid = validateGhostSlug(effectiveSlug);
  const routeValid =
    proposedRoute.length === 0 || proposedRoute.startsWith("/");
  const canSubmit =
    title.trim().length > 0 && slugValid && routeValid && !submitting;

  const onSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    const payload = buildGhostPayload({
      title: title.trim(),
      slug: effectiveSlug,
      cluster: cluster.trim().length > 0 ? cluster.trim() : null,
      proposed_route:
        proposedRoute.trim().length > 0 ? proposedRoute.trim() : null,
      status,
      planned_in: plannedIn.trim().length > 0 ? plannedIn.trim() : null,
      created_by: userId,
    });

    const { error } = await createGhost(payload);
    setSubmitting(false);
    if (error) {
      const info = classifyGhostWriteError(error);
      toast.error(info.userMessage);
      return;
    }
    toast.success("Ghost-узел создан");
    qc.invalidateQueries({ queryKey: JOURNEY_QUERY_KEYS.nodes() });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onOpenChange(false)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Новый ghost-узел</DialogTitle>
          <DialogDescription>
            Планируемый экран, который ещё не реализован в коде.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-title">Заголовок *</Label>
            <Input
              id="ghost-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Например, «Редактор таможенных данных»"
              autoFocus
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-slug">Слаг *</Label>
            <Input
              id="ghost-slug"
              value={effectiveSlug}
              onChange={(e) => {
                setSlugTouched(true);
                setSlug(e.target.value);
              }}
              placeholder="my-feature-name"
              className={!slugValid ? "border-error" : undefined}
            />
            {!slugValid && (
              <p className="text-xs text-error">
                Слаг должен быть в формате kebab-case (a-z, 0-9, разделённые
                дефисами).
              </p>
            )}
            {slugValid && (
              <p className="text-xs text-text-subtle">
                node_id = <code>ghost:{effectiveSlug}</code>
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-cluster">Кластер</Label>
            <Input
              id="ghost-cluster"
              value={cluster}
              onChange={(e) => setCluster(e.target.value)}
              placeholder="Quotes / Procurement / …"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-route">Предлагаемый маршрут</Label>
            <Input
              id="ghost-route"
              value={proposedRoute}
              onChange={(e) => setProposedRoute(e.target.value)}
              placeholder="/customs/editor"
              className={!routeValid ? "border-error" : undefined}
            />
            {!routeValid && (
              <p className="text-xs text-error">
                Маршрут должен начинаться с &laquo;/&raquo;.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ghost-status">Статус</Label>
            <Select
              value={status}
              onValueChange={(v) => setStatus(v as GhostStatus)}
            >
              <SelectTrigger id="ghost-status">
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
            <Label htmlFor="ghost-planned-in">Запланирован в</Label>
            <Input
              id="ghost-planned-in"
              value={plannedIn}
              onChange={(e) => setPlannedIn(e.target.value)}
              placeholder="v1.1 / Q3 2026"
            />
          </div>
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
            {submitting ? "Создание…" : "Создать"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
