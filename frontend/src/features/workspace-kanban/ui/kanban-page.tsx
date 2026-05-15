"use client";

import dynamic from "next/dynamic";
import { AppToaster } from "@/shared/ui/app-toaster";
import type { UserAvatarChipUser } from "@/entities/user/ui/user-avatar-chip";
import type { WorkspaceKanbanBoard } from "../model/types";
import { KANBAN_COLUMNS } from "../model/types";

// The board is interactive only (dnd-kit). Rendering it on the server produces
// hydration mismatches (React error #418) because @dnd-kit/core injects
// attributes (aria-describedby, data-*) whose generated values differ between
// server and client. No SEO value in pre-rendering a drag-and-drop surface, so
// skip SSR — the enclosing page.tsx still fetches data on the server.
const KanbanBoard = dynamic(
  () => import("./kanban-board").then((m) => ({ default: m.KanbanBoard })),
  {
    ssr: false,
    loading: () => (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="min-h-[300px] rounded-lg border bg-muted/40 p-3"
          />
        ))}
      </div>
    ),
  },
);

export interface KanbanPageProps {
  domain: "logistics" | "customs";
  board: WorkspaceKanbanBoard;
  isHead: boolean;
  teamUsers: UserAvatarChipUser[];
}

/**
 * Client shell for the logistics / customs kanban board. The server component
 * (page.tsx) fetches the board once; subsequent mutations happen client-side
 * with optimistic updates inside `KanbanBoard`.
 */
export function KanbanPage({
  domain,
  board,
  isHead,
  teamUsers,
}: KanbanPageProps) {
  const totalActive =
    board.unassigned.length + board.in_progress.length;

  return (
    <>
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {totalActive === 0
            ? "Нет заявок в работе"
            : `${totalActive} ${pluralizeInvoices(totalActive)} в работе`}
        </p>
        <KanbanBoard
          domain={domain}
          initialBoard={normalizeBoard(board)}
          isHead={isHead}
          teamUsers={teamUsers}
        />
      </div>
      <AppToaster />
    </>
  );
}

/** Ensure every column key exists even if a fetcher omitted an empty one. */
function normalizeBoard(board: WorkspaceKanbanBoard): WorkspaceKanbanBoard {
  const out: WorkspaceKanbanBoard = {
    unassigned: [],
    in_progress: [],
    completed: [],
  };
  for (const col of KANBAN_COLUMNS) {
    out[col] = board[col] ?? [];
  }
  return out;
}

function pluralizeInvoices(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "заявка";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20))
    return "заявки";
  return "заявок";
}
