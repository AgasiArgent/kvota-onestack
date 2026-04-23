"use client";

/**
 * Admin-only sidebar manager for ghost nodes — "+ Ghost" trigger plus an
 * expandable list of existing ghosts with per-row action menus.
 *
 * Rationale: the canvas ghost-node card (Task 16) stays visual-only; all
 * mutation affordances live here so the ghost-node component keeps a
 * single responsibility (rendering) and remains compatible with Task 16's
 * original contract. This also keeps the drawer (Task 19's domain)
 * untouched.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { listGhosts } from "@/entities/journey";
import type { JourneyGhostNode } from "@/entities/journey";
import { GhostCreateDialog } from "./ghost-create-dialog";
import { GhostActionMenu } from "./ghost-action-menu";

interface Props {
  readonly userId: string;
}

export function GhostListManager({ userId }: Props) {
  const [createOpen, setCreateOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const { data: ghostsRes } = useQuery({
    queryKey: ["journey", "ghosts"],
    queryFn: async () => {
      const res = await listGhosts();
      return res.data as JourneyGhostNode[] | null;
    },
  });

  const ghosts = ghostsRes ?? [];

  return (
    <div className="flex flex-col gap-2">
      <Button
        size="sm"
        variant="outline"
        className="w-full justify-start"
        onClick={() => setCreateOpen(true)}
        data-testid="journey-add-ghost"
      >
        <Plus className="mr-1.5 h-3.5 w-3.5" />
        Добавить ghost
      </Button>

      {ghosts.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 text-xs text-text-subtle hover:text-text"
          >
            <ChevronRight
              className={`h-3.5 w-3.5 transition-transform ${
                expanded ? "rotate-90" : ""
              }`}
            />
            Ghost-узлы ({ghosts.length})
          </button>
          {expanded && (
            <ul
              data-testid="journey-ghost-list"
              className="flex flex-col gap-1 rounded-md border border-border-light bg-surface p-1"
            >
              {ghosts.map((g) => (
                <li
                  key={g.id}
                  className="flex items-center justify-between gap-2 rounded px-2 py-1 text-xs"
                >
                  <span className="truncate" title={g.title}>
                    {g.title}
                  </span>
                  <GhostActionMenu ghost={g} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {createOpen && (
        <GhostCreateDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          userId={userId}
        />
      )}
    </div>
  );
}
