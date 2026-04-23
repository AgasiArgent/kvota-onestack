"use client";

/**
 * Confirmation dialog for deleting a ghost node.
 *
 * Req 7.1 — admin only. Req 7.5 prefers "mark as shipped" over delete for
 * shipped ghosts (audit trail), but admins can still remove proposed /
 * abandoned ghosts permanently. `AlertDialog` primitive is not installed
 * in this workspace, so a standard `Dialog` with explicit confirm copy
 * fills the role.
 */

import { useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { JourneyGhostNode } from "@/entities/journey";
import { deleteGhost, JOURNEY_QUERY_KEYS } from "@/entities/journey";
import { classifyGhostWriteError } from "./_ghost-dialog-helpers";

interface Props {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly ghost: JourneyGhostNode;
}

export function GhostDeleteConfirm({ open, onOpenChange, ghost }: Props) {
  const qc = useQueryClient();
  const [submitting, setSubmitting] = useState(false);

  const onConfirm = async () => {
    setSubmitting(true);
    const { error } = await deleteGhost(ghost.id);
    setSubmitting(false);
    if (error) {
      const info = classifyGhostWriteError(error);
      toast.error(info.userMessage);
      return;
    }
    toast.success("Ghost-узел удалён");
    qc.invalidateQueries({ queryKey: JOURNEY_QUERY_KEYS.nodes() });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onOpenChange(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Удалить ghost-узел</DialogTitle>
          <DialogDescription>
            Удалить ghost-узел «{ghost.title}»? Это действие необратимо.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={submitting}
          >
            {submitting ? "Удаление…" : "Удалить"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
