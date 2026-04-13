"use client";

import { Toaster } from "sonner";
import { KanbanBoard } from "./kanban-board";
import type { KanbanResponse } from "../model/types";

export interface KanbanPageProps {
  data: KanbanResponse;
}

/**
 * Top-level kanban screen. Server component fetches state once; subsequent
 * board mutations happen client-side with optimistic updates.
 */
export function KanbanPage({ data }: KanbanPageProps) {
  const totalCards = Object.values(data.columns).reduce(
    (sum, col) => sum + col.length,
    0
  );

  return (
    <>
      <div className="space-y-6">
        <header>
          <h1 className="text-xl font-semibold text-foreground">
            Канбан закупок
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {totalCards === 0
              ? "Нет заявок в работе"
              : `${totalCards} ${pluralizeQuotes(totalCards)} в работе`}
          </p>
        </header>

        <KanbanBoard initialColumns={data.columns} />
      </div>
      <Toaster position="top-right" richColors />
    </>
  );
}

function pluralizeQuotes(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "заявка";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20))
    return "заявки";
  return "заявок";
}
