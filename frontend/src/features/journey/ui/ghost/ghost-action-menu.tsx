"use client";

/**
 * Action menu for admins to manage a single ghost node.
 *
 * Triggered from a small icon button on the ghost-node card (canvas) or
 * from any other admin-only surface. Hosts the edit / delete dialogs;
 * "mark as shipped" is implemented inside the edit dialog so it shares
 * the same optimistic flow.
 */

import { useState } from "react";
import { MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { JourneyGhostNode } from "@/entities/journey";
import { GhostEditDialog } from "./ghost-edit-dialog";
import { GhostDeleteConfirm } from "./ghost-delete-confirm";

interface Props {
  readonly ghost: JourneyGhostNode;
}

export function GhostActionMenu({ ghost }: Props) {
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label="Действия ghost-узла"
          className="flex h-6 w-6 items-center justify-center rounded border border-border-light bg-background text-text-subtle hover:text-text"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setEditOpen(true)}>
            Редактировать
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => setDeleteOpen(true)}
            className="text-error focus:text-error"
          >
            Удалить
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {editOpen && (
        <GhostEditDialog
          open={editOpen}
          onOpenChange={setEditOpen}
          ghost={ghost}
        />
      )}
      {deleteOpen && (
        <GhostDeleteConfirm
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          ghost={ghost}
        />
      )}
    </>
  );
}
