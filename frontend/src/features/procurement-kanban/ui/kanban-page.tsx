"use client";

import dynamic from "next/dynamic";
import { Toaster } from "sonner";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";
import type { KanbanResponse } from "../model/types";

// Board is interactive only (dnd-kit). Rendering it on the server produces
// hydration mismatches (React error #418) because @dnd-kit/core injects
// attributes (aria-describedby, data-*) whose generated values differ between
// server and client. There's no SEO value in pre-rendering a drag-and-drop
// surface, so skip SSR entirely — the enclosing page.tsx still fetches data
// on the server and passes it down as a prop.
const KanbanBoard = dynamic(
  () => import("./kanban-board").then((m) => ({ default: m.KanbanBoard })),
  {
    ssr: false,
    loading: () => (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="min-h-[300px] rounded-lg border bg-muted/40 p-3"
          />
        ))}
      </div>
    ),
  }
);

export interface KanbanPageProps {
  data: KanbanResponse;
  workload: ProcurementUserWorkload[];
  orgId: string;
}

/**
 * Top-level kanban screen. Server component fetches state once; subsequent
 * board mutations happen client-side with optimistic updates.
 */
export function KanbanPage({ data, workload, orgId }: KanbanPageProps) {
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
              ? "Нет карточек в работе"
              : `${totalCards} ${pluralizeCards(totalCards)} в работе`}
          </p>
        </header>

        <KanbanBoard
          initialColumns={data.columns}
          workload={workload}
          orgId={orgId}
        />
      </div>
      <Toaster position="top-right" richColors />
    </>
  );
}

function pluralizeCards(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "карточка";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20))
    return "карточки";
  return "карточек";
}
