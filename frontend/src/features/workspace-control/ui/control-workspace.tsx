"use client";

import { useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  ControlBoardDomain,
  ControlKanbanCard,
} from "@/entities/workspace-control";
import { ControlBoard } from "./control-board";
import { columnsForDomain } from "../model/columns";

export interface ControlWorkspaceProps {
  /** calc-board cards, or null when the user can't see the calc board. */
  calcCards: ControlKanbanCard[] | null;
  /** spec-board cards, or null when the user can't see the spec board. */
  specCards: ControlKanbanCard[] | null;
}

const DOMAIN_LABELS: Record<ControlBoardDomain, string> = {
  calc: "Контроль расчёта",
  spec: "Контроль спецификации",
};

/**
 * Two-board control workspace with a switcher (control-spec-workspace Req 9.1).
 *
 * One route, two kanbans. A user who can see both boards gets a switcher to
 * toggle between «Контроль расчёта» (calc) and «Контроль спецификации» (spec);
 * a user who can see only one board sees that board with no switcher. The page
 * guard guarantees at least one board is non-null (fail-closed, Req 11.5).
 */
export function ControlWorkspace({
  calcCards,
  specCards,
}: ControlWorkspaceProps) {
  const available: ControlBoardDomain[] = [
    ...(calcCards !== null ? (["calc"] as const) : []),
    ...(specCards !== null ? (["spec"] as const) : []),
  ];
  const [active, setActive] = useState<ControlBoardDomain>(available[0]);

  const cardsFor = (domain: ControlBoardDomain): ControlKanbanCard[] =>
    (domain === "calc" ? calcCards : specCards) ?? [];

  // Single-board view — no switcher needed.
  if (available.length === 1) {
    const domain = available[0];
    return (
      <ControlBoard
        domain={domain}
        columns={columnsForDomain(domain)}
        cards={cardsFor(domain)}
      />
    );
  }

  return (
    <div className="space-y-4">
      <Tabs
        value={active}
        onValueChange={(value) => setActive(value as ControlBoardDomain)}
      >
        <TabsList>
          {available.map((domain) => (
            <TabsTrigger key={domain} value={domain}>
              {DOMAIN_LABELS[domain]}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <ControlBoard
        domain={active}
        columns={columnsForDomain(active)}
        cards={cardsFor(active)}
      />
    </div>
  );
}
